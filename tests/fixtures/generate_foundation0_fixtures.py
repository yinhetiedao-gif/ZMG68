"""Generate deterministic raster fixtures for FOUNDATION 0 headless tests."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).parent


def dense_dot_matrix() -> None:
    image = Image.new("L", (256, 256), "white")
    draw = ImageDraw.Draw(image)
    for row in range(20):
        for column in range(20):
            x, y = 14 + column * 12, 14 + row * 12
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill="black")
    image.save(ROOT / "test_dense_dot_matrix.png")


def simple_geometric_pattern() -> None:
    image = Image.new("L", (256, 256), "white")
    draw = ImageDraw.Draw(image)
    draw.ellipse((26, 34, 96, 104), fill="black")
    draw.rectangle((142, 42, 220, 112), fill="black")
    draw.polygon(((74, 172), (128, 126), (182, 172), (160, 222), (96, 222)), fill="black")
    image.save(ROOT / "test_simple_geometry.png")


if __name__ == "__main__":
    dense_dot_matrix()
    simple_geometric_pattern()
