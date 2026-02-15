import queue
import threading
import time


class TTSFeedback:
    """Non-blocking TTS using pyttsx3 in a daemon thread with cooldown."""

    def __init__(self, cooldown: float = 5.0) -> None:
        self.cooldown = cooldown
        self.last_message: str = ""
        self._last_speak_time: float = 0
        self._queue: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _worker(self) -> None:
        """Background thread that processes TTS messages."""
        import pyttsx3

        engine = pyttsx3.init()
        engine.setProperty("rate", 160)

        while True:
            msg = self._queue.get()
            if msg is None:
                break
            try:
                engine.say(msg)
                engine.runAndWait()
            except Exception:
                pass

    def speak(self, message: str) -> None:
        """Queue a message for TTS if cooldown has elapsed."""
        now = time.time()
        if now - self._last_speak_time < self.cooldown:
            return
        self._last_speak_time = now
        self.last_message = message
        self._queue.put(message)

    def speak_now(self, message: str) -> None:
        """Queue a message immediately, bypassing cooldown.

        Used for transition messages that should always play.
        """
        self._last_speak_time = time.time()
        self.last_message = message
        self._queue.put(message)

    def speak_transition(self, from_state: str, to_state: str, messages: dict) -> None:
        """Speak the transition message if one is defined (bypasses cooldown)."""
        msg = messages.get((from_state, to_state))
        if msg:
            self.speak_now(msg)

    def speak_warning(self, message: str) -> None:
        """Speak a warning/guidance message with cooldown."""
        self.speak(message)

    def shutdown(self) -> None:
        """Signal the worker to stop."""
        self._queue.put(None)
