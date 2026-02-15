from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from config import (
    COLOR_ACTIVE,
    COLOR_ARROW,
    COLOR_ARROW_TAKEN,
    COLOR_COMPLETED,
    COLOR_GLOW,
    COLOR_PENDING,
    COLOR_TEXT,
    GUI_BG_COLOR,
)
from fsm.states import STATE_LAYOUT, STATES
from gui.drawing import rounded_rect

# Pre-defined transition edges for drawing arrows (from_state, to_state)
_FORWARD_EDGES = [
    ("IDLE", "WATER_NO_HANDS"),
    ("IDLE", "HANDS_NO_WATER"),
    ("IDLE", "WASHING"),
    ("WATER_NO_HANDS", "WASHING"),
    ("HANDS_NO_WATER", "WASHING"),
    ("WASHING", "SOAPING"),
    ("SOAPING", "RINSING"),
    ("RINSING", "TOWEL_DRYING"),
    ("RINSING", "CLOTHES_DRYING"),
    ("RINSING", "BLOWER_DRYING"),
    ("TOWEL_DRYING", "DONE"),
    ("CLOTHES_DRYING", "DONE"),
    ("BLOWER_DRYING", "DONE"),
]


class FSMPanel:
    """Right panel: live FSM flowchart with 8-layer multi-column layout."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height

        # Box sizing
        self.box_w = 120
        self.box_h = 32
        self.corner_r = 10  # corner radius for rounded boxes
        self.active_extra = 8  # active box is slightly larger

        # Vertical layout: 7 layers
        n_layers = len(STATE_LAYOUT)
        self.title_h = 55   # room for title + progress bar
        self.footer_h = 80  # room for guidance + score
        usable = height - self.title_h - self.footer_h
        self.layer_spacing = usable // (n_layers + 1)
        self.start_y = self.title_h + self.layer_spacing

        # Pre-compute center positions for every state: state_name -> (cx, cy)
        self._positions: Dict[str, Tuple[int, int]] = {}
        for layer_idx, layer in enumerate(STATE_LAYOUT):
            cy = self.start_y + layer_idx * self.layer_spacing
            n = len(layer)
            for col_idx, state_name in enumerate(layer):
                cx = int(width * (col_idx + 1) / (n + 1))
                self._positions[state_name] = (cx, cy)

        # Total states (excluding DONE for progress)
        self._total_states = len(self._positions) - 1  # DONE doesn't count

    def render(
        self,
        current_state: str,
        state_history: List[Dict],
        time_in_state: float,
        score: Optional[Dict] = None,
    ) -> np.ndarray:
        panel = np.full((self.height, self.width, 3), GUI_BG_COLOR, dtype=np.uint8)

        # Title
        title = "FSM Flowchart"
        ts = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)[0]
        cv2.putText(
            panel, title, (self.width // 2 - ts[0] // 2, 22),
            cv2.FONT_HERSHEY_SIMPLEX, 0.65, COLOR_TEXT, 2,
        )

        visited = {entry["state"] for entry in state_history}

        # --- Progress bar ---
        self._draw_progress_bar(panel, visited)

        # --- Arrows (behind boxes) ---
        taken_edges = self._compute_taken_edges(state_history)
        for src, dst in _FORWARD_EDGES:
            if src in self._positions and dst in self._positions:
                sx, sy = self._positions[src]
                dx, dy = self._positions[dst]
                p1 = (sx, sy + self.box_h // 2 + 2)
                p2 = (dx, dy - self.box_h // 2 - 2)
                is_taken = (src, dst) in taken_edges
                color = COLOR_ARROW_TAKEN if is_taken else COLOR_ARROW
                thick = 2 if is_taken else 1
                cv2.arrowedLine(panel, p1, p2, color, thick, tipLength=0.12)

        # --- State boxes ---
        for state_name, (cx, cy) in self._positions.items():
            is_active = state_name == current_state
            is_completed = state_name in visited and not is_active

            if is_active:
                self._draw_active_box(panel, state_name, cx, cy, time_in_state)
            elif is_completed:
                self._draw_completed_box(panel, state_name, cx, cy)
            else:
                self._draw_pending_box(panel, state_name, cx, cy)

        # --- Guidance text ---
        guidance_y = self.height - self.footer_h + 15
        state_def = STATES.get(current_state)
        if state_def:
            guidance = state_def.guidance_message
            gts = cv2.getTextSize(guidance, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
            gx = max(10, self.width // 2 - gts[0] // 2)
            cv2.putText(
                panel, guidance, (gx, guidance_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, COLOR_ACTIVE, 1,
            )

        # --- Score display ---
        score_y = self.height - 15
        if score is not None:
            self._draw_score_badge(panel, score, score_y)
        elif current_state != "DONE":
            text = "Score: -- (in progress)"
            sts = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0]
            cv2.putText(
                panel, text, (self.width // 2 - sts[0] // 2, score_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 150, 150), 1,
            )

        return panel

    # ── Progress bar ──

    def _draw_progress_bar(self, panel: np.ndarray, visited: set) -> None:
        # Count visited (excluding DONE)
        n_visited = len(visited - {"DONE"})
        ratio = min(n_visited / max(self._total_states, 1), 1.0)

        bar_w = self.width - 60
        bar_h = 10
        bar_x = 30
        bar_y = 36
        r = bar_h // 2

        # Background
        rounded_rect(panel, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (60, 55, 50), radius=r, thickness=-1)

        # Fill
        fill_w = int(bar_w * ratio)
        if fill_w > r * 2:
            rounded_rect(panel, (bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h), COLOR_ACTIVE, radius=r, thickness=-1)
        elif fill_w > 0:
            cv2.rectangle(panel, (bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h), COLOR_ACTIVE, -1)

        # Percentage label
        pct_text = f"{int(ratio * 100)}%"
        cv2.putText(
            panel, pct_text, (bar_x + bar_w + 5, bar_y + bar_h - 1),
            cv2.FONT_HERSHEY_SIMPLEX, 0.32, COLOR_TEXT, 1,
        )

    # ── Edge history ──

    @staticmethod
    def _compute_taken_edges(state_history: List[Dict]) -> set:
        taken = set()
        for i in range(1, len(state_history)):
            prev = state_history[i - 1]["state"]
            curr = state_history[i]["state"]
            taken.add((prev, curr))
        return taken

    # ── Box drawing helpers ──

    def _draw_active_box(
        self, panel: np.ndarray, name: str, cx: int, cy: int, tis: float,
    ) -> None:
        e = self.active_extra
        bw, bh = self.box_w + e * 2, self.box_h + e * 2
        x1, y1 = cx - bw // 2, cy - bh // 2

        # Glow effect: larger semi-transparent rounded rect behind
        glow_pad = 5
        glow_layer = panel.copy()
        rounded_rect(
            glow_layer,
            (x1 - glow_pad, y1 - glow_pad),
            (x1 + bw + glow_pad, y1 + bh + glow_pad),
            COLOR_GLOW,
            radius=self.corner_r + glow_pad,
            thickness=-1,
        )
        cv2.addWeighted(glow_layer, 0.25, panel, 0.75, 0, panel)

        # Box fill
        rounded_rect(panel, (x1, y1), (x1 + bw, y1 + bh), (30, 55, 30), radius=self.corner_r, thickness=-1)
        # Box border
        rounded_rect(panel, (x1, y1), (x1 + bw, y1 + bh), COLOR_ACTIVE, radius=self.corner_r, thickness=2)

        label = self._short_label(name)
        ts = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0]
        cv2.putText(
            panel, label, (cx - ts[0] // 2, cy - 2),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOR_ACTIVE, 1,
        )
        time_txt = f"{tis:.1f}s"
        ts2 = cv2.getTextSize(time_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)[0]
        cv2.putText(
            panel, time_txt, (cx - ts2[0] // 2, cy + 14),
            cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLOR_TEXT, 1,
        )

    def _draw_completed_box(self, panel: np.ndarray, name: str, cx: int, cy: int) -> None:
        bw, bh = self.box_w, self.box_h
        x1, y1 = cx - bw // 2, cy - bh // 2

        # Solid fill
        rounded_rect(panel, (x1, y1), (x1 + bw, y1 + bh), COLOR_COMPLETED, radius=self.corner_r, thickness=-1)
        # Subtle border
        rounded_rect(panel, (x1, y1), (x1 + bw, y1 + bh), (80, 200, 50), radius=self.corner_r, thickness=1)

        # Label with checkmark
        label = self._short_label(name)
        check_label = f"{label} \u2713"
        ts = cv2.getTextSize(check_label, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)[0]
        cv2.putText(
            panel, check_label, (cx - ts[0] // 2, cy + ts[1] // 2),
            cv2.FONT_HERSHEY_SIMPLEX, 0.42, COLOR_TEXT, 1,
        )

    def _draw_pending_box(self, panel: np.ndarray, name: str, cx: int, cy: int) -> None:
        bw, bh = self.box_w, self.box_h
        x1, y1 = cx - bw // 2, cy - bh // 2

        rounded_rect(panel, (x1, y1), (x1 + bw, y1 + bh), COLOR_PENDING, radius=self.corner_r, thickness=1)

        label = self._short_label(name)
        ts = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)[0]
        cv2.putText(
            panel, label, (cx - ts[0] // 2, cy + ts[1] // 2),
            cv2.FONT_HERSHEY_SIMPLEX, 0.42, COLOR_PENDING, 1,
        )

    # ── Score badge ──

    def _draw_score_badge(self, panel: np.ndarray, score: Dict, y: int) -> None:
        text = f"Score: {score['total']}/{score['max_total']}"
        ts = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        badge_w = ts[0] + 24
        badge_h = ts[1] + 16
        bx = self.width // 2 - badge_w // 2
        by = y - badge_h + 2

        # Colored badge background
        ratio = score["total"] / max(score["max_total"], 1)
        if ratio >= 0.8:
            bg = (60, 160, 60)    # green
        elif ratio >= 0.5:
            bg = (40, 160, 200)   # yellow-ish
        else:
            bg = (60, 80, 180)    # red-ish
        rounded_rect(panel, (bx, by), (bx + badge_w, by + badge_h), bg, radius=8, thickness=-1)
        cv2.putText(
            panel, text, (bx + 12, by + badge_h - 8),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2,
        )

    @staticmethod
    def _short_label(name: str) -> str:
        """Friendly short label for display."""
        labels = {
            "IDLE": "IDLE",
            "WATER_NO_HANDS": "WATER ONLY",
            "HANDS_NO_WATER": "HANDS ONLY",
            "WASHING": "WASHING",
            "SOAPING": "SOAPING",
            "RINSING": "RINSING",
            "TOWEL_DRYING": "TOWEL",
            "CLOTHES_DRYING": "CLOTHES",
            "BLOWER_DRYING": "BLOWER",
            "DONE": "DONE",
        }
        return labels.get(name, name)
