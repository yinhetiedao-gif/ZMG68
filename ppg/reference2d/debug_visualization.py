from __future__ import annotations

"""开发期可视化：原图、二值图、Blob、中心点、半径和 Watershed。"""

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw


def render_debug(preprocessed, features, debug: dict[str, Any], output: str | Path) -> str:
    gray = np.asarray(preprocessed.grayscale, dtype=float)
    base = Image.fromarray(np.uint8(np.clip(gray, 0, 1) * 255), mode="L").convert("RGBA")
    # Watershed 分区用低透明度颜色叠加，便于检查粘连圆点是否真正被拆开。
    labels = np.asarray(debug.get("watershed_labels")) if debug.get("watershed_labels") is not None else None
    if labels is not None and labels.shape == gray.shape:
        overlay = np.zeros((labels.shape[0], labels.shape[1], 4), dtype=np.uint8)
        palette = ((30, 136, 229), (67, 160, 71), (251, 140, 0), (156, 39, 176), (0, 150, 136), (229, 57, 53))
        for label in np.unique(labels):
            if int(label) <= 0: continue
            color = palette[(int(label) - 1) % len(palette)]
            region = labels == label; overlay[region, :3] = color; overlay[region, 3] = 48
        base = Image.alpha_composite(base, Image.fromarray(overlay, mode="RGBA"))
    base = base.convert("RGB")
    draw = ImageDraw.Draw(base)
    width, height = base.size
    for feature in features:
        x = feature.center_x / 100.0 * width; y = feature.center_y / 100.0 * height
        rx = feature.radius_x / 100.0 * width; ry = feature.radius_y / 100.0 * height
        draw.ellipse((x-rx, y-ry, x+rx, y+ry), outline="#e53935", width=1)
        draw.ellipse((x-2, y-2, x+2, y+2), fill="#1565c0")
    for y, x in debug.get("local_maxima", []):
        draw.ellipse((x-3, y-3, x+3, y+3), outline="#00a152", width=1)
    target = Path(output); target.parent.mkdir(parents=True, exist_ok=True); base.save(target)
    return str(target)
