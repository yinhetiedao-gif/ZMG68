from copy import deepcopy
from dataclasses import replace
import math
import numpy as np
import pytest
from ppg.foundation import Canvas, PatternDocument, Reference, RectElement, FilledRegionElement
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.fabric_preview import build_fabric_design, build_fabric_preview
from xiaomang_pattern_lab.fabric_candidate import build_fabric_candidate, instance_matrix, _prototype_components
from xiaomang_pattern_lab.fabric_fusion import FabricFusionService, FabricFusionFailure
from xiaomang_pattern_lab.fabric_stl import export_validated_fabric_stl
from xiaomang_pattern_lab.stl_export import STLExporter
from xiaomang_pattern_lab.mesh_validation import MeshValidator
from xiaomang_pattern_lab.shared_fields import WaveField, LinearField, SizeModifier, RotationModifier, FieldMapping
from fastapi.testclient import TestClient
from xiaomang_pattern_lab.web import create_app


def fixture(count=9, mode='cells_only'):
    doc = PatternDocument(Canvas(120, 80, 'svg', .5, 20, 40), Reference('', False), [
        RectElement(f'square-{i}', 30+i%13*12, 50+i//13*12, 6, 6, rotation=(i%3)*15) for i in range(count)])
    doc.metadata['fabric_config'] = {'config_version':1, 'shape_source':'original', 'output_mode':mode,
        'base': {'type':'solid','thickness_mm':.6,'margin_mm':1},
        'original_shape': {'size_scale':1,'height_mm':2},
        'placement': {'mode':'area_fill','spacing_x_mm':1,'spacing_y_mm':1},
        # Preserved unused Fin is not the shape source.
        'unit_cell': {'type':'fin','width_mm':4,'depth_mm':1,'height_mm':8}}
    return doc


def build(doc):
    dto = PatternDocumentDTO.from_document(doc, 'original-shape', 7)
    design = build_fabric_design(doc, dto, preview_limit=False)
    candidate = build_fabric_candidate(design.plan, design.config.base, design.design_bounds_mm,
        document_id=dto.document_id, document_revision=7, output_mode=design.config.output_mode)
    return design, candidate


def hole():
    return FilledRegionElement('hole',40,60,12,12,rotation=20, style={'fill':'black','fill-rule':'evenodd'},
        path_data='M0 0H12V12H0Z M3 3H9V9H3Z',base_x=0,base_y=0,base_width=12,base_height=12)


def test_169_final_squares_once_no_base_no_area_fill_and_no_source_mutation():
    doc = fixture(169)
    doc.fields = [LinearField('user-linear', angle=0,start=30,end=174).to_dict()]
    doc.modifiers = [SizeModifier('size','user-linear',FieldMapping(.7,1)).to_dict(),
        RotationModifier('rotate','user-linear',FieldMapping(-10,10)).to_dict()]
    original = deepcopy(doc.to_dict())
    design, candidate = build(doc)
    assert len(design.plan.instances) == len(candidate.cell_meshes) == 169
    assert candidate.base_mesh is None and candidate.report['attachment_counts']['VALID'] == 169
    assert candidate.report['components']['prefusion_components'] == 169
    assert design.metadata['placement_mode'] == 'pattern_points'
    assert all(i.rotation_deg == 0 and i.z_mm == 0 and i.cell_type == 'original_contour' for i in design.plan.instances)
    assert doc.to_dict() == original
    final = FabricFusionService().build(candidate)
    data, _ = export_validated_fabric_stl(final)
    mesh = STLExporter.reload_bytes_as_mesh_result(data)
    validation = MeshValidator().validate(mesh)
    assert validation.is_valid and validation.component_count == 169 and validation.degenerate_face_count == 0


@pytest.mark.parametrize('kind',['uniform','linear','wave'])
@pytest.mark.parametrize('mode',['cells_only','cells_with_base'])
def test_each_element_height_preview_candidate_and_roundtrip(kind, mode):
    doc = fixture(mode=mode)
    if kind != 'uniform':
        doc.fields = [(LinearField('height', angle=0,start=15,end=63) if kind=='linear' else WaveField('height', wavelength=24,angle=45)).to_dict()]
        doc.metadata['fabric_config']['field_modifiers'] = {'height': {'enabled':True,'field_id':'height','min_height_mm':2,'max_height_mm':5}}
    design, candidate = build(doc)
    for i, mesh in zip(design.plan.instances, candidate.cell_meshes):
        value = (i.x_mm-15)/48 if kind=='linear' else (math.sin(2*math.pi*(i.x_mm+i.y_mm)/math.sqrt(2)/24)+1)/2
        expected = 2 if kind=='uniform' else 2+3*value
        assert i.height_mm == pytest.approx(expected)
        assert mesh.bounds[0,2] == (0 if mode=='cells_only' else .6)
        assert mesh.bounds[1,2] == pytest.approx(i.z_mm+expected)
    final = FabricFusionService().build(candidate)
    payload, _ = export_validated_fabric_stl(final)
    mesh = STLExporter.reload_bytes_as_mesh_result(payload)
    validation = MeshValidator().validate(mesh)
    assert validation.is_valid and validation.is_watertight and validation.degenerate_face_count == 0
    assert mesh.mesh.volume > 0 and mesh.mesh.is_winding_consistent
    assert validation.component_count == (9 if mode=='cells_only' else 1)
    np.testing.assert_allclose(mesh.mesh.bounds, final.report['bounds_mm'], atol=1e-5, rtol=0)


def test_real_hole_and_size_around_anchor_no_double_rotation():
    doc = fixture(); doc.elements = [hole()]
    first, a = build(doc)
    original_vertices = a.cell_meshes[0].vertices.copy()
    assert a.cell_meshes[0].euler_number == 0
    # 12x12 source square minus 6x6 hole, mm scale .5, extrusion 2mm.
    assert a.cell_meshes[0].volume == pytest.approx((144-36)*.25*2)
    doc.metadata['fabric_config']['original_shape']['size_scale'] = 1.5
    second, b = build(doc)
    i = second.plan.instances[0]
    np.testing.assert_allclose(b.cell_meshes[0].vertices[:,:2],
        (original_vertices[:,:2]-[i.x_mm,i.y_mm])*1.5+[i.x_mm,i.y_mm], atol=1e-12)
    assert b.cell_meshes[0].volume == pytest.approx(a.cell_meshes[0].volume*1.5**2)
    assert b.cell_meshes[0].euler_number == 0
    data, _ = export_validated_fabric_stl(FabricFusionService().build(b))
    reloaded = STLExporter.reload_bytes_as_mesh_result(data)
    assert reloaded.mesh.euler_number == 0 and MeshValidator().validate(reloaded).is_valid


def test_multiple_parts_one_element_keep_ids_one_height_and_actual_component_count():
    doc=fixture(); item=hole();item.id='multi';item.style={'fill':'black','fill-rule':'evenodd'}
    item.path_data='M0 0H4V4H0Z M8 8H12V12H8Z';doc.elements=[item]
    design, candidate=build(doc)
    assert len(design.plan.instances)==1 and candidate.report['components']['cell_components']==2
    assert candidate.report['attachments'][0]['source_id']=='multi'
    final=FabricFusionService().build(candidate)
    assert final.report['connected_component_count']==2


def test_original_grid_material_attachment_and_detached_hole_keep_existing_strict_gate():
    doc=fixture(mode='cells_with_base')
    doc.metadata['fabric_config']['base'].update(type='grid',spacing_x_mm=4,spacing_y_mm=4,line_width_mm=2)
    design,candidate=build(doc)
    assert candidate.report['attachment_counts']['ATTACHED']==9
    final=FabricFusionService().build(candidate)
    data,_=export_validated_fabric_stl(final)
    validation=MeshValidator().validate(STLExporter.reload_bytes_as_mesh_result(data))
    assert validation.is_valid and validation.is_watertight and validation.component_count==1
    doc=fixture(1,mode='cells_with_base')
    doc.metadata['fabric_config']['base'].update(type='grid',spacing_x_mm=5,spacing_y_mm=5,line_width_mm=.5)
    _,candidate=build(doc)
    assert candidate.report['attachment_counts']['DETACHED']==1
    with pytest.raises(FabricFusionFailure): FabricFusionService().build(candidate)


def test_original_rejects_invalid_height_empty_and_density_empty_without_reinterpreting_old_null():
    doc=fixture()
    for height in (0, -1, float('nan')):
        bad=deepcopy(doc);bad.metadata['fabric_config']['original_shape']['height_mm']=height
        with pytest.raises(ValueError): build(bad)
    doc.elements=[]
    with pytest.raises(ValueError): build(doc)
    doc=fixture(mode='cells_with_base');doc.fields=[{'id':'zero','type':'constant','parameters':{'value':0}}]
    doc.metadata['fabric_config']['field_modifiers']={'density':{'enabled':True,'field_id':'zero','threshold':1}}
    with pytest.raises(ValueError,match='没有启用'): build(doc)
    legacy=fixture();del legacy.metadata['fabric_config']['shape_source'];del legacy.metadata['fabric_config']['unit_cell']
    payload=build_fabric_preview(legacy,PatternDocumentDTO.from_document(legacy,'old',1))
    assert payload['count']==0 and payload['prototype'] is None


def test_original_api_preview_export_and_content_bound_stale_guard(monkeypatch):
    monkeypatch.setenv('XIAOMANG_ENV','staging')
    monkeypatch.setenv('XIAOMANG_FABRIC_STL_TEST_EXPORT','1')
    body={'document':PatternDocumentDTO.from_document(fixture(),'original-api',7).to_dict(),'document_revision':7}
    with TestClient(create_app()) as client:
        preview=client.post('/api/v1/fabric/preview',json=body)
        assert preview.status_code==200,preview.text
        assert preview.json()['shape_source']=='original' and len(preview.json()['contour_prototypes'])==9
        built=client.post('/api/v1/fabric/fusion',json=body)
        assert built.status_code==200,built.text
        assert built.json()['final_fabric_mesh_ready'] and built.json()['connected_component_count']==9
        url='/api/v1/fabric/'+built.json()['final_fabric_mesh_id']+'/model.stl'
        file=client.post(url,json=body)
        assert file.status_code==200 and file.headers['content-type']=='model/stl'
        assert MeshValidator().validate(STLExporter.reload_bytes_as_mesh_result(file.content)).is_valid
        for key,value in [('shape_source','unit_cell'),('output_mode','cells_with_base')]:
            changed=deepcopy(body);changed['document']['document']['metadata']['fabric_config'][key]=value
            assert client.post(url,json=changed).status_code==422
        changed=deepcopy(body);changed['document']['document']['metadata']['fabric_config']['original_shape']['size_scale']=1.3
        assert client.post(url,json=changed).status_code==422
        empty=deepcopy(body);empty['document']['document']['elements']=[];empty['document']['document']['transforms']={}
        assert client.post('/api/v1/fabric/fusion',json=empty).status_code==422
