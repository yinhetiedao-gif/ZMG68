"""Gate 1 coverage for the unified placement/prototype assignment layer."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ppg.foundation import Canvas, CircleElement, PatternDocument, Reference, pattern_document_to_svg
from xiaomang_pattern_lab.parametric import GridParametricModel
from xiaomang_pattern_lab.evaluation import evaluate_pattern_document
from xiaomang_pattern_lab.placement_assignment import (
    AssignmentEngine,
    AssignmentSettings,
    GridSlotProvider,
    ImportedElementSlotProvider,
    PlacementAssignmentState,
    RandomSettings,
    ReplacementMap,
    ShapePrototypeRegistry,
)


class PlacementAssignmentTests(unittest.TestCase):
    def test_imported_slots_preserve_source_ids_and_geometry(self) -> None:
        elements = [
            CircleElement(id="dot-a", x=12.5, y=24.0, width=6.0, height=6.0, rotation=4.0),
            CircleElement(id="dot-b", x=42.0, y=24.0, width=10.0, height=10.0),
        ]
        slots = ImportedElementSlotProvider.from_elements(elements)
        self.assertEqual([slot.slot_id for slot in slots], ["dot-a", "dot-b"])
        self.assertEqual((slots[0].center_x, slots[0].center_y), (12.5, 24.0))
        self.assertEqual(slots[1].width, 10.0)

    def test_grid_provider_reuses_existing_stable_grid_ids(self) -> None:
        model = GridParametricModel(rows=2, columns=3, spacing_x=20, spacing_y=30, element_width=8)
        slots = GridSlotProvider.from_model(model)
        self.assertEqual([slot.slot_id for slot in slots], [
            "grid:r0:c0", "grid:r0:c1", "grid:r0:c2",
            "grid:r1:c0", "grid:r1:c1", "grid:r1:c2",
        ])
        self.assertEqual([(slot.row, slot.column) for slot in slots[:2]], [(0, 0), (0, 1)])

    def test_default_assignment_is_a_noop_for_circle_grid(self) -> None:
        model = GridParametricModel(rows=3, columns=4, spacing_x=15, spacing_y=17, element_width=7)
        source = model.generate()
        slots = GridSlotProvider.from_model(model)
        result = AssignmentEngine().evaluate(slots, source)
        self.assertEqual([item.id for item in result], [item.id for item in source])
        for expected, actual in zip(source, result):
            self.assertEqual(type(expected), type(actual))
            self.assertAlmostEqual(expected.x, actual.x)
            self.assertAlmostEqual(expected.y, actual.y)
            self.assertAlmostEqual(expected.width, actual.width)
            self.assertAlmostEqual(expected.height, actual.height)
            self.assertAlmostEqual(expected.rotation, actual.rotation)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = PatternDocument(Canvas(100, 100), Reference(""), source)
            assigned = PatternDocument(Canvas(100, 100), Reference(""), result)
            pattern_document_to_svg(legacy, str(root / "legacy.svg"))
            pattern_document_to_svg(assigned, str(root / "assigned.svg"))
            self.assertEqual((root / "legacy.svg").read_bytes(), (root / "assigned.svg").read_bytes())

    def test_replacement_is_non_destructive_and_restorable(self) -> None:
        elements = [CircleElement(id="dot-1", x=20, y=30, width=6, height=6)]
        slots = ImportedElementSlotProvider.from_elements(elements)
        registry = ShapePrototypeRegistry.with_builtins()
        replacement = ReplacementMap()
        replacement.set("dot-1", "ellipse")
        engine = AssignmentEngine(registry)
        replaced = engine.evaluate(slots, elements, replacement_map=replacement)
        self.assertEqual(replaced[0].id, "dot-1")
        self.assertEqual(replaced[0].type, "ellipse")
        self.assertEqual(elements[0].type, "circle")
        replacement.clear()
        restored = engine.evaluate(slots, elements, replacement_map=replacement)
        self.assertEqual(restored[0].type, "circle")
        self.assertAlmostEqual(restored[0].width, 6.0)

    def test_seeded_shape_randomness_is_stable_per_slot(self) -> None:
        elements = [CircleElement(id="dot-%d" % index, x=index * 10, y=20, width=6, height=6) for index in range(5)]
        slots = ImportedElementSlotProvider.from_elements(elements)
        settings = AssignmentSettings(strategy="weighted_random", shape_pool=["circle", "ellipse"])
        random_settings = RandomSettings(enabled=True, seed=42, shape_random=True, rotation_random=17, size_random=0.2)
        engine = AssignmentEngine(ShapePrototypeRegistry.with_builtins())
        first = engine.evaluate(slots, elements, assignment=settings, random_settings=random_settings)
        second = engine.evaluate(slots, elements, assignment=settings, random_settings=random_settings)
        self.assertEqual([(item.type, round(item.x, 6), round(item.width, 6), round(item.rotation, 6)) for item in first],
                         [(item.type, round(item.x, 6), round(item.width, 6), round(item.rotation, 6)) for item in second])

    def test_state_attaches_to_pattern_document_and_round_trips(self) -> None:
        model = GridParametricModel(rows=2, columns=2)
        state = PlacementAssignmentState(
            slots=GridSlotProvider.from_model(model),
            prototypes=ShapePrototypeRegistry.with_builtins(),
            replacement_map=ReplacementMap({"grid:r0:c0": "ellipse"}),
            assignment=AssignmentSettings(strategy="single", single_prototype_id="ellipse"),
            random=RandomSettings(enabled=False, seed=99),
            enabled=True,
        )
        document = PatternDocument(Canvas(100, 100, unit="mm", mm_per_unit=1.0), Reference(""), model.generate())
        state.attach(document)
        reloaded = PlacementAssignmentState.from_document(PatternDocument.from_dict(document.to_dict()))
        self.assertTrue(reloaded.enabled)
        self.assertEqual(len(reloaded.slots), 4)
        self.assertEqual(reloaded.replacement_map.values["grid:r0:c0"], "ellipse")
        self.assertEqual(reloaded.assignment.single_prototype_id, "ellipse")
        self.assertEqual(reloaded.random.seed, 99)

    def test_enabled_state_uses_assignment_layer_without_changing_document_sources(self) -> None:
        source = [CircleElement(id="dot-1", x=20, y=30, width=6, height=6)]
        document = PatternDocument(Canvas(100, 100, unit="mm", mm_per_unit=1.0), Reference(""), source)
        state = PlacementAssignmentState(
            slots=ImportedElementSlotProvider.from_elements(source),
            prototypes=ShapePrototypeRegistry.with_builtins(),
            replacement_map=ReplacementMap({"dot-1": "ellipse"}),
            enabled=True,
        )
        state.attach(document)
        evaluated = evaluate_pattern_document(document)
        self.assertEqual(evaluated[0].type, "ellipse")
        self.assertEqual(document.elements[0].type, "circle")


if __name__ == "__main__":
    unittest.main()
