"""Deterministic image fixtures and ground truth for Pattern Lab verification."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from PIL import Image, ImageDraw
from ppg.runtime_paths import resource_path


ROOT = resource_path("xiaomang_pattern_lab", "fixtures")
CANVAS = 320


def _inside_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    last = len(polygon) - 1
    for index, (xi, yi) in enumerate(polygon):
        xj, yj = polygon[last]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi:
            inside = not inside
        last = index
    return inside


def _star_polygon(cx: float, cy: float, outer: float, inner: float, points: int = 5) -> List[Tuple[float, float]]:
    result: List[Tuple[float, float]] = []
    for index in range(points * 2):
        radius = outer if index % 2 == 0 else inner
        angle = -math.pi / 2 + index * math.pi / points
        result.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return result


def _write(name: str, dots: Iterable[Tuple[float, float, float]]) -> Path:
    ROOT.mkdir(parents=True, exist_ok=True)
    image = Image.new("L", (CANVAS, CANVAS), "white")
    draw = ImageDraw.Draw(image)
    payload = []
    for index, (x, y, radius) in enumerate(dots):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="black")
        payload.append({"id": "source-%04d" % index, "x": x, "y": y, "width": 2 * radius, "height": 2 * radius})
    image_path = ROOT / (name + ".png")
    image.save(image_path)
    (ROOT / (name + ".truth.json")).write_text(
        json.dumps({"canvas": [CANVAS, CANVAS], "elements": payload}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return image_path


def build_fixed_suite() -> Dict[str, Path]:
    """Create the six stable test inputs and their known source geometry."""
    names = (
        "regular_dot_matrix", "size_gradient_dot_matrix", "star_halftone",
        "high_density_dot_matrix", "twisted_dot_matrix", "mixed_size_dot_matrix",
    )
    # In a PyInstaller build fixture data is immutable bundled resource data.
    # Reuse it rather than attempting to write into ``_internal``.
    if all((ROOT / (name + ".png")).is_file() and (ROOT / (name + ".truth.json")).is_file()
           for name in names):
        return {name: ROOT / (name + ".png") for name in names}
    regular = [(28 + col * 24, 28 + row * 24, 5.0) for row in range(12) for col in range(12)]
    gradient = []
    for row in range(12):
        for col in range(12):
            radius = 2.0 + (col + row) / 22.0 * 5.0
            gradient.append((28 + col * 24, 28 + row * 24, radius))
    star = []
    star_polygon = _star_polygon(160, 160, 128, 56)
    for row in range(16):
        for col in range(16):
            x, y = 22 + col * 18, 22 + row * 18
            if _inside_polygon((x, y), star_polygon):
                radius = 2.5 + max(0.0, 1.0 - math.dist((x, y), (160, 160)) / 145.0) * 3.5
                star.append((x, y, radius))
    dense = [(14 + col * 12, 14 + row * 12, 2.6) for row in range(25) for col in range(25)]
    twisted = []
    for row in range(14):
        for col in range(14):
            x = 31 + col * 20 + math.sin(row * 0.71) * 5.5
            y = 31 + row * 20 + math.sin(col * 0.63) * 5.5
            twisted.append((x, y, 4.2))
    mixed = []
    sizes = (2.5, 4.0, 5.5, 7.0)
    for row in range(12):
        for col in range(12):
            radius = sizes[(row * 7 + col * 11) % len(sizes)]
            mixed.append((28 + col * 24, 28 + row * 24, radius))
    paths = {
        "regular_dot_matrix": _write("regular_dot_matrix", regular),
        "size_gradient_dot_matrix": _write("size_gradient_dot_matrix", gradient),
        "star_halftone": _write("star_halftone", star),
        "high_density_dot_matrix": _write("high_density_dot_matrix", dense),
        "twisted_dot_matrix": _write("twisted_dot_matrix", twisted),
        "mixed_size_dot_matrix": _write("mixed_size_dot_matrix", mixed),
    }
    # JPEG input is a smoke fixture for the import contract, rather than an
    # additional scored reference pattern.
    with Image.open(paths["regular_dot_matrix"]) as source:
        source.convert("RGB").save(ROOT / "regular_dot_matrix.jpg", quality=95)
    return paths


def ground_truth(case_name: str) -> List[dict]:
    truth_path = ROOT / (case_name + ".truth.json")
    return list(json.loads(truth_path.read_text(encoding="utf-8"))["elements"])


if __name__ == "__main__":
    build_fixed_suite()
