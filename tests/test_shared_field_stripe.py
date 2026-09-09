"""Gate C: StripeField scalar and shared modifier integration."""
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
from xiaomang_pattern_lab.shared_fields import FieldContext, FieldMapping, FieldRegistry, RotationModifier, SharedFieldEngine, SizeModifier, StripeField
from xiaomang_pattern_lab.shared_modifiers import SharedModifierStack


def row():
    return [CircleElement("a", 0, 0, 4, 4), CircleElement("b", 10, 0, 4, 4), CircleElement("c", 20, 0, 4, 4), CircleElement("d", 30, 0, 4, 4)]


class StripeFieldTests(unittest.TestCase):
    def test_stripe_is_deterministic_bounded_and_periodic(self):
        field = StripeField("stripe", period=20, duty_cycle=.5)
        context = FieldContext((0, 0, 100, 100))
        values = [field.evaluate(item, context) for item in row()]
        shifted = [field.evaluate(CircleElement(item.id, item.x + 20, item.y, item.width, item.height), context) for item in row()]
        self.assertEqual(values, shifted)
        self.assertTrue(all(0 <= value <= 1 for value in values))
        self.assertEqual(field.evaluate(row()[0], context), field.evaluate(row()[0], context))

    def test_stripe_angle_phase_duty_and_invert_change_scalar(self):
        context = FieldContext((0, 0, 100, 100))
        horizontal = StripeField("h", period=20, duty_cycle=.25, phase=0)
        vertical = StripeField("v", angle=90, period=20, duty_cycle=.25, phase=0)
        self.assertNotEqual(horizontal.evaluate(CircleElement("p", 5, 1, 1, 1), context), vertical.evaluate(CircleElement("p", 5, 1, 1, 1), context))
        self.assertEqual(StripeField("wide", period=20, duty_cycle=1).evaluate(row()[0], context), 1.0)
        self.assertEqual(StripeField("off", period=20, duty_cycle=0).evaluate(row()[0], context), 0.0)
        self.assertEqual(StripeField("inv", period=20, duty_cycle=.5, invert=True).evaluate(row()[0], context), 0.0)

    def test_stripe_reuses_size_rotation_and_document_evaluate(self):
        engine = SharedFieldEngine(FieldRegistry([StripeField("stripe", period=20)]), [
            SizeModifier("size", "stripe", FieldMapping(1, 2)),
            RotationModifier("rotation", "stripe", FieldMapping(-15, 15)),
        ])
        source = row(); result = engine.apply(source)
        self.assertNotEqual(result, source)
        self.assertEqual(source, row())
        model = GridParametricModel(rows=1, columns=4, spacing_x=10, spacing_y=10, element_width=4)
        payload = engine.to_dict()
        document = PatternDocument(Canvas(80, 40), Reference(""), model.generate(),
            metadata={PARAMETRIC_METADATA_KEY: {"mode": "grid", "grid": model.to_dict()}},
            fields=payload["fields"], modifiers=payload["modifiers"])
        evaluated = evaluate_pattern_document(document)
        self.assertNotEqual([item.rotation for item in evaluated], [0.0] * 4)

    def test_stripe_save_load_undo_redo(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            session = PatternLabSession(FoundationPipeline(None, None), root,
                                        document=PatternDocument(Canvas(80, 40), Reference(""), row()))
            settings = SizeFieldModifier(mode=SizeFieldMode.STRIPE, wavelength=20, duty_cycle=.5,
                                         min_scale=1, max_scale=2)
            session.activate_shared_modifiers(SharedModifierStack(size_field=settings))
            expected = deepcopy(session.document.elements)
            saved = session.save_document(root / "stripe.pattern.json")
            session.undo(); self.assertEqual(session.document.elements, row())
            session.redo(); self.assertEqual(session.document.elements, expected)
            restored = PatternLabSession(FoundationPipeline(None, None), root / "reload")
            restored.load_document(str(saved))
            self.assertEqual(restored.document.elements, expected)


if __name__ == "__main__":
    unittest.main()
