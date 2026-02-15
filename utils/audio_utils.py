import threading
import numpy as np

from config import AUDIO_SAMPLE_RATE, AUDIO_CHUNK_DURATION


class AudioCapture:
    """Captures audio from the microphone in a background thread using sounddevice."""

    def __init__(
        self,
        sample_rate: int = AUDIO_SAMPLE_RATE,
        chunk_duration: float = AUDIO_CHUNK_DURATION,
    ):
        self.sample_rate = sample_rate
        self.chunk_duration = chunk_duration
        self.chunk_samples = int(sample_rate * chunk_duration)
        self._buffer = np.zeros(self.chunk_samples, dtype=np.float32)
        self._lock = threading.Lock()
        self._stream = None

    def start(self) -> None:
        """Start the audio input stream."""
        import sounddevice as sd

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=1024,
            callback=self._audio_callback,
        )
        self._stream.start()

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        """Called by sounddevice for each audio block."""
        mono = indata[:, 0]
        with self._lock:
            # Shift buffer left and append new data
            shift = len(mono)
            if shift >= len(self._buffer):
                self._buffer[:] = mono[-len(self._buffer) :]
            else:
                self._buffer[:-shift] = self._buffer[shift:]
                self._buffer[-shift:] = mono

    def get_chunk(self) -> np.ndarray:
        """Return a copy of the current audio buffer (16kHz mono float32)."""
        with self._lock:
            return self._buffer.copy()

    def stop(self) -> None:
        """Stop the audio stream."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
