"""Single-origin production serving does not change the API or expose local files."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from xiaomang_pattern_lab.web import create_app
from xiaomang_pattern_lab.web.assets import TemporaryAssetStore


class WebRenderStaticTests(unittest.TestCase):
    def test_spa_and_api_share_one_origin_without_exposing_other_files(self):
        with TemporaryDirectory() as folder:
            dist = Path(folder)
            (dist / "assets").mkdir()
            (dist / "index.html").write_text("<html>Pattern Lab</html>", encoding="utf-8")
            (dist / "assets" / "main.js").write_text("window.test = 1", encoding="utf-8")
            (dist / "favicon.svg").write_text("<svg/>", encoding="utf-8")
            (dist / "private.json").write_text("secret", encoding="utf-8")
            with patch.dict(os.environ, {"XIAOMANG_ENV": "staging"}):
                with TestClient(create_app(web_dist=dist)) as client:
                    self.assertIn("Pattern Lab", client.get("/").text)
                    self.assertIn("Pattern Lab", client.get("/design").text)
                    self.assertIn("Pattern Lab", client.get("/design/grid").text)
                    self.assertIn("window.test", client.get("/assets/main.js").text)
                    self.assertEqual(client.get("/favicon.svg").status_code, 200)
                    self.assertEqual(client.get("/api/v1/health").status_code, 200)
                    self.assertEqual(client.get("/api/v1/not-a-route").status_code, 404)
                    self.assertEqual(client.get("/private.json").status_code, 404)
                    self.assertEqual(client.get("/docs").status_code, 404)
                    self.assertEqual(client.get("/openapi.json").status_code, 404)

    def test_missing_build_fails_fast(self):
        with TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError, "Web build is missing"):
                create_app(web_dist=Path(folder))

    def test_windows_upload_header_does_not_echo_absolute_path_on_linux(self):
        uploads = TemporaryAssetStore()
        try:
            item = uploads.put(b"<svg xmlns='http://www.w3.org/2000/svg'/>",
                               "image/svg+xml", "C:\\Users\\secret\\pattern.svg")
            self.assertEqual(item.filename, "pattern.svg")
        finally:
            uploads._directory.cleanup()


if __name__ == "__main__":
    unittest.main()
