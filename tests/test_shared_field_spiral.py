"""Gate E: SpiralField polar scalar and shared modifier integration."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import math
import unittest

from ppg.foundation import Canvas, CircleElement, FoundationPipeline, PatternDocument, Reference
from xiaomang_pattern_lab.evaluation import evaluate_pattern_document
from xiaomang_pattern_lab.parametric import GridParametricModel, PARAMETRIC_METADATA_KEY
from xiaomang_pattern_lab.parametric_families import SizeFieldMode, SizeFieldModifier
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.shared_fields import FieldContext, FieldMapping, FieldRegistry, RotationModifier, SharedFieldEngine, SizeModifier, SpiralField
from xiaomang_pattern_lab.shared_modifiers import SharedModifierStack


def probes():
    return [CircleElement("east", 20, 0, 4, 4), CircleElement("north", 0, 20, 4, 4),
            CircleElement("west", -20, 0, 4, 4), CircleElement("south", 0, -20, 4, 4)]


class SpiralFieldTests(unittest.TestCase):
    def test_spiral_is_finite_bounded_and_deterministic(self):
        field = SpiralField("spiral", center_x=0, center_y=0, turns=3, phase=.2, falloff=1.4)
        context = FieldContext((-40, -40, 40, 40))
        first = [field.evaluate(item, context) for item in probes()]
        second = [field.evaluate(item, context) for item in probes()]
        self.assertEqual(first, second)
        self.assertTrue(all(0 <= value <= 1 and math.isfinite(value) for value in first))

    def test_spiral_direction_phase_center_and_turns_change_field(self):
        context = FieldContext((-40, -40, 40, 40))
        base = SpiralField("base", turns=2, phase=0, center_x=0, center_y=0)
        reverse = SpiralField("reverse", turns=2, phase=0, direction=-1, center_x=0, center_y=0)
        shifted = SpiralField("shifted", turns=2, phase=.25, center_x=0, center_y=0)
        moved = SpiralField("moved", turns=2, phase=0, center_x=10, center_y=0)
        more = SpiralField("more", turns=5, phase=0, center_x=0, center_y=0)
        sample = CircleElement("sample", 20, 7, 1, 1)
        self.assertNotEqual(base.evaluate(sample, context), reverse.evaluate(sample, context))
        self.assertNotEqual(base.evaluate(sample, context), shifted.evaluate(sample, context))
        self.assertNotEqual(base.evaluate(sample, context), moved.evaluate(sample, context))
        self.assertNotEqual(base.evaluate(sample, context), more.evaluate(sample, context))

    def test_spiral_reuses_size_rotation_and_document_grid(self):
        engine = SharedFieldEngine(FieldRegistry([SpiralField("spiral", turns=3)]), [
            SizeModifier("size", "spiral", FieldMapping(1, 2)),
            RotationModifier("rotation", "spiral", FieldMapping(-30, 30)),
        ])
        source = probes(); result = engine.apply(source)
        self.assertNotEqual(result, source)
        self.assertEqual(source, probes())
        model = GridParametricModel(rows=2, columns=2, spacing_x=20, spacing_y=20, element_width=4)
        payload = engine.to_dict()
        document = PatternDocument(Canvas(80, 80), Reference(""), model.generate(),
            metadata={PARAMETRIC_METADATA_KEY: {"mode": "grid", "grid": model.to_dict()}},
            fields=payload["fields"], modifiers=payload["modifiers"])
        evaluated = evaluate_pattern_document(document)
        self.assertEqual([item.id for item in evaluated], [item.id for item in model.generate()])
        self.assertNotEqual([item.rotation for item in evaluated], [0.0] * 4)

    def test_spiral_save_load_undo_redo(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            session = PatternLabSession(FoundationPipeline(None, None), root,
                                        document=PatternDocument(Canvas(80, 80), Reference(""), probes()))
            settings = SizeFieldModifier(mode=SizeFieldMode.SPIRAL, center_x=0, center_y=0, turns=3,
                                         min_scale=1, max_scale=2)
            session.activate_shared_modifiers(SharedModifierStack(size_field=settings))
            expected = deepcopy(session.document.elements)
            saved = session.save_document(root / "spiral.pattern.json")
            session.undo(); self.assertEqual(session.document.elements, probes())
            session.redo(); self.assertEqual(session.document.elements, expected)
            restored = PatternLabSession(FoundationPipeline(None, None), root / "reload")
            restored.load_document(str(saved))
            self.assertEqual(restored.document.elements, expected)


if __name__ == "__main__":
    unittest.main()
