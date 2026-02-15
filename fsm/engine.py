import time
from collections import deque
from typing import Dict, List, Optional, Tuple

from config import CUE_BUFFER_SIZE, IDLE_TIMEOUT
from fsm.states import STATES, STATE_ORDER

# Threshold: if all activity cues are below this, the user is "idle"
_ACTIVITY_THRESHOLD = 0.3


class FSMEngine:
    """FSM engine with sustained-condition timers and idle timeout."""

    def __init__(self) -> None:
        self.current_state: str = "IDLE"
        self.time_entered: float = time.time()
        self.state_history: List[Dict] = [
            {"state": "IDLE", "enter_time": self.time_entered, "exit_time": None}
        ]
        self.cue_buffer: deque = deque(maxlen=CUE_BUFFER_SIZE)

        # Sustained condition tracking: name -> time when condition first became True
        self._condition_since: Dict[str, float] = {}

        # Idle timeout: time of last detected activity
        self._last_activity_time: float = time.time()

        # Adaptive guidance: Level of Detail increases on idle timeout regressions
        self.lod_level: int = 0

    # ── Properties ──

    @property
    def time_in_state(self) -> float:
        return time.time() - self.time_entered

    # ── Sustained condition helper ──

    def _check_sustained(self, name: str, condition: bool, now: float) -> float:
        """Return how many seconds *name* has been continuously True.

        Returns 0.0 if the condition is currently False.
        """
        if condition:
            if name not in self._condition_since:
                self._condition_since[name] = now
            return now - self._condition_since[name]
        else:
            self._condition_since.pop(name, None)
            return 0.0

    # ── Activity detection ──

    def _has_activity(self, cues: Dict[str, float]) -> bool:
        """Check if any activity cue for the current state is above threshold."""
        state_def = STATES.get(self.current_state)
        if state_def is None or not state_def.activity_cues:
            return True  # IDLE and DONE have no activity check

        return any(
            cues.get(key, 0) > _ACTIVITY_THRESHOLD
            for key in state_def.activity_cues
        )

    # ── Main update ──

    def update(self, cues: Dict[str, float]) -> Optional[Tuple[str, str]]:
        """Process new cues. Returns (from_state, to_state) on transition, else None."""
        now = time.time()
        self.cue_buffer.append(cues)

        # Build the sustained callback for this tick
        def sustained(name: str, condition: bool) -> float:
            return self._check_sustained(name, condition, now)

        # 1) Update activity timer
        if self._has_activity(cues):
            self._last_activity_time = now

        # 2) Check forward transitions
        state_def = STATES.get(self.current_state)
        if state_def is not None:
            t = self.time_in_state
            for transition in state_def.transitions:
                if transition.condition(cues, t, sustained):
                    return self._transition_to(transition.target)

        # 3) Idle timeout: if no activity for IDLE_TIMEOUT seconds → IDLE
        #    (only for non-IDLE, non-DONE states)
        if (
            self.current_state not in ("IDLE", "DONE")
            and (now - self._last_activity_time) >= IDLE_TIMEOUT
        ):
            # Increase guidance detail on idle regression
            self.lod_level = min(self.lod_level + 1, 2)
            return self._transition_to("IDLE")

        return None

    # ── Transition execution ──

    def _transition_to(self, new_state: str) -> Tuple[str, str]:
        now = time.time()
        old_state = self.current_state

        # Close current history entry
        if self.state_history:
            self.state_history[-1]["exit_time"] = now

        self.current_state = new_state
        self.time_entered = now
        self.state_history.append(
            {"state": new_state, "enter_time": now, "exit_time": None}
        )

        # Clear sustained timers and cue buffer on transition
        self._condition_since.clear()
        self.cue_buffer.clear()
        self._last_activity_time = now

        return (old_state, new_state)

    # ── Queries ──

    def get_visited_states(self) -> set:
        return {entry["state"] for entry in self.state_history}

    def get_score(self) -> Optional[Dict]:
        """Assessment score (available once DONE is reached)."""
        if self.current_state != "DONE":
            return None

        points_map = {
            "WASHING": 15,
            "SOAPING": 25,
            "RINSING": 8,
            "RINSING_OK": 6,
            "RINSING_THOROUGH": 6,
            "TOWEL_DRYING": 15,
            "CLOTHES_DRYING": 5,
            "BLOWER_DRYING": 10,
            "DONE": 10,
        }

        visited = self.get_visited_states()
        score: Dict = {"total": 0, "max_total": 100, "details": {}}

        for state_name, pts in points_map.items():
            completed = state_name in visited
            score["details"][state_name] = {
                "points": pts if completed else 0,
                "max_points": pts,
                "completed": completed,
            }
            if completed:
                score["total"] += pts

        return score

    def reset(self) -> None:
        self.current_state = "IDLE"
        self.time_entered = time.time()
        self.state_history = [
            {"state": "IDLE", "enter_time": self.time_entered, "exit_time": None}
        ]
        self.cue_buffer.clear()
        self._condition_since.clear()
        self._last_activity_time = time.time()
        self.lod_level = 0
