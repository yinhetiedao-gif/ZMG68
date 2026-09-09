"""Gate 0: deactivating shared effects must recover untouched source geometry."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ppg.foundation import Canvas, CircleElement, FoundationPipeline, PatternDocument, Reference
from xiaomang_pattern_lab.evaluation import serialize_elements
from xiaomang_pattern_lab.parametric_families import SizeFieldMode, SizeFieldModifier
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.shared_modifiers import SharedModifierStack


class ModifierSafetyContractTests(unittest.TestCase):
    def test_repeated_changes_and_deactivation_restore_source(self):
        with TemporaryDirectory() as directory:
            document = PatternDocument(Canvas(200, 120), Reference(''), [
                CircleElement('a', 20, 30, 8, 8), CircleElement('b', 80, 40, 12, 12)])
            source = deepcopy(serialize_elements(document.elements))
            session = PatternLabSession(FoundationPipeline(None, None), Path(directory), document=document)
            session.activate_shared_modifiers(SharedModifierStack(size_field=SizeFieldModifier(
                mode=SizeFieldMode.LINEAR_X, min_scale=.5, max_scale=2)))
            self.assertNotEqual(serialize_elements(document.elements), source)
            for maximum in (3, 1.5, 4):
                stack = SharedModifierStack.from_document(document)
                self.assertEqual(stack.source_elements, source)
                stack.size_field.max_scale = maximum
                session.update_shared_modifiers(stack)
            session.deactivate_shared_modifiers()
            self.assertEqual(serialize_elements(document.elements), source)
            self.assertEqual(serialize_elements(session.evaluate_elements()), source)


if __name__ == '__main__':
    unittest.main()
