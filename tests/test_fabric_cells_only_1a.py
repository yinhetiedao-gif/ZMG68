"""Mode-specific regression: no plate, no weakened geometric validation."""
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch
import os
import numpy as np
import pytest
from fastapi.testclient import TestClient
from ppg.foundation import PatternDocument, Canvas, Reference, RectElement
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.fabric_base import FabricBaseBuilder, FabricConfig
from xiaomang_pattern_lab.fabric_preview import build_fabric_design
from xiaomang_pattern_lab.fabric_candidate import build_fabric_candidate
from xiaomang_pattern_lab.fabric_fusion import FabricFusionService, FabricFusionFailure
from xiaomang_pattern_lab.fabric_stl import export_validated_fabric_stl
from xiaomang_pattern_lab.mesh_validation import MeshValidator
from xiaomang_pattern_lab.stl_export import STLExporter
from xiaomang_pattern_lab.web import create_app
from tests.test_web_server_wm3 import build_payload
from xiaomang_pattern_lab.shared_fields import LinearField, SizeModifier, RotationModifier, FieldMapping


def fixture(mode='cells_only', count=9, factor=1, unit='mm'):
    doc = PatternDocument(Canvas(60, 40, unit, factor, 10, 20), Reference('', False), [
        RectElement(f'cell-{i}', 14 + i % 3 * 20, 24 + i // 3 * 12, 2, 2) for i in range(count)])
    doc.metadata['fabric_config'] = {'config_version': 1, 'output_mode': mode,
        'base': {'type': 'solid', 'thickness_mm': .6, 'margin_mm': 1},
        'unit_cell': {'type': 'pyramid', 'width_mm': 4.8, 'depth_mm': 4.8, 'height_mm': 3, 'size_mode': 'follow_pattern'},
        'placement': {'mode': 'pattern_points', 'spacing_x_mm': 5, 'spacing_y_mm': 5}}
    return doc


def build(doc):
    dto = PatternDocumentDTO.from_document(doc, 'cells-only-acceptance', 3)
    design = build_fabric_design(doc, dto, preview_limit=False)
    return design, build_fabric_candidate(design.plan, design.config.base, design.design_bounds_mm,
        document_id=dto.document_id, document_revision=3, output_mode=design.config.output_mode)


@pytest.mark.parametrize('unit,factor', [('mm', 1), ('mm', 2), ('px', .25)])
def test_nine_no_base_meshes_stl_and_transform_parity(unit, factor):
    doc = fixture(factor=factor, unit=unit)
    before = deepcopy(doc.to_dict())
    with patch.object(FabricBaseBuilder, 'geometry', side_effect=AssertionError('no base entity')):
        design, candidate = build(doc)
    assert candidate.base_mesh is None
    assert candidate.report['components']['base_components'] == 0
    assert candidate.report['attachment_counts']['VALID'] == 9
    for instance, transform, mesh in zip(design.plan.instances, candidate.instance_transforms, candidate.cell_meshes):
        assert instance.z_mm == mesh.bounds[0, 2] == 0
        assert transform['x_mm'] == instance.x_mm
        assert transform['cell_width_mm'] == instance.cell_width_mm == 4.8
        assert transform['rotation_deg'] == instance.rotation_deg
    final = FabricFusionService().build(candidate)
    # At 0.25 mm/unit the 3 mm row spacing is smaller than 4.8 mm depth:
    # actual overlapping cells union into three columns, never fake nine shells.
    expected_components = 3 if factor == .25 else 9
    assert final.report['connected_component_count'] == expected_components
    assert not final.report['fused']
    payload, report = export_validated_fabric_stl(final)
    mesh = STLExporter.reload_bytes_as_mesh_result(payload)
    validation = MeshValidator().validate(mesh)
    assert validation.is_valid and validation.is_watertight and validation.component_count == expected_components
    assert validation.degenerate_face_count == 0
    assert mesh.mesh.is_winding_consistent and mesh.mesh.volume > 0
    np.testing.assert_allclose(mesh.mesh.bounds, [[14*factor-2.4,24*factor-2.4,0],
        [54*factor+2.4,48*factor+2.4,3]], atol=1e-5, rtol=0)
    assert report['roundtrip_validation']['component_count'] == expected_components
    assert doc.to_dict() == before


def test_overlap_is_real_union_and_empty_or_bad_transform_block():
    design, candidate = build(fixture(count=2))
    a = design.plan.instances[0]
    plan = replace(design.plan, instances=(a, replace(a, id='overlap', x_mm=a.x_mm+1)))
    source = build_fabric_candidate(plan, design.config.base, design.design_bounds_mm,
        document_id='overlap', document_revision=1, output_mode='cells_only')
    final = FabricFusionService().build(source)
    assert final.report['connected_component_count'] == 1
    assert final.mesh_result.mesh.volume < source.mesh.volume
    assert final.report['validation_report']['degenerate_face_count'] == 0
    export_validated_fabric_stl(final)
    for instances in ((), (replace(a, scale_x=0),), (replace(a, height_mm=1e-12),)):
        source = build_fabric_candidate(replace(plan, instances=instances), design.config.base,
            design.design_bounds_mm, document_id='bad', document_revision=1, output_mode='cells_only')
        with pytest.raises(FabricFusionFailure, match='无效|未连接'):
            FabricFusionService().build(source)


def test_legacy_defaults_with_base_and_invalid_mode_rejected():
    doc = fixture()
    del doc.metadata['fabric_config']['output_mode']
    assert build(doc)[0].config.output_mode == 'cells_with_base'
    assert build(doc)[0].plan.instances[0].z_mm == .6
    doc.metadata['fabric_config']['output_mode'] = 'invalid'
    with pytest.raises(ValueError):
        FabricConfig.from_mapping(doc.metadata['fabric_config'])


def test_no_base_area_fill_keeps_layout_bounds_without_solid_or_grid_entity():
    for base_type in ('solid', 'grid'):
        doc = fixture()
        config = doc.metadata['fabric_config']
        config['base'] = {'type': base_type, 'thickness_mm': .6, 'margin_mm': 1,
            'spacing_x_mm': 5, 'spacing_y_mm': 5, 'line_width_mm': 1}
        config['placement'] = {'mode': 'area_fill', 'spacing_x_mm': 10, 'spacing_y_mm': 10}
        original = deepcopy(doc.to_dict())
        with patch.object(FabricBaseBuilder, 'geometry', side_effect=AssertionError('no base entity')):
            design, candidate = build(doc)
        assert design.metadata['base_preview']['bounds_mm'] == (12, 22, 56, 50)
        assert design.plan.count == 8
        assert [(i.x_mm, i.y_mm, i.z_mm) for i in design.plan.instances] == [
            (17 + column * 10, 27 + row * 10, 0) for row in range(2) for column in range(4)]
        assert candidate.base_mesh is None
        final = FabricFusionService().build(candidate)
        _, report = export_validated_fabric_stl(final)
        assert report['roundtrip_validation']['component_count'] == 8
        assert report['roundtrip_validation']['degenerate_face_count'] == 0
        assert doc.to_dict() == original


def test_no_base_final_pattern_scale_fabric_scale_height_rotation_once():
    doc = fixture()
    doc.fields = [LinearField('linear', angle=0, start=14, end=54).to_dict()]
    doc.modifiers = [SizeModifier('size', 'linear', FieldMapping(.8,1.2)).to_dict(),
        RotationModifier('rotation', 'linear', FieldMapping(-20,20)).to_dict()]
    doc.metadata['fabric_config']['field_modifiers'] = {
        'height': {'enabled': True, 'field_id': 'linear', 'min_height_mm': 2, 'max_height_mm': 6},
        'scale': {'enabled': True, 'field_id': 'linear', 'min_scale': .5, 'max_scale': 1.5},
        'orientation': {'enabled': True, 'field_id': 'linear', 'min_angle_deg': 10, 'max_angle_deg': 30}}
    design, candidate = build(doc)
    for item, mesh in zip(design.plan.instances, candidate.cell_meshes):
        value = (item.x_mm-14)/40
        assert item.cell_width_mm == pytest.approx(4.8*(.8+.4*value)*(.5+value))
        assert item.height_mm == pytest.approx(2+4*value)
        assert item.rotation_deg == pytest.approx(-20+40*value+10+20*value)
        assert item.z_mm == mesh.bounds[0,2] == 0
    final = FabricFusionService().build(candidate)
    _, report = export_validated_fabric_stl(final)
    assert report['roundtrip_validation']['component_count'] == 9


def test_api_modes_cache_stale_export_flag_and_standard_multi_component():
    dto = PatternDocumentDTO.from_document(fixture(), 'api-no-base', 4).to_dict()
    body = {'document': dto, 'document_revision': 4}
    with patch.dict(os.environ, {'XIAOMANG_ENV': 'staging', 'XIAOMANG_FABRIC_STL_TEST_EXPORT': '1'}), TestClient(create_app()) as client:
        preview = client.post('/api/v1/fabric/preview', json=body).json()
        assert preview['output_mode'] == 'cells_only'
        assert all(i['z_mm'] == 0 for i in preview['instances'])
        preflight = client.post('/api/v1/fabric/candidate', json=body)
        assert preflight.status_code == 200, preflight.text
        assert preflight.json()['attachment_counts']['VALID'] == 9
        first = client.post('/api/v1/fabric/fusion', json=body)
        assert first.status_code == 200, first.text
        result = first.json()
        assert result['connected_component_count'] == 9 and result['export_available']
        url = f"/api/v1/fabric/{result['final_fabric_mesh_id']}/model.stl"
        artifact = client.post(url, json=body)
        assert artifact.status_code == 200 and 'model/stl' in artifact.headers['content-type']
        assert MeshValidator().validate(STLExporter.reload_bytes_as_mesh_result(artifact.content)).component_count == 9
        assert client.post('/api/v1/fabric/fusion', json=body).json()['cache_hit']
        legacy = client.post('/api/v1/manufacturing/build', json=build_payload(PatternDocumentDTO.from_dict(dto), .6))
        assert legacy.status_code != 200 and 'model/stl' not in legacy.headers['content-type']
        other = deepcopy(body)
        other['document']['document']['metadata']['fabric_config']['output_mode'] = 'cells_with_base'
        assert client.post(url, json=other).status_code == 422
        based = client.post('/api/v1/fabric/fusion', json=other)
        assert based.status_code == 200, based.text
        assert based.json()['connected_component_count'] == 1
        assert based.json()['final_fabric_mesh_id'] != result['final_fabric_mesh_id']
        standard = deepcopy(dto)
        del standard['document']['metadata']['fabric_config']
        normal = client.post('/api/v1/manufacturing/build', json=build_payload(PatternDocumentDTO.from_dict(standard), 2))
        assert normal.status_code == 200, normal.text
        assert normal.json()['component_count'] == 9
    with patch.dict(os.environ, {'XIAOMANG_ENV': 'staging', 'XIAOMANG_FABRIC_STL_TEST_EXPORT': '0'}), TestClient(create_app()) as client:
        assert not client.post('/api/v1/fabric/fusion', json=body).json()['export_available']
        assert client.post(url, json=body).status_code == 403
