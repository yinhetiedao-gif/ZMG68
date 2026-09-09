"""Single world↔screen coordinate transform used by Canvas, picking and rulers."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CanvasViewTransform:
    """Map PatternDocument world coordinates (currently mm) to Canvas pixels."""

    world_width: float
    world_height: float
    viewport_width: float
    viewport_height: float
    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    world_origin_x: float = 0.0
    world_origin_y: float = 0.0
    origin_x: float = 0.0
    origin_y: float = 0.0

    def __post_init__(self) -> None:
        self.zoom = max(0.05, min(float(self.zoom), 20.0))
        self._recalculate_fit()

    @property
    def fit_scale(self) -> float:
        return min((self.viewport_width - 40.0) / max(self.world_width, 1e-9),
                   (self.viewport_height - 40.0) / max(self.world_height, 1e-9))

    @property
    def scale(self) -> float:
        return max(self.fit_scale * self.zoom, 1e-9)

    def _recalculate_fit(self) -> None:
        # pan is screen pixels, while origin is the centering offset.  Keeping
        # this explicit prevents screen pixels from leaking into PatternDocument.
        self.origin_x = (self.viewport_width - self.world_width * self.scale) / 2.0 + self.pan_x
        self.origin_y = (self.viewport_height - self.world_height * self.scale) / 2.0 + self.pan_y

    def resize_viewport(self, width: float, height: float) -> None:
        self.viewport_width = max(float(width), 1.0)
        self.viewport_height = max(float(height), 1.0)
        self._recalculate_fit()

    def worldToScreen(self, x: float, y: float) -> tuple[float, float]:
        return (self.origin_x + (float(x) - self.world_origin_x) * self.scale,
                self.origin_y + (float(y) - self.world_origin_y) * self.scale)

    def screenToWorld(self, x: float, y: float) -> tuple[float, float]:
        return ((float(x) - self.origin_x) / self.scale + self.world_origin_x,
                (float(y) - self.origin_y) / self.scale + self.world_origin_y)

    def set_zoom_at(self, zoom: float, screen_x: float, screen_y: float) -> None:
        before = self.screenToWorld(screen_x, screen_y)
        self.zoom = max(0.05, min(float(zoom), 20.0))
        self._recalculate_fit()
        after = self.worldToScreen(*before)
        self.pan_x += float(screen_x) - after[0]
        self.pan_y += float(screen_y) - after[1]
        self._recalculate_fit()

    def pan_pixels(self, dx: float, dy: float) -> None:
        self.pan_x += float(dx); self.pan_y += float(dy)
        self._recalculate_fit()

    def reset(self) -> None:
        self.zoom = 1.0; self.pan_x = 0.0; self.pan_y = 0.0
        self._recalculate_fit()

    def visible_world_bounds(self) -> tuple[float, float, float, float]:
        left, top = self.screenToWorld(0, 0)
        right, bottom = self.screenToWorld(self.viewport_width, self.viewport_height)
        return left, top, right, bottom

    def format_zoom(self) -> str:
        return "%d%%" % round(self.zoom * 100.0)
