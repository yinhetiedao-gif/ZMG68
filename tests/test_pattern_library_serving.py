"""The reused library is isolated from the editor/API and manufacturing."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from xiaomang_pattern_lab.web import create_app


class PatternLibraryServingTests(unittest.TestCase):
    def test_library_refresh_assets_and_api_are_isolated(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            library = root / "library"
            library.mkdir()
            (library / "index.html").write_text("<html>library</html>", encoding="utf-8")
            (library / "waves-1").mkdir()
            (library / "waves-1" / "index.html").write_text("<html>waves</html>", encoding="utf-8")
            (library / "client").mkdir()
            (library / "client" / "main.js").write_text("console.log('library')", encoding="utf-8")
            (root / "private.txt").write_text("private", encoding="utf-8")
            editor = root / "editor"
            editor.mkdir()
            (editor / "assets").mkdir()
            (editor / "index.html").write_text("<html>editor</html>", encoding="utf-8")
            with patch.dict(os.environ, {"XIAOMANG_PATTERN_LIBRARY_DIST": str(library)}):
                with TestClient(create_app(web_dist=editor)) as client:
                    self.assertIn("library", client.get("/patterns/").text)
                    self.assertIn("waves", client.get("/patterns/waves-1/").text)
                    self.assertEqual(client.get("/patterns/client/main.js").status_code, 200)
                    self.assertEqual(client.get("/patterns/no-such-pattern/").status_code, 404)
                    self.assertEqual(client.get("/patterns/missing.js").status_code, 404)
                    self.assertEqual(client.get("/patterns/%2e%2e/private.txt").status_code, 404)
                    self.assertIn("editor", client.get("/").text)
                    self.assertIn("editor", client.get("/design").text)
                    self.assertEqual(client.get("/api/v1/health").status_code, 200)
                    self.assertEqual(client.get("/api/v1/not-a-route").status_code, 404)

    def test_library_is_opt_in_and_missing_build_is_not_silently_accepted(self):
        with patch.dict(os.environ, {"XIAOMANG_PATTERN_LIBRARY_DIST": ""}):
            with TestClient(create_app()) as client:
                self.assertEqual(client.get("/patterns/").status_code, 404)
        with TemporaryDirectory() as folder:
            with patch.dict(os.environ, {"XIAOMANG_PATTERN_LIBRARY_DIST": folder}):
                with self.assertRaisesRegex(RuntimeError, "Pattern library build is missing"):
                    create_app()
