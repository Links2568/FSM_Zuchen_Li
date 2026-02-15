import os
from typing import Dict, List

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from fsm.states import STATE_ORDER


# Colors for each state
STATE_COLORS = {
    "IDLE": "#808080",
    "WATER_NO_HANDS": "#4FC3F7",
    "HANDS_NO_WATER": "#CE93D8",
    "WASHING": "#64B5F6",
    "SOAPING": "#FFB74D",
    "RINSING": "#81C784",
    "TOWEL_DRYING": "#FFD54F",
    "CLOTHES_DRYING": "#FF8A65",
    "BLOWER_DRYING": "#90CAF9",
    "DONE": "#4CAF50",
}


def generate_timeline(
    state_history: List[Dict], output_dir: str = "outputs"
) -> str:
    """Generate a timeline visualization of the hand washing session."""
    os.makedirs(output_dir, exist_ok=True)

    if not state_history:
        return ""

    # Use the first entry's enter_time as t=0
    t0 = state_history[0]["enter_time"]

    fig, ax = plt.subplots(figsize=(12, 3))

    for entry in state_history:
        state = entry["state"]
        start = entry["enter_time"] - t0
        end = (entry["exit_time"] or state_history[-1].get("enter_time", entry["enter_time"])) - t0
        duration = max(end - start, 0.1)

        color = STATE_COLORS.get(state, "#808080")
        y_idx = STATE_ORDER.index(state) if state in STATE_ORDER else 0

        ax.barh(
            y_idx, duration, left=start, height=0.6,
            color=color, edgecolor="white", linewidth=0.5,
        )
        if duration > 1.5:
            ax.text(
                start + duration / 2, y_idx, f"{duration:.1f}s",
                ha="center", va="center", fontsize=8, color="black",
            )

    ax.set_yticks(range(len(STATE_ORDER)))
    ax.set_yticklabels(STATE_ORDER)
    ax.set_xlabel("Time (seconds)")
    ax.set_title("Hand Washing Session Timeline")
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.3)

    plt.tight_layout()
    filepath = os.path.join(output_dir, "timeline.png")
    plt.savefig(filepath, dpi=150)
    plt.close()
    return filepath
