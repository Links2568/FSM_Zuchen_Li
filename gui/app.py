from typing import Dict, List, Optional

import cv2
import numpy as np

from config import GUI_WIDTH, GUI_HEIGHT
from gui.camera_panel import CameraPanel
from gui.fsm_panel import FSMPanel


class GUIApp:
    """Split-screen GUI: left half = camera, right half = FSM diagram.

    Uses only cv2.imshow — no tkinter/Qt. Runs in the main thread (macOS requirement).
    """

    def __init__(self, width: int = GUI_WIDTH, height: int = GUI_HEIGHT) -> None:
        self.width = width
        self.height = height
        self.camera_panel = CameraPanel(width // 2, height)
        self.fsm_panel = FSMPanel(width // 2, height)

    def render(
        self,
        camera_frame: np.ndarray,
        current_state: str,
        time_in_state: float,
        cues: Dict[str, float],
        state_history: List[Dict],
        last_tts: str,
        score: Optional[Dict] = None,
    ) -> np.ndarray:
        """Compose and display the split-screen frame."""
        left = self.camera_panel.render(
            camera_frame, cues, current_state, time_in_state, last_tts, score
        )
        right = self.fsm_panel.render(current_state, state_history, time_in_state, score)
        combined = np.hstack([left, right])
        cv2.imshow("Hand Washing Assessment", combined)
        return combined
