"""Gate B: WaveField as a reusable scalar for Size/Rotation modifiers."""
from __future__ import annotations

from copy import deepcopy
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ppg.foundation import Canvas, CircleElement, PatternDocument, Reference
from xiaomang_pattern_lab.evaluation import evaluate_pattern_document
from xiaomang_pattern_lab.parametric import GridParametricModel, PARAMETRIC_METADATA_KEY
from xiaomang_pattern_lab.shared_fields import (
    FieldContext, FieldMapping, FieldRegistry, RotationModifier, SharedFieldEngine, SizeModifier, WaveField,
)
from xiaomang_pattern_lab.parametric_families import SizeFieldMode, SizeFieldModifier
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.shared_modifiers import SharedModifierStack
from ppg.foundation import FoundationPipeline


def dots() -> list[CircleElement]:
    return [CircleElement("left", -10, 0, 4, 4), CircleElement("middle", 0, 0, 4, 4),
            CircleElement("right", 10, 0, 4, 4)]


class WaveFieldTests(unittest.TestCase):
    def test_wave_is_finite_bounded_and_deterministic(self) -> None:
        field = WaveField("wave", wavelength=20, phase=.25, amplitude=.8, offset=.1)
        source = dots()
        before = deepcopy(source)
        context = FieldContext.from_elements(source)
        first = [field.evaluate(item, context) for item in source]
        second = [field.evaluate(item, context) for item in source]
        self.assertEqual(first, second)
        self.assertTrue(all(0.0 <= value <= 1.0 and math.isfinite(value) for value in first))
        self.assertEqual(source, before)

    def test_wave_periodicity_and_angle(self) -> None:
        field = WaveField("wave", angle=0, wavelength=20, phase=0, amplitude=1, offset=0)
        context = FieldContext((0, 0, 100, 100))
        a = field.evaluate(CircleElement("a", 3, 0, 1, 1), context)
        b = field.evaluate(CircleElement("b", 23, 0, 1, 1), context)
        self.assertAlmostEqual(a, b)
        rotated = WaveField("rotated", angle=90, wavelength=20, phase=0, amplitude=1, offset=0)
        self.assertAlmostEqual(rotated.evaluate(CircleElement("c", 0, 3, 1, 1), context), a)

    def test_wave_reuses_size_and_rotation_modifiers(self) -> None:
        engine = SharedFieldEngine(
            FieldRegistry([WaveField("wave", wavelength=20)]),
            [SizeModifier("size", "wave", FieldMapping(1, 2)),
             RotationModifier("rotation", "wave", FieldMapping(-20, 20))],
        )
        source = dots(); result = engine.apply(source)
        self.assertNotEqual([item.width for item in result], [item.width for item in source])
        self.assertNotEqual([item.rotation for item in result], [item.rotation for item in source])
        self.assertEqual(source, dots())

    def test_wave_engine_roundtrip_and_document_evaluate(self) -> None:
        engine = SharedFieldEngine(
            FieldRegistry([WaveField("wave", angle=20, wavelength=30, phase=.4, amplitude=.7, offset=.1)]),
            [SizeModifier("size", "wave", FieldMapping(.5, 1.8))],
        )
        payload = engine.to_dict()
        restored = SharedFieldEngine.from_dict(payload)
        self.assertEqual(restored.to_dict(), payload)
        self.assertEqual(restored.apply(dots()), engine.apply(dots()))

        model = GridParametricModel(rows=1, columns=3, spacing_x=10, spacing_y=10, element_width=4)
        document = PatternDocument(Canvas(80, 50), Reference(""), model.generate(),
            metadata={PARAMETRIC_METADATA_KEY: {"mode": "grid", "grid": model.to_dict()}},
            fields=payload["fields"], modifiers=payload["modifiers"])
        evaluated = evaluate_pattern_document(document)
        self.assertEqual([item.id for item in evaluated], [item.id for item in model.generate()])
        self.assertNotEqual([item.width for item in evaluated], [item.width for item in model.generate()])

    def test_wave_session_undo_redo_and_save_reload(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            document = PatternDocument(Canvas(80, 50), Reference(""), dots())
            session = PatternLabSession(FoundationPipeline(None, None), root, document=document)
            settings = SizeFieldModifier(mode=SizeFieldMode.WAVE, wavelength=20, amplitude=1, min_scale=1, max_scale=2)
            session.activate_shared_modifiers(SharedModifierStack(size_field=settings))
            expected = deepcopy(session.document.elements)
            saved = session.save_document(root / "wave.pattern.json")
            self.assertEqual(session.document.fields[0]["type"], "wave")
            session.undo()
            self.assertEqual([item.width for item in session.document.elements], [4, 4, 4])
            session.redo()
            self.assertEqual(session.document.elements, expected)
            restored = PatternLabSession(FoundationPipeline(None, None), root / "reload")
            restored.load_document(str(saved))
            self.assertEqual(restored.document.elements, expected)


if __name__ == "__main__":
    unittest.main()
