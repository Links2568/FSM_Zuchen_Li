import asyncio
import logging
from typing import Dict, List

from sensing.vlm_provider import VLMProvider, _fallback_cues

log = logging.getLogger(__name__)


class VLMPool:
    """
    Round-robin dispatcher across multiple vLLM instances.
    With 2 GPUs at ~1.1s per call, achieves ~0.55s effective interval.
    Future: switch mode to "ensemble" to send same frame to all instances.
    """

    def __init__(self, providers: List[VLMProvider], mode: str = "round_robin"):
        self.providers = providers
        self.mode = mode
        self.next_idx = 0
        self.pending_tasks: Dict[int, asyncio.Task] = {}

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
        """
        if self._all_backed_off():
            return

        if self.mode == "round_robin":
            # Find the next provider that isn't backed off
            for _ in range(len(self.providers)):
                provider = self.providers[self.next_idx]
                self.next_idx = (self.next_idx + 1) % len(self.providers)
                if not provider.is_backed_off:
                    task = asyncio.create_task(provider.get_cues(frame_b64, None))
                    self.pending_tasks[id(task)] = task
                    return
        elif self.mode == "ensemble":
            for provider in self.providers:
                if not provider.is_backed_off:
                    task = asyncio.create_task(provider.get_cues(frame_b64, None))
                    self.pending_tasks[id(task)] = task

    async def collect_results(self) -> List[Dict[str, float]]:
        """Collect all completed VLM results (non-blocking)."""
        completed: List[Dict[str, float]] = []
        done_keys: List[int] = []
        for key, task in self.pending_tasks.items():
            if task.done():
                try:
                    result = task.result()
                    completed.append(result)
                except Exception as e:
                    log.warning(f"VLM task exception: {e}")
                    completed.append(_fallback_cues())
                done_keys.append(key)
        for key in done_keys:
            del self.pending_tasks[key]
        return completed
