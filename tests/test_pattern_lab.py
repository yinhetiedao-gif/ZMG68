"""Pattern Lab: fixed-suite proof, independent from any Tk display."""
from __future__ import annotations

from pathlib import Path
import unittest

from xiaomang_pattern_lab.fixtures import ROOT as FIXTURE_ROOT, build_fixed_suite
from xiaomang_pattern_lab.verification import run_fixed_suite


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work" / "pattern_lab" / "acceptance"


class PatternLabAcceptanceTests(unittest.TestCase):
    def test_fixed_raster_to_editable_geometry_suite(self):
        build_fixed_suite()
        report = run_fixed_suite(str(OUT))
        self.assertEqual([metric.case for metric in report], [
            "regular_dot_matrix", "size_gradient_dot_matrix", "star_halftone",
            "high_density_dot_matrix", "twisted_dot_matrix", "mixed_size_dot_matrix",
        ])
        for metric in report:
            self.assertEqual(metric.detected_element_count, metric.source_element_count)
            self.assertEqual(metric.editable_element_count, metric.detected_element_count)
            self.assertEqual(metric.matched_count, metric.source_element_count)
            self.assertLess(metric.mean_position_error, 8.0)
            self.assertLess(metric.mean_size_error, 12.0)
            self.assertTrue(metric.raster_hidden_geometry_intact)
            self.assertTrue(metric.svg_roundtrip_preserved)
            self.assertTrue(metric.save_reload_preserved)
        self.assertTrue((OUT / "pattern-lab-report.json").is_file())

    def test_jpg_import_contract(self):
        fixtures = build_fixed_suite()
        self.assertTrue((FIXTURE_ROOT / "regular_dot_matrix.jpg").is_file())
        self.assertTrue(fixtures["regular_dot_matrix"].is_file())


if __name__ == "__main__":
    unittest.main()
