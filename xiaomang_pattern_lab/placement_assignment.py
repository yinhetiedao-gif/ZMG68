"""Unified placement, prototype and assignment primitives.

This module is deliberately UI-free.  It is an additive bridge between the
existing Foundation ``PatternDocument``/Grid model and future multi-shape
editing.  A placement slot describes *where* a cell lives; an
``ElementPrototype`` (the existing, serializable type from ``parametric``)
describes *what* is placed there.  Keeping those concerns separate lets an
imported element be replaced and restored without destroying its source
geometry.

The default configuration is a strict no-op: Circle Grid, no replacement and
randomness disabled produce the same stable ids and geometry as the existing
GridParametricModel.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
import hashlib
import math
from typing import Any, Iterable, Mapping, Sequence

from ppg.foundation.models import ELEMENT_TYPES, Element, PatternDocument

from .parametric import (
    CirclePrototype,
    ElementPrototype,
    EllipsePrototype,
    GridParametricModel,
    PolygonPrototype,
    RectPrototype,
)
from .shared_modifiers import ModifierScope, ModifierScopeMode


PLACEMENT_METADATA_KEY = "xiaomang_pattern_lab.placement_assignment"


@dataclass(frozen=True)
class PlacementSlot:
    """A stable location record independent of the shape placed in it."""

    slot_id: str
    source_element_id: str
    center_x: float
    center_y: float
    width: float
    height: float
    rotation: float = 0.0
    row: int | None = None
    column: int | None = None
    source_type: str = ""
    visible: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "source_element_id": self.source_element_id,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "width": self.width,
            "height": self.height,
            "rotation": self.rotation,
            "row": self.row,
            "column": self.column,
            "source_type": self.source_type,
            "visible": self.visible,
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PlacementSlot":
        return cls(
            slot_id=str(value.get("slot_id", "")),
            source_element_id=str(value.get("source_element_id", value.get("slot_id", ""))),
            center_x=float(value.get("center_x", value.get("x", 0.0))),
            center_y=float(value.get("center_y", value.get("y", 0.0))),
            width=max(0.01, float(value.get("width", 1.0))),
            height=max(0.01, float(value.get("height", 1.0))),
            rotation=float(value.get("rotation", 0.0)),
            row=None if value.get("row") is None else int(value["row"]),
            column=None if value.get("column") is None else int(value["column"]),
            source_type=str(value.get("source_type", "")),
            visible=bool(value.get("visible", True)),
            metadata=deepcopy(dict(value.get("metadata") or {})),
        )


class ImportedElementSlotProvider:
    """Expose existing document elements as stable placement slots."""

    @staticmethod
    def from_elements(elements: Iterable[Element]) -> list[PlacementSlot]:
        return [
            PlacementSlot(
                slot_id=str(element.id),
                source_element_id=str(element.id),
                center_x=float(element.x),
                center_y=float(element.y),
                width=max(0.01, float(element.width)),
                height=max(0.01, float(element.height)),
                rotation=float(element.rotation),
                source_type=str(element.type),
                visible=bool(element.visible),
                metadata={"provider": "imported_element"},
            )
            for element in elements
        ]

    @classmethod
    def from_document(cls, document: PatternDocument) -> list[PlacementSlot]:
        return cls.from_elements(document.elements)


class GridSlotProvider:
    """Adapt the existing GridParametricModel; it does not implement a new Grid."""

    @staticmethod
    def from_model(model: GridParametricModel) -> list[PlacementSlot]:
        model.normalized()
        slots: list[PlacementSlot] = []
        generated = {element.id: element for element in model.generate(include_overrides=True)}
        for row in range(model.rows):
            for column in range(model.columns):
                element_id = model.element_id(row, column)
                element = generated[element_id]
                slots.append(
                    PlacementSlot(
                        slot_id=element_id,
                        source_element_id=element_id,
                        center_x=element.x,
                        center_y=element.y,
                        width=element.width,
                        height=element.height,
                        rotation=element.rotation,
                        row=row,
                        column=column,
                        source_type=element.type,
                        visible=element.visible,
                        metadata={"provider": "grid", "model": "GridParametricModel"},
                    )
                )
        return slots


class ShapePrototypeRegistry:
    """Registry for the existing ``ElementPrototype`` hierarchy.

    No parallel shape class hierarchy is introduced.  Future custom SVG or
    compound prototypes can be registered by id using ``ElementPrototype``.
    """

    def __init__(self, prototypes: Mapping[str, ElementPrototype] | None = None) -> None:
        self._prototypes: dict[str, ElementPrototype] = {}
        if prototypes:
            for identifier, prototype in prototypes.items():
                self.register(identifier, prototype)

    @classmethod
    def with_builtins(cls) -> "ShapePrototypeRegistry":
        registry = cls()
        registry.register("circle", CirclePrototype())
        registry.register("ellipse", EllipsePrototype())
        registry.register("square", RectPrototype(rx_ratio=0.0, ry_ratio=0.0))
        registry.register("rectangle", RectPrototype(rx_ratio=0.0, ry_ratio=0.0))
        # Built-in paths use normalized local coordinates centred at (0, 0).
        # They all flow through the existing generic FilledRegion renderer and
        # SVG exporter; Canvas does not need a branch per named shape.
        registry.register("diamond", _filled_polygon(
            "M 0 -0.5 L 0.5 0 L 0 0.5 L -0.5 0 Z", "diamond",
        ))
        registry.register("triangle", _filled_polygon(
            "M 0 -0.5 L 0.5 0.5 L -0.5 0.5 Z", "triangle",
        ))
        registry.register("star", _filled_polygon(_star_path(), "star"))
        registry.register("line", _filled_polygon(
            "M -0.5 -0.075 L 0.5 -0.075 L 0.5 0.075 L -0.5 0.075 Z", "line",
        ))
        return registry

    def register(self, prototype_id: str, prototype: ElementPrototype) -> None:
        identifier = str(prototype_id).strip()
        if not identifier:
            raise ValueError("Prototype id 不能为空。")
        if not isinstance(prototype, ElementPrototype):
            raise TypeError("Prototype 必须是 ElementPrototype。")
        self._prototypes[identifier] = deepcopy(prototype)

    def get(self, prototype_id: str) -> ElementPrototype:
        try:
            return deepcopy(self._prototypes[str(prototype_id)])
        except KeyError as exc:
            raise KeyError("未注册 Prototype：%s" % prototype_id) from exc

    def ids(self) -> tuple[str, ...]:
        return tuple(self._prototypes.keys())

    def to_dict(self) -> dict[str, dict[str, Any]]:
        return {identifier: prototype.to_dict() for identifier, prototype in self._prototypes.items()}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "ShapePrototypeRegistry":
        registry = cls()
        for identifier, raw in (value or {}).items():
            if isinstance(raw, Mapping):
                registry.register(str(identifier), ElementPrototype.from_dict(dict(raw)))
        return registry


@dataclass
class ReplacementMap:
    """Non-destructive source-slot to prototype mapping."""

    values: dict[str, str] = field(default_factory=dict)

    def set(self, slot_id: str, prototype_id: str) -> None:
        self.values[str(slot_id)] = str(prototype_id)

    def remove(self, slot_id: str) -> None:
        self.values.pop(str(slot_id), None)

    def clear(self) -> None:
        self.values.clear()

    def to_dict(self) -> dict[str, str]:
        return dict(self.values)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "ReplacementMap":
        return cls({str(key): str(item) for key, item in (value or {}).items()})


@dataclass
class ShapePoolEntry:
    """One enabled/weighted prototype in the Gate M Shape Pool.

    This intentionally contains no geometry.  Shape geometry remains owned by
    :class:`ShapePrototypeRegistry`, so a pool cannot become a second Shape
    system or silently copy source Elements.
    """

    prototype_id: str
    weight: float = 0.0
    enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "prototype_id": str(self.prototype_id),
            "weight": max(0.0, float(self.weight)),
            "enabled": bool(self.enabled),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | str) -> "ShapePoolEntry":
        # A historical payload used a simple list of ids.  It remains readable
        # and is intentionally not treated as an active pool unless enabled.
        if isinstance(value, str):
            return cls(prototype_id=value, weight=1.0, enabled=True)
        return cls(
            prototype_id=str(value.get("prototype_id", value.get("id", ""))),
            weight=max(0.0, float(value.get("weight", 0.0))),
            enabled=bool(value.get("enabled", False)),
        )


def default_shape_pool() -> list[ShapePoolEntry]:
    """Return fresh, deterministic product defaults without enabling them."""

    return [
        ShapePoolEntry("circle", 40.0, True),
        ShapePoolEntry("diamond", 25.0, True),
        ShapePoolEntry("star", 20.0, True),
        ShapePoolEntry("triangle", 15.0, True),
        ShapePoolEntry("square", 0.0, False),
        ShapePoolEntry("line", 0.0, False),
    ]


@dataclass
class AssignmentSettings:
    strategy: str = "manual"
    single_prototype_id: str | None = None
    shape_pool: list[str] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "single_prototype_id": self.single_prototype_id,
            "shape_pool": list(self.shape_pool),
            "weights": dict(self.weights),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "AssignmentSettings":
        value = value or {}
        return cls(
            strategy=str(value.get("strategy", "manual")),
            single_prototype_id=value.get("single_prototype_id"),
            shape_pool=[str(item) for item in value.get("shape_pool") or []],
            weights={str(key): float(item) for key, item in (value.get("weights") or {}).items()},
        )


@dataclass
class RandomSettings:
    """One deterministic, non-destructive transform/randomness record.

    ``shape_random`` is retained only for historical AssignmentSettings
    payloads.  Gate M ShapePool uses its own persisted ShapePool seed so a
    transform slider can never silently reshuffle prototypes.  Gate N uses
    this record for Size / Rotation / Position / Occupancy and one shared
    ModifierScope.
    """

    enabled: bool = False
    seed: int = 1
    shape_random: bool = False
    occupancy: float = 1.0
    size_random: float = 0.0
    rotation_random: float = 0.0
    # ``position_jitter`` remains a readable legacy uniform amplitude.
    position_jitter: float = 0.0
    position_jitter_x: float | None = None
    position_jitter_y: float | None = None
    scope: ModifierScope = field(default_factory=ModifierScope)

    def jitter_x(self) -> float:
        return max(0.0, self.position_jitter if self.position_jitter_x is None else self.position_jitter_x)

    def jitter_y(self) -> float:
        return max(0.0, self.position_jitter if self.position_jitter_y is None else self.position_jitter_y)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "seed": self.seed,
            "shape_random": self.shape_random,
            "occupancy": self.occupancy,
            "size_random": self.size_random,
            "rotation_random": self.rotation_random,
            "position_jitter": self.position_jitter,
            "position_jitter_x": self.position_jitter_x,
            "position_jitter_y": self.position_jitter_y,
            "scope": self.scope.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "RandomSettings":
        value = value or {}
        legacy_jitter = max(0.0, float(value.get("position_jitter", 0.0)))
        raw_jitter_x, raw_jitter_y = value.get("position_jitter_x"), value.get("position_jitter_y")
        return cls(
            enabled=bool(value.get("enabled", False)),
            seed=int(value.get("seed", 1)),
            shape_random=bool(value.get("shape_random", False)),
            occupancy=min(1.0, max(0.0, float(value.get("occupancy", 1.0)))),
            size_random=min(1.0, max(0.0, float(value.get("size_random", 0.0)))),
            rotation_random=max(0.0, float(value.get("rotation_random", 0.0))),
            position_jitter=legacy_jitter,
            position_jitter_x=None if raw_jitter_x is None else max(0.0, float(raw_jitter_x)),
            position_jitter_y=None if raw_jitter_y is None else max(0.0, float(raw_jitter_y)),
            scope=ModifierScope.from_dict(value.get("scope")),
        )


def deterministic_unit(seed: int, slot_id: str, channel: str) -> float:
    """Stable [0,1) value; independent of process/hash randomisation."""

    digest = hashlib.sha256(f"{int(seed)}|{slot_id}|{channel}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


class AssignmentEngine:
    """Evaluate slots without mutating their source document elements."""

    def __init__(self, registry: ShapePrototypeRegistry | None = None) -> None:
        self.registry = registry or ShapePrototypeRegistry.with_builtins()

    @staticmethod
    def _weighted_pick_entries(entries: Sequence[ShapePoolEntry], slot: PlacementSlot,
                               seed: int) -> str | None:
        """Select a prototype using only stable persisted inputs.

        SHA-256 is deliberately used rather than Python ``hash`` or global
        ``random``.  Evaluation order, canvas zoom and a process restart can
        therefore never change the selected shape for a stable PlacementSlot.
        """

        candidates = [entry for entry in entries if entry.enabled and entry.weight > 0.0]
        weights = [max(0.0, float(entry.weight)) for entry in candidates]
        total = sum(weights)
        if total <= 0.0:
            return None
        target = deterministic_unit(seed, slot.slot_id, "shape_assignment") * total
        for entry, weight in zip(candidates, weights):
            target -= weight
            if target <= 0:
                return entry.prototype_id
        return candidates[-1].prototype_id

    @staticmethod
    def _legacy_pool_entries(settings: AssignmentSettings) -> list[ShapePoolEntry]:
        return [
            ShapePoolEntry(identifier, settings.weights.get(identifier, 1.0), True)
            for identifier in settings.shape_pool
        ]

    @classmethod
    def shape_assignment_for(cls, slot: PlacementSlot, *, shape_pool: Sequence[ShapePoolEntry],
                             seed: int) -> str | None:
        """Public deterministic Shape Pool lookup used by tests and diagnostics."""

        return cls._weighted_pick_entries(shape_pool, slot, int(seed))

    def _prototype_id_for(self, slot: PlacementSlot, settings: AssignmentSettings,
                          replacement_map: ReplacementMap, random_settings: RandomSettings,
                          shape_pool: Sequence[ShapePoolEntry] | None = None,
                          shape_pool_enabled: bool = False,
                          shape_random_seed: int | None = None,
                          shape_pool_scope: ModifierScope | None = None,
                          scope_element: Element | None = None) -> str | None:
        # Manual editing always wins over any generated assignment.
        if slot.slot_id in replacement_map.values:
            return replacement_map.values[slot.slot_id]
        if shape_pool_enabled:
            # Scope is deliberately evaluated after the manual ReplacementMap
            # precedence rule.  A local, explicit edit must survive a later
            # change to the generated Shape Pool area.
            if shape_pool_scope is not None:
                if scope_element is None and shape_pool_scope.mode is not ModifierScopeMode.ALL:
                    return None
                if scope_element is not None and not shape_pool_scope.contains(scope_element):
                    return None
            return self.shape_assignment_for(
                slot,
                shape_pool=shape_pool or (),
                seed=random_settings.seed if shape_random_seed is None else shape_random_seed,
            )
        if settings.strategy == "single":
            return settings.single_prototype_id
        if settings.strategy in {"weighted_random", "random"} and random_settings.enabled and random_settings.shape_random:
            return self.shape_assignment_for(slot, shape_pool=self._legacy_pool_entries(settings), seed=random_settings.seed)
        if settings.strategy == "checkerboard" and settings.shape_pool:
            index = ((slot.row or 0) + (slot.column or 0)) % len(settings.shape_pool)
            return settings.shape_pool[index]
        return None

    def evaluate(self, slots: Iterable[PlacementSlot], source_elements: Mapping[str, Element] | Iterable[Element],
                 *, replacement_map: ReplacementMap | None = None,
                 assignment: AssignmentSettings | None = None,
                 random_settings: RandomSettings | None = None,
                 shape_pool: Sequence[ShapePoolEntry] | None = None,
                 shape_pool_enabled: bool = False,
                 shape_random_seed: int | None = None,
                 shape_pool_scope: ModifierScope | None = None) -> list[Element]:
        source_map = {element.id: element for element in source_elements} if not isinstance(source_elements, Mapping) else dict(source_elements)
        replacement_map = replacement_map or ReplacementMap()
        assignment = assignment or AssignmentSettings()
        random_settings = random_settings or RandomSettings()
        output: list[Element] = []
        for slot in slots:
            source = source_map.get(slot.source_element_id) or source_map.get(slot.slot_id)
            # A Scope measures the current placement position rather than the
            # stale source snapshot.  It therefore remains correct after a
            # Grid structure rebuild or a persisted local slot transform.
            scope_element = None
            if source is not None:
                scope_element = deepcopy(source)
                scope_element.id = slot.source_element_id or slot.slot_id
                scope_element.x, scope_element.y = slot.center_x, slot.center_y
                scope_element.width, scope_element.height = slot.width, slot.height
                scope_element.rotation, scope_element.visible = slot.rotation, slot.visible
            prototype_id = self._prototype_id_for(
                slot, assignment, replacement_map, random_settings,
                shape_pool=shape_pool,
                shape_pool_enabled=shape_pool_enabled,
                shape_random_seed=shape_random_seed,
                shape_pool_scope=shape_pool_scope,
                scope_element=scope_element,
            )
            if prototype_id is None:
                if source is None:
                    continue
                # Original geometry remains the base if neither a manual nor
                # a ShapePool assignment applies.  Gate N must still work for
                # ordinary imported/free Elements, not only prototypes.
                derived = deepcopy(source)
            else:
                prototype = self.registry.get(prototype_id)
                derived = prototype.instantiate(
                    element_id=slot.source_element_id or slot.slot_id,
                    x=slot.center_x, y=slot.center_y,
                    width=slot.width, height=slot.height,
                    rotation=slot.rotation, visible=slot.visible,
                )

            # Random transform is a separate channel group and is evaluated
            # after Shape Assignment but before the existing Modifier Stack.
            # The same Scope semantics as Gate J/M.1 prevent it from touching
            # source geometry or elements outside the intended region.
            random_in_scope = (
                random_settings.enabled
                and (scope_element is None or random_settings.scope.contains(scope_element))
            )
            if random_in_scope:
                if random_settings.size_random:
                    factor = 1.0 + (
                        deterministic_unit(random_settings.seed, slot.slot_id, "size") * 2.0 - 1.0
                    ) * random_settings.size_random
                    derived.width = max(0.01, derived.width * factor)
                    derived.height = max(0.01, derived.height * factor)
                if random_settings.rotation_random:
                    derived.rotation += (
                        deterministic_unit(random_settings.seed, slot.slot_id, "rotation") * 2.0 - 1.0
                    ) * random_settings.rotation_random
                jitter_x, jitter_y = random_settings.jitter_x(), random_settings.jitter_y()
                if jitter_x:
                    derived.x += (
                        deterministic_unit(random_settings.seed, slot.slot_id, "offset_x") * 2.0 - 1.0
                    ) * jitter_x
                if jitter_y:
                    derived.y += (
                        deterministic_unit(random_settings.seed, slot.slot_id, "offset_y") * 2.0 - 1.0
                    ) * jitter_y
                if random_settings.occupancy < 1.0:
                    derived.visible = bool(derived.visible) and (
                        deterministic_unit(random_settings.seed, slot.slot_id, "occupancy") < random_settings.occupancy
                    )
            output.append(derived)
        return output


@dataclass
class PlacementAssignmentState:
    """Serializable state kept in PatternDocument metadata when enabled."""

    slots: list[PlacementSlot] = field(default_factory=list)
    prototypes: ShapePrototypeRegistry = field(default_factory=ShapePrototypeRegistry.with_builtins)
    replacement_map: ReplacementMap = field(default_factory=ReplacementMap)
    assignment: AssignmentSettings = field(default_factory=AssignmentSettings)
    random: RandomSettings = field(default_factory=RandomSettings)
    # Gate M's product-facing state.  ``assignment`` / ``random`` above stay
    # only as a backward-compatible reader for early experimental documents.
    shape_pool: list[ShapePoolEntry] = field(default_factory=default_shape_pool)
    shape_pool_enabled: bool = False
    shape_random_seed: int = 1
    # Gate M.1 reuses the one shared scope value object used by Modifier Stack.
    # An omitted field in a historical PatternDocument safely means All.
    shape_pool_scope: ModifierScope = field(default_factory=ModifierScope)
    # Durable audit/source snapshot used to restore the original shape after
    # any number of evaluations or a Save/Load cycle.  It is never Canvas
    # state and is absent in old payloads, which remain valid.
    source_elements: list[dict[str, Any]] = field(default_factory=list)
    enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        assignment_payload = self.assignment.to_dict()
        return {
            "version": 4,
            "enabled": self.enabled,
            "slots": [slot.to_dict() for slot in self.slots],
            "shape_prototypes": self.prototypes.to_dict(),
            "replacement_map": self.replacement_map.to_dict(),
            "shape_pool": [entry.to_dict() for entry in self.shape_pool],
            "shape_pool_enabled": bool(self.shape_pool_enabled),
            "shape_random_seed": int(self.shape_random_seed),
            "shape_pool_scope": self.shape_pool_scope.to_dict(),
            "assignment_settings": assignment_payload,
            "random_settings": self.random.to_dict(),
            "source_elements": deepcopy(self.source_elements),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "PlacementAssignmentState":
        value = value or {}
        raw_prototypes = value.get("shape_prototypes")
        prototypes = ShapePrototypeRegistry.from_dict(raw_prototypes) if raw_prototypes else ShapePrototypeRegistry.with_builtins()
        assignment_payload = dict(value.get("assignment_settings") or {})
        # ``shape_pool`` was initially nested under assignment_settings; keep
        # accepting and emitting the explicit top-level field for schema
        # migration and easier project inspection.
        raw_pool = value.get("shape_pool") or []
        if ("shape_pool" in value and "shape_pool" not in assignment_payload
                and all(isinstance(item, str) for item in raw_pool)):
            assignment_payload["shape_pool"] = raw_pool
        if raw_pool and all(isinstance(item, str) for item in raw_pool):
            pool = [ShapePoolEntry.from_dict(item) for item in raw_pool]
        elif raw_pool:
            pool = [ShapePoolEntry.from_dict(item) for item in raw_pool if isinstance(item, (str, Mapping))]
        else:
            pool = default_shape_pool()
        return cls(
            slots=[PlacementSlot.from_dict(item) for item in value.get("slots") or []],
            prototypes=prototypes,
            replacement_map=ReplacementMap.from_dict(value.get("replacement_map")),
            assignment=AssignmentSettings.from_dict(assignment_payload),
            random=RandomSettings.from_dict(value.get("random_settings")),
            shape_pool=pool,
            shape_pool_enabled=bool(value.get("shape_pool_enabled", False)),
            shape_random_seed=int(value.get("shape_random_seed", value.get("random_settings", {}).get("seed", 1))),
            shape_pool_scope=ModifierScope.from_dict(value.get("shape_pool_scope")),
            source_elements=[deepcopy(dict(item)) for item in value.get("source_elements") or [] if isinstance(item, Mapping)],
            enabled=bool(value.get("enabled", False)),
        )

    def set_source_elements(self, elements: Iterable[Element]) -> None:
        self.source_elements = [asdict(element) for element in elements]

    def source_snapshot(self) -> list[Element]:
        result: list[Element] = []
        for raw in self.source_elements:
            values = deepcopy(dict(raw))
            kind = str(values.pop("type"))
            result.append(ELEMENT_TYPES[kind](**values))
        return result

    def attach(self, document: PatternDocument) -> None:
        document.metadata[PLACEMENT_METADATA_KEY] = self.to_dict()

    def pool_entry(self, prototype_id: str) -> ShapePoolEntry:
        for entry in self.shape_pool:
            if entry.prototype_id == str(prototype_id):
                return entry
        entry = ShapePoolEntry(str(prototype_id), 0.0, False)
        self.shape_pool.append(entry)
        return entry

    def has_active_pool_candidates(self) -> bool:
        return any(entry.enabled and entry.weight > 0.0 for entry in self.shape_pool)

    def reset_shape_pool(self) -> None:
        """Reset only Gate M state; replacements and source snapshots survive."""

        self.shape_pool = default_shape_pool()
        self.shape_pool_enabled = False
        self.shape_random_seed = 1
        self.shape_pool_scope = ModifierScope()

    @classmethod
    def from_document(cls, document: PatternDocument) -> "PlacementAssignmentState":
        return cls.from_dict(document.metadata.get(PLACEMENT_METADATA_KEY))


def default_circle_grid_state(model: GridParametricModel) -> PlacementAssignmentState:
    """Build the Gate 1 compatibility state without changing old output."""

    source = model.generate(include_overrides=True)
    registry = ShapePrototypeRegistry.with_builtins()
    return PlacementAssignmentState(
        slots=GridSlotProvider.from_model(model),
        prototypes=registry,
        replacement_map=ReplacementMap(),
        assignment=AssignmentSettings(strategy="manual"),
        random=RandomSettings(),
        source_elements=[asdict(element) for element in source],
        enabled=False,
    )


def _filled_polygon(path_data: str, name: str) -> PolygonPrototype:
    """Create a normalized, renderer-independent built-in shape prototype."""

    return PolygonPrototype(
        path_data=path_data,
        base_x=0.0,
        base_y=0.0,
        base_width=1.0,
        base_height=1.0,
        filled=True,
        style={"fill": "#000000", "stroke": "none"},
        metadata={"builtin_shape": name, "normalized_local_coordinates": True},
    )


def _star_path(points: int = 5, inner_radius: float = 0.22,
               outer_radius: float = 0.5) -> str:
    coordinates: list[tuple[float, float]] = []
    for index in range(points * 2):
        angle = -math.pi / 2.0 + index * math.pi / points
        radius = outer_radius if index % 2 == 0 else inner_radius
        coordinates.append((math.cos(angle) * radius, math.sin(angle) * radius))
    return "M " + " L ".join("%.8g %.8g" % point for point in coordinates) + " Z"
