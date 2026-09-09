from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class ReferenceImage:
    """已解码的源图和制造尺寸元数据。"""

    source_path: str
    image: Image.Image
    width_px: int
    height_px: int
    dpi: tuple[float, float] | None
    color_space: str
    alpha_channel: bool
    physical_width_mm: float | None = None
    physical_height_mm: float | None = None

    def metadata(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "dpi": list(self.dpi) if self.dpi else None,
            "color_space": self.color_space,
            "alpha_channel": self.alpha_channel,
            "physical_width_mm": self.physical_width_mm,
            "physical_height_mm": self.physical_height_mm,
        }


@dataclass(frozen=True)
class PreprocessConfig:
    threshold_method: str = "otsu"
    threshold: float = 0.5
    adaptive_block_size: int = 21
    adaptive_c: float = 0.0
    gamma: float = 1.0
    contrast: float = 1.0
    blur: float = 0.0
    median_size: int = 0
    invert: bool = False
    morphology: str = "none"
    morphology_kernel: int = 0
    morphology_iterations: int = 1
    min_area: int = 3


@dataclass(frozen=True)
class PreprocessedImage:
    grayscale: np.ndarray
    binary_mask: np.ndarray
    threshold: float
    config: PreprocessConfig


@dataclass(frozen=True)
class DotFeature:
    id: int
    center_x: float
    center_y: float
    radius_x: float
    radius_y: float
    diameter: float
    area: float
    bounding_box: tuple[float, float, float, float]
    circularity: float
    eccentricity: float
    rotation: float
    confidence: float
    region_id: str
    element_type: str = "dot"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "radius_x": self.radius_x,
            "radius_y": self.radius_y,
            "diameter": self.diameter,
            "area": self.area,
            "bounding_box": list(self.bounding_box),
            "circularity": self.circularity,
            "eccentricity": self.eccentricity,
            "rotation": self.rotation,
            "confidence": self.confidence,
            "region_id": self.region_id,
            "element_type": self.element_type,
        }


@dataclass(frozen=True)
class ClassificationResult:
    primary_type: str
    secondary_types: tuple[str, ...]
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {"primary_type": self.primary_type, "secondary_types": list(self.secondary_types), "confidence": self.confidence}


@dataclass(frozen=True)
class SpatialFields:
    density_field: tuple[tuple[float, ...], ...]
    size_field: tuple[tuple[float, ...], ...]
    rotation_field: tuple[tuple[float, ...], ...]
    nearest_neighbor_mean: float
    spacing_anisotropy: float
    symmetry: dict[str, float]
    grid_spacing: tuple[float, float] = (0.0, 0.0)
    principal_direction: float = 0.0
    local_orientation_mean: float = 0.0
    position_distortion: float = 0.0
    size_distribution: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "density_field": [list(row) for row in self.density_field],
            "size_field": [list(row) for row in self.size_field],
            "rotation_field": [list(row) for row in self.rotation_field],
            "nearest_neighbor_mean": self.nearest_neighbor_mean,
            "spacing_anisotropy": self.spacing_anisotropy,
            "symmetry": self.symmetry,
            "grid_spacing": list(self.grid_spacing),
            "principal_direction": self.principal_direction,
            "local_orientation_mean": self.local_orientation_mean,
            "position_distortion": self.position_distortion,
            "size_distribution": self.size_distribution,
        }


@dataclass(frozen=True)
class EditableGeometry:
    dots: tuple[dict[str, Any], ...] = ()
    lines: tuple[dict[str, Any], ...] = ()
    shapes: tuple[dict[str, Any], ...] = ()
    mask: dict[str, Any] = field(default_factory=lambda: {"type": "binary", "feather": 0.0})

    def to_dict(self) -> dict[str, Any]:
        return {"dots": list(self.dots), "lines": list(self.lines), "shapes": list(self.shapes), "mask": self.mask}


@dataclass
class Reference2DResult:
    """结构化 P0 结果，并通过属性兼容现有 AnalysisResult/UI。"""

    legacy: Any
    source: ReferenceImage
    preprocessed: PreprocessedImage
    classification: ClassificationResult
    features: tuple[DotFeature, ...]
    fields: SpatialFields
    geometry: EditableGeometry
    generator: dict[str, Any]
    modifiers: tuple[dict[str, Any], ...]
    similarity: dict[str, float]
    # 新版产品文档：检测到的每个元素均可直接编辑；保留 None 兼容旧调用方。
    editable_document: Any | None = None
    # 仅开发可视化使用，绝不写入项目 JSON。
    debug: dict[str, Any] | None = None

    def __getattr__(self, name: str) -> Any:
        # 现有 UI 继续使用 generator_key、suggestions、details 等字段，升级无需改动
        # 交互流程；新增模块数据则通过明确的结构化属性提供给后续功能。
        if name == "details":
            return {
                **getattr(self.legacy, "details", {}),
                "分类主类型": self.classification.primary_type,
                "分类次类型": "、".join(self.classification.secondary_types) or "无",
                "可编辑对象": f"点 {len(self.geometry.dots)} · 线 {len(self.geometry.lines)} · 面 {len(self.geometry.shapes)}",
                "平均最近邻": f"{self.fields.nearest_neighbor_mean:.2f}%",
                "重建模式": str(self.generator.get("mode", "direct")),
                "Generator 拟合分数": f"{float(self.generator.get('score', 0.0)):.3f}",
                "网格间距": f"{self.fields.grid_spacing[0]:.2f} × {self.fields.grid_spacing[1]:.2f}%",
                "主方向": f"{self.fields.principal_direction:.1f}°",
                "位置畸变": f"{self.fields.position_distortion:.3f}",
            }
        if name == "metrics":
            return {
                **getattr(self.legacy, "metrics", {}),
                "Reference2D 检测元素": len(self.features),
                "Reference2D IoU": round(self.similarity.get("mask_iou", 0.0), 3),
                "Reference2D Dice": round(self.similarity.get("mask_dice", 0.0), 3),
            }
        return getattr(self.legacy, name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.metadata(),
            "preprocessed": {"threshold": self.preprocessed.threshold, "config": self.preprocessed.config.__dict__},
            "classification": self.classification.to_dict(),
            "features": [feature.to_dict() for feature in self.features],
            "fields": self.fields.to_dict(),
            "generator": self.generator,
            "modifiers": list(self.modifiers),
            "geometry": self.geometry.to_dict(),
            "similarity": self.similarity,
            "editable_document": self.editable_document.to_dict() if self.editable_document is not None else None,
            "legacy": self.legacy.to_dict() if hasattr(self.legacy, "to_dict") else {},
        }
