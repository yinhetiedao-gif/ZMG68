"""Fixed-scale regression for the headless part of Pattern Lab performance."""
from __future__ import annotations

import unittest

from xiaomang_pattern_lab.performance_benchmark import run_benchmark


class PatternLabPerformanceTests(unittest.TestCase):
    def test_fixed_interaction_scales_do_not_mutate_document_during_motion(self):
        report = run_benchmark()
        self.assertEqual([item["element_count"] for item in report], [144, 500, 1000, 3000])
        for item in report:
            self.assertEqual(item["document_updates_during_transient"], 0)
            self.assertEqual(item["svg_serializations_during_transient"], 0)
            self.assertEqual(item["undo_records_during_transient"], 0)
            self.assertGreaterEqual(item["transient_drag_240_ms"], 0.0)
            self.assertGreaterEqual(item["size_gradient_slider_preview_ms"], 0.0)


if __name__ == "__main__":
    unittest.main()
