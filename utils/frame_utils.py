import base64
import cv2
import numpy as np

from config import FRAME_MAX_SIDE, FRAME_JPEG_QUALITY


def resize_frame(frame: np.ndarray, max_side: int = FRAME_MAX_SIDE) -> np.ndarray:
    """Resize frame so the longest side is at most max_side pixels."""
    h, w = frame.shape[:2]
    if max(h, w) <= max_side:
        return frame
    scale = max_side / max(h, w)
    new_w, new_h = int(w * scale), int(h * scale)
    return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)


def frame_to_base64(frame: np.ndarray, quality: int = FRAME_JPEG_QUALITY) -> str:
    """Encode a BGR frame as a base64 JPEG string."""
    resized = resize_frame(frame)
    _, buf = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def preprocess_frame(frame: np.ndarray) -> str:
    """Full preprocessing pipeline: resize + base64 encode."""
    return frame_to_base64(frame)
