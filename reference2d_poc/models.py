from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from pathlib import Path
from typing import Any


@dataclass
class DotObject:
    """一个真正属于 GeometryLayer 的可编辑椭圆/圆点对象。"""

    id: str
    x: float
    y: float
    radius_x: float
    radius_y: float
    rotation: float
    fill: str
    source_confidence: float
    object_type: str = "dot"

    def contains(self, x: float, y: float) -> bool:
        """按旋转椭圆命中测试；用于 Canvas 层未来直接复用。"""
        if self.radius_x <= 0 or self.radius_y <= 0:
            return False
        radians = math.radians(-self.rotation)
        dx, dy = x - self.x, y - self.y
        local_x = dx * math.cos(radians) - dy * math.sin(radians)
        local_y = dx * math.sin(radians) + dy * math.cos(radians)
        return (local_x / self.radius_x) ** 2 + (local_y / self.radius_y) ** 2 <= 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.object_type,
            "x": round(self.x, 6),
            "y": round(self.y, 6),
            "radius_x": round(self.radius_x, 6),
            "radius_y": round(self.radius_y, 6),
            "rotation": round(self.rotation, 6),
            "fill": self.fill,
            "source_confidence": round(self.source_confidence, 6),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DotObject":
        return cls(
            id=str(data["id"]),
            x=float(data["x"]),
            y=float(data["y"]),
            radius_x=float(data["radius_x"]),
            radius_y=float(data["radius_y"]),
            rotation=float(data.get("rotation", 0.0)),
            fill=str(data.get("fill", "#000000")),
            source_confidence=float(data.get("source_confidence", 0.0)),
            object_type=str(data.get("type", "dot")),
        )


@dataclass
class ReferenceLayer:
    """仅保存源图片信息；不能承载或生成 GeometryLayer 对象。"""

    source_path: str
    width: float
    height: float
    visible: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "reference",
            "source_path": self.source_path,
            "width": self.width,
            "height": self.height,
            "visible": self.visible,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReferenceLayer":
        return cls(
            source_path=str(data["source_path"]),
            width=float(data["width"]),
            height=float(data["height"]),
            visible=bool(data.get("visible", True)),
        )


@dataclass
class GeometryLayer:
    """只接受真实几何对象；当前 Stage A 仅接受 DotObject。"""

    dots: list[DotObject] = field(default_factory=list)
    visible: bool = True

    def add_dot(self, dot: DotObject) -> None:
        if any(existing.id == dot.id for existing in self.dots):
            raise ValueError(f"重复的 GeometryLayer 对象 ID：{dot.id}")
        self.dots.append(dot)

    def get_dot(self, dot_id: str) -> DotObject:
        for dot in self.dots:
            if dot.id == dot_id:
                return dot
        raise KeyError(f"不存在的点对象：{dot_id}")

    def remove_dot(self, dot_id: str) -> DotObject:
        for index, dot in enumerate(self.dots):
            if dot.id == dot_id:
                return self.dots.pop(index)
        raise KeyError(f"不存在的点对象：{dot_id}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "geometry",
            "visible": self.visible,
            "objects": [dot.to_dict() for dot in self.dots],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GeometryLayer":
        objects = data.get("objects", [])
        unsupported = [item.get("type") for item in objects if item.get("type", "dot") != "dot"]
        if unsupported:
            raise ValueError(f"Stage A POC 只支持 dot，发现不支持的对象：{unsupported}")
        return cls(
            dots=[DotObject.from_dict(item) for item in objects],
            visible=bool(data.get("visible", True)),
        )


@dataclass
class Document2D:
    """最小可保存二维文档；Reference 与 Geometry 永远分层存储。"""

    reference_layer: ReferenceLayer
    geometry_layer: GeometryLayer
    selected_object_id: str | None = None
    format_version: int = 1

    def hide_reference(self) -> None:
        self.reference_layer.visible = False

    def show_reference(self) -> None:
        self.reference_layer.visible = True

    def select_at(self, x: float, y: float) -> DotObject | None:
        """按绘制层级选中最上层的真实 DotObject。"""
        for dot in reversed(self.geometry_layer.dots):
            if dot.contains(x, y):
                self.selected_object_id = dot.id
                return dot
        self.selected_object_id = None
        return None

    def set_dot_radius(self, dot_id: str, radius_x: float, radius_y: float | None = None) -> DotObject:
        if radius_x <= 0 or (radius_y is not None and radius_y <= 0):
            raise ValueError("点半径必须大于 0")
        dot = self.geometry_layer.get_dot(dot_id)
        dot.radius_x = float(radius_x)
        dot.radius_y = float(radius_y if radius_y is not None else radius_x)
        return dot

    def move_dot(self, dot_id: str, x: float, y: float) -> DotObject:
        dot = self.geometry_layer.get_dot(dot_id)
        dot.x, dot.y = float(x), float(y)
        return dot

    def delete_selected(self) -> DotObject:
        if not self.selected_object_id:
            raise ValueError("没有选中的对象，无法删除")
        deleted = self.geometry_layer.remove_dot(self.selected_object_id)
        self.selected_object_id = None
        return deleted

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "xiaomang-reference2d-poc",
            "format_version": self.format_version,
            "reference_layer": self.reference_layer.to_dict(),
            "geometry_layer": self.geometry_layer.to_dict(),
            "selected_object_id": self.selected_object_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Document2D":
        if data.get("format") != "xiaomang-reference2d-poc":
            raise ValueError("不是 Reference2D POC 项目文件")
        document = cls(
            reference_layer=ReferenceLayer.from_dict(data["reference_layer"]),
            geometry_layer=GeometryLayer.from_dict(data["geometry_layer"]),
            selected_object_id=data.get("selected_object_id"),
            format_version=int(data.get("format_version", 1)),
        )
        if document.selected_object_id and not any(
            dot.id == document.selected_object_id for dot in document.geometry_layer.dots
        ):
            document.selected_object_id = None
        return document

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Document2D":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
