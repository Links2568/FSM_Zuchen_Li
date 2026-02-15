import json
import logging
import re
import time
from typing import Dict, Optional

import httpx
import openai

from config import VLM_MAX_TOKENS, VLM_TIMEOUT, VLM_PROMPT
from sensing.base import SensingProvider

log = logging.getLogger(__name__)

# All visual cue keys the VLM should return
VISUAL_CUE_KEYS = [
    "hands_visible",
    "hands_under_water",
    "hands_on_soap",
    "foam_visible",
    "towel_drying",
    "hands_touch_clothes",
    "blower_visible",
]


def _parse_vlm_response(text: str) -> Dict[str, float]:
    """Parse JSON from VLM response, handling markdown wrapping and preamble."""
    # Try to extract JSON from markdown code block
    md_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if md_match:
        text = md_match.group(1)
    else:
        # Try to find raw JSON object
        json_match = re.search(r"\{[^{}]*\}", text)
        if json_match:
            text = json_match.group(0)

    data = json.loads(text)
    cues = {}
    for key in VISUAL_CUE_KEYS:
        val = data.get(key, 0.5)
        cues[key] = max(0.0, min(1.0, float(val)))
    return cues


def _fallback_cues() -> Dict[str, float]:
    """Return neutral cues when VLM response cannot be parsed."""
    return {key: 0.5 for key in VISUAL_CUE_KEYS}


def _zero_cues() -> Dict[str, float]:
    """Return zero cues (used for initial state before VLM responds)."""
    return {key: 0.0 for key in VISUAL_CUE_KEYS}


# Backoff: after a connection failure, skip this provider for this many seconds
_BACKOFF_SECONDS = 10.0


class VLMProvider(SensingProvider):
    """Qwen3-VL provider that communicates with a vLLM instance via OpenAI API."""

    def __init__(self, name: str, base_url: str):
        self.name = name
        self.base_url = base_url
        self._client: Optional[openai.AsyncOpenAI] = None
        self._model_name: Optional[str] = None
        self._model_resolved = False
        self._fail_until: float = 0.0

    @property
    def client(self) -> openai.AsyncOpenAI:
        """Lazy-create the async client so it binds to the current event loop."""
        if self._client is None:
            self._client = openai.AsyncOpenAI(
                base_url=self.base_url,
                api_key="dummy",
                max_retries=0,
                timeout=httpx.Timeout(VLM_TIMEOUT, connect=5.0),
            )
        return self._client

    def reset_client(self) -> None:
        """Drop the current client so the next call creates a fresh one."""
        self._client = None

    @property
    def is_backed_off(self) -> bool:
        return time.monotonic() < self._fail_until

    def _enter_backoff(self) -> None:
        self._fail_until = time.monotonic() + _BACKOFF_SECONDS

    async def _resolve_model_name(self) -> str:
        """Query /v1/models to get the actual model name served by vLLM."""
        if self._model_resolved:
            return self._model_name  # type: ignore[return-value]
        try:
            models = await self.client.models.list()
            if models.data:
                self._model_name = models.data[0].id
                self._model_resolved = True
                log.info(f"[{self.name}] Resolved model name: {self._model_name}")
                return self._model_name
        except Exception as e:
            log.warning(f"[{self.name}] Could not resolve model name: {e}")
        from config import VLM_MODEL_NAME
        self._model_name = VLM_MODEL_NAME
        self._model_resolved = True
        return self._model_name

    async def health_check(self) -> bool:
        """Check if the VLM endpoint is reachable and serving a model."""
        try:
            models = await self.client.models.list()
            if models.data:
                self._model_name = models.data[0].id
                self._model_resolved = True
                log.info(f"[{self.name}] Health check OK — model: {self._model_name}")
                return True
            log.warning(f"[{self.name}] Health check: no models served")
            return False
        except Exception as e:
            log.error(f"[{self.name}] Health check FAILED: {e}")
            self._enter_backoff()
            return False

    async def get_cues(
        self, frame_b64: str | None, audio_chunk: bytes | None
    ) -> Dict[str, float]:
        if frame_b64 is None:
            return _zero_cues()
        if self.is_backed_off:
            return _fallback_cues()

        model_name = await self._resolve_model_name()
        try:
            response = await self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{frame_b64}"
                                },
                            },
                            {"type": "text", "text": VLM_PROMPT},
                        ],
                    }
                ],
                max_tokens=VLM_MAX_TOKENS,
            )
            text = response.choices[0].message.content or ""
            cues = _parse_vlm_response(text)
            log.debug(f"[{self.name}] Cues: {cues}")
            return cues
        except json.JSONDecodeError as e:
            log.warning(f"[{self.name}] JSON parse error: {e}")
            return _fallback_cues()
        except openai.APITimeoutError as e:
            log.error(f"[{self.name}] Request timed out, backing off {_BACKOFF_SECONDS}s: {e}")
            self._enter_backoff()
            return _fallback_cues()
        except openai.APIConnectionError as e:
            log.error(f"[{self.name}] Connection failed, backing off {_BACKOFF_SECONDS}s: {e}")
            self._enter_backoff()
            return _fallback_cues()
        except Exception as e:
            log.error(f"[{self.name}] VLM call failed: {type(e).__name__}: {e}")
            return _fallback_cues()
