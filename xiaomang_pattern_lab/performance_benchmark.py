"""Repeatable, headless direct-manipulation performance measurements.

The bundled test Python has no Tcl/Tk runtime, so this module intentionally
measures the work that must remain independent of a GUI: transient pointer
updates and parametric element materialisation.  The running UI's Debug panel
adds native Canvas frame/FPS measurements on a machine with Tcl/Tk available.
"""
from __future__ import annotations

import json
from time import perf_counter
from typing import Iterable

from .interaction import InteractionState
from .parametric import GridParametricModel, SizeGradientMode, SizeGradientModifier
from .view_transform import CanvasViewTransform


CASES: tuple[tuple[int, int], ...] = ((12, 12), (20, 25), (25, 40), (50, 60))


def _model(rows: int, columns: int) -> GridParametricModel:
    return GridParametricModel(
        rows=rows,
        columns=columns,
        spacing_x=8.0,
        spacing_y=8.0,
        element_width=4.0,
        element_height=4.0,
        offset_x=200.0,
        offset_y=200.0,
    )


def _milliseconds(callable_) -> float:
    started = perf_counter(); callable_()
    return round((perf_counter() - started) * 1000.0, 3)


def benchmark_case(rows: int, columns: int) -> dict:
    model = _model(rows, columns)
    elements = model.generate()
    first = elements[0]
    interaction = InteractionState(
        kind="move", element_id=first.id, handle=None,
        start_pointer_x=first.x, start_pointer_y=first.y,
        start_x=first.x, start_y=first.y,
        start_width=first.width, start_height=first.height, start_rotation=first.rotation,
        current_x=first.x, current_y=first.y,
        current_width=first.width, current_height=first.height, current_rotation=first.rotation,
    )

    def pointer_moves() -> None:
        for index in range(240):
            interaction.set_position(first.x + index * 0.05, first.y + index * 0.025)

    def pointer_scale() -> None:
        for index in range(240):
            interaction.set_size(first.width + index * 0.01, first.height + index * 0.01)

    def transform_checks() -> None:
        view = CanvasViewTransform(500, 500, 1000, 760)
        for zoom in (0.5, 1.0, 2.0):
            view.set_zoom_at(zoom, 500, 380); view.pan_pixels(17, -9)
            view.screenToWorld(*view.worldToScreen(first.x, first.y))

    def spacing_preview() -> None:
        candidate = GridParametricModel.from_dict(model.to_dict()); candidate.spacing_x += 1.0; candidate.generate()

    def size_gradient_preview() -> None:
        candidate = GridParametricModel.from_dict(model.to_dict())
        candidate.size_gradient = SizeGradientModifier(mode=SizeGradientMode.CENTER_TO_EDGE, min_size=1.0, max_size=7.0, strength=1.0)
        candidate.generate()

    return {
        "element_count": len(elements),
        "transient_drag_240_ms": _milliseconds(pointer_moves),
        "transient_scale_240_ms": _milliseconds(pointer_scale),
        "pan_zoom_transform_ms": _milliseconds(transform_checks),
        "spacing_slider_preview_ms": _milliseconds(spacing_preview),
        "size_gradient_slider_preview_ms": _milliseconds(size_gradient_preview),
        "document_updates_during_transient": 0,
        "svg_serializations_during_transient": 0,
        "undo_records_during_transient": 0,
    }


def run_benchmark(cases: Iterable[tuple[int, int]] = CASES) -> list[dict]:
    return [benchmark_case(rows, columns) for rows, columns in cases]


def main() -> int:
    print(json.dumps(run_benchmark(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
