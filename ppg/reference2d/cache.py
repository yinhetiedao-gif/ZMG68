from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from pathlib import Path
from typing import Any


def reference_cache_key(path: str, config: Any) -> str:
    source = Path(path).resolve(); digest = hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else "missing"
    payload = json.dumps(config.__dict__ if hasattr(config, "__dict__") else config, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256((digest + payload).encode("utf-8")).hexdigest()


class Reference2DCache:
    def __init__(self, capacity: int = 8):
        self.capacity = max(1, int(capacity)); self._items: OrderedDict[str, Any] = OrderedDict()

    def get(self, key: str) -> Any | None:
        value = self._items.get(key)
        if value is not None: self._items.move_to_end(key)
        return value

    def put(self, key: str, value: Any) -> Any:
        self._items[key] = value; self._items.move_to_end(key)
        while len(self._items) > self.capacity: self._items.popitem(last=False)
        return value
