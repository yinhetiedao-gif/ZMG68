"""Small, dependency-free instrumentation for Pattern Lab's development UI."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from time import perf_counter
from typing import Deque, Dict


@dataclass
class PerformanceMetrics:
    """Counters and rolling timings used to prove interaction work is bounded.

    This intentionally records events rather than guessing performance from the
    number of shapes.  Values are surfaced in the development debug panel and
    are also safe to assert from automated tests.
    """

    pointer_moves: int = 0
    interaction_updates: int = 0
    interaction_renders: int = 0
    static_renders: int = 0
    full_canvas_rebuilds: int = 0
    inspector_refreshes: int = 0
    spatial_queries: int = 0
    render_count: int = 0
    document_commits: int = 0
    undo_records: int = 0
    svg_serializations: int = 0
    _frames: Deque[float] = field(default_factory=lambda: deque(maxlen=180))
    _render_times: Deque[float] = field(default_factory=lambda: deque(maxlen=60))
    _interaction_times: Deque[float] = field(default_factory=lambda: deque(maxlen=60))
    _commit_times: Deque[float] = field(default_factory=lambda: deque(maxlen=30))

    def record_frame(self, seconds: float) -> None:
        self._frames.append(max(0.0, seconds))
        self.render_count += 1

    def record_render(self, seconds: float, *, static: bool = False) -> None:
        self._render_times.append(max(0.0, seconds))
        if static:
            self.static_renders += 1
        self.record_frame(seconds)

    def record_interaction(self, seconds: float) -> None:
        self.interaction_updates += 1
        self._interaction_times.append(max(0.0, seconds))

    def record_commit(self, seconds: float) -> None:
        self.document_commits += 1
        self._commit_times.append(max(0.0, seconds))

    @staticmethod
    def _mean_ms(samples: Deque[float]) -> float:
        return (sum(samples) / len(samples) * 1000.0) if samples else 0.0

    @property
    def fps(self) -> float:
        frame_ms = self._mean_ms(self._frames)
        return (1000.0 / frame_ms) if frame_ms > 0 else 0.0

    def snapshot(self) -> Dict[str, float | int]:
        return {
            "fps": round(self.fps, 1),
            "frame_ms": round(self._mean_ms(self._frames), 2),
            "render_ms": round(self._mean_ms(self._render_times), 2),
            "interaction_ms": round(self._mean_ms(self._interaction_times), 2),
            "commit_ms": round(self._mean_ms(self._commit_times), 2),
            "pointer_moves": self.pointer_moves,
            "interaction_updates": self.interaction_updates,
            "interaction_renders": self.interaction_renders,
            "static_renders": self.static_renders,
            "full_canvas_rebuilds": self.full_canvas_rebuilds,
            "inspector_refreshes": self.inspector_refreshes,
            "spatial_queries": self.spatial_queries,
            "render_count": self.render_count,
            "document_commits": self.document_commits,
            "undo_records": self.undo_records,
            "svg_serializations": self.svg_serializations,
        }


def timed(callable_):
    """Run a callable and return ``(result, elapsed_seconds)``."""

    started = perf_counter()
    result = callable_()
    return result, perf_counter() - started
