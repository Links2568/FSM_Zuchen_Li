import os
from typing import Dict, List, Optional

from fsm.states import STATE_ORDER


def generate_report(
    state_history: List[Dict],
    score: Optional[Dict] = None,
    output_dir: str = "outputs",
) -> str:
    """Generate a text assessment report for the hand washing session."""
    os.makedirs(output_dir, exist_ok=True)

    lines = ["=" * 50]
    lines.append("  HAND WASHING ASSESSMENT REPORT")
    lines.append("=" * 50)
    lines.append("")

    if not state_history:
        lines.append("No session data recorded.")
        filepath = os.path.join(output_dir, "report.txt")
        with open(filepath, "w") as f:
            f.write("\n".join(lines))
        return filepath

    t0 = state_history[0]["enter_time"]

    # Session summary
    last = state_history[-1]
    total_time = (last.get("exit_time") or last["enter_time"]) - t0
    lines.append(f"Total session time: {total_time:.1f}s")
    lines.append(f"States visited: {len(state_history)}")
    completed = last["state"] == "DONE"
    lines.append(f"Completed: {'Yes' if completed else 'No'}")
    lines.append("")

    # State breakdown
    lines.append("-" * 50)
    lines.append("  STATE BREAKDOWN")
    lines.append("-" * 50)
    for entry in state_history:
        state = entry["state"]
        start = entry["enter_time"] - t0
        end = (entry["exit_time"] or last["enter_time"]) - t0
        duration = end - start
        lines.append(f"  {state:<16} {start:6.1f}s - {end:6.1f}s  ({duration:.1f}s)")
    lines.append("")

    # Score
    if score:
        lines.append("-" * 50)
        lines.append("  SCORE")
        lines.append("-" * 50)
        for state_name, detail in score["details"].items():
            status = "PASS" if detail["completed"] else "MISS"
            lines.append(
                f"  {state_name:<16} {detail['points']:3d}/{detail['max_points']:3d}  [{status}]"
            )
        lines.append("")
        lines.append(f"  TOTAL: {score['total']}/{score['max_total']}")
    lines.append("")
    lines.append("=" * 50)

    report_text = "\n".join(lines)

    filepath = os.path.join(output_dir, "report.txt")
    with open(filepath, "w") as f:
        f.write(report_text)

    print(report_text)
    return filepath
