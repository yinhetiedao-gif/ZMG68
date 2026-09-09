from __future__ import annotations

import copy


class History:
    """小而可靠的项目快照历史；避免在滑块拖动期间逐帧写入。"""
    def __init__(self, limit: int = 60):
        self.limit = limit
        self._undo: list[dict] = []
        self._redo: list[dict] = []

    def push(self, snapshot: dict) -> None:
        snapshot = copy.deepcopy(snapshot)
        if self._undo and self._undo[-1] == snapshot:
            return
        self._undo.append(snapshot)
        self._undo = self._undo[-self.limit:]
        self._redo.clear()

    def undo(self, current: dict) -> dict | None:
        if not self._undo:
            return None
        # Snapshots include the current state. Drop it, then restore the previous one.
        if self._undo[-1] == current:
            self._redo.append(self._undo.pop())
        if not self._undo:
            return None
        return copy.deepcopy(self._undo[-1])

    def redo(self, current: dict) -> dict | None:
        if not self._redo:
            return None
        next_state = self._redo.pop()
        self._undo.append(copy.deepcopy(next_state))
        return next_state
