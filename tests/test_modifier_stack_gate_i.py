"""Gate I: non-destructive position/deformation modifier layers."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import math
import unittest

from ppg.foundation import Canvas, CircleElement, FoundationPipeline, PatternDocument, Reference
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.shared_modifiers import PositionModifier, SharedModifierStack


def make_document():
    source = [
        CircleElement("left", -10, 0, 4, 4),
        CircleElement("right", 10, 0, 4, 4),
        CircleElement("top", 0, 10, 4, 4),
    ]
    return PatternDocument(Canvas(80, 80), Reference(""), source), source


class ModifierStackGateITests(unittest.TestCase):
    def test_all_position_modes_are_deterministic_and_non_destructive(self):
        cases = [
            ("offset", {"offset_x": 3, "offset_y": -2}, lambda p: (p.x, p.y)),
            ("attractor", {"center_x": 0, "center_y": 0, "amount": 2}, lambda p: (p.x, p.y)),
            ("repeller", {"center_x": 0, "center_y": 0, "amount": 2}, lambda p: (p.x, p.y)),
            ("radial_push", {"center_x": 0, "center_y": 0, "amount": 2}, lambda p: (p.x, p.y)),
            ("twist", {"center_x": 0, "center_y": 0, "angle": 90, "radius": 100}, lambda p: (p.x, p.y)),
            ("wave", {"angle": 0, "amount": 4, "wavelength": 40, "radius": 100}, lambda p: (p.x, p.y)),
        ]
        for mode, params, _ in cases:
            document, source = make_document()
            stack = SharedModifierStack(source_elements=source)
            stack.add_modifier("position", PositionModifier(mode=mode, **params).to_dict())
            stack.attach(document)
            before = deepcopy(document.elements)
            session = PatternLabSession(FoundationPipeline(None, None), Path("."), document=document)
            first = session.evaluate_elements()
            second = session.evaluate_elements()
            self.assertEqual(first, second, mode)
            self.assertEqual(document.elements, before, mode)
        # Directional assertions make the modes meaningful rather than merely
        # checking that a layer serializes.
        document, source = make_document()
        stack = SharedModifierStack(source_elements=source)
        stack.add_modifier("position", PositionModifier(mode="attractor", amount=2, radius=1e9).to_dict())
        stack.attach(document)
        point = PatternLabSession(FoundationPipeline(None, None), Path("."), document=document).evaluate_elements()[0]
        self.assertAlmostEqual(point.x, -8.0, places=6)
        document, source = make_document()
        stack = SharedModifierStack(source_elements=source)
        stack.add_modifier("position", PositionModifier(mode="twist", angle=90, radius=1e9).to_dict())
        stack.attach(document)
        point = PatternLabSession(FoundationPipeline(None, None), Path("."), document=document).evaluate_elements()[0]
        self.assertAlmostEqual(point.x, 0.0, places=6)
        self.assertAlmostEqual(point.y, -10.0, places=6)

    def test_session_stack_edit_undo_redo_and_save_load(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            document, source = make_document()
            session = PatternLabSession(FoundationPipeline(None, None), root, document=document)
            session.add_modifier_layer("position", PositionModifier(mode="offset", offset_x=5).to_dict(), modifier_id="move-1")
            moved = session.evaluate_elements()[0]
            self.assertAlmostEqual(moved.x, -5.0)
            self.assertEqual(session.undo_record_count, 1)
            session.undo()
            self.assertEqual(session.evaluate_elements()[0].x, -10.0)
            session.redo()
            self.assertEqual(session.evaluate_elements()[0].x, -5.0)
            saved = session.save_document(root / "gate-i.pattern.json")
            restored = PatternLabSession(FoundationPipeline(None, None), root / "reload")
            restored.load_document(str(saved))
            stack = SharedModifierStack.from_document(restored.document)
            self.assertEqual(stack.modifiers[0]["type"], "position")
            self.assertEqual(stack.modifiers[0]["id"], "move-1")
            self.assertAlmostEqual(restored.evaluate_elements()[0].x, -5.0)


if __name__ == "__main__":
    unittest.main()
