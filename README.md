# Hand Washing Skill Assessment System

A real-time, AI-powered system that observes and assesses hand washing technique using a **Finite State Machine (FSM)**, **Vision Language Models (VLMs)**, **audio classification (YAMNet)**, and **text-to-speech feedback**. Built for the University of Michigan SURE program (Project #9: Seeing Skill with States).

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [FSM Design](#fsm-design)
4. [Sensing Pipeline](#sensing-pipeline)
5. [Feedback System](#feedback-system)
6. [GUI Layout](#gui-layout)
7. [Scoring](#scoring)
8. [Project Structure](#project-structure)
9. [Prerequisites](#prerequisites)
10. [Environment Setup](#environment-setup)
11. [Running the System](#running-the-system)
12. [Configuration Reference](#configuration-reference)
13. [Testing](#testing)
14. [Session Outputs](#session-outputs)
15. [Troubleshooting](#troubleshooting)

---

## Overview

The system watches a user washing their hands via webcam and microphone, classifies visual and audio cues in real time, drives a 10-state FSM to track progress through the hand washing procedure, and provides voice guidance and a live split-screen GUI.

**Key capabilities:**

- Real-time multi-modal sensing (vision + audio)
- 10-state FSM with sustained-condition transitions and idle timeout
- Round-robin VLM inference across multiple GPUs for low-latency visual classification
- YAMNet-based audio classification for water and blower sounds
- Non-blocking text-to-speech guidance with transition and periodic warning messages
- Split-screen GUI: live camera feed with cue overlay (left) + FSM flowchart (right)
- Post-session reports: JSON log, timeline visualization, text score report
- 100-point scoring system based on states visited

---

## System Architecture

```
 macOS (local machine)                     Remote HPC (UMich Lighthouse)
+-------------------------------+         +-------------------------------+
|  Webcam  -->  Frame Queue  ---|--SSH--->|  vLLM: Qwen3-VL-8B (GPU 0)  |
|  Mic     -->  AudioCapture    |  tunnel |  vLLM: Qwen3-VL-8B (GPU 1)  |
|                               |         |  vLLM: Qwen3-VL-8B (GPU 2)  |
|  Main Thread:                 |         +-------------------------------+
|    cv2.imshow (GUI)           |
|    FSM engine                 |
|    TTS feedback               |
|                               |
|  Background Thread:           |
|    async VLM dispatch (0.37s) |
|    YAMNet audio classify (1s) |
+-------------------------------+
```

**Threading model:**

- **Main thread** — captures webcam frames, collects cues from queue, updates FSM, renders GUI via `cv2.imshow` (macOS requires imshow on the main thread), handles keyboard input.
- **Background daemon thread** — runs an asyncio event loop that dispatches frames to the VLM pool in round-robin and runs YAMNet audio classification. Results are pushed to a thread-safe `cue_queue`.

**Communication:**

| Queue | Direction | Purpose |
|-------|-----------|---------|
| `frame_queue` (maxsize=1) | main -> sensing | Latest camera frame (base64 JPEG). Old frames are dropped. |
| `cue_queue` (unbounded) | sensing -> main | `("visual", {...})` or `("audio", {...})` cue dicts. Drained each GUI frame. |

---

## FSM Design

### States (10)

| # | State | Description | Activity Cues |
|---|-------|-------------|---------------|
| 0 | **IDLE** | Waiting for hand washing to begin | (none — uses own timeout) |
| 1 | **WATER_NO_HANDS** | Water running, no hands detected | `water_sound` |
| 2 | **HANDS_NO_WATER** | Hands visible, no water | `hands_visible` |
| 3 | **WASHING** | Hands under running water | `hands_visible`, `water_sound`, `hands_under_water` |
| 4 | **SOAPING** | Applying hand soap / lathering | `hands_visible`, `hands_on_soap`, `foam_visible` |
| 5 | **RINSING** | Rinsing soap off under water | `hands_under_water`, `water_sound`, `hands_visible` |
| 6 | **TOWEL_DRYING** | Drying hands with a towel | `towel_drying`, `hands_visible` |
| 7 | **CLOTHES_DRYING** | Drying hands on clothes | `hands_touch_clothes`, `hands_visible` |
| 8 | **BLOWER_DRYING** | Drying hands with a blower/dryer | `blower_visible`, `blower_sound` |
| 9 | **DONE** | Hand washing complete | (none — terminal state) |

### Transition Flowchart

```
                    IDLE
                  /  |  \
                 v   v   v
     WATER_NO_HANDS  |  HANDS_NO_WATER
              \      |      /
               v     v     v
                  WASHING
                     |
                     v
                  SOAPING
                     |
                     v
                  RINSING
                /    |    \
               v     v     v
     TOWEL_DRYING  CLOTHES_DRYING  BLOWER_DRYING
               \     |     /
                v    v    v
                   DONE
```

### Transition Conditions

All sustained-condition transitions require the condition to be continuously true for **1.3 seconds** before firing. This prevents false triggers from momentary cue spikes.

| From | To | Condition |
|------|----|-----------|
| IDLE | WATER_NO_HANDS | `water_sound > 0.5` AND `hands_visible < 0.4` sustained 1.3s |
| IDLE | HANDS_NO_WATER | `hands_visible > 0.5` AND `water_sound < 0.4` sustained 1.3s |
| IDLE / WATER_NO_HANDS / HANDS_NO_WATER | WASHING | `hands_under_water > 0.5` AND `water_sound > 0.5` sustained 1.3s |
| WASHING | SOAPING | `hands_on_soap > 0.5` (immediate) |
| SOAPING | RINSING | `hands_under_water > 0.5` AND `water_sound > 0.5` sustained 1.3s |
| RINSING | TOWEL_DRYING | `towel_drying > 0.5` sustained 1.3s |
| RINSING | CLOTHES_DRYING | `hands_touch_clothes > 0.5` sustained 1.3s |
| RINSING | BLOWER_DRYING | `blower_sound > 0.3` OR `blower_visible > 0.3` (immediate) |
| TOWEL_DRYING | DONE | In state >= 1.3s AND `towel_drying < 0.3` |
| CLOTHES_DRYING | DONE | In state >= 1.3s AND `hands_touch_clothes < 0.3` |
| BLOWER_DRYING | DONE | In state >= 1.3s AND `blower_sound < 0.2` AND `blower_visible < 0.2` |

### Idle Timeout

If all activity cues for the current state drop below 0.3 for **5 seconds**, the FSM transitions back to IDLE. This applies to all states except IDLE and DONE.

---

## Sensing Pipeline

### Visual Sensing (VLM)

- **Model:** Qwen3-VL-8B running on vLLM (OpenAI-compatible API)
- **Dispatch:** Round-robin across 2-3 GPU instances (configurable in `config.py`)
- **Interval:** Frame dispatched every ~0.37s; each inference takes ~1.1s; round-robin masks latency
- **Prompt:** Asks the VLM to return a JSON dict with 7 float cues (0-1):
  - `hands_visible`, `hands_under_water`, `hands_on_soap`, `foam_visible`, `towel_drying`, `hands_touch_clothes`, `blower_visible`
- **Parsing:** Handles raw JSON, markdown-wrapped JSON (`` ```json ... ``` ``), and preamble text
- **Fallback:** Returns 0.0 for all cues on first call; 0.5 on parse error (prevents false transitions)
- **Backoff:** 10-second cooldown on connection failures

### Audio Sensing (YAMNet)

- **Model:** YAMNet from TensorFlow Hub (pretrained on AudioSet)
- **Input:** 16 kHz mono audio, 2-second chunks captured via `sounddevice`
- **Cue mapping:**
  - `water_sound` — matched against YAMNet classes: "Water tap, faucet", "Water", "Sink (filling or washing)", "Pour", "Stream", "Trickle, dribble"
  - `blower_sound` — matched against: "Hair dryer", "Mechanical fan", "Air conditioning"
- **Output:** Max classification score across matching classes for each cue

### Ensemble Merging

Visual and audio cues are merged into a single dict (`{**visual_cues, **audio_cues}`) each frame. The merged dict is passed to the FSM engine.

---

## Feedback System

### Text-to-Speech (TTS)

- **Engine:** pyttsx3 (uses macOS NSSpeechSynthesizer natively)
- **Architecture:** Non-blocking — messages are queued and processed by a background daemon thread
- **Speech rate:** 160 words per minute

**Two types of TTS messages:**

1. **Transition messages** — Played immediately when the FSM changes state. These bypass the cooldown to ensure every state change is announced. Example: *"Applying hand soap, great!"*

2. **State warnings** — Periodic reminders while staying in a state. Governed by a 5-second cooldown and per-state tracking so each warning plays exactly once per state visit. Examples:
   - IDLE (20s): *"Please turn on the faucet and start washing your hands."*
   - SOAPING (10s): *"Remember to lather all surfaces of your hands for at least 20 seconds."*
   - SOAPING (25s): *"Great lathering! You can rinse your hands now."*
   - RINSING (15s): *"Make sure to rinse off all the soap."*

3. **Congratulations** — When DONE is reached, plays a congratulations message with the final score.

### Full Message Tables

**Transition Messages (21 total):**

| From | To | Message |
|------|----|---------|
| IDLE | WATER_NO_HANDS | "Water detected. Please put your hands under the water." |
| IDLE | HANDS_NO_WATER | "Hands detected. Please turn on the faucet." |
| IDLE | WASHING | "Good, now washing your hands." |
| WATER_NO_HANDS | WASHING | "Hands detected, now washing." |
| HANDS_NO_WATER | WASHING | "Water detected, now washing." |
| WASHING | SOAPING | "Applying hand soap, great!" |
| SOAPING | RINSING | "Rinsing the soap off now." |
| RINSING | TOWEL_DRYING | "Drying hands with a towel, good choice." |
| RINSING | CLOTHES_DRYING | "Drying hands on clothes. A towel would be better." |
| RINSING | BLOWER_DRYING | "Using the hand dryer." |
| TOWEL_DRYING | DONE | "All done! Great job washing your hands." |
| CLOTHES_DRYING | DONE | "All done! Next time try using a towel." |
| BLOWER_DRYING | DONE | "All done! Great job." |
| WATER_NO_HANDS | IDLE | "Activity stopped. Please continue." |
| HANDS_NO_WATER | IDLE | "Activity stopped. Please continue." |
| WASHING | IDLE | "You seem to have stopped. Please continue washing." |
| SOAPING | IDLE | "You seem to have stopped. Please continue." |
| RINSING | IDLE | "You seem to have stopped. Please continue rinsing." |
| TOWEL_DRYING | IDLE | "You seem to have stopped drying." |
| CLOTHES_DRYING | IDLE | "You seem to have stopped drying." |
| BLOWER_DRYING | IDLE | "You seem to have stopped drying." |

**State Warnings (12 total across 9 states):**

| State | Delay | Message |
|-------|-------|---------|
| IDLE | 20s | "Please turn on the faucet and start washing your hands." |
| WATER_NO_HANDS | 10s | "Please put your hands under the water." |
| WATER_NO_HANDS | 20s | "Please save water. Put your hands under or turn off the faucet." |
| HANDS_NO_WATER | 10s | "Please turn on the faucet." |
| WASHING | 20s | "Please save water. Apply soap or turn off the faucet." |
| SOAPING | 10s | "Remember to lather all surfaces of your hands for at least 20 seconds." |
| SOAPING | 25s | "Great lathering! You can rinse your hands now." |
| RINSING | 15s | "Make sure to rinse off all the soap." |
| TOWEL_DRYING | 8s | "Make sure your hands are fully dry." |
| CLOTHES_DRYING | 8s | "Try using a clean towel next time for better hygiene." |
| BLOWER_DRYING | 8s | "Keep your hands under the dryer until fully dry." |

---

## GUI Layout

The GUI is a 1280x720 split-screen window rendered entirely with OpenCV (no tkinter/Qt dependency).

### Left Panel — Camera Feed (640x720)

- **Live webcam feed** with a semi-transparent overlay at the bottom (310px)
- **State badge:** Colored rounded rectangle at the top of the overlay showing the current state name and elapsed time
- **Cue bars (9 total):**
  - Visual Cues section (7 bars): `hands_visible`, `hands_under_water`, `hands_on_soap`, `foam_visible`, `towel_drying`, `hands_touch_clothes`, `blower_visible`
  - Audio Cues section (2 bars): `water_sound`, `blower_sound`
  - Color-coded fill: green (>0.6), yellow (0.3-0.6), red (<0.3)
  - Rounded bar ends for modern look
- **TTS message area:** Shows the last spoken TTS message with a `>>` prefix indicator
- **Congratulations overlay:** When DONE is reached, a centered dark popup shows "Congratulations!", total session time, final score (color-coded), and a subtitle

### Right Panel — FSM Flowchart (640x720)

- **Title:** "FSM Flowchart"
- **Progress bar:** Horizontal bar at the top showing percentage of states visited
- **Flowchart:** 7-layer vertical layout with state boxes:
  - **Active (current):** Larger box with teal border, glow effect, and time-in-state counter
  - **Completed (visited):** Emerald green filled box with checkmark
  - **Pending (not visited):** Gray outline only
- **Arrows:** Lines between state boxes showing possible transitions
  - Teal and thicker for transitions already taken
  - Gray and thinner for transitions not yet taken
- **Guidance text:** Current state's guidance message displayed below the flowchart
- **Score badge:** Displayed at the bottom once DONE is reached, with color-coded background (green >= 80%, cyan >= 50%, red < 50%)

### Keyboard Controls

| Key | Action |
|-----|--------|
| `q` | Quit the application |
| `r` | Reset the FSM (start over) |

---

## Scoring

When the DONE state is reached, the system calculates a score out of 100 points based on which states were visited during the session.

| State | Points | Notes |
|-------|--------|-------|
| WASHING | 15 | Basic water washing |
| SOAPING | 25 | Most important step |
| RINSING | 20 | Proper rinse |
| TOWEL_DRYING | 15 | Best drying method |
| BLOWER_DRYING | 10 | Acceptable drying |
| CLOTHES_DRYING | 5 | Least hygienic drying |
| DONE | 10 | Completion bonus |
| **Total** | **100** | |

A perfect run (IDLE -> WASHING -> SOAPING -> RINSING -> TOWEL_DRYING -> DONE) scores 85/100 (WASHING 15 + SOAPING 25 + RINSING 20 + TOWEL_DRYING 15 + DONE 10).

---

## Project Structure

```
FSM_Zuchen_Li/
├── main.py                    # Entry point — CLI, main loop, thread orchestration
├── config.py                  # All tunable parameters (VLM, audio, FSM, GUI, TTS)
├── requirements.txt           # Python dependencies
│
├── fsm/                       # Finite State Machine
│   ├── __init__.py
│   ├── states.py              # 10 state definitions, transition conditions, layout
│   └── engine.py              # FSMEngine: update loop, sustained timers, scoring
│
├── sensing/                   # Multi-modal sensing
│   ├── __init__.py
│   ├── base.py                # Abstract SensingProvider interface
│   ├── vlm_provider.py        # Single VLM endpoint (OpenAI API via vLLM)
│   ├── vlm_pool.py            # Round-robin dispatch across multiple VLM instances
│   ├── audio_provider.py      # YAMNet audio classification (water/blower sounds)
│   └── ensemble.py            # Merge visual + audio cues into unified dict
│
├── feedback/                  # User feedback
│   ├── __init__.py
│   ├── tts.py                 # Non-blocking TTS with cooldown (pyttsx3)
│   └── messages.py            # Transition messages and state warnings
│
├── gui/                       # Split-screen GUI (OpenCV only)
│   ├── __init__.py
│   ├── app.py                 # GUIApp: composes camera + FSM panels
│   ├── camera_panel.py        # Left panel: webcam + cue overlay + congrats
│   ├── fsm_panel.py           # Right panel: flowchart + progress + score
│   └── drawing.py             # Rounded rectangle drawing utility
│
├── output/                    # Post-session output generation
│   ├── __init__.py
│   ├── logger.py              # JSON session logger
│   ├── timeline.py            # Matplotlib timeline visualization
│   └── report.py              # Text report with score breakdown
│
├── utils/                     # Utility functions
│   ├── __init__.py
│   ├── frame_utils.py         # Frame resize + base64 encoding
│   └── audio_utils.py         # AudioCapture (sounddevice wrapper)
│
├── tests/                     # Unit tests
│   ├── test_fsm.py            # 16 FSM transition tests
│   ├── test_vlm.py            # 7 VLM response parsing tests
│   └── test_audio.py          # 3 audio provider tests
│
└── outputs/                   # Generated session data (JSON logs, reports)
    ├── session_*.json
    ├── timeline.png
    └── report.txt
```

---

## Prerequisites

- **Python 3.10+** (tested on 3.12)
- **macOS** (required for `cv2.imshow` on main thread and pyttsx3 NSSpeechSynthesizer)
- **Webcam** (built-in or USB)
- **Microphone** (for audio cues; optional with `--no-audio`)
- **Remote GPU access** for VLM inference (UMich Lighthouse HPC with L40S GPUs, accessed via SSH tunnel)

---

## Environment Setup

### 1. Create conda environment

```bash
conda create -n handwash python=3.12
conda activate handwash
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up SSH tunnel to remote VLM servers

The VLM models (Qwen3-VL-8B) run on remote GPUs via vLLM with an OpenAI-compatible API. Set up SSH port forwarding:

```bash
# Forward 3 GPU endpoints (adjust hostnames/ports for your setup)
ssh -L 8000:localhost:8000 \
    -L 8001:localhost:8001 \
    -L 8002:localhost:8002 \
    your_user@lighthouse.umich.edu
```

### 4. Start vLLM servers on remote GPUs

On each GPU node:

```bash
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3-VL-8B \
    --port 800X \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.9
```

### 5. Verify connectivity

```bash
curl http://localhost:8000/v1/models
```

---

## Running the System

### Live webcam mode (default)

```bash
python main.py
```

### Video file mode

```bash
python main.py --mode video --input path/to/video.mp4
```

### Disable audio capture

```bash
python main.py --no-audio
```

### Disable TTS voice feedback

```bash
python main.py --no-tts
```

### Combined options

```bash
python main.py --no-audio --no-tts --log-level DEBUG
```

### Full usage

```
usage: main.py [-h] [--mode {live,video}] [--input INPUT]
               [--no-audio] [--no-tts]
               [--log-level {DEBUG,INFO,WARNING}]

Hand Washing Skill Assessment

options:
  -h, --help            show this help message and exit
  --mode {live,video}   Input mode: 'live' for webcam, 'video' for file
  --input INPUT         Video file path (for --mode video)
  --no-audio            Disable audio capture
  --no-tts              Disable TTS voice feedback
  --log-level {DEBUG,INFO,WARNING}
                        Logging level
```

---

## Configuration Reference

All tunable parameters are in `config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `VLM_MODEL_NAME` | `"qwen3vl"` | Model name for vLLM |
| `VLM_MAX_TOKENS` | `80` | Max tokens per VLM response |
| `VLM_TIMEOUT` | `15` | VLM request timeout (seconds) |
| `FRAME_MAX_SIDE` | `480` | Max frame dimension for VLM input |
| `FRAME_JPEG_QUALITY` | `70` | JPEG quality for frame encoding |
| `AUDIO_SAMPLE_RATE` | `16000` | Audio sample rate (Hz) |
| `AUDIO_CHUNK_DURATION` | `2` | Audio chunk duration (seconds) |
| `VLM_DISPATCH_INTERVAL` | `0.37` | Seconds between VLM dispatches |
| `AUDIO_SAMPLE_INTERVAL` | `1.0` | Seconds between audio classifications |
| `CUE_BUFFER_SIZE` | `5` | Number of cue sets to buffer |
| `IDLE_TIMEOUT` | `5.0` | Seconds of inactivity before returning to IDLE |
| `TTS_COOLDOWN` | `5` | Minimum seconds between TTS warning messages |
| `GUI_WIDTH` | `1280` | GUI window width |
| `GUI_HEIGHT` | `720` | GUI window height |
| `POOL_MODE` | `"round_robin"` | VLM pool dispatch strategy |
| `VLM_PROVIDERS` | 3 endpoints | List of VLM endpoint configurations |

---

## Testing

Run all FSM tests:

```bash
python -m pytest tests/test_fsm.py -v
```

Run all tests:

```bash
python -m pytest tests/ -v
```

Run tests without pytest:

```bash
python tests/test_fsm.py
```

### Test coverage

- **`test_fsm.py`** (16 tests) — All FSM transitions, idle timeout, DONE terminal state, zero/fallback cues, reset, scoring
- **`test_vlm.py`** (7 tests) — VLM response parsing: raw JSON, markdown wrapping, preamble, value clamping, missing keys, fallback/zero cues
- **`test_audio.py`** (3 tests) — Audio cue mapping keys, no-chunk handling, YAMNet class name definitions

---

## Session Outputs

After each session (quit with `q` or video ends), three files are generated in `outputs/`:

1. **`session_{timestamp}.json`** — Full session log including state history (with enter/exit timestamps) and all events (transitions, cue snapshots)

2. **`timeline.png`** — Matplotlib horizontal bar chart showing the time spent in each state. Each state visit is a colored bar, labeled with its duration.

3. **`report.txt`** — Human-readable text report including:
   - Session summary (total time, states visited, completion status)
   - State-by-state breakdown with enter/exit times and durations
   - Score breakdown per state (points earned / max points, PASS/MISS)
   - Total score

---

## Troubleshooting

### VLM endpoints unreachable

```
WARNING: Some VLM endpoints are unreachable.
```

- Verify SSH tunnel is open: `lsof -i :8000`
- Verify vLLM server is running on the remote machine
- Check `config.py` `VLM_PROVIDERS` URLs match your tunnel ports

### No audio capture

```
Warning: Could not start audio capture
```

- Grant microphone permission in macOS System Preferences -> Privacy & Security -> Microphone
- Run with `--no-audio` to skip audio sensing (visual cues only)

### TTS not working

- Verify pyttsx3 is installed: `python -c "import pyttsx3; e = pyttsx3.init(); e.say('test'); e.runAndWait()"`
- macOS may require accessibility permissions for speech synthesis
- Run with `--no-tts` to disable voice feedback

### GUI window not appearing

- macOS requires `cv2.imshow` to run on the main thread (this is already handled)
- Ensure `opencv-python` (not `opencv-python-headless`) is installed

### Slow VLM responses

- Check GPU utilization on remote machine: `nvidia-smi`
- Add more VLM providers to `VLM_PROVIDERS` in `config.py` for better round-robin coverage
- Reduce `FRAME_MAX_SIDE` or `FRAME_JPEG_QUALITY` for smaller payloads
