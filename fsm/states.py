"""FSM state definitions for the hand washing assessment system.

10 states, 7 layers. Transition conditions use a `sustained` callback:
    sustained(name: str, condition: bool) -> float
Returns how many seconds the named condition has been continuously true.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

# Type alias: condition(cues, time_in_state, sustained_fn) -> bool
ConditionFn = Callable[[Dict[str, float], float, Any], bool]


@dataclass
class Transition:
    target: str
    condition: ConditionFn
    description: str = ""


@dataclass
class State:
    name: str
    description: str
    guidance_message: str
    transitions: List[Transition] = field(default_factory=list)
    # Cues that indicate the user is still "active" in this state.
    # If ALL of these drop below 0.3 for IDLE_TIMEOUT seconds → IDLE.
    # Each entry is a cue key name.
    activity_cues: List[str] = field(default_factory=list)


# ──────────────────── Layout ────────────────────
# 7 layers for the GUI flowchart.
# Each layer is a list of state names rendered side-by-side.
STATE_LAYOUT: List[List[str]] = [
    ["IDLE"],
    ["WATER_NO_HANDS", "HANDS_NO_WATER"],
    ["WASHING"],
    ["SOAPING"],
    ["RINSING"],
    ["TOWEL_DRYING", "CLOTHES_DRYING", "BLOWER_DRYING"],
    ["DONE"],
]

# Flat ordered list of all state names (top → bottom, left → right)
STATE_ORDER: List[str] = [s for layer in STATE_LAYOUT for s in layer]


# ──────────────────── Transition conditions ────────────────────
# sustained(name, cond) returns seconds the condition has been continuously True.

def _idle_to_water_no_hands(cues: dict, t: float, sustained) -> bool:
    """Water sound detected for >1.3s, no hands."""
    water = cues.get("water_sound", 0) > 0.5
    no_hands = cues.get("hands_visible", 0) < 0.4
    return sustained("water_no_hands", water and no_hands) >= 1.3


def _idle_to_hands_no_water(cues: dict, t: float, sustained) -> bool:
    """Hands visible for >1.3s, no water sound."""
    hands = cues.get("hands_visible", 0) > 0.5
    no_water = cues.get("water_sound", 0) < 0.4
    return sustained("hands_no_water", hands and no_water) >= 1.3


def _to_washing(cues: dict, t: float, sustained) -> bool:
    """Hands under water + water sound for >1.3s → WASHING."""
    under = cues.get("hands_under_water", 0) > 0.5
    water = cues.get("water_sound", 0) > 0.5
    return sustained("hands_and_water", under and water) >= 1.3



def _washing_to_soaping(cues: dict, t: float, sustained) -> bool:
    """Hands touching soap → SOAPING (immediate)."""
    return cues.get("hands_on_soap", 0) > 0.5


def _soaping_to_rinsing(cues: dict, t: float, sustained) -> bool:
    """Hands back under running water for >1.3s → RINSING."""
    under = cues.get("hands_under_water", 0) > 0.5
    water = cues.get("water_sound", 0) > 0.5
    return sustained("rinsing_entry", under and water) >= 1.3


def _rinsing_to_towel(cues: dict, t: float, sustained) -> bool:
    """Towel drying for >1.3s → TOWEL_DRYING."""
    return sustained("towel_entry", cues.get("towel_drying", 0) > 0.5) >= 1.3


def _rinsing_to_clothes(cues: dict, t: float, sustained) -> bool:
    """Clothes drying for >1.3s → CLOTHES_DRYING."""
    return sustained("clothes_entry", cues.get("hands_touch_clothes", 0) > 0.5) >= 1.3


def _rinsing_to_blower(cues: dict, t: float, sustained) -> bool:
    """Blower sound or visible → BLOWER_DRYING (low threshold, immediate)."""
    return cues.get("blower_sound", 0) > 0.3 or cues.get("blower_visible", 0) > 0.3


def _towel_to_done(cues: dict, t: float, sustained) -> bool:
    """Finished towel drying: in state >1.3s and action stopped."""
    return t >= 1.3 and cues.get("towel_drying", 0) < 0.3


def _clothes_to_done(cues: dict, t: float, sustained) -> bool:
    """Finished clothes drying: in state >1.3s and action stopped."""
    return t >= 1.3 and cues.get("hands_touch_clothes", 0) < 0.3


def _blower_to_done(cues: dict, t: float, sustained) -> bool:
    """Finished blower drying: in state >1.3s and blower off."""
    return (
        t >= 1.3
        and cues.get("blower_sound", 0) < 0.2
        and cues.get("blower_visible", 0) < 0.2
    )


# ──────────────────── State definitions ────────────────────

STATES: Dict[str, State] = {
    "IDLE": State(
        name="IDLE",
        description="Waiting for hand washing to begin",
        guidance_message="Please turn on the faucet and start washing your hands.",
        transitions=[
            # Check WASHING first (immediate if hands+water together >2s)
            Transition("WASHING", _to_washing, "Hands + water for >1.3s"),
            Transition("WATER_NO_HANDS", _idle_to_water_no_hands, "Water for >1.3s, no hands"),
            Transition("HANDS_NO_WATER", _idle_to_hands_no_water, "Hands for >1.3s, no water"),
        ],
        activity_cues=[],  # IDLE has no activity check (uses its own timeout)
    ),
    "WATER_NO_HANDS": State(
        name="WATER_NO_HANDS",
        description="Water running but no hands detected",
        guidance_message="Please put your hands under the water.",
        transitions=[
            Transition("WASHING", _to_washing, "Hands + water for >1.3s"),
        ],
        activity_cues=["water_sound"],
    ),
    "HANDS_NO_WATER": State(
        name="HANDS_NO_WATER",
        description="Hands visible but no water detected",
        guidance_message="Please turn on the faucet.",
        transitions=[
            Transition("WASHING", _to_washing, "Hands under water + water sound for >1.3s"),
        ],
        activity_cues=["hands_visible"],
    ),
    "WASHING": State(
        name="WASHING",
        description="Washing hands under running water",
        guidance_message="Good, washing your hands. Apply soap when ready.",
        transitions=[
            Transition("SOAPING", _washing_to_soaping, "Soap detected"),
        ],
        activity_cues=["hands_visible", "water_sound", "hands_under_water"],
    ),
    "SOAPING": State(
        name="SOAPING",
        description="Applying hand soap",
        guidance_message="Lather the soap well over all hand surfaces.",
        transitions=[
            Transition("RINSING", _soaping_to_rinsing, "Hands under water >1.3s"),
        ],
        activity_cues=["hands_visible", "hands_on_soap", "foam_visible"],
    ),
    "RINSING": State(
        name="RINSING",
        description="Rinsing hand soap off under water",
        guidance_message="Rinse all the soap off, then dry your hands.",
        transitions=[
            Transition("TOWEL_DRYING", _rinsing_to_towel, "Towel for >1.3s"),
            Transition("CLOTHES_DRYING", _rinsing_to_clothes, "Clothes for >1.3s"),
            Transition("BLOWER_DRYING", _rinsing_to_blower, "Blower detected"),
        ],
        activity_cues=["hands_under_water", "water_sound", "hands_visible"],
    ),
    "TOWEL_DRYING": State(
        name="TOWEL_DRYING",
        description="Drying hands with a towel",
        guidance_message="Dry your hands thoroughly with the towel.",
        transitions=[
            Transition("DONE", _towel_to_done, "Towel drying finished"),
        ],
        activity_cues=["towel_drying", "hands_visible"],
    ),
    "CLOTHES_DRYING": State(
        name="CLOTHES_DRYING",
        description="Drying hands on clothes",
        guidance_message="Using clothes to dry. A towel is recommended next time.",
        transitions=[
            Transition("DONE", _clothes_to_done, "Clothes drying finished"),
        ],
        activity_cues=["hands_touch_clothes", "hands_visible"],
    ),
    "BLOWER_DRYING": State(
        name="BLOWER_DRYING",
        description="Drying hands with a blower / dryer",
        guidance_message="Drying hands with the blower.",
        transitions=[
            Transition("DONE", _blower_to_done, "Blower drying finished"),
        ],
        activity_cues=["blower_visible", "blower_sound"],
    ),
    "DONE": State(
        name="DONE",
        description="Hand washing complete",
        guidance_message="All done! Great job washing your hands.",
        transitions=[],
        activity_cues=[],  # DONE never times out
    ),
}
