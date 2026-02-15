# Hand Washing Skill Assessment System

A real-time, AI-powered system that observes and assesses hand washing technique using a **Finite State Machine (FSM)**, **Vision Language Models (VLMs)**, **audio classification (YAMNet)**, and **text-to-speech feedback**. Built for the University of Michigan SURE program (Project #9: Seeing Skill with States).

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [VLM Backend Configuration](#vlm-backend-configuration)
4. [Running the System](#running-the-system)
5. [System Architecture](#system-architecture)
6. [FSM Design](#fsm-design)
7. [Sensing Pipeline](#sensing-pipeline)
8. [Feedback System](#feedback-system)
9. [GUI Layout](#gui-layout)
10. [Scoring](#scoring)
11. [Project Structure](#project-structure)
12. [Configuration Reference](#configuration-reference)
13. [Testing](#testing)
14. [Session Outputs](#session-outputs)
15. [Troubleshooting](#troubleshooting)

---

## Overview

The system watches a user washing their hands via webcam and microphone, classifies visual and audio cues in real time, drives a 12-state FSM to track progress through the hand washing procedure, and provides adaptive voice guidance and a live split-screen GUI.

**Key capabilities:**

- Real-time multi-modal sensing (vision + audio)
- 12-state FSM with sustained-condition transitions, idle timeout, and rinsing quality sub-states
- Switchable VLM backend: local vLLM (Qwen3-VL) or Gemini 2.5 Flash cloud API
- Binary VLM classification (0/1) for robust cue detection
- YAMNet-based audio classification for water and blower sounds
- Adaptive Level-of-Detail (LoD) guidance that increases specificity when the user struggles
- Non-blocking text-to-speech with transition messages, periodic warnings, and congratulations
- Flexible transition paths: re-soap, skip-soap, skip-rinse
- Split-screen GUI: live camera feed with cue overlay (left) + FSM flowchart (right)
- Post-session reports: JSON log, timeline visualization, text score report
- 100-point scoring system with rinsing quality bonuses

---

## Quick Start

### Prerequisites

- **Python 3.10+** (tested on 3.12)
- **macOS** (required for `cv2.imshow` on main thread and pyttsx3 NSSpeechSynthesizer)
- **Webcam** (built-in or USB)
- **Microphone** (for audio cues; optional with `--no-audio`)
- **VLM backend** — either remote GPU access (local vLLM) or a Gemini API key (cloud)

### 1. Create conda environment

```bash
conda create -n handwash python=3.12
conda activate handwash
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API keys

```bash
cp .env.example .env
```

Edit `.env` and fill in your API keys (only needed for cloud backends):

```
GEMINI_API_KEY=your-gemini-api-key-here
```

### 4. Choose VLM backend

Edit `config.py` line 11 — change this **one line** to switch:

```python
VLM_BACKEND = "local"   # Local vLLM via SSH tunnel (Qwen3-VL-8B)
VLM_BACKEND = "gemini"  # Gemini 2.5 Flash cloud API
```

### 5. Run

```bash
python main.py
```

---

## VLM Backend Configuration

The system supports multiple VLM backends via a single switch in `config.py`. All backends use the OpenAI-compatible API format, so the rest of the codebase is unchanged.

### Option A: Local vLLM (default)

```python
VLM_BACKEND = "local"
```

Uses Qwen3-VL-8B running on remote GPUs via vLLM, accessed through SSH tunnels. Best for low-latency, high-throughput inference with no API costs.

**Setup:**

1. Set up SSH tunnel to remote VLM servers:

```bash
# Forward 3 GPU endpoints (adjust hostnames/ports for your setup)
ssh -L 8000:localhost:8000 \
    -L 8001:localhost:8001 \
    -L 8002:localhost:8002 \
    your_user@lighthouse.umich.edu
```

2. Start vLLM servers on each remote GPU node:

```bash
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3-VL-8B \
    --port 800X \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.9
```

3. Verify connectivity:

```bash
curl http://localhost:8000/v1/models
```

**Config defaults:** 3 providers on ports 8000-8002, dispatch interval 0.37s, round-robin dispatch.

### Option B: Gemini 2.5 Flash

```python
VLM_BACKEND = "gemini"
```

Uses Google's Gemini 2.5 Flash via its OpenAI-compatible endpoint. No GPU setup needed — just an API key.

**Setup:**

1. Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)
2. Add it to `.env`:

```
GEMINI_API_KEY=your-key-here
```

3. Set `VLM_BACKEND = "gemini"` in `config.py`

**Config defaults:** 1 provider, dispatch interval 2.0s (safe for free tier rate limits; lower this if you have a paid tier).

### Adding more backends

To add a new OpenAI-compatible backend (e.g., OpenAI GPT-4o, local Ollama), add a new config dict in `config.py`:

```python
_MY_BACKEND_CONFIG = {
    "model_name": "gpt-4o",
    "api_key": os.getenv("OPENAI_API_KEY", ""),
    "dispatch_interval": 1.0,
    "providers": [
        {"name": "openai", "url": "https://api.openai.com/v1"},
    ],
}

_BACKENDS = {"local": _LOCAL_CONFIG, "gemini": _GEMINI_CONFIG, "my_backend": _MY_BACKEND_CONFIG}
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

### Keyboard Controls

| Key | Action |
|-----|--------|
| `q` | Quit the application |
| `r` | Reset the FSM (start over) |

---

## System Architecture

```
 macOS (local machine)                     Remote HPC / Cloud API
+-------------------------------+         +-------------------------------+
|  Webcam  -->  Frame Queue  ---|-------->|  vLLM: Qwen3-VL-8B (GPU x3) |
|  Mic     -->  AudioCapture    |   SSH   |  — OR —                      |
|                               |  tunnel |  Gemini 2.5 Flash (cloud)    |
|  Main Thread:                 |   /API  +-------------------------------+
|    cv2.imshow (GUI)           |
|    FSM engine                 |
|    TTS feedback               |
|                               |
|  Background Thread:           |
|    async VLM dispatch         |
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

### States (12)

| # | State | Description | Activity Cues |
|---|-------|-------------|---------------|
| 0 | **IDLE** | Waiting for hand washing to begin | (none — uses own timeout) |
| 1 | **WATER_NO_HANDS** | Water running, no hands detected | `water_sound` |
| 2 | **HANDS_NO_WATER** | Hands visible, no water | `hands_visible` |
| 3 | **WASHING** | Hands under running water | `hands_visible`, `water_sound`, `hands_under_water` |
| 4 | **SOAPING** | Applying hand soap / lathering | `hands_visible`, `hands_on_soap`, `foam_visible` |
| 5 | **RINSING** | Rinsing soap off (< 5s) | `hands_under_water`, `water_sound`, `hands_visible` |
| 6 | **RINSING_OK** | Adequate rinsing (5-10s) | `hands_under_water`, `water_sound`, `hands_visible` |
| 7 | **RINSING_THOROUGH** | Thorough rinsing (>= 10s total) | `hands_under_water`, `water_sound`, `hands_visible` |
| 8 | **TOWEL_DRYING** | Drying hands with a towel | `towel_drying`, `hands_visible` |
| 9 | **CLOTHES_DRYING** | Drying hands on clothes | `hands_touch_clothes`, `hands_visible` |
| 10 | **BLOWER_DRYING** | Drying hands with a blower/dryer | `blower_visible`, `blower_sound` |
| 11 | **DONE** | Hand washing complete | (none — terminal state) |

### Rinsing Quality Sub-States

Rinsing is divided into three progressive quality levels based on active rinsing duration (hands under water + water sound):

| Sub-State | Duration | Points | Description |
|-----------|----------|--------|-------------|
| **RINSING** | 0-5s | 8 | Initial rinsing, minimal |
| **RINSING_OK** | 5-10s | +6 | Adequate rinsing |
| **RINSING_THOROUGH** | >= 10s | +6 | Thorough, recommended rinsing |

Transitions between rinsing sub-states require active rinsing cues (`hands_under_water > 0.5` AND `water_sound > 0.5`). Simply being in the state without active cues does not trigger the upgrade.

### Transition Flowchart

```
                      IDLE
                    /  |  \
                   v   v   v
       WATER_NO_HANDS  |  HANDS_NO_WATER
                \      |      /
                 v     v     v
                    WASHING --------.--------.
                       |             \        \
                       v              \        \
                    SOAPING ---.-------.--------.
                       |        \      |        |
                       v         v     v        v
    RINSING --> RINSING_OK --> RINSING_THOROUGH |
       |            |              |            |
       |<--- re-soap (back to SOAPING) ------->|
       |            |              |            |
       v            v              v            v
     TOWEL_DRYING  CLOTHES_DRYING  BLOWER_DRYING
                \     |     /
                 v    v    v
                     DONE
```

**Special transition paths:**

- **Re-soap** — From any rinsing state (RINSING, RINSING_OK, RINSING_THOROUGH) back to SOAPING when soap is detected again
- **Skip soap** — From WASHING directly to any drying state (towel/clothes/blower) without soaping
- **Skip rinse** — From SOAPING directly to any drying state without rinsing

### Transition Conditions

All sustained-condition transitions require the condition to be continuously true for **1.3 seconds** before firing. This prevents false triggers from momentary cue spikes.

| From | To | Condition |
|------|----|-----------|
| IDLE | WATER_NO_HANDS | `water_sound > 0.5` AND `hands_visible < 0.4` sustained 1.3s |
| IDLE | HANDS_NO_WATER | `hands_visible > 0.5` AND `water_sound < 0.4` sustained 1.3s |
| IDLE / WATER_NO_HANDS / HANDS_NO_WATER | WASHING | `hands_under_water > 0.5` AND `water_sound > 0.5` sustained 1.3s |
| WASHING | SOAPING | `hands_on_soap > 0.5` (immediate) |
| SOAPING | RINSING | `hands_under_water > 0.5` AND `water_sound > 0.5` sustained 1.3s |
| RINSING | RINSING_OK | In state >= 5s AND `hands_under_water > 0.5` AND `water_sound > 0.5` |
| RINSING_OK | RINSING_THOROUGH | In state >= 5s AND `hands_under_water > 0.5` AND `water_sound > 0.5` |
| RINSING / RINSING_OK / RINSING_THOROUGH | SOAPING | `hands_on_soap > 0.5` (immediate, re-soap) |
| WASHING / SOAPING / RINSING* | TOWEL_DRYING | `towel_drying > 0.5` sustained 1.3s |
| WASHING / SOAPING / RINSING* | CLOTHES_DRYING | `hands_touch_clothes > 0.5` sustained 1.3s |
| WASHING / SOAPING / RINSING* | BLOWER_DRYING | `blower_sound > 0.3` OR `blower_visible > 0.3` (immediate) |
| TOWEL_DRYING | DONE | In state >= 1.3s AND `towel_drying < 0.3` |
| CLOTHES_DRYING | DONE | In state >= 1.3s AND `hands_touch_clothes < 0.3` |
| BLOWER_DRYING | DONE | In state >= 1.3s AND `blower_sound < 0.2` AND `blower_visible < 0.2` |

*RINSING\* = RINSING, RINSING_OK, or RINSING_THOROUGH*

### Idle Timeout

If all activity cues for the current state drop below 0.3 for **5 seconds**, the FSM transitions back to IDLE. This applies to all states except IDLE and DONE.

### Adaptive Level-of-Detail (LoD) Guidance

Each idle timeout regression increments a global `lod_level` (0 → 1 → 2, capped at 2). The guidance messages become progressively more specific:

| LoD Level | Style | Example (WASHING state) |
|-----------|-------|------------------------|
| 0 (basic) | Short directive | "Apply soap when ready." |
| 1 (detailed) | Contextual instruction | "Good, your hands are under water. Now apply soap to both hands." |
| 2 (very detailed) | Step-by-step | "Reach for the soap dispenser and press it to get soap on your hands. Rub all surfaces." |

The `lod_level` resets to 0 when the FSM is manually reset.

---

## Sensing Pipeline

### Visual Sensing (VLM)

- **Backends:** Local vLLM (Qwen3-VL-8B) or Gemini 2.5 Flash — switchable via `VLM_BACKEND` in `config.py`
- **Dispatch:** Round-robin across configured providers (3 GPUs for local, 1 endpoint for Gemini)
- **Interval:** Configurable per backend (0.37s for local, 2.0s for Gemini)
- **Prompt:** Binary classification — asks the VLM to return a JSON dict with 7 binary cues (0 or 1):
  - `hands_visible`, `hands_under_water`, `hands_on_soap`, `foam_visible`, `towel_drying`, `hands_touch_clothes`, `blower_visible`
  - Uses 1 if clearly true, 0 if not or uncertain
- **Parsing:** Handles raw JSON, markdown-wrapped JSON (`` ```json ... ``` ``), and preamble text
- **Defaults:** Missing keys default to 0; fallback cues (on parse error) are all 0.0
- **Backoff:** 10-second cooldown on connection failures
- **Concurrency:** Each provider is limited to 1 in-flight request to prevent request flooding

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

**Three types of TTS messages:**

1. **Transition messages** — Played immediately when the FSM changes state. These use `speak_now()` to bypass the cooldown, ensuring every state change is announced. Example: *"Applying hand soap, great!"*

2. **State warnings** — Periodic reminders while staying in a state. Governed by a 5-second cooldown and per-state tracking so each warning plays exactly once per state visit. Warning tracking resets on every state transition. Examples:
   - IDLE (20s): *"Please turn on the faucet and start washing your hands."*
   - SOAPING (10s): *"Remember to lather all surfaces of your hands for at least 20 seconds."*
   - RINSING_OK (8s): *"Good rinsing! Keep going a bit longer for a thorough rinse."*

3. **Congratulations** — When DONE is reached, plays a congratulations message with the final score.

### Adaptive LoD Guidance

Each state has 3 levels of guidance text (basic, detailed, very detailed). The current level is determined by `fsm.lod_level`, which increments when the user times out to IDLE. This guidance is displayed on the FSM flowchart panel and covers all 12 states.

### Full Message Tables

**Transition Messages (49 total):**

| From | To | Message |
|------|----|---------|
| IDLE | WATER_NO_HANDS | "Water detected. Please put your hands under the water." |
| IDLE | HANDS_NO_WATER | "Hands detected. Please turn on the faucet." |
| IDLE | WASHING | "Good, now washing your hands." |
| WATER_NO_HANDS | WASHING | "Hands detected, now washing." |
| HANDS_NO_WATER | WASHING | "Water detected, now washing." |
| WASHING | SOAPING | "Applying hand soap, great!" |
| SOAPING | RINSING | "Rinsing the soap off now." |
| RINSING | RINSING_OK | "Good rinsing! Keep going for a thorough rinse." |
| RINSING_OK | RINSING_THOROUGH | "Excellent! Thorough rinsing achieved." |
| RINSING | SOAPING | "Re-applying soap for another round." |
| RINSING_OK | SOAPING | "Re-applying soap for another round." |
| RINSING_THOROUGH | SOAPING | "Re-applying soap for another round." |
| RINSING | TOWEL_DRYING | "Drying hands with a towel, good choice." |
| RINSING | CLOTHES_DRYING | "Drying hands on clothes. A towel would be better." |
| RINSING | BLOWER_DRYING | "Using the hand dryer." |
| RINSING_OK | TOWEL_DRYING | "Drying hands with a towel, good choice." |
| RINSING_OK | CLOTHES_DRYING | "Drying hands on clothes. A towel would be better." |
| RINSING_OK | BLOWER_DRYING | "Using the hand dryer." |
| RINSING_THOROUGH | TOWEL_DRYING | "Drying hands with a towel, good choice." |
| RINSING_THOROUGH | CLOTHES_DRYING | "Drying hands on clothes. A towel would be better." |
| RINSING_THOROUGH | BLOWER_DRYING | "Using the hand dryer." |
| WASHING | TOWEL_DRYING | "Drying without soap. Try using soap next time." |
| WASHING | CLOTHES_DRYING | "Drying on clothes without soap. Try soap and a towel next time." |
| WASHING | BLOWER_DRYING | "Drying without soap. Try using soap next time." |
| SOAPING | TOWEL_DRYING | "Drying without rinsing. Make sure to rinse off the soap next time." |
| SOAPING | CLOTHES_DRYING | "Drying on clothes without rinsing. Rinse and use a towel next time." |
| SOAPING | BLOWER_DRYING | "Drying without rinsing. Make sure to rinse off the soap next time." |
| TOWEL_DRYING | DONE | "All done! Great job washing your hands." |
| CLOTHES_DRYING | DONE | "All done! Next time try using a towel." |
| BLOWER_DRYING | DONE | "All done! Great job." |
| WATER_NO_HANDS | IDLE | "Activity stopped. Please continue." |
| HANDS_NO_WATER | IDLE | "Activity stopped. Please continue." |
| WASHING | IDLE | "You seem to have stopped. Please continue washing." |
| SOAPING | IDLE | "You seem to have stopped. Please continue." |
| RINSING | IDLE | "You seem to have stopped. Please continue rinsing." |
| RINSING_OK | IDLE | "You seem to have stopped. Please continue rinsing." |
| RINSING_THOROUGH | IDLE | "You seem to have stopped rinsing." |
| TOWEL_DRYING | IDLE | "You seem to have stopped drying." |
| CLOTHES_DRYING | IDLE | "You seem to have stopped drying." |
| BLOWER_DRYING | IDLE | "You seem to have stopped drying." |

**State Warnings (14 total across 11 states):**

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
| RINSING_OK | 8s | "Good rinsing! Keep going a bit longer for a thorough rinse." |
| RINSING_THOROUGH | 8s | "Excellent rinse! You can dry your hands now." |
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
  - **Layer 4 (rinsing):** Three states side-by-side — RINSING, RINSING_OK, RINSING_THOROUGH — with horizontal arrows showing quality progression
  - **Active (current):** Larger box with teal border, glow effect, and time-in-state counter
  - **Completed (visited):** Emerald green filled box with checkmark
  - **Pending (not visited):** Gray outline only
- **Arrows:**
  - **Primary forward edges:** Always drawn (dimmer when untaken, teal and thicker when taken)
  - **Optional edges:** Skip-soap, skip-rinse, and re-soap paths are only drawn when the transition has actually been taken, reducing visual clutter
  - **Directional arrows:** Horizontal for same-layer (rinsing quality), downward for forward transitions, upward for revert transitions (re-soap)
- **Guidance text:** Current state's LoD-aware guidance message displayed below the flowchart, with automatic word wrapping
- **Score badge:** Displayed at the bottom once DONE is reached, with color-coded background (green >= 80%, cyan >= 50%, red < 50%)

---

## Scoring

When the DONE state is reached, the system calculates a score out of 100 points based on which states were visited during the session.

| State | Points | Notes |
|-------|--------|-------|
| WASHING | 15 | Basic water washing |
| SOAPING | 25 | Most important step |
| RINSING | 8 | Initial rinsing (< 5s) |
| RINSING_OK | 6 | Adequate rinsing (5-10s bonus) |
| RINSING_THOROUGH | 6 | Thorough rinsing (>= 10s bonus) |
| TOWEL_DRYING | 15 | Best drying method |
| BLOWER_DRYING | 10 | Acceptable drying |
| CLOTHES_DRYING | 5 | Least hygienic drying |
| DONE | 10 | Completion bonus |
| **Total** | **100** | |

**Example scores:**

- **Perfect run** (WASHING -> SOAPING -> RINSING -> RINSING_OK -> RINSING_THOROUGH -> TOWEL_DRYING -> DONE): **85/100**
- **Good run, no thorough rinse** (WASHING -> SOAPING -> RINSING -> RINSING_OK -> TOWEL_DRYING -> DONE): **79/100**
- **Partial run, no rinsing quality** (WASHING -> SOAPING -> RINSING -> TOWEL_DRYING -> DONE): **73/100**
- **Skipped soap** (WASHING -> RINSING -> TOWEL_DRYING -> DONE): **48/100**

Note: The theoretical maximum of 100 requires visiting all three mutually exclusive drying methods, which is not possible in a single session. The practical maximum with towel drying is 85.

---

## Project Structure

```
FSM_Zuchen_Li/
├── main.py                    # Entry point — CLI, main loop, thread orchestration
├── config.py                  # Backend switch + all tunable parameters
├── requirements.txt           # Python dependencies
├── .env.example               # API key template (copy to .env)
├── .env                       # API keys (gitignored)
│
├── fsm/                       # Finite State Machine
│   ├── __init__.py
│   ├── states.py              # 12 state definitions, transition conditions, layout
│   └── engine.py              # FSMEngine: update loop, sustained timers, scoring, LoD
│
├── sensing/                   # Multi-modal sensing
│   ├── __init__.py
│   ├── base.py                # Abstract SensingProvider interface
│   ├── vlm_provider.py        # VLM endpoint (OpenAI-compatible: vLLM, Gemini, etc.)
│   ├── vlm_pool.py            # Round-robin dispatch with per-provider concurrency cap
│   ├── audio_provider.py      # YAMNet audio classification (water/blower sounds)
│   └── ensemble.py            # Merge visual + audio cues into unified dict
│
├── feedback/                  # User feedback
│   ├── __init__.py
│   ├── tts.py                 # Non-blocking TTS with cooldown + speak_now (pyttsx3)
│   └── messages.py            # Transition messages, state warnings, LoD guidance
│
├── gui/                       # Split-screen GUI (OpenCV only)
│   ├── __init__.py
│   ├── app.py                 # GUIApp: composes camera + FSM panels
│   ├── camera_panel.py        # Left panel: webcam + cue overlay + congrats
│   ├── fsm_panel.py           # Right panel: flowchart + progress + score + guidance
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
│   ├── test_fsm.py            # 24 FSM transition + scoring tests
│   ├── test_vlm.py            # 7 VLM response parsing tests
│   └── test_audio.py          # 3 audio provider tests
│
└── outputs/                   # Generated session data (JSON logs, reports)
    ├── session_*.json
    ├── timeline.png
    └── report.txt
```

---

## Configuration Reference

All tunable parameters are in `config.py`:

**VLM Backend (derived from `VLM_BACKEND`):**

| Parameter | `"local"` | `"gemini"` | Description |
|-----------|-----------|------------|-------------|
| `VLM_MODEL_NAME` | `"qwen3vl"` | `"gemini-2.5-flash"` | Model name |
| `VLM_API_KEY` | `"dummy"` | from `.env` | API key |
| `VLM_DISPATCH_INTERVAL` | `0.37` | `2.0` | Seconds between VLM dispatches |
| `VLM_PROVIDERS` | 3 local endpoints | 1 Gemini endpoint | Provider list |

**Other parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `VLM_MAX_TOKENS` | `80` | Max tokens per VLM response |
| `VLM_TIMEOUT` | `15` | VLM request timeout (seconds) |
| `FRAME_MAX_SIDE` | `480` | Max frame dimension for VLM input |
| `FRAME_JPEG_QUALITY` | `70` | JPEG quality for frame encoding |
| `AUDIO_SAMPLE_RATE` | `16000` | Audio sample rate (Hz) |
| `AUDIO_CHUNK_DURATION` | `2` | Audio chunk duration (seconds) |
| `AUDIO_SAMPLE_INTERVAL` | `1.0` | Seconds between audio classifications |
| `CUE_BUFFER_SIZE` | `5` | Number of cue sets to buffer |
| `IDLE_TIMEOUT` | `5.0` | Seconds of inactivity before returning to IDLE |
| `TTS_COOLDOWN` | `5` | Minimum seconds between TTS warning messages |
| `GUI_WIDTH` | `1280` | GUI window width |
| `GUI_HEIGHT` | `720` | GUI window height |
| `POOL_MODE` | `"round_robin"` | VLM pool dispatch strategy |

---

## Testing

Run all tests:

```bash
python -m pytest tests/ -v
```

Run FSM tests only:

```bash
python -m pytest tests/test_fsm.py -v
```

Run tests without pytest:

```bash
python tests/test_fsm.py
```

### Test coverage

- **`test_fsm.py`** (24 tests) — All FSM transitions including rinsing quality upgrades, re-soap, skip-soap, skip-rinse, idle timeout with LoD increment, DONE terminal state, zero/fallback cues, reset, scoring (full and partial paths)
- **`test_vlm.py`** (7 tests) — VLM response parsing: raw JSON, markdown wrapping, preamble, value clamping, missing keys (default 0), fallback/zero cues
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

- **Local backend:** Verify SSH tunnel is open (`lsof -i :8000`), verify vLLM server is running on the remote machine, check `config.py` provider URLs match your tunnel ports
- **Gemini backend:** Verify your API key is set correctly in `.env`, check that `VLM_BACKEND = "gemini"` in `config.py`

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

- **Local backend:** Check GPU utilization on remote machine (`nvidia-smi`), add more providers for better round-robin coverage, reduce `FRAME_MAX_SIDE` or `FRAME_JPEG_QUALITY`
- **Gemini backend:** Lower `dispatch_interval` in `_GEMINI_CONFIG` if you have a paid tier with higher rate limits
