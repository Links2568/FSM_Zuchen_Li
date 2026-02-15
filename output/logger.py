import json
import os
import time
from typing import Dict, List


class StateLogger:
    """Logs state transitions and cues to a JSON file."""

    def __init__(self, output_dir: str = "outputs") -> None:
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.session_id = f"session_{int(time.time())}"
        self.events: List[Dict] = []

    def log_transition(self, from_state: str, to_state: str, cues: Dict[str, float]) -> None:
        """Log a state transition event."""
        self.events.append({
            "type": "transition",
            "timestamp": time.time(),
            "from_state": from_state,
            "to_state": to_state,
            "cues": cues,
        })

    def log_cues(self, state: str, cues: Dict[str, float]) -> None:
        """Log a periodic cue snapshot."""
        self.events.append({
            "type": "cues",
            "timestamp": time.time(),
            "state": state,
            "cues": cues,
        })

    def save(self, state_history: List[Dict]) -> str:
        """Save the full session log to a JSON file."""
        filepath = os.path.join(self.output_dir, f"{self.session_id}.json")
        data = {
            "session_id": self.session_id,
            "state_history": state_history,
            "events": self.events,
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        return filepath
