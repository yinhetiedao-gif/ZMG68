"""Gate U-Core regression: final 2D connected components stay derived-only."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from ppg.foundation import Canvas, CircleElement, FilledRegionElement, FoundationPipeline, PatternDocument, Reference
from xiaomang_pattern_lab.connectivity import ConnectivityAnalyzer
from xiaomang_pattern_lab.parametric import GridParametricModel
from xiaomang_pattern_lab.session import PatternLabSession


def circle(identifier: str, x: float, y: float = 20.0, diameter: float = 10.0) -> CircleElement:
    return CircleElement(id=identifier, x=x, y=y, width=diameter, height=diameter, style={"fill": "#000"})


def document(elements) -> PatternDocument:
    return PatternDocument(Canvas(1200, 200, "mm", 1.0), Reference("", False), list(elements))


class ConnectivityGateUCoreTests(unittest.TestCase):
    def test_two_separated_circles_are_two_isolated_components(self):
        report = ConnectivityAnalyzer().analyze_document(document([circle("a", 10), circle("b", 40)]))
        self.assertEqual((report.total_element_count, report.component_count, report.isolated_count), (2, 2, 2))
        self.assertEqual(report.largest_component_size, 1)
        self.assertEqual(set(report.isolated_element_ids), {"a", "b"})

    def test_two_overlapping_circles_are_one_component(self):
        report = ConnectivityAnalyzer().analyze_document(document([circle("a", 10), circle("b", 18)]))
        self.assertEqual((report.component_count, report.isolated_count, report.largest_component_size), (1, 0, 2))

    def test_two_tangent_circles_count_as_connected(self):
        report = ConnectivityAnalyzer().analyze_document(document([circle("a", 10), circle("b", 20)]))
        self.assertEqual((report.component_count, report.isolated_count), (1, 0))

    def test_three_connected_and_one_isolated(self):
        report = ConnectivityAnalyzer().analyze_document(document([
            circle("a", 10), circle("b", 18), circle("c", 26), circle("lonely", 100),
        ]))
        self.assertEqual(report.component_count, 2)
        self.assertEqual(report.isolated_element_ids, ("lonely",))
        self.assertEqual(report.largest_component_size, 3)

    def test_one_hundred_chain_elements_use_broad_phase_and_form_one_component(self):
        report = ConnectivityAnalyzer().analyze_document(document([
            circle("unit-%03d" % index, 10.0 + index * 9.0) for index in range(100)
        ]))
        self.assertEqual((report.total_element_count, report.component_count, report.largest_component_size), (100, 1, 100))
        # A broad phase must avoid the 4,950 all-pairs exact tests.
        self.assertLess(report.candidate_pair_count, 1000)

    def test_invalid_final_geometry_is_skipped_not_invented(self):
        good, invalid = circle("good", 10), circle("invalid", 40)
        invalid.width = invalid.height = 1e-9
        report = ConnectivityAnalyzer().analyze_document(document([good, invalid]))
        self.assertEqual((report.total_element_count, report.skipped_invalid_count), (1, 1))
        self.assertEqual(report.component_count, 1)

    def test_shape_replacement_is_analyzed_as_final_filled_geometry(self):
        with tempfile.TemporaryDirectory() as temporary:
            session = PatternLabSession(
                FoundationPipeline(None, None), Path(temporary),
                document=document([circle("first", 10), circle("second", 18)]),
            )
            session.select("first")
            session.replace_selected_shape("star")
            self.assertIsInstance(session.document.element("first"), FilledRegionElement)
            report = session.analyze_connectivity()
            self.assertEqual((report.total_element_count, report.component_count), (2, 1))

    def test_pattern_lab_final_geometry_analysis_does_not_mutate_document_or_undo(self):
        model = GridParametricModel(rows=2, columns=3, spacing_x=8, spacing_y=8,
                                    element_width=10, element_height=10, offset_x=30, offset_y=30)
        with tempfile.TemporaryDirectory() as temporary:
            session = PatternLabSession(
                FoundationPipeline(None, None), Path(temporary), document=document(model.generate()),
            )
            session.activate_grid(model)
            before = session.document.to_dict()
            revision, undo_count = session.revision, session.undo_record_count
            report = session.analyze_connectivity()
            self.assertEqual((report.total_element_count, report.component_count), (6, 1))
            self.assertEqual(session.document.to_dict(), before)
            self.assertEqual((session.revision, session.undo_record_count), (revision, undo_count))


if __name__ == "__main__":
    unittest.main()
