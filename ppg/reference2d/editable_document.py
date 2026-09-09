from __future__ import annotations

"""Reference → Editable 2D 的唯一事实来源。

``elements`` 是当前可见、可选、可导出的真实对象；``base_elements`` 是
Primitive Detection / Generator Fitting 得到的稳定基线；``overrides`` 只保存
用户的局部差异。这样 Rebuild 不需要重新读取 Raster，也不会吞掉局部编辑。
"""

from dataclasses import dataclass, field
import copy
import math
from typing import Any, Iterable


@dataclass
class EditableElement:
    id: str
    primitive_type: str
    x: float
    y: float
    width: float
    height: float
    radius: float
    rotation: float = 0.0
    opacity: float = 1.0
    enabled: bool = True
    group_id: str | None = None
    source: str = "detected"
    confidence: float = 0.0

    def clone(self) -> "EditableElement":
        return copy.deepcopy(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "primitive_type": self.primitive_type,
            "x": round(float(self.x), 6), "y": round(float(self.y), 6),
            "width": round(float(self.width), 6), "height": round(float(self.height), 6),
            "radius": round(float(self.radius), 6), "rotation": round(float(self.rotation), 6),
            "opacity": round(float(self.opacity), 6), "enabled": bool(self.enabled),
            "group_id": self.group_id, "source": self.source,
            "confidence": round(float(self.confidence), 6),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "EditableElement":
        width = max(0.001, float(value.get("width", value.get("radius", 1.0) * 2.0)))
        height = max(0.001, float(value.get("height", value.get("radius", 1.0) * 2.0)))
        return cls(
            id=str(value.get("id", "element")),
            primitive_type=str(value.get("primitive_type", value.get("type", "dot"))),
            x=float(value.get("x", 0.0)), y=float(value.get("y", 0.0)), width=width, height=height,
            radius=max(0.001, float(value.get("radius", min(width, height) / 2.0))),
            rotation=float(value.get("rotation", 0.0)),
            opacity=max(0.0, min(1.0, float(value.get("opacity", 1.0)))),
            enabled=bool(value.get("enabled", True)), group_id=value.get("group_id"),
            source=str(value.get("source", "detected")),
            confidence=max(0.0, min(1.0, float(value.get("confidence", value.get("source_confidence", 0.0))))),
        )

    def contains(self, x: float, y: float) -> bool:
        if not self.enabled:
            return False
        angle = math.radians(-self.rotation)
        dx, dy = x - self.x, y - self.y
        local_x = dx * math.cos(angle) - dy * math.sin(angle)
        local_y = dx * math.sin(angle) + dy * math.cos(angle)
        if self.primitive_type == "line":
            return abs(local_y) <= max(0.35, self.height / 2.0) and abs(local_x) <= max(0.35, self.width / 2.0)
        return (local_x / max(0.001, self.width / 2.0)) ** 2 + (local_y / max(0.001, self.height / 2.0)) ** 2 <= 1.0


@dataclass
class EditablePatternDocument:
    # 用户要求的固定工作单字段。
    canvas: dict[str, Any] = field(default_factory=lambda: {"width": 100.0, "height": 100.0, "units": "percent"})
    reference: dict[str, Any] = field(default_factory=dict)
    generator: dict[str, Any] = field(default_factory=lambda: {"mode": "direct", "base": None, "score": 0.0})
    modifiers: list[dict[str, Any]] = field(default_factory=list)
    elements: list[EditableElement] = field(default_factory=list)
    overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    masks: list[dict[str, Any]] = field(default_factory=list)
    fields: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    # 非渲染基线：Local Override 可跨 Rebuild 保持。
    base_elements: list[EditableElement] = field(default_factory=list)
    added_elements: list[EditableElement] = field(default_factory=list)
    selected_ids: list[str] = field(default_factory=list)
    format_version: int = 2

    def __post_init__(self) -> None:
        if not self.base_elements and self.elements:
            self.base_elements = [item.clone() for item in self.elements]

    @property
    def mode(self) -> str:
        requested = str(self.generator.get("mode", "")).lower()
        if requested in {"direct", "parametric"}:
            return requested
        return "parametric" if self.generator.get("base") and float(self.generator.get("score", 0.0)) > 0.0 else "direct"

    def element(self, element_id: str) -> EditableElement:
        for item in self.elements:
            if item.id == element_id:
                return item
        raise KeyError(f"不存在的可编辑元素：{element_id}")

    def _base_element(self, element_id: str) -> EditableElement | None:
        for item in self.base_elements + self.added_elements:
            if item.id == element_id:
                return item
        return None

    def select_at(self, x: float, y: float, tolerance: float = 0.0, additive: bool = False) -> EditableElement | None:
        for item in reversed(self.elements):
            if item.contains(x, y) or (tolerance > 0 and math.hypot(item.x - x, item.y - y) <= tolerance):
                self.selected_ids = list(dict.fromkeys((self.selected_ids if additive else []) + [item.id]))
                return item
        if not additive:
            self.selected_ids = []
        return None

    def select_rect(self, x0: float, y0: float, x1: float, y1: float, additive: bool = False) -> list[EditableElement]:
        left, right = sorted((x0, x1)); top, bottom = sorted((y0, y1))
        selected = [item for item in self.elements if item.enabled and left <= item.x <= right and top <= item.y <= bottom]
        self.selected_ids = list(dict.fromkeys((self.selected_ids if additive else []) + [item.id for item in selected]))
        return selected

    def move(self, ids: Iterable[str], dx: float, dy: float) -> None:
        for element_id in ids:
            item = self.element(element_id)
            item.x += float(dx); item.y += float(dy)
            override = self.overrides.setdefault(item.id, {})
            override["offset_x"] = float(override.get("offset_x", 0.0)) + float(dx)
            override["offset_y"] = float(override.get("offset_y", 0.0)) + float(dy)

    def move_to(self, element_id: str, x: float, y: float) -> None:
        item = self.element(element_id)
        self.move([element_id], float(x) - item.x, float(y) - item.y)

    def scale(self, ids: Iterable[str], factor: float) -> None:
        factor = max(0.01, float(factor))
        for element_id in ids:
            item = self.element(element_id)
            item.width *= factor; item.height *= factor; item.radius *= factor
            override = self.overrides.setdefault(item.id, {})
            override["size_scale"] = float(override.get("size_scale", 1.0)) * factor

    def set_radius(self, ids: Iterable[str], radius: float) -> None:
        target = max(0.001, float(radius))
        for element_id in list(ids):
            item = self.element(element_id)
            self.scale([element_id], target / max(0.001, item.radius))

    def rotate(self, ids: Iterable[str], degrees: float) -> None:
        for element_id in ids:
            item = self.element(element_id)
            item.rotation += float(degrees)
            override = self.overrides.setdefault(item.id, {})
            override["rotation_offset"] = float(override.get("rotation_offset", 0.0)) + float(degrees)

    def set_rotation(self, ids: Iterable[str], degrees: float) -> None:
        for element_id in list(ids):
            item = self.element(element_id)
            self.rotate([element_id], float(degrees) - item.rotation)

    def set_enabled(self, ids: Iterable[str], enabled: bool) -> None:
        for element_id in ids:
            item = self.element(element_id); item.enabled = bool(enabled)
            self.overrides.setdefault(item.id, {})["enabled"] = bool(enabled)

    def delete(self, ids: Iterable[str] | None = None) -> list[EditableElement]:
        wanted = set(ids or self.selected_ids)
        deleted = [item for item in self.elements if item.id in wanted]
        self.elements = [item for item in self.elements if item.id not in wanted]
        self.selected_ids = [item_id for item_id in self.selected_ids if item_id not in wanted]
        for item in deleted:
            self.overrides.setdefault(item.id, {})["deleted"] = True
        return deleted

    def duplicate(self, ids: Iterable[str] | None = None, dx: float = 2.0, dy: float = 2.0) -> list[EditableElement]:
        wanted = set(ids or self.selected_ids); result: list[EditableElement] = []
        occupied = {item.id for item in self.base_elements + self.added_elements + self.elements}
        for item in list(self.elements):
            if item.id not in wanted:
                continue
            index = 1; clone_id = f"{item.id}-copy-{index:03d}"
            while clone_id in occupied:
                index += 1; clone_id = f"{item.id}-copy-{index:03d}"
            clone = item.clone(); clone.id = clone_id; clone.x += float(dx); clone.y += float(dy); clone.source = "duplicated"
            self.elements.append(clone); self.added_elements.append(clone.clone()); result.append(clone); occupied.add(clone.id)
        self.selected_ids = [item.id for item in result]
        return result

    def group(self, ids: Iterable[str] | None = None, group_id: str | None = None) -> str:
        wanted = set(ids or self.selected_ids)
        group_id = group_id or f"group-{len(self.metadata.get('groups', [])) + 1:04d}"
        for item in self.elements:
            if item.id in wanted:
                item.group_id = group_id
                self.overrides.setdefault(item.id, {})["group_id"] = group_id
        groups = list(self.metadata.get("groups", []))
        if group_id not in groups:
            groups.append(group_id)
        self.metadata["groups"] = groups
        return group_id

    def rebuild(self) -> list[EditableElement]:
        """从 Base Generator + Modifier Stack + Local Overrides 重新物化元素。"""
        from .rebuild import rebuild_document
        return rebuild_document(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "xiaomang-editable-pattern-document", "format_version": self.format_version,
            "canvas": copy.deepcopy(self.canvas), "reference": copy.deepcopy(self.reference),
            "generator": copy.deepcopy(self.generator), "modifiers": copy.deepcopy(self.modifiers),
            "elements": [item.to_dict() for item in self.elements],
            "base_elements": [item.to_dict() for item in self.base_elements],
            "added_elements": [item.to_dict() for item in self.added_elements],
            "overrides": copy.deepcopy(self.overrides), "masks": copy.deepcopy(self.masks),
            "fields": copy.deepcopy(self.fields), "metadata": copy.deepcopy(self.metadata),
            "selected_ids": list(self.selected_ids),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "EditablePatternDocument":
        if value.get("format") not in (None, "xiaomang-editable-pattern-document"):
            raise ValueError("不是 EditablePatternDocument 项目文件")
        elements = [EditableElement.from_dict(item) for item in value.get("elements", []) if isinstance(item, dict)]
        has_baseline = isinstance(value.get("base_elements"), list)
        base = [EditableElement.from_dict(item) for item in value.get("base_elements", []) if isinstance(item, dict)] if has_baseline else [item.clone() for item in elements]
        # v1 文档的 elements 已经是物化结果，不能把旧 override 再应用一遍。
        overrides = {str(k): dict(v) for k, v in value.get("overrides", {}).items() if isinstance(v, dict)} if has_baseline else {}
        added = [EditableElement.from_dict(item) for item in value.get("added_elements", []) if isinstance(item, dict)]
        valid = {item.id for item in elements}
        return cls(
            canvas=dict(value.get("canvas", {})), reference=dict(value.get("reference", {})), generator=dict(value.get("generator", {})),
            modifiers=[dict(item) for item in value.get("modifiers", []) if isinstance(item, dict)], elements=elements,
            base_elements=base, added_elements=added, overrides=overrides,
            masks=[dict(item) for item in value.get("masks", []) if isinstance(item, dict)], fields=dict(value.get("fields", {})),
            metadata=dict(value.get("metadata", {})), selected_ids=[str(item) for item in value.get("selected_ids", []) if str(item) in valid],
            format_version=max(2, int(value.get("format_version", 1))),
        )
