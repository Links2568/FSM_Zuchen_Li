from typing import Dict

import numpy as np

from sensing.base import SensingProvider

# YAMNet class names mapped to our audio cue keys
AUDIO_CUE_MAPPING = {
    "water_sound": [
        "Water tap, faucet", "Water", "Sink (filling or washing)", "Pour",
        "Stream", "Trickle, dribble",
    ],
    "blower_sound": [
        "Hair dryer", "Mechanical fan", "Air conditioning",
    ],
}

AUDIO_CUE_KEYS = list(AUDIO_CUE_MAPPING.keys())


class AudioProvider(SensingProvider):
    """YAMNet-based audio classifier running on CPU."""

    def __init__(self) -> None:
        self._model = None
        self._class_names: list[str] = []

    def _load_model(self) -> None:
        """Lazy-load YAMNet model from TensorFlow Hub."""
        if self._model is not None:
            return
        import tensorflow_hub as hub
        import csv

        self._model = hub.load("https://tfhub.dev/google/yamnet/1")

        class_map_path = self._model.class_map_path().numpy().decode("utf-8")
        with open(class_map_path) as f:
            reader = csv.DictReader(f)
            self._class_names = [row["display_name"] for row in reader]

    async def get_cues(
        self, frame_b64: str | None, audio_chunk: bytes | None
    ) -> Dict[str, float]:
        if audio_chunk is None:
            return {key: 0.0 for key in AUDIO_CUE_KEYS}
        self._load_model()
        return self._classify(audio_chunk)

    def classify_waveform(self, waveform: np.ndarray) -> Dict[str, float]:
        """Classify a 16kHz mono float32 waveform. Can be called directly."""
        self._load_model()
        return self._classify(waveform)

    def _classify(self, waveform: np.ndarray | bytes) -> Dict[str, float]:
        """Run YAMNet on waveform and map to our audio cues."""
        if isinstance(waveform, bytes):
            waveform = np.frombuffer(waveform, dtype=np.float32)

        waveform = waveform.astype(np.float32)
        if waveform.ndim > 1:
            waveform = waveform[:, 0]

        scores, embeddings, spectrogram = self._model(waveform)
        scores_np = scores.numpy()
        avg_scores = scores_np.mean(axis=0)

        cues: Dict[str, float] = {}
        for cue_key, class_names in AUDIO_CUE_MAPPING.items():
            max_score = 0.0
            for class_name in class_names:
                if class_name in self._class_names:
                    idx = self._class_names.index(class_name)
                    max_score = max(max_score, float(avg_scores[idx]))
            cues[cue_key] = min(1.0, max_score)

        return cues
