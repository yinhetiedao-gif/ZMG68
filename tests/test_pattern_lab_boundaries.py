"""Guard the promise that the disposable harness cannot leak into the Core Engine."""
from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ppg" / "foundation"


class PatternLabBoundaryTests(unittest.TestCase):
    def test_core_engine_has_no_ui_or_image_runtime_dependency(self):
        forbidden = (
            "import tkinter", "from tkinter", "from PIL", "import PIL",
            "upstream_svg_pipeline", "imagetosvg-mcp",
        )
        for source in CORE.glob("*.py"):
            text = source.read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, text, "%s leaks %s into Xiaomang Core Engine" % (source.name, token))

    def test_harness_is_outside_core_engine(self):
        harness = ROOT / "xiaomang_pattern_lab" / "ui_harness.py"
        self.assertTrue(harness.is_file())
        self.assertFalse(str(harness).startswith(str(CORE)))


if __name__ == "__main__":
    unittest.main()
