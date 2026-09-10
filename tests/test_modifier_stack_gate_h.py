"""Gate H: ordered, non-destructive Size/Rotation modifier layers."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ppg.foundation import Canvas, CircleElement, FoundationPipeline, PatternDocument, Reference
from xiaomang_pattern_lab.parametric_families import RotationFieldMode, RotationFieldModifier, SizeFieldMode, SizeFieldModifier
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.shared_modifiers import SharedModifierStack


def source_elements():
    return [CircleElement("left", -10, 0, 4, 4), CircleElement("right", 10, 0, 4, 4)]


class ModifierStackGateHTests(unittest.TestCase):
    def test_multiple_layers_apply_in_order_and_preserve_source(self):
        source = source_elements()
        document = PatternDocument(Canvas(60, 40), Reference(""), source)
        stack = SharedModifierStack(source_kind="imported_elements", source_elements=source)
        stack.add_modifier("size", SizeFieldModifier(mode=SizeFieldMode.LINEAR_X, min_scale=.5, max_scale=1.5).to_dict(), modifier_id="wave-size")
        stack.add_modifier("rotation", RotationFieldModifier(mode=RotationFieldMode.CONSTANT, angle=25).to_dict(), modifier_id="spiral-rotation")
        stack.attach(document)
        session = PatternLabSession(FoundationPipeline(None, None), Path("."), document=document)
        evaluated = session.evaluate_elements()
        self.assertLess(evaluated[0].width, evaluated[1].width)
        self.assertEqual([round(item.rotation) for item in evaluated], [25, 25])
        self.assertEqual(document.elements, source)
        self.assertEqual([item["id"] for item in SharedModifierStack.from_document(document).modifiers], ["wave-size", "spiral-rotation"])

    def test_disable_reenable_duplicate_reorder_and_reset_are_persistent(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            document = PatternDocument(Canvas(60, 40), Reference(""), source_elements())
            session = PatternLabSession(FoundationPipeline(None, None), root, document=document)
            size = SizeFieldModifier(mode=SizeFieldMode.LINEAR_X, min_scale=.5, max_scale=1.5)
            session.add_modifier_layer("size", size.to_dict(), modifier_id="size-1")
            session.add_modifier_layer("rotation", RotationFieldModifier(angle=20).to_dict(), modifier_id="rotation-1")
            before_disable = deepcopy(session.evaluate_elements())
            session.set_modifier_enabled(0, False)
            disabled = session.evaluate_elements()
            self.assertEqual([item.width for item in disabled], [4, 4])
            self.assertEqual([round(item.rotation) for item in disabled], [20, 20])
            session.set_modifier_enabled(0, True)
            self.assertEqual(session.evaluate_elements(), before_disable)
            duplicate_id = session.duplicate_modifier_layer(0)
            self.assertEqual(duplicate_id, "size-1-copy")
            self.assertEqual([item["id"] for item in SharedModifierStack.from_document(session.document).modifiers], ["size-1", duplicate_id, "rotation-1"])
            session.move_modifier_layer(2, -1)
            session.move_modifier_layer(1, -1)
            self.assertEqual([item["id"] for item in SharedModifierStack.from_document(session.document).modifiers], ["rotation-1", "size-1", duplicate_id])
            session.reset_modifier_layer(1)
            session.reset_modifier_layer(2)
            reset = session.evaluate_elements()
            self.assertEqual([item.width for item in reset], [4, 4])
            saved = session.save_document(root / "gate-h.pattern.json")
            restored = PatternLabSession(FoundationPipeline(None, None), root / "reload")
            restored.load_document(str(saved))
            self.assertEqual(restored.document.metadata, session.document.metadata)
            self.assertEqual([item["id"] for item in SharedModifierStack.from_document(restored.document).modifiers], ["rotation-1", "size-1", duplicate_id])


if __name__ == "__main__":
    unittest.main()
