"""Hand Washing Skill Assessment System — Entry Point.

Real-time FSM-based assessment using VLM + YAMNet sensing with split-screen GUI.

macOS constraint: cv2.imshow MUST run in the main thread.
Async VLM/audio sensing runs in a background thread.

Usage:
    python main.py --mode live
    python main.py --mode video --input demo.mp4
"""

import argparse
import asyncio
import logging
import queue
import threading
import time

import cv2
import numpy as np

from config import (
    VLM_DISPATCH_INTERVAL,
    AUDIO_SAMPLE_INTERVAL,
    POOL_MODE,
    VLM_PROVIDERS,
    TTS_COOLDOWN,
)
from sensing.vlm_provider import VLMProvider, _zero_cues
from sensing.vlm_pool import VLMPool
from sensing.audio_provider import AudioProvider, AUDIO_CUE_KEYS
from sensing.ensemble import EnsembleMerger
from fsm.engine import FSMEngine
from feedback.tts import TTSFeedback
from feedback.messages import TRANSITION_MESSAGES, STATE_WARNINGS
from gui.app import GUIApp
from output.logger import StateLogger
from output.timeline import generate_timeline
from output.report import generate_report
from utils.frame_utils import preprocess_frame
from utils.audio_utils import AudioCapture

log = logging.getLogger(__name__)

# Thread-safe queues for communication
cue_queue: queue.Queue = queue.Queue()
frame_queue: queue.Queue = queue.Queue(maxsize=1)

# Global flag to stop the sensing loop
running = True


async def sensing_loop(
    vlm_pool: VLMPool,
    audio_provider: AudioProvider,
    audio_capture: AudioCapture | None,
    cue_q: queue.Queue,
    frame_q: queue.Queue,
) -> None:
    """Background async loop: dispatch VLM requests + run YAMNet, push cues to queue."""
    last_vlm_dispatch = 0.0
    last_audio_time = 0.0

    while running:
        now = time.time()

        # Dispatch frame to VLM pool at the configured interval
        if now - last_vlm_dispatch >= VLM_DISPATCH_INTERVAL:
            try:
                frame_b64 = frame_q.get_nowait()
                await vlm_pool.submit_frame(frame_b64)
                last_vlm_dispatch = now
            except queue.Empty:
                pass

        # Collect completed VLM results
        results = await vlm_pool.collect_results()
        for cues in results:
            cue_q.put(("visual", cues))

        # Run YAMNet at the configured interval
        if audio_capture is not None and now - last_audio_time >= AUDIO_SAMPLE_INTERVAL:
            try:
                chunk = audio_capture.get_chunk()
                audio_cues = audio_provider.classify_waveform(chunk)
                cue_q.put(("audio", audio_cues))
            except Exception as e:
                log.warning(f"Audio classification error: {e}")
            last_audio_time = now

        await asyncio.sleep(0.05)


def run_sensing_thread(
    vlm_pool: VLMPool,
    audio_provider: AudioProvider,
    audio_capture: AudioCapture | None,
) -> threading.Thread:
    """Start the sensing loop in a background daemon thread."""
    loop = asyncio.new_event_loop()

    def target():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            sensing_loop(vlm_pool, audio_provider, audio_capture, cue_queue, frame_queue)
        )

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return thread


async def _startup_health_check(vlm_pool: VLMPool) -> None:
    """Run VLM health checks and report status."""
    print("Checking VLM endpoints...")
    results = await vlm_pool.health_check()
    all_ok = True
    for name, ok in results.items():
        status = "OK" if ok else "UNREACHABLE"
        print(f"  {name}: {status}")
        if not ok:
            all_ok = False
    if not all_ok:
        print("  WARNING: Some VLM endpoints are unreachable.")
        print("  Make sure SSH tunnel is open and vLLM servers are running.")
        print("  System will continue but visual cues may be unavailable.\n")
    else:
        print("  All VLM endpoints healthy.\n")


