# config.py — All tunable parameters

# === VLM (remote via SSH tunnel) ===
VLM_MODEL_NAME = "qwen3vl"
VLM_MAX_TOKENS = 80
VLM_TIMEOUT = 15

VLM_PROMPT = (
    'Return ONLY JSON, no explanation: '
    '{"hands_visible":0-1,"hands_under_water":0-1,'
    '"hands_on_soap":0-1,"foam_visible":0-1,'
    '"towel_drying":0-1,"hands_touch_clothes":0-1,'
    '"blower_visible":0-1}. '
    'hands_on_soap: hands touching or right next to soap, not just soap visible. '
    'hands_touch_clothes: hands rubbing or wiping against clothes worn on the person body.'
)

# === Frame ===
FRAME_MAX_SIDE = 480
FRAME_JPEG_QUALITY = 70

# === Audio ===
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHUNK_DURATION = 2

# === Timing ===
VLM_DISPATCH_INTERVAL = 0.37
AUDIO_SAMPLE_INTERVAL = 1.0

# === FSM ===
CUE_BUFFER_SIZE = 5
IDLE_TIMEOUT = 5.0  # seconds of no activity before returning to IDLE

# === TTS ===
TTS_COOLDOWN = 5

# === GUI ===
GUI_WIDTH = 1280
GUI_HEIGHT = 720
GUI_BG_COLOR = (35, 25, 25)        # dark blue-gray (BGR)

# FSM diagram colors (BGR for OpenCV)
COLOR_ACTIVE = (209, 206, 0)       # teal-cyan accent
COLOR_COMPLETED = (100, 180, 60)   # emerald green
COLOR_PENDING = (120, 110, 100)    # soft warm gray
COLOR_ARROW = (160, 155, 150)      # muted gray
COLOR_ARROW_TAKEN = (209, 206, 0)  # teal for taken transitions
COLOR_TEXT = (245, 240, 235)       # warm white
COLOR_GLOW = (209, 206, 0)        # glow around active box
COLOR_OVERLAY_BG = (45, 35, 30)   # camera overlay background
COLOR_SECTION_ACCENT = (209, 206, 0)  # section header accent line

# State badge colors for camera panel (BGR)
STATE_BADGE_COLORS = {
    "IDLE":            (140, 130, 120),  # gray
    "WATER_NO_HANDS":  (200, 160, 40),   # blue
    "HANDS_NO_WATER":  (50, 160, 200),   # orange
    "WASHING":         (200, 180, 0),     # cyan
    "SOAPING":         (180, 100, 220),   # pink-magenta
    "RINSING":         (200, 200, 0),     # teal
    "TOWEL_DRYING":    (100, 180, 60),    # emerald
    "CLOTHES_DRYING":  (60, 140, 190),    # warm orange
    "BLOWER_DRYING":   (180, 160, 50),    # blue-teal
    "DONE":            (80, 200, 80),     # green
}

# === VLM Pool ===
POOL_MODE = "round_robin"
VLM_PROVIDERS = [
    {"name": "qwen3vl_gpu0", "url": "http://localhost:8000/v1", "weight": 1.0},
    {"name": "qwen3vl_gpu1", "url": "http://localhost:8001/v1", "weight": 1.0},
    {"name": "qwen3vl_gpu2", "url": "http://localhost:8002/v1", "weight": 1.0},
]
