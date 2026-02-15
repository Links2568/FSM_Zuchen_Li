"""Unit tests for the FSM engine with 10-state hand washing model."""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fsm.engine import FSMEngine


def test_initial_state():
    fsm = FSMEngine()
    assert fsm.current_state == "IDLE"


def test_idle_to_water_no_hands():
    """Water for >3s without hands → WATER_NO_HANDS."""
    fsm = FSMEngine()
    cues = {"hands_visible": 0.1, "water_sound": 0.7}
    # First call: starts the sustained timer
    assert fsm.update(cues) is None
    # Pretend 4 seconds have passed
    fsm._condition_since["water_no_hands"] = time.time() - 4
    result = fsm.update(cues)
    assert result == ("IDLE", "WATER_NO_HANDS")


def test_idle_to_hands_no_water():
    """Hands for >3s without water → HANDS_NO_WATER."""
    fsm = FSMEngine()
    cues = {"hands_visible": 0.8, "water_sound": 0.1}
    fsm.update(cues)
    fsm._condition_since["hands_no_water"] = time.time() - 4
    result = fsm.update(cues)
    assert result == ("IDLE", "HANDS_NO_WATER")


def test_idle_to_washing():
    """Hands under water + water sound for >1.3s → WASHING."""
    fsm = FSMEngine()
    cues = {"hands_under_water": 0.8, "water_sound": 0.7}
    fsm.update(cues)
    fsm._condition_since["hands_and_water"] = time.time() - 3
    result = fsm.update(cues)
    assert result == ("IDLE", "WASHING")


def test_water_no_hands_to_washing():
    """From WATER_NO_HANDS, hands appear + water → WASHING."""
    fsm = FSMEngine()
    # Get to WATER_NO_HANDS
    cues_water = {"hands_visible": 0.1, "water_sound": 0.7}
    fsm.update(cues_water)
    fsm._condition_since["water_no_hands"] = time.time() - 4
    fsm.update(cues_water)
    assert fsm.current_state == "WATER_NO_HANDS"

    # Now hands appear under water
    cues_both = {"hands_under_water": 0.8, "water_sound": 0.7}
    fsm.update(cues_both)
    fsm._condition_since["hands_and_water"] = time.time() - 3
    result = fsm.update(cues_both)
    assert result == ("WATER_NO_HANDS", "WASHING")


def test_washing_to_soaping():
    """Soap detected → SOAPING (immediate)."""
    fsm = FSMEngine()
    # Skip to WASHING
    fsm._transition_to("WASHING")
    cues = {"hands_on_soap": 0.7, "hands_visible": 0.8}
    result = fsm.update(cues)
    assert result == ("WASHING", "SOAPING")


def test_soaping_to_rinsing():
    """Hands under water for >2s → RINSING."""
    fsm = FSMEngine()
    fsm._transition_to("SOAPING")
    cues = {"hands_under_water": 0.7, "water_sound": 0.7}
    fsm.update(cues)
    fsm._condition_since["rinsing_entry"] = time.time() - 3
    result = fsm.update(cues)
    assert result == ("SOAPING", "RINSING")


def test_rinsing_to_towel():
    """Towel for >2s → TOWEL_DRYING."""
    fsm = FSMEngine()
    fsm._transition_to("RINSING")
    cues = {"towel_drying": 0.7, "hands_visible": 0.8}
    fsm.update(cues)
    fsm._condition_since["towel_entry"] = time.time() - 3
    result = fsm.update(cues)
    assert result == ("RINSING", "TOWEL_DRYING")


def test_rinsing_to_blower():
    """Blower detected → BLOWER_DRYING (immediate)."""
    fsm = FSMEngine()
    fsm._transition_to("RINSING")
    cues = {"blower_sound": 0.7, "hands_visible": 0.8}
    result = fsm.update(cues)
    assert result == ("RINSING", "BLOWER_DRYING")


def test_towel_to_done():
    """Towel drying for >3s then stopped → DONE."""
    fsm = FSMEngine()
    fsm._transition_to("TOWEL_DRYING")
    fsm.time_entered = time.time() - 4
    cues = {"towel_drying": 0.1, "hands_visible": 0.8}
    result = fsm.update(cues)
    assert result == ("TOWEL_DRYING", "DONE")


def test_idle_timeout():
    """Any state (except DONE) → IDLE after 5s inactivity."""
    fsm = FSMEngine()
    fsm._transition_to("WASHING")
    # No activity for 6 seconds
    fsm._last_activity_time = time.time() - 6
    cues = {"hands_visible": 0.1, "water_sound": 0.1}
    result = fsm.update(cues)
    assert result == ("WASHING", "IDLE")


def test_done_no_idle_timeout():
    """DONE should NOT timeout to IDLE."""
    fsm = FSMEngine()
    fsm._transition_to("DONE")
    fsm._last_activity_time = time.time() - 100
    cues = {}
    result = fsm.update(cues)
    assert result is None
    assert fsm.current_state == "DONE"


def test_no_transition_on_zero_cues():
    fsm = FSMEngine()
    result = fsm.update({k: 0.0 for k in [
        "hands_visible", "water_sound",
        "hands_under_water", "hands_on_soap",
    ]})
    assert result is None
    assert fsm.current_state == "IDLE"


def test_no_transition_on_fallback_cues():
    """Fallback 0.5 cues should not trigger any transition."""
    fsm = FSMEngine()
    fallback = {k: 0.5 for k in [
        "hands_visible", "water_sound",
        "hands_under_water", "hands_on_soap", "foam_visible",
        "towel_drying",
        "hands_touch_clothes", "blower_visible", "blower_sound",
    ]}
    for _ in range(10):
        result = fsm.update(fallback)
        assert result is None
    assert fsm.current_state == "IDLE"


def test_reset():
    fsm = FSMEngine()
    fsm._transition_to("WASHING")
    fsm.reset()
    assert fsm.current_state == "IDLE"
    assert len(fsm.state_history) == 1
    assert len(fsm._condition_since) == 0


def test_score():
    fsm = FSMEngine()
    assert fsm.get_score() is None
    # Walk through to DONE
    fsm._transition_to("WASHING")
    fsm._transition_to("SOAPING")
    fsm._transition_to("RINSING")
    fsm._transition_to("TOWEL_DRYING")
    fsm._transition_to("DONE")
    score = fsm.get_score()
    assert score is not None
    assert score["total"] > 0
    assert score["max_total"] == 100


if __name__ == "__main__":
    test_initial_state()
    test_idle_to_water_no_hands()
    test_idle_to_hands_no_water()
    test_idle_to_washing()
    test_water_no_hands_to_washing()
    test_washing_to_soaping()
    test_soaping_to_rinsing()
    test_rinsing_to_towel()
    test_rinsing_to_blower()
    test_towel_to_done()
    test_idle_timeout()
    test_done_no_idle_timeout()
    test_no_transition_on_zero_cues()
    test_no_transition_on_fallback_cues()
    test_reset()
    test_score()
    print("All FSM tests passed!")
