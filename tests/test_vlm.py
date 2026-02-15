"""Tests for VLM provider JSON parsing."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sensing.vlm_provider import _parse_vlm_response, _fallback_cues, _zero_cues, VISUAL_CUE_KEYS


def test_parse_raw_json():
    """Parse raw JSON response."""
    text = '{"hands_visible":0.8,"hands_under_water":0.5,"hands_on_soap":0.0,"foam_visible":0.0,"hands_shaking":0.0}'
    cues = _parse_vlm_response(text)
    assert cues["hands_visible"] == 0.8
    assert cues["hands_under_water"] == 0.5
    assert len(cues) == len(VISUAL_CUE_KEYS)


def test_parse_markdown_wrapped():
    """Parse JSON wrapped in markdown code block."""
    text = '```json\n{"hands_visible":0.9,"hands_under_water":0.6,"hands_on_soap":0.0,"foam_visible":0.0,"hands_shaking":0.0}\n```'
    cues = _parse_vlm_response(text)
    assert cues["hands_visible"] == 0.9


def test_parse_with_preamble():
    """Parse JSON with preamble text."""
    text = 'Here is the analysis:\n{"hands_visible":0.5,"hands_under_water":0.2,"hands_on_soap":0.0,"foam_visible":0.0,"hands_shaking":0.0}'
    cues = _parse_vlm_response(text)
    assert cues["hands_visible"] == 0.5


def test_clamp_values():
    """Values should be clamped to [0, 1]."""
    text = '{"hands_visible":1.5,"hands_under_water":-0.2,"hands_on_soap":0.0,"foam_visible":0.0,"hands_shaking":0.0}'
    cues = _parse_vlm_response(text)
    assert cues["hands_visible"] == 1.0
    assert cues["hands_under_water"] == 0.0


def test_missing_keys_default():
    """Missing keys should default to 0.5."""
    text = '{"hands_visible":0.8}'
    cues = _parse_vlm_response(text)
    assert cues["hands_visible"] == 0.8
    assert cues["hands_on_soap"] == 0.5  # default


def test_fallback_cues():
    """Fallback cues should all be 0.5."""
    cues = _fallback_cues()
    assert all(v == 0.5 for v in cues.values())
    assert len(cues) == len(VISUAL_CUE_KEYS)


def test_zero_cues():
    """Zero cues should all be 0.0 (used for initial state)."""
    cues = _zero_cues()
    assert all(v == 0.0 for v in cues.values())
    assert len(cues) == len(VISUAL_CUE_KEYS)


if __name__ == "__main__":
    test_parse_raw_json()
    test_parse_markdown_wrapped()
    test_parse_with_preamble()
    test_clamp_values()
    test_missing_keys_default()
    test_fallback_cues()
    test_zero_cues()
    print("All VLM parsing tests passed!")
