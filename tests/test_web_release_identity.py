import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from xiaomang_pattern_lab.web import create_app


class ReleaseIdentityTests(unittest.TestCase):
    def test_platform_identity_and_effective_capabilities_without_secrets(self):
        with patch.dict(os.environ, {'RENDER_GIT_COMMIT': 'a'*40, 'XIAOMANG_ENV': 'staging',
                'XIAOMANG_FABRIC_STL_TEST_EXPORT': '1', 'SOME_SECRET': 'do-not-expose'}):
            with TestClient(create_app()) as client:
                health = client.get('/api/v1/health')
                self.assertEqual(health.status_code, 200)
                data = health.json()
                self.assertEqual(data['backend_commit'], 'a'*40)
                self.assertEqual(data['environment'], 'staging')
                self.assertEqual(data['capabilities'], {'fabric_preflight': True,
                    'fabric_final_mesh': True, 'fabric_stl_test_export': True})
                self.assertNotIn('do-not-expose', health.text)
                routes = {(r.path, method) for r in client.app.routes for method in getattr(r, 'methods', ())}
                self.assertIn(('/api/v1/fabric/candidate', 'POST'), routes)
                self.assertIn(('/api/v1/fabric/fusion', 'POST'), routes)
                self.assertIn(('/api/v1/fabric/{result_id}/model.stl', 'POST'), routes)

    def test_unknown_commit_and_production_export_remains_disabled(self):
        with patch.dict(os.environ, {'RENDER_GIT_COMMIT': 'not-a-commit', 'XIAOMANG_ENV': 'production',
                'XIAOMANG_FABRIC_STL_TEST_EXPORT': '1'}):
            with TestClient(create_app()) as client:
                data = client.get('/api/v1/health').json()
                self.assertEqual(data['backend_commit'], 'UNKNOWN')
                self.assertFalse(data['capabilities']['fabric_stl_test_export'])
                self.assertFalse(client.get('/api/v1/contract').json()['fabric_stl_test_export_enabled'])
