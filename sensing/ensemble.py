from typing import Dict


class EnsembleMerger:
    """Merges visual and audio cues into a single cue dictionary.

    Future: support multi-VLM voting / weighted ensemble.
    """

    def merge(
        self, visual_cues: Dict[str, float], audio_cues: Dict[str, float]
    ) -> Dict[str, float]:
        """Combine visual and audio cues. Audio keys are kept separate."""
        return {**visual_cues, **audio_cues}
