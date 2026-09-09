"""Gate D: CheckerField world-coordinate alternation."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ppg.foundation import Canvas, CircleElement, FoundationPipeline, PatternDocument, Reference
from xiaomang_pattern_lab.evaluation import evaluate_pattern_document
from xiaomang_pattern_lab.parametric import GridParametricModel, PARAMETRIC_METADATA_KEY
from xiaomang_pattern_lab.parametric_families import SizeFieldMode, SizeFieldModifier
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.shared_fields import CheckerField, FieldContext, FieldMapping, FieldRegistry, RotationModifier, SharedFieldEngine, SizeModifier
from xiaomang_pattern_lab.shared_modifiers import SharedModifierStack


def cells():
    return [CircleElement("00", 1, 1, 4, 4), CircleElement("10", 11, 1, 4, 4),
            CircleElement("01", 1, 11, 4, 4), CircleElement("11", 11, 11, 4, 4)]


class CheckerFieldTests(unittest.TestCase):
    def test_checker_adjacent_cells_alternate_and_is_bounded(self):
        field = CheckerField("checker", cell_width=10, cell_height=10)
        context = FieldContext((0, 0, 30, 30))
        values = [field.evaluate(item, context) for item in cells()]
        self.assertEqual(values, [1.0, 0.0, 0.0, 1.0])
        self.assertTrue(all(0 <= value <= 1 for value in values))

    def test_checker_rotation_offset_and_invert_are_world_based(self):
        context = FieldContext((-20, -20, 20, 20))
        base = CheckerField("base", cell_width=10, cell_height=10)
        moved = CheckerField("moved", cell_width=10, cell_height=10, offset_x=5, offset_y=0)
        rotated = CheckerField("rotated", cell_width=10, cell_height=10, angle=45)
        self.assertNotEqual(base.evaluate(cells()[0], context), moved.evaluate(cells()[0], context))
        rotation_probe = CircleElement("probe", 15, 1, 1, 1)
        self.assertNotEqual(base.evaluate(rotation_probe, context), rotated.evaluate(rotation_probe, context))
        self.assertEqual(CheckerField("inv", cell_width=10, cell_height=10, invert=True).evaluate(cells()[0], context), 0.0)

    def test_checker_reuses_size_rotation_and_document_grid(self):
        engine = SharedFieldEngine(FieldRegistry([CheckerField("checker", cell_width=10, cell_height=10)]), [
            SizeModifier("size", "checker", FieldMapping(1, 2)),
            RotationModifier("rotation", "checker", FieldMapping(0, 90)),
        ])
        source = cells(); result = engine.apply(source)
        self.assertNotEqual(result, source)
        self.assertEqual(source, cells())
        model = GridParametricModel(rows=2, columns=2, spacing_x=10, spacing_y=10, element_width=4)
        payload = engine.to_dict()
        document = PatternDocument(Canvas(50, 50), Reference(""), model.generate(),
            metadata={PARAMETRIC_METADATA_KEY: {"mode": "grid", "grid": model.to_dict()}},
            fields=payload["fields"], modifiers=payload["modifiers"])
        evaluated = evaluate_pattern_document(document)
        self.assertEqual([item.id for item in evaluated], [item.id for item in model.generate()])
        self.assertNotEqual([item.rotation for item in evaluated], [0.0] * 4)

    def test_checker_save_load_undo_redo(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            session = PatternLabSession(FoundationPipeline(None, None), root,
                                        document=PatternDocument(Canvas(50, 50), Reference(""), cells()))
            settings = SizeFieldModifier(mode=SizeFieldMode.CHECKER, cell_width=10, cell_height=10,
                                         min_scale=1, max_scale=2)
            session.activate_shared_modifiers(SharedModifierStack(size_field=settings))
            expected = deepcopy(session.document.elements)
            saved = session.save_document(root / "checker.pattern.json")
            session.undo(); self.assertEqual(session.document.elements, cells())
            session.redo(); self.assertEqual(session.document.elements, expected)
            restored = PatternLabSession(FoundationPipeline(None, None), root / "reload")
            restored.load_document(str(saved))
            self.assertEqual(restored.document.elements, expected)


if __name__ == "__main__":
    unittest.main()