def main() -> None:
    global running

    parser = argparse.ArgumentParser(description="Hand Washing Skill Assessment")
    parser.add_argument(
        "--mode", choices=["live", "video"], default="live",
        help="Input mode: 'live' for webcam, 'video' for file",
    )
    parser.add_argument("--input", type=str, default=None, help="Video file path (for --mode video)")
    parser.add_argument("--no-audio", action="store_true", help="Disable audio capture")
    parser.add_argument("--no-tts", action="store_true", help="Disable TTS voice feedback")
    parser.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING"], default="INFO",
        help="Logging level",
    )
    args = parser.parse_args()

    # --- Setup logging ---
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # --- Initialize components ---
    print("Initializing Hand Washing Assessment System...")

    # VLM providers (remote via SSH tunnel)
    providers = [
        VLMProvider(name=p["name"], base_url=p["url"]) for p in VLM_PROVIDERS
    ]
    vlm_pool = VLMPool(providers, mode=POOL_MODE)

    # Startup health check for VLM endpoints
    asyncio.run(_startup_health_check(vlm_pool))

    # asyncio.run() closed its event loop, so the httpx connections inside
    # the AsyncOpenAI clients are now stale.  Drop them so the sensing
    # thread's event loop creates fresh ones.
    for p in providers:
        p.reset_client()

    # Audio
    audio_provider = AudioProvider()
    audio_capture = None
    if not args.no_audio:
        try:
            audio_capture = AudioCapture()
            audio_capture.start()
            print("Audio capture started.")
        except Exception as e:
            print(f"Warning: Could not start audio capture: {e}")
            audio_capture = None

    # FSM, merger, TTS, GUI, logger
    fsm = FSMEngine()
    merger = EnsembleMerger()
    tts = TTSFeedback(cooldown=TTS_COOLDOWN) if not args.no_tts else None
    gui = GUIApp()
    logger = StateLogger()

    # --- Start background sensing thread ---
    sensing_thread = run_sensing_thread(vlm_pool, audio_provider, audio_capture)
    print("Sensing thread started.")

    # --- Open video source ---
    if args.mode == "video" and args.input:
        cap = cv2.VideoCapture(args.input)
        print(f"Playing video: {args.input}")
    else:
        cap = cv2.VideoCapture(0)
        print("Webcam opened. Press 'q' to quit, 'r' to reset.")

    if not cap.isOpened():
        print("Error: Could not open video source.")
        return

    # Initialize cues with zeros — not empty dicts, not 0.5 fallbacks.
    # This way the GUI renders all bars at 0 until real data arrives,
    # and the FSM won't trigger any transitions from zero cues.
    visual_cues: dict = _zero_cues()
    audio_cues: dict = {key: 0.0 for key in AUDIO_CUE_KEYS}
    has_new_cues = False  # Only update FSM when fresh cues arrive
    last_warning_time: float = 0
    spoken_warnings: set = set()   # Track (state, delay) warnings already spoken
    done_announced: bool = False   # Whether DONE congratulations TTS has played
    session_done_time: float = 0.0 # Frozen total session time once DONE

    print("System ready. Starting assessment...\n")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                if args.mode == "video":
                    print("\nVideo ended.")
                    break
                continue

            # Send latest frame to sensing thread (drop old frames)
            frame_b64 = preprocess_frame(frame)
            try:
                frame_queue.get_nowait()  # discard stale frame
            except queue.Empty:
                pass
            frame_queue.put(frame_b64)

            # Collect cues from sensing thread (non-blocking drain)
            has_new_cues = False
            while not cue_queue.empty():
                try:
                    cue_type, cues = cue_queue.get_nowait()
                    if cue_type == "visual":
                        visual_cues = cues
                        has_new_cues = True
                    elif cue_type == "audio":
                        audio_cues = cues
                        has_new_cues = True
                except queue.Empty:
                    break

            # Merge cues
            merged = merger.merge(visual_cues, audio_cues)

            # Only update FSM when new sensing data arrives,
            # not on every GUI frame (avoids flooding the cue buffer
            # with identical stale values).
            transition = None
            if has_new_cues:
                transition = fsm.update(merged)

            # Handle state transitions
            if transition:
                from_state, to_state = transition
                print(f"  Transition: {from_state} -> {to_state}")
                logger.log_transition(from_state, to_state, merged)
                spoken_warnings.clear()  # Reset warnings for new state

                if tts:
                    msg = TRANSITION_MESSAGES.get((from_state, to_state))
                    if msg:
                        tts.speak_now(msg)  # Always play transition messages

                # Record frozen session time when DONE is reached
                if to_state == "DONE":
                    session_done_time = (
                        fsm.state_history[-1]["enter_time"]
                        - fsm.state_history[0]["enter_time"]
                    )

            # Congratulations TTS when first entering DONE
            if fsm.current_state == "DONE" and not done_announced:
                done_announced = True
                if tts:
                    score = fsm.get_score()
                    pts = score["total"] if score else 0
                    tts.speak_now(
                        f"Congratulations! You finished washing your hands. "
                        f"Your score is {pts} out of 100."
                    )

            # State warnings (periodic encouragement)
            if tts and fsm.current_state in STATE_WARNINGS:
                warnings_cfg = STATE_WARNINGS[fsm.current_state]
                # Normalize: single dict or list of dicts
                if isinstance(warnings_cfg, dict):
                    warnings_cfg = [warnings_cfg]
                for warning in warnings_cfg:
                    key = (fsm.current_state, warning["delay"])
                    if key in spoken_warnings:
                        continue  # Already spoken this warning in this state visit
                    if fsm.time_in_state > warning["delay"]:
                        now = time.time()
                        if now - last_warning_time > TTS_COOLDOWN:
                            tts.speak_warning(warning["message"])
                            spoken_warnings.add(key)
                            last_warning_time = now
                            break  # One warning per frame to avoid queueing multiple

            # Compute display time: frozen total session time in DONE, else time_in_state
            if fsm.current_state == "DONE" and session_done_time > 0:
                display_time = session_done_time
            else:
                display_time = fsm.time_in_state

            # Render split-screen GUI
            score = fsm.get_score()
            last_tts_msg = tts.last_message if tts else ""
            gui.render(
                frame, fsm.current_state, display_time,
                merged, fsm.state_history, last_tts_msg, score,
            )

            # Handle key presses
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("r"):
                fsm.reset()
                visual_cues = _zero_cues()
                audio_cues = {k: 0.0 for k in AUDIO_CUE_KEYS}
                print("FSM reset.")

    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        running = False

        # Post-session output
        print("\nGenerating session outputs...")
        score = fsm.get_score()
        log_path = logger.save(fsm.state_history)
        print(f"  Session log: {log_path}")

        timeline_path = generate_timeline(fsm.state_history)
        if timeline_path:
            print(f"  Timeline: {timeline_path}")

        report_path = generate_report(fsm.state_history, score)
        print(f"  Report: {report_path}")

        # Cleanup
        cap.release()
        cv2.destroyAllWindows()
        if audio_capture:
            audio_capture.stop()
        if tts:
            tts.shutdown()

        print("Done.")


if __name__ == "__main__":
    main()
