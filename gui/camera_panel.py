from typing import Dict, Optional

import cv2
import numpy as np

from config import (
    COLOR_OVERLAY_BG,
    COLOR_SECTION_ACCENT,
    COLOR_TEXT,
    STATE_BADGE_COLORS,
)
from gui.drawing import rounded_rect


class CameraPanel:
    """Left panel: webcam feed with cue overlay bars and status text."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height

    def render(
        self,
        frame: np.ndarray,
        cues: Dict[str, float],
        current_state: str,
        time_in_state: float,
        last_tts: str,
        score: Optional[Dict] = None,
    ) -> np.ndarray:
        panel = cv2.resize(frame, (self.width, self.height))

        # --- Semi-transparent overlay at bottom ---
        overlay_h = 310
        overlay_y = self.height - overlay_h
        overlay = panel.copy()
        # Rounded overlay background
        rounded_rect(
            overlay,
            (4, overlay_y),
            (self.width - 4, self.height - 4),
            COLOR_OVERLAY_BG,
            radius=14,
            thickness=-1,
        )
        cv2.addWeighted(overlay, 0.75, panel, 0.25, 0, panel)

        # --- State badge at top of overlay ---
        badge_color = STATE_BADGE_COLORS.get(current_state, (140, 130, 120))
        badge_label = current_state.replace("_", " ")
        badge_ts = cv2.getTextSize(badge_label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
        badge_w = badge_ts[0] + 20
        badge_h = badge_ts[1] + 14
        badge_x = (self.width - badge_w) // 2
        badge_y = overlay_y + 8
        rounded_rect(panel, (badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h), badge_color, radius=badge_h // 2, thickness=-1)
        cv2.putText(
            panel, badge_label,
            (badge_x + 10, badge_y + badge_ts[1] + 6),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2,
        )
        # Time beside badge
        time_txt = f"{time_in_state:.1f}s"
        cv2.putText(
            panel, time_txt,
            (badge_x + badge_w + 10, badge_y + badge_ts[1] + 6),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1,
        )

        y = badge_y + badge_h + 12
        bar_x = 15
        bar_w = 150
        bar_h = 13
        label_w = 120

        visual_keys = [
            "hands_visible", "hands_under_water",
            "hands_on_soap", "foam_visible",
            "towel_drying", "hands_touch_clothes", "blower_visible",
        ]
        audio_keys = ["water_sound", "blower_sound"]

        # Visual cues header
        self._draw_section_header(panel, "Visual Cues", bar_x, y)
        y += 18
        for key in visual_keys:
            val = cues.get(key, 0.0)
            self._draw_bar(panel, key, val, bar_x, y, label_w, bar_w, bar_h)
            y += bar_h + 4

        y += 6

        # Audio cues header
        self._draw_section_header(panel, "Audio Cues", bar_x, y)
        y += 18
        for key in audio_keys:
            val = cues.get(key, 0.0)
            self._draw_bar(panel, key, val, bar_x, y, label_w, bar_w, bar_h)
            y += bar_h + 4

        # --- TTS message area on right side of overlay ---
        info_x = self.width // 2 + 10
        info_y = badge_y + badge_h + 20

        if last_tts:
            # Speech indicator prefix
            cv2.putText(
                panel, ">>", (info_x, info_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, COLOR_SECTION_ACCENT, 1,
            )
            max_chars = 28
            lines = [last_tts[i : i + max_chars] for i in range(0, len(last_tts), max_chars)]
            for i, line in enumerate(lines[:4]):
                prefix = '"' if i == 0 else ' '
                suffix = '"' if i == len(lines[:4]) - 1 else ''
                cv2.putText(
                    panel,
                    f'{prefix}{line}{suffix}',
                    (info_x + 22, info_y + i * 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 200, 130), 1,
                )

        # --- Congratulations overlay when DONE ---
        if current_state == "DONE":
            self._draw_congrats_overlay(panel, time_in_state, score)

        return panel

    def _draw_congrats_overlay(
        self, panel: np.ndarray, session_time: float, score: Optional[Dict],
    ) -> None:
        """Big centered congratulations overlay."""
        cx, cy = self.width // 2, self.height // 3

        # Semi-transparent dark backdrop
        overlay = panel.copy()
        box_w, box_h = 360, 160
        x1 = cx - box_w // 2
        y1 = cy - box_h // 2
        rounded_rect(overlay, (x1, y1), (x1 + box_w, y1 + box_h), (30, 30, 20), radius=18, thickness=-1)
        cv2.addWeighted(overlay, 0.85, panel, 0.15, 0, panel)

        # Border
        rounded_rect(panel, (x1, y1), (x1 + box_w, y1 + box_h), (80, 200, 80), radius=18, thickness=2)

        # Title
        title = "Congratulations!"
        ts = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
        cv2.putText(
            panel, title, (cx - ts[0] // 2, y1 + 40),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80, 230, 80), 2,
        )

        # Session time
        mins = int(session_time) // 60
        secs = int(session_time) % 60
        time_str = f"Total time: {mins}m {secs}s" if mins > 0 else f"Total time: {secs}s"
        ts2 = cv2.getTextSize(time_str, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)[0]
        cv2.putText(
            panel, time_str, (cx - ts2[0] // 2, y1 + 75),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, COLOR_TEXT, 1,
        )

        # Score
        if score is not None:
            score_str = f"Score: {score['total']} / {score['max_total']}"
            ts3 = cv2.getTextSize(score_str, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)[0]
            # Color based on score
            ratio = score["total"] / max(score["max_total"], 1)
            if ratio >= 0.8:
                sc = (80, 230, 80)
            elif ratio >= 0.5:
                sc = (60, 210, 220)
            else:
                sc = (80, 100, 220)
            cv2.putText(
                panel, score_str, (cx - ts3[0] // 2, y1 + 115),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, sc, 2,
            )

        # Subtitle
        sub = "Great job washing your hands!"
        ts4 = cv2.getTextSize(sub, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
        cv2.putText(
            panel, sub, (cx - ts4[0] // 2, y1 + box_h - 15),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1,
        )

    def _draw_section_header(
        self, panel: np.ndarray, title: str, x: int, y: int,
    ) -> None:
        """Section header with a thin accent line."""
        cv2.putText(
            panel, title, (x, y),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, COLOR_TEXT, 1,
        )
        ts = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
        cv2.line(
            panel, (x + ts[0] + 6, y - 4), (x + 280, y - 4),
            COLOR_SECTION_ACCENT, 1,
        )

    def _draw_bar(
        self, panel: np.ndarray, label: str, value: float,
        x: int, y: int, label_w: int, bar_w: int, bar_h: int,
    ) -> None:
        short_label = label.replace("_", " ")[:16]
        cv2.putText(
            panel, short_label, (x, y + bar_h - 3),
            cv2.FONT_HERSHEY_SIMPLEX, 0.3, (200, 200, 200), 1,
        )

        bx = x + label_w
        # Background bar with rounded ends
        r = bar_h // 2
        rounded_rect(panel, (bx, y), (bx + bar_w, y + bar_h), (50, 50, 55), radius=r, thickness=-1)

        fill_w = int(bar_w * value)
        # Gradient color: green → yellow → red
        if value > 0.6:
            color = (80, 200, 80)    # green
        elif value > 0.3:
            color = (60, 200, 200)   # yellow
        else:
            color = (70, 80, 200)    # red

        if fill_w > r * 2:
            rounded_rect(panel, (bx, y), (bx + fill_w, y + bar_h), color, radius=r, thickness=-1)
        elif fill_w > 0:
            cv2.rectangle(panel, (bx, y), (bx + fill_w, y + bar_h), color, -1)

        cv2.putText(
            panel, f"{value:.2f}", (bx + bar_w + 5, y + bar_h - 3),
            cv2.FONT_HERSHEY_SIMPLEX, 0.28, (180, 180, 180), 1,
        )
