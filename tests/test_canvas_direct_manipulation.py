"""Headless proof for Canvas Direct Manipulation's math and transaction semantics."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from ppg.foundation import Canvas, CircleElement, FoundationPipeline, PatternDocument, Reference
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.view_transform import CanvasViewTransform


class CanvasDirectManipulationTests(unittest.TestCase):
    def test_screen_world_roundtrip_at_50_100_200_percent_and_after_pan(self):
        for zoom in (0.5, 1.0, 2.0):
            view = CanvasViewTransform(320, 240, 960, 640, zoom=zoom)
            view.set_zoom_at(zoom, 430, 270)
            view.pan_pixels(73, -41)
            for point in ((0, 0), (17.5, 29.25), (160, 120), (319.9, 239.9)):
                screen = view.worldToScreen(*point)
                restored = view.screenToWorld(*screen)
                self.assertAlmostEqual(restored[0], point[0], places=7)
                self.assertAlmostEqual(restored[1], point[1], places=7)

    def test_transaction_is_one_undo_and_one_redo(self):
        with tempfile.TemporaryDirectory() as directory:
            document = PatternDocument(
                Canvas(100, 100, "mm", 1.0), Reference("reference.png", False),
                [CircleElement("dot-1", 20, 20, 8, 8)],
            )
            session = PatternLabSession(FoundationPipeline(None, None), Path(directory), document=document)
            session.select("dot-1")
            before = document.to_dict()
            session.begin_transaction("移动")
            for x in (21, 24, 29, 35):
                session.set_element_position("dot-1", x, 37)
            self.assertTrue(session.transaction_active)
            self.assertTrue(session.commit_transaction())
            after = session.document.to_dict()
            self.assertNotEqual(before, after)
            self.assertTrue(session.undo())
            self.assertEqual(session.document.to_dict(), before)
            self.assertTrue(session.redo())
            self.assertEqual(session.document.to_dict(), after)

    def test_inspector_set_position_and_size_use_document_source_of_truth(self):
        with tempfile.TemporaryDirectory() as directory:
            document = PatternDocument(
                Canvas(100, 100, "mm", 1.0), Reference("reference.png", False),
                [CircleElement("dot-1", 20, 20, 8, 8)],
            )
            session = PatternLabSession(FoundationPipeline(None, None), Path(directory), document=document)
            session.set_element_position("dot-1", 55, 47)
            session.set_element_size("dot-1", 14, 14)
            self.assertEqual((session.document.element("dot-1").x, session.document.element("dot-1").y), (55, 47))
            self.assertEqual((session.document.element("dot-1").width, session.document.element("dot-1").height), (14, 14))


if __name__ == "__main__":
    unittest.main()
