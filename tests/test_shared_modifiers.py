"""Regression tests for source-independent shared modifier evaluation."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ppg.foundation import Canvas, CircleElement, FoundationPipeline, PatternDocument, Reference
from xiaomang_pattern_lab.parametric_families import RotationFieldMode, RotationFieldModifier, SizeFieldMode, SizeFieldModifier
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.shared_modifiers import SharedModifierStack


def dots() -> list[CircleElement]:
    return [CircleElement(id="dot-%d" % index, x=20 + index * 30, y=40, width=10, height=10) for index in range(3)]


class SharedModifierTests(unittest.TestCase):
    def test_imported_elements_can_use_shared_fields_without_grid_fit(self) -> None:
        document = PatternDocument(Canvas(140, 100, unit="mm", mm_per_unit=1.0), Reference(""), dots())
        stack = SharedModifierStack(
            size_field=SizeFieldModifier(mode=SizeFieldMode.LINEAR_X, min_scale=0.5, max_scale=1.5),
            rotation_field=RotationFieldModifier(mode=RotationFieldMode.CONSTANT, angle=20),
        )
        stack.attach(document, source_kind="imported_elements", source_elements=document.elements)
        session = PatternLabSession(FoundationPipeline(None, None), Path("."), document=document)
        evaluated = session.evaluate_elements()
        self.assertLess(evaluated[0].width, evaluated[1].width)
        self.assertLess(evaluated[1].width, evaluated[2].width)
        self.assertEqual([round(item.rotation) for item in evaluated], [20, 20, 20])
        self.assertEqual([item.width for item in document.elements], [10, 10, 10])

    def test_shared_stack_survives_session_save_reload(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            document = PatternDocument(Canvas(140, 100, unit="mm", mm_per_unit=1.0), Reference(""), dots())
            session = PatternLabSession(FoundationPipeline(None, None), root, document=document)
            stack = SharedModifierStack(
                size_field=SizeFieldModifier(mode=SizeFieldMode.LINEAR_X, min_scale=0.5, max_scale=1.5),
                rotation_field=RotationFieldModifier(mode=RotationFieldMode.CONSTANT, angle=12),
            )
            session.activate_shared_modifiers(stack)
            saved = session.save_document(str(root / "shared.pattern.json"))
            restored = PatternLabSession(FoundationPipeline(None, None), root / "reload")
            restored.load_document(str(saved))
            self.assertTrue(restored.has_shared_modifiers)
            self.assertEqual([round(item.rotation) for item in restored.document.elements], [12, 12, 12])
            self.assertLess(restored.document.elements[0].width, restored.document.elements[-1].width)

    def test_grid_source_and_shared_effects_compose_without_replacing_grid(self) -> None:
        from xiaomang_pattern_lab.parametric import GridParametricModel

        model = GridParametricModel(rows=2, columns=2, spacing_x=20, spacing_y=20, element_width=8)
        document = PatternDocument(Canvas(100, 100, unit="mm", mm_per_unit=1.0), Reference(""), model.generate())
        session = PatternLabSession(FoundationPipeline(None, None), Path("."), document=document)
        session.activate_grid(model)
        stack = SharedModifierStack(
            rotation_field=RotationFieldModifier(mode=RotationFieldMode.CONSTANT, angle=15),
            source_kind="grid",
        )
        session.activate_shared_modifiers(stack, source_kind="grid")
        self.assertEqual(session.pattern_mode.value, "grid")
        self.assertEqual([round(item.rotation) for item in session.document.elements], [15, 15, 15, 15])
        self.assertEqual([item.id for item in session.document.elements], ["grid:r0:c0", "grid:r0:c1", "grid:r1:c0", "grid:r1:c1"])


if __name__ == "__main__":
    unittest.main()
