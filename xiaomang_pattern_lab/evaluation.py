"""Single non-UI evaluation entry point for Matrix Parametric V1.

``PatternDocument`` remains the only persistent model; the Canvas never owns a
parallel geometry list.  In Free mode the document's editable Elements are the
result.  In Grid mode the compact model plus modifiers and local overrides are
evaluated to the same Foundation Element types immediately before render,
export, save validation or a deliberate bake.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from typing import Iterable

from ppg.foundation.models import Element, PatternDocument

from .parametric import PARAMETRIC_METADATA_KEY, GridParametricModel, PatternMode
from .parametric_families import parametric_model_from_payload
from .placement_assignment import AssignmentEngine, PlacementAssignmentState
from .shared_modifiers import SharedModifierStack


def serialize_elements(elements: Iterable[Element]) -> list[dict]:
    """Store original imported geometry without retaining any Canvas state."""

    return [asdict(element) for element in elements]


def grid_model_from_document(document: PatternDocument) -> GridParametricModel | None:
    payload = document.metadata.get(PARAMETRIC_METADATA_KEY)
    if not isinstance(payload, dict) or payload.get("mode") != PatternMode.GRID.value:
        return None
    # ``model`` is the canonical family payload used by the newer generic
    # session.  Keep accepting the historical ``grid`` and
    # ``parametric_model`` keys so old projects remain loadable.
    raw_model = payload.get("grid") or payload.get("model") or payload.get("parametric_model")
    return GridParametricModel.from_dict(raw_model) if isinstance(raw_model, dict) else None


def parametric_model_from_document(document: PatternDocument):
    """Read any family from compact metadata, while retaining Grid projects."""
    payload = document.metadata.get(PARAMETRIC_METADATA_KEY)
    if not isinstance(payload, dict): return None
    mode = str(payload.get("mode", ""))
    if mode == PatternMode.GRID.value:
        return grid_model_from_document(document)
    raw_model = payload.get("model") or payload.get("parametric_model")
    return parametric_model_from_payload(mode, raw_model) if isinstance(raw_model, dict) else None


def evaluate_pattern_document(document: PatternDocument) -> list[Element]:
    """Evaluate one document into transient final Foundation Elements.

    There is deliberately no ``final_elements`` state in the model.  The caller
    may choose to materialise this result into the existing compatibility
    ``document.elements`` collection for the current Canvas frame, but all
    authoritative parametric information remains compact in metadata.
    """

    # Placement/assignment is an opt-in additive layer.  Existing projects do
    # not carry this metadata and therefore follow the exact legacy path.
    placement_raw = document.metadata.get("xiaomang_pattern_lab.placement_assignment")
    shared_modifiers = SharedModifierStack.from_document(document)
    if isinstance(placement_raw, dict) and bool(placement_raw.get("enabled", False)):
        state = PlacementAssignmentState.from_dict(placement_raw)
        source = shared_modifiers.source_snapshot() if shared_modifiers and shared_modifiers.source_elements else document.elements
        evaluated = AssignmentEngine(state.prototypes).evaluate(
            state.slots,
            source,
            replacement_map=state.replacement_map,
            assignment=state.assignment,
            random_settings=state.random,
        )
        return shared_modifiers.apply(evaluated) if shared_modifiers else evaluated
    model = parametric_model_from_document(document)
    if model is None:
        source = shared_modifiers.source_snapshot() if shared_modifiers and shared_modifiers.source_elements else document.elements
        return shared_modifiers.apply(source) if shared_modifiers else deepcopy(document.elements)
    evaluated = model.generate()
    return shared_modifiers.apply(evaluated) if shared_modifiers else evaluated


def materialize_evaluated_elements(document: PatternDocument) -> list[Element]:
    """Refresh the one existing Element collection from the Evaluate pipeline."""

    document.elements = evaluate_pattern_document(document)
    document._sync_transforms()
    document.validate()
    return document.elements
