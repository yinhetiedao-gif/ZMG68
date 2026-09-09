from __future__ import annotations

from pathlib import Path

from PIL import Image

from .models import ReferenceImage


def decode_reference(path: str, target_width_mm: float | None = None, target_height_mm: float | None = None) -> ReferenceImage:
    """读取 PNG/JPG/WEBP/TIFF/BMP，并保留像素、色彩、透明通道和 DPI。"""
    source_path = Path(path).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"参考图片不存在：{source_path}")
    with Image.open(source_path) as opened:
        image = opened.convert("RGBA")
        width, height = opened.size
        raw_dpi = opened.info.get("dpi")
        dpi = None
        if isinstance(raw_dpi, (tuple, list)) and len(raw_dpi) >= 2:
            try:
                dx, dy = float(raw_dpi[0]), float(raw_dpi[1])
                if dx > 1 and dy > 1:
                    dpi = (dx, dy)
            except (TypeError, ValueError):
                pass
        color_space = str(opened.mode or "RGBA")
        has_alpha = "A" in opened.mode or "transparency" in opened.info
    physical_width = float(target_width_mm) if target_width_mm and target_width_mm > 0 else None
    physical_height = float(target_height_mm) if target_height_mm and target_height_mm > 0 else None
    if dpi:
        physical_width = physical_width or width / dpi[0] * 25.4
        physical_height = physical_height or height / dpi[1] * 25.4
    elif physical_width and not physical_height:
        physical_height = physical_width * height / max(1, width)
    elif physical_height and not physical_width:
        physical_width = physical_height * width / max(1, height)
    return ReferenceImage(str(source_path), image, width, height, dpi, color_space, has_alpha, physical_width, physical_height)
