"""Bounded, process-local Alpha manufacturing result cache."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Lock, RLock
from time import monotonic
from typing import Any


MAX_MANUFACTURING_RESULTS = 32
MANUFACTURING_RESULT_TTL_SECONDS = 30 * 60


@dataclass
class StoredManufacturingResult:
    result: Any
    response: dict[str, Any]
    stl_bytes: bytes | None = None
    preview_glb_bytes: bytes | None = None
    artifact_lock: Any = field(default_factory=Lock, repr=False, compare=False)


class InMemoryManufacturingResultStore:
    """No persistence: restart, expiry, or capacity eviction loses results."""

    def __init__(self, *, max_entries: int = MAX_MANUFACTURING_RESULTS,
                 ttl_seconds: float = MANUFACTURING_RESULT_TTL_SECONDS) -> None:
        if max_entries < 1 or ttl_seconds <= 0:
            raise ValueError("制造结果缓存容量和有效期必须大于零。")
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._items: OrderedDict[str, tuple[float, StoredManufacturingResult]] = OrderedDict()
        self._lock = RLock()

    def _expire(self, now: float) -> None:
        for key, (created, _) in list(self._items.items()):
            if now - created >= self.ttl_seconds:
                del self._items[key]

    def put(self, result_id: str, value: StoredManufacturingResult) -> None:
        with self._lock:
            self._expire(monotonic())
            self._items.pop(result_id, None)
            self._items[result_id] = (monotonic(), value)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)

    def get(self, result_id: str) -> StoredManufacturingResult | None:
        with self._lock:
            self._expire(monotonic())
            item = self._items.get(result_id)
            return None if item is None else item[1]

    def delete(self, result_id: str) -> None:
        with self._lock:
            self._items.pop(result_id, None)
