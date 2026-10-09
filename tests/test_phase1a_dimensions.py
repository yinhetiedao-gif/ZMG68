"""Regression only: existing world-mm pipeline, no new sizing model."""
from copy import deepcopy
from unittest.mock import patch
import os
import numpy as np
import pytest
from fastapi.testclient import TestClient
from ppg.foundation import Canvas, PatternDocument, RectElement, Reference
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.shared_fields import LinearField
from xiaomang_pattern_lab.stl_export import STLExporter
from xiaomang_pattern_lab.mesh_validation import MeshValidator
from xiaomang_pattern_lab.web import create_app


@pytest.mark.parametrize('unit,factor', [('mm', 1), ('mm', 2), ('px', .25)])
def test_non_square_nonzero_origin_scale_plan_final_mesh_stl(unit, factor):
    elements = [RectElement(f'p-{i}', 11 + (i % 5) * 58 / 4,
        21 + (i // 5) * 38 / 3, 2, 2) for i in range(20)]
    document = PatternDocument(Canvas(60, 40, unit, factor, 10, 20), Reference('', False), elements)
    document.fields = [LinearField('owned-height', angle=0, start=10 * factor, end=70 * factor).to_dict()]
    document.metadata['fabric_config'] = {'config_version': 1,
        'base': {'type': 'solid', 'thickness_mm': .6, 'margin_mm': 1},
        'unit_cell': {'type': 'pyramid', 'width_mm': 2.4, 'depth_mm': 2.4, 'height_mm': 3, 'size_mode': 'fixed'},
        'placement': {'mode': 'pattern_points', 'spacing_x_mm': 5, 'spacing_y_mm': 5},
        'field_modifiers': {'height': {'enabled': True, 'field_id': 'owned-height', 'min_height_mm': 2, 'max_height_mm': 6}}}
    dto = PatternDocumentDTO.from_document(document, f'dimensions-{unit}-{factor}', 7)
    body = {'document': dto.to_dict(), 'document_revision': 7}
    before = deepcopy(document.to_dict())
    with patch.dict(os.environ, {'XIAOMANG_ENV': 'staging', 'XIAOMANG_FABRIC_STL_TEST_EXPORT': '1'}), TestClient(create_app()) as client:
        preview = client.post('/api/v1/fabric/preview', json=body)
        assert preview.status_code == 200, preview.text
        plan = preview.json()
        assert plan['active_count'] == 20
        for index, instance in enumerate(plan['instances']):
            assert instance['x_mm'] == pytest.approx(elements[index].x * factor)
            assert instance['y_mm'] == pytest.approx(elements[index].y * factor)
            assert instance['cell_width_mm'] == pytest.approx(2.4)
            assert instance['cell_height_mm'] == pytest.approx(2 + 4 * (elements[index].x - 10) / 60)
        expected_bounds = [[10 * factor - 1, 20 * factor - 1, 0], [70 * factor + 1, 60 * factor + 1, .6 + max(i['height_mm'] for i in plan['instances'])]]
        final = client.post('/api/v1/fabric/fusion', json=body)
        assert final.status_code == 200, final.text
        result = final.json()
        np.testing.assert_allclose(result['bounds_mm'], expected_bounds, rtol=0, atol=1e-8)
        artifact = client.post(f"/api/v1/fabric/{result['final_fabric_mesh_id']}/model.stl", json=body)
        assert artifact.status_code == 200, artifact.text
        mesh = STLExporter.reload_bytes_as_mesh_result(artifact.content)
        report = MeshValidator().validate(mesh)
        assert report.is_valid and report.is_watertight and report.component_count == 1
        assert report.degenerate_face_count == 0 and mesh.mesh.volume > 0
        np.testing.assert_allclose(mesh.mesh.bounds, expected_bounds, rtol=0, atol=1e-5)
    assert document.to_dict() == before
