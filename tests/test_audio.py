"""Tests for audio provider (basic structure tests, no hardware needed)."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sensing.audio_provider import AUDIO_CUE_MAPPING, AUDIO_CUE_KEYS, AudioProvider


def test_cue_mapping_keys():
    """Audio cue mapping should have expected keys."""
    expected = {"water_sound", "blower_sound"}
    assert set(AUDIO_CUE_KEYS) == expected


def test_audio_provider_no_chunk():
    """AudioProvider should return zeros when no audio chunk is provided."""
    import asyncio

    provider = AudioProvider()
    cues = asyncio.run(provider.get_cues(None, None))
    assert all(v == 0.0 for v in cues.values())
    assert len(cues) == len(AUDIO_CUE_KEYS)


def test_cue_mapping_has_class_names():
    """Each audio cue should map to at least one YAMNet class name."""
    for key, names in AUDIO_CUE_MAPPING.items():
        assert len(names) > 0, f"{key} has no class name mappings"


if __name__ == "__main__":
    test_cue_mapping_keys()
    test_audio_provider_no_chunk()
    test_cue_mapping_has_class_names()
    print("All audio tests passed!")
