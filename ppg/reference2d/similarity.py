from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from .models import EditableGeometry


def evaluate_geometry(reference_mask: np.ndarray, geometry: EditableGeometry) -> dict[str, float]:
    height, width = reference_mask.shape; image = Image.new("L", (width, height), 0); draw = ImageDraw.Draw(image)
    for dot in geometry.dots:
        x, y = float(dot["position"][0]) / 100.0 * width, float(dot["position"][1]) / 100.0 * height
        rx, ry = max(1.0, float(dot["radius_x"]) / 100.0 * width), max(1.0, float(dot["radius_y"]) / 100.0 * height)
        draw.ellipse((x - rx, y - ry, x + rx, y + ry), fill=255)
    for line in geometry.lines:
        points = [(float(x) / 100 * width, float(y) / 100 * height) for x, y in line["control_points"]]
        draw.line(points, fill=255, width=max(1, round(float(line.get("width", 1)) / 100 * min(width, height))))
    generated = np.asarray(image, dtype=bool); reference = np.asarray(reference_mask, dtype=bool); intersection = np.logical_and(reference, generated).sum(); union = np.logical_or(reference, generated).sum()
    return {"mask_iou": float(intersection / max(1, union)), "mask_dice": float(2 * intersection / max(1, reference.sum() + generated.sum())), "reference_area": float(reference.mean()), "generated_area": float(generated.mean())}
