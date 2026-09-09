"""无 Blender 依赖的本地最终 STL 后端。

将当前二维工作单栅格化为高分辨率黑色实体 Mask，再使用
``raster_print`` 的连续 SDF + Marching Tetrahedra 管线生成封闭 STL。
这是桌面版的默认制造后端；Blender 仅保留为可选实验后端，不再是安装前提。
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from .raster_print import QUALITY_STEP, _write_smooth_stl, audit_stl


@dataclass(frozen=True)
class NativeResult:
    stl_path: str
    triangles: int
    vertices: int
    blender_path: str
    worker_log: str
    source_cleanup: dict
    audit: dict


def _bounds(primitives: list[dict]) -> tuple[float, float, float, float]:
    points: list[tuple[float, float]] = []
    for item in primitives:
        try:
            x, y = float(item["x"]), float(item["y"])
            radius = max(0.05, float(item.get("size", 0.0)))
            radius_x = max(0.05, float(item.get("radius_x", radius)))
            radius_y = max(0.05, float(item.get("radius_y", radius)))
            if item.get("kind") == "ellipse":
                angle = math.radians(float(item.get("rotation", 0.0)))
                extent_x = math.hypot(radius_x * math.cos(angle), radius_y * math.sin(angle))
                extent_y = math.hypot(radius_x * math.sin(angle), radius_y * math.cos(angle))
            else:
                extent_x, extent_y = radius_x, radius_y
            points.extend(((x - extent_x, y - extent_y), (x + extent_x, y + extent_y)))
            if item.get("kind") == "line":
                x2, y2 = float(item["x2"]), float(item["y2"])
                points.extend(((x2 - radius_x, y2 - radius_y), (x2 + radius_x, y2 + radius_y)))
        except (KeyError, TypeError, ValueError):
            continue
    if not points:
        raise ValueError("没有可用于本地 STL 的二维图元。")
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)


def _rasterize(primitives: list[dict], quality: str) -> tuple[list[bytearray], int, int, float]:
    min_x, min_y, max_x, max_y = _bounds(primitives)
    span_x = max(0.1, max_x - min_x)
    span_y = max(0.1, max_y - min_y)
    # 质量档控制真实建模分辨率，而不是把低分辨率预览直接导出。
    step = QUALITY_STEP.get(quality, QUALITY_STEP["标准"])
    width_px = max(160, min(700, int(round(span_x / step))))
    height_px = max(32, min(700, int(round(span_y / span_x * width_px))))
    # 保留一个像素的边界，避免极端贴边图元被裁剪。
    image = Image.new("L", (width_px, height_px), 0)
    draw = ImageDraw.Draw(image)

    def point(x: float, y: float) -> tuple[int, int]:
        return (
            int(round((x - min_x) / span_x * (width_px - 1))),
            int(round((max_y - y) / span_y * (height_px - 1))),
        )

    def radius_px(size: float) -> int:
        return max(1, int(round(abs(float(size)) / span_x * width_px)))

    def rotated_ellipse(center: tuple[int, int], rx: int, ry: int, rotation: float, steps: int = 40) -> list[tuple[float, float]]:
        angle = math.radians(rotation)
        cosine, sine = math.cos(angle), math.sin(angle)
        return [
            (center[0] + rx * math.cos(index * math.tau / steps) * cosine - ry * math.sin(index * math.tau / steps) * sine,
             center[1] + rx * math.cos(index * math.tau / steps) * sine + ry * math.sin(index * math.tau / steps) * cosine)
            for index in range(steps)
        ]

    for item in primitives:
        try:
            kind = str(item.get("kind", "dot"))
            size = max(0.05, float(item.get("size", 1.0)))
            center = point(float(item["x"]), float(item["y"]))
            if kind == "line" and item.get("x2") is not None and item.get("y2") is not None:
                end = point(float(item["x2"]), float(item["y2"]))
                draw.line((center, end), fill=255, width=radius_px(size))
                # 圆头避免离散栅格在线段末端产生断口。
                r = radius_px(size) // 2
                for cx, cy in (center, end):
                    draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=255)
            elif kind in ("triangle", "square"):
                r = radius_px(size)
                if kind == "triangle":
                    polygon = [(center[0], center[1]-r), (center[0]+r, center[1]+r), (center[0]-r, center[1]+r)]
                else:
                    polygon = [(center[0]-r, center[1]-r), (center[0]+r, center[1]-r), (center[0]+r, center[1]+r), (center[0]-r, center[1]+r)]
                draw.polygon(polygon, fill=255)
            elif kind == "ellipse":
                rx = radius_px(float(item.get("radius_x", size)))
                ry = max(1, int(round(abs(float(item.get("radius_y", size))) / span_y * height_px)))
                draw.polygon(rotated_ellipse(center, rx, ry, float(item.get("rotation", 0.0))), fill=255)
            else:
                r = radius_px(size)
                draw.ellipse((center[0]-r, center[1]-r, center[0]+r, center[1]+r), fill=255)
        except (KeyError, TypeError, ValueError):
            continue

    # 轻微闭运算修补像素级断口，同时保持用户可见的元素边界。
    image = image.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    pixels = image.load()
    mask = [bytearray(1 if pixels[x, y] > 0 else 0 for x in range(width_px)) for y in range(height_px)]
    return mask, width_px, height_px, span_x


def run_native_stl_job(
    primitives: list[dict],
    output_stl: str,
    *,
    thickness: float = 1.2,
    quality: str = "标准",
    roundness: float = 55.0,
    organic_blend: float = 55.0,
    minimum_feature_mm: float = 0.8,
    allow_multipart: bool = False,
) -> NativeResult:
    if not primitives:
        raise ValueError("没有可用于 3D 建模的点线面元素。")
    if thickness <= 0:
        raise ValueError("模型厚度必须大于 0。")
    # 延迟导入，避免与兼容模块形成循环依赖。
    from .blender_worker import cleanup_primitives

    cleaned, cleanup_report = cleanup_primitives(primitives, minimum_feature_mm)
    mask, width_px, _height_px, model_width = _rasterize(cleaned, quality)
    output = Path(output_stl).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    triangles = _write_smooth_stl(mask, width_px, len(mask), model_width, float(thickness), float(roundness), float(organic_blend), quality, output)
    audit = audit_stl(output)
    components = int(audit.get("connected_components", 0))
    if not audit.get("watertight") or (components > 1 and not allow_multipart):
        output.unlink(missing_ok=True)
        if components > 1:
            raise RuntimeError(f"最终模型包含 {components} 个独立组件。请连接图元，或明确启用多部件导出。")
        raise RuntimeError("最终模型未通过封闭、裸边、非流形或退化面检查，已阻止 STL 输出。")
    return NativeResult(str(output), int(triangles), int(triangles * 3), "native", "本地 SDF 网格后端；无需 Blender。", cleanup_report, audit)
