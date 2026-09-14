"""Versioned, local-only parametric presets for Xiaomang Pattern Lab.

A preset is intentionally an *effect recipe*, not a project snapshot.  It has
no raster reference, source geometry, selection, viewport state, placement
slots, replacement map, or local overrides.  That boundary lets the same
recipe be applied to a different PatternDocument without ever rewriting its
editable source elements.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable, Mapping
from uuid import uuid4

from ppg.foundation.models import Element


PRESET_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class GeometryBounds:
    """World-coordinate bounds used to adapt an effect recipe to new geometry."""

    min_x: float
    min_y: float
    width: float
    height: float

    @property
    def max_x(self) -> float:
        return self.min_x + self.width

    @property
    def max_y(self) -> float:
        return self.min_y + self.height

    @property
    def diagonal(self) -> float:
        return math.hypot(self.width, self.height)

    def to_dict(self) -> dict[str, float]:
        return {"min_x": self.min_x, "min_y": self.min_y, "width": self.width, "height": self.height}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "GeometryBounds | None":
        if not isinstance(value, Mapping):
            return None
        try:
            width, height = float(value["width"]), float(value["height"])
            if width <= 0.0 or height <= 0.0:
                return None
            return cls(float(value["min_x"]), float(value["min_y"]), width, height)
        except (KeyError, TypeError, ValueError):
            return None


def bounds_from_elements(elements: Iterable[Element]) -> GeometryBounds:
    items = list(elements)
    if not items:
        # An empty document cannot meaningfully host a visible effect, but a
        # stable non-zero range keeps a malformed preset from dividing by zero.
        return GeometryBounds(0.0, 0.0, 1.0, 1.0)
    min_x = min(item.x - item.width / 2.0 for item in items)
    min_y = min(item.y - item.height / 2.0 for item in items)
    max_x = max(item.x + item.width / 2.0 for item in items)
    max_y = max(item.y + item.height / 2.0 for item in items)
    return GeometryBounds(min_x, min_y, max(0.01, max_x - min_x), max(0.01, max_y - min_y))


def _without_selection(scope: Mapping[str, Any] | None) -> dict[str, Any]:
    """Scopes are reusable; volatile Element selection ids are not."""

    result = deepcopy(dict(scope or {}))
    if str(result.get("mode", "all")) == "selected":
        result["selected_element_ids"] = []
    return result


def _sanitize_stack(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """Retain effect configuration while deliberately excluding target data."""

    value = deepcopy(dict(raw or {}))
    value.pop("source_elements", None)
    value.pop("local_overrides", None)
    value.pop("source_kind", None)
    value["modifiers"] = [
        {**deepcopy(dict(item)), "scope": _without_selection(item.get("scope"))}
        for item in value.get("modifiers", []) if isinstance(item, Mapping)
    ]
    # Legacy stack fields have no selected scope, but are kept for backward
    # compatibility with documents saved before explicit Gate-H layers.
    return value


def _sanitize_assignment(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """Keep ShapePool/Random settings but not geometry-bound placement state."""

    value = deepcopy(dict(raw or {}))
    kept = {
        "version": int(value.get("version", 4)),
        "enabled": bool(value.get("enabled", False)),
        "shape_prototypes": deepcopy(value.get("shape_prototypes") or {}),
        "shape_pool": deepcopy(value.get("shape_pool") or []),
        "shape_pool_enabled": bool(value.get("shape_pool_enabled", False)),
        "shape_random_seed": int(value.get("shape_random_seed", 1)),
        "shape_pool_scope": _without_selection(value.get("shape_pool_scope")),
        "assignment_settings": deepcopy(value.get("assignment_settings") or {}),
        "random_settings": deepcopy(value.get("random_settings") or {}),
    }
    if isinstance(kept["random_settings"], Mapping):
        kept["random_settings"]["scope"] = _without_selection(kept["random_settings"].get("scope"))
    return kept


def _sanitize_shape_pool(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    value = deepcopy(dict(raw or {}))
    value["shape_pool_scope"] = _without_selection(value.get("shape_pool_scope"))
    return value


def _sanitize_random_settings(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    value = deepcopy(dict(raw or {}))
    value["scope"] = _without_selection(value.get("scope"))
    return value


@dataclass
class ParametricPreset:
    """Portable effect configuration persisted separately from projects."""

    name: str
    fields: list[dict[str, Any]] = field(default_factory=list)
    modifiers: list[dict[str, Any]] = field(default_factory=list)
    shared_modifier_stack: dict[str, Any] = field(default_factory=dict)
    shape_pool: dict[str, Any] = field(default_factory=dict)
    assignment_settings: dict[str, Any] = field(default_factory=dict)
    random_settings: dict[str, Any] = field(default_factory=dict)
    source_bounds: GeometryBounds | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    preset_id: str = field(default_factory=lambda: str(uuid4()))
    schema_version: int = PRESET_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "preset_id": self.preset_id,
            "name": self.name,
            "fields": deepcopy(self.fields),
            "modifiers": deepcopy(self.modifiers),
            "shared_modifier_stack": _sanitize_stack(self.shared_modifier_stack),
            "shape_pool": _sanitize_shape_pool(self.shape_pool),
            "assignment_settings": deepcopy(self.assignment_settings),
            "random_settings": _sanitize_random_settings(self.random_settings),
            "source_bounds": self.source_bounds.to_dict() if self.source_bounds else None,
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ParametricPreset":
        if not isinstance(value, Mapping):
            raise ValueError("参数预设必须是 JSON 对象。")
        version = int(value.get("schema_version", 0))
        if version > PRESET_SCHEMA_VERSION:
            raise ValueError("该参数预设版本较新，当前版本无法安全读取。")
        name = str(value.get("name", "未命名预设")).strip() or "未命名预设"
        return cls(
            schema_version=version or PRESET_SCHEMA_VERSION,
            preset_id=str(value.get("preset_id") or uuid4()),
            name=name,
            fields=[deepcopy(dict(item)) for item in value.get("fields", []) if isinstance(item, Mapping)],
            modifiers=[deepcopy(dict(item)) for item in value.get("modifiers", []) if isinstance(item, Mapping)],
            shared_modifier_stack=_sanitize_stack(value.get("shared_modifier_stack")),
            shape_pool=_sanitize_shape_pool(value.get("shape_pool")),
            assignment_settings=deepcopy(dict(value.get("assignment_settings") or {})),
            random_settings=_sanitize_random_settings(value.get("random_settings")),
            source_bounds=GeometryBounds.from_dict(value.get("source_bounds")),
            metadata=deepcopy(dict(value.get("metadata") or {})),
        )

    def copy_named(self, name: str) -> "ParametricPreset":
        clone = ParametricPreset.from_dict(self.to_dict())
        clone.preset_id = str(uuid4())
        clone.name = str(name).strip() or (self.name + " 副本")
        return clone


def _adapt_number(key: str, value: float, source: GeometryBounds, target: GeometryBounds) -> float:
    sx, sy = target.width / source.width, target.height / source.height
    average = (sx + sy) / 2.0
    if key in {"center_x", "origin_x"}:
        return target.min_x + ((value - source.min_x) / source.width) * target.width
    if key in {"center_y", "origin_y"}:
        return target.min_y + ((value - source.min_y) / source.height) * target.height
    if key.endswith("_x") and key in {"offset_x", "position_jitter_x"}:
        return value * sx
    if key.endswith("_y") and key in {"offset_y", "position_jitter_y"}:
        return value * sy
    if key in {"width", "cell_width"}:
        return value * sx
    if key in {"height", "cell_height"}:
        return value * sy
    if key in {"radius", "ring_width", "wavelength", "amount", "position_jitter"}:
        return value * average
    return value


def adapt_effect_config(value: Any, source: GeometryBounds | None, target: GeometryBounds) -> Any:
    """Map documented world-coordinate parameters to target geometry bounds.

    Unitless controls (strength, angle, seed, weights, occupancy) remain exact.
    The deliberately small mapping list prevents arbitrary numeric metadata from
    being reinterpreted as a length.
    """

    if source is None:
        return deepcopy(value)
    if isinstance(value, Mapping):
        return {str(key): adapt_effect_config(item, source, target) if not isinstance(item, (int, float)) or isinstance(item, bool)
                else _adapt_number(str(key), float(item), source, target)
                for key, item in value.items()}
    if isinstance(value, list):
        return [adapt_effect_config(item, source, target) for item in value]
    return deepcopy(value)


class PresetRepository:
    """Independent local storage; failures in one file cannot block the Lab."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, preset_id: str) -> Path:
        return self.root / (str(preset_id) + ".preset.json")

    def list(self) -> list[ParametricPreset]:
        result: list[ParametricPreset] = []
        for path in sorted(self.root.glob("*.preset.json"), key=lambda item: item.name.lower()):
            try:
                result.append(ParametricPreset.from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, ValueError, json.JSONDecodeError):
                # Invalid or future presets are intentionally skipped.  The
                # caller can surface a warning in its conversion log.
                continue
        return sorted(result, key=lambda item: item.name.casefold())

    def get(self, preset_id: str) -> ParametricPreset:
        path = self._path(preset_id)
        if not path.is_file():
            raise KeyError("找不到参数预设：%s" % preset_id)
        return ParametricPreset.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, preset: ParametricPreset) -> ParametricPreset:
        path = self._path(preset.preset_id)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(preset.to_dict(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)
        return preset

    def delete(self, preset_id: str) -> None:
        path = self._path(preset_id)
        if not path.is_file():
            raise KeyError("找不到参数预设：%s" % preset_id)
        path.unlink()
