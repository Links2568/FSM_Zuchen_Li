from abc import ABC, abstractmethod
from typing import Dict


class SensingProvider(ABC):
    """Abstract interface for all sensing providers (VLM, audio, etc.)."""

    @abstractmethod
    async def get_cues(
        self, frame_b64: str | None, audio_chunk: bytes | None
    ) -> Dict[str, float]:
        """Return a dict of cue_name -> confidence (0.0 to 1.0)."""
        pass
