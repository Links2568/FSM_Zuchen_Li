import asyncio
import logging
from typing import Dict, List

from sensing.vlm_provider import VLMProvider, _fallback_cues

log = logging.getLogger(__name__)


class VLMPool:
    """
    Round-robin dispatcher across multiple vLLM instances.
    With 3 GPUs at ~1.1s per call, achieves ~0.37s effective interval.

    Each provider is limited to 1 in-flight request at a time.
    If a provider's previous request hasn't completed, it is skipped.
    """

    def __init__(self, providers: List[VLMProvider], mode: str = "round_robin"):
        self.providers = providers
        self.mode = mode
        self.next_idx = 0
        # At most one pending task per provider (keyed by provider index)
        self._provider_task: Dict[int, asyncio.Task] = {}

    async def health_check(self) -> Dict[str, bool]:
        """Check all providers and return {name: reachable} dict."""
        results = {}
        for provider in self.providers:
            ok = await provider.health_check()
            results[provider.name] = ok
        return results

    def _all_backed_off(self) -> bool:
        """True if every provider is in backoff (all endpoints down)."""
        return all(p.is_backed_off for p in self.providers)

    async def submit_frame(self, frame_b64: str) -> None:
        """Dispatch a frame to one or more VLM providers.

        Skips dispatch entirely if all providers are in backoff.
        Each provider can have at most one in-flight request.
        """
        if self._all_backed_off():
            return

        if self.mode == "round_robin":
            # Find the next provider that isn't backed off and isn't busy
            for _ in range(len(self.providers)):
                idx = self.next_idx
                self.next_idx = (self.next_idx + 1) % len(self.providers)
                provider = self.providers[idx]
                if provider.is_backed_off:
                    continue
                # Skip if this provider already has an in-flight request
                existing = self._provider_task.get(idx)
                if existing is not None and not existing.done():
                    continue
                task = asyncio.create_task(provider.get_cues(frame_b64, None))
                self._provider_task[idx] = task
                return
        elif self.mode == "ensemble":
            for idx, provider in enumerate(self.providers):
                if provider.is_backed_off:
                    continue
                existing = self._provider_task.get(idx)
                if existing is not None and not existing.done():
                    continue
                task = asyncio.create_task(provider.get_cues(frame_b64, None))
                self._provider_task[idx] = task

    async def collect_results(self) -> List[Dict[str, float]]:
        """Collect all completed VLM results (non-blocking)."""
        completed: List[Dict[str, float]] = []
        done_keys: List[int] = []
        for idx, task in self._provider_task.items():
            if task.done():
                try:
                    result = task.result()
                    completed.append(result)
                except Exception as e:
                    log.warning(f"VLM task exception: {e}")
                    completed.append(_fallback_cues())
                done_keys.append(idx)
        for key in done_keys:
            del self._provider_task[key]
        return completed
