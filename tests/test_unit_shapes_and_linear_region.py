"""Authority and STL regression for new prototypes and local size scope."""
from copy import deepcopy
import numpy as np
import pytest
from ppg.foundation import CircleElement, EllipseElement, RectElement
from xiaomang_pattern_lab.fabric_cells import UnitCellDefinition, UNIT_CELL_REGISTRY
from xiaomang_pattern_lab.fabric_fusion import FabricFusionService
from xiaomang_pattern_lab.fabric_stl import export_validated_fabric_stl
from xiaomang_pattern_lab.stl_export import STLExporter
from xiaomang_pattern_lab.shared_fields import (SharedFieldEngine, FieldRegistry, LinearField, ConstantField,
    SizeModifier, FieldPositionModifier, FieldMapping, LinearSizeRegion)
from tests.test_fabric_cells_only_1a import fixture, build

SHAPES = ('dome', 'frustum', 'hex_prism', 'wedge', 'cross', 'ring')

@pytest.mark.parametrize('kind', SHAPES)
@pytest.mark.parametrize('mode', ['cells_only', 'cells_with_base'])
def test_prototype_final_and_real_binary_roundtrip(kind, mode):
    prototype = UNIT_CELL_REGISTRY.create(UnitCellDefinition(kind, 4.8, 4.8, 3))
    assert prototype.is_watertight and prototype.is_winding_consistent and prototype.volume > 0
    assert np.min(prototype.area_faces) > 1e-12
    np.testing.assert_allclose(prototype.bounds, [[-2.4,-2.4,0],[2.4,2.4,3]], atol=1e-8)
    if kind == 'dome':
        assert np.count_nonzero(prototype.vertices[:,2] == 3) == 1
    if kind == 'ring':
        bottom = prototype.triangles[np.all(prototype.triangles[:,:,2] == 0, axis=1)]
        assert len(bottom) and all(np.linalg.norm(t.mean(axis=0)[:2]) > .9 for t in bottom)
        assert prototype.euler_number == 0  # Closed genus-one shell: real through-hole.
        from shapely.geometry import Polygon, Point
        assert all(not Polygon(t[:,:2]).covers(Point(0,0)) for t in bottom)
    doc = fixture(mode)
    doc.metadata['fabric_config']['unit_cell']['type'] = kind
    design, candidate = build(doc)
    assert design.plan.prototype is build(doc)[0].plan.prototype
    assert len(candidate.cell_meshes) == 9
    final = FabricFusionService().build(candidate)
    payload, report = export_validated_fabric_stl(final)
    reopened = STLExporter.reload_bytes_as_mesh_result(payload).mesh
    assert reopened.is_watertight and reopened.is_winding_consistent and reopened.volume > 0
    assert report['roundtrip_validation']['degenerate_face_count'] == 0
    assert report['roundtrip_validation']['component_count'] == (9 if mode == 'cells_only' else 1)
    np.testing.assert_allclose(reopened.bounds, final.mesh_result.mesh.bounds, atol=1e-5)

@pytest.mark.parametrize('kind', ['frustum','cross','ring'])
@pytest.mark.parametrize('ratio', [.1,.3,.9])
def test_shape_parameter_extremes_and_cache_identity(kind, ratio):
    mesh = UNIT_CELL_REGISTRY.create(UnitCellDefinition(kind, 4, 6, 3, ratio))
    assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume > 0 and mesh.area_faces.min() > 1e-12
    with pytest.raises(ValueError):
        UnitCellDefinition(kind,4,6,3,0)

def engine(modifiers):
    return SharedFieldEngine(FieldRegistry([LinearField('axis', angle=0,start=10,end=30), ConstantField('constant', value=.5)]), modifiers)

def test_local_scope_preserves_outside_prior_size_and_center_and_serializes():
    source = [CircleElement(str(i), x, 50, 4, 4) for i,x in enumerate([0,10,20,30,40])]
    before = deepcopy(source)
    prior = SizeModifier('prior','constant',FieldMapping(.8,.8))
    local = SizeModifier('local','axis',FieldMapping(.6,1.2),region=LinearSizeRegion(20,50,20,10,0))
    result = engine([prior,local]).apply(source)
    assert [e.x for e in result] == [e.x for e in before]
    assert [e.width for e in result] == pytest.approx([3.2,1.92,2.88,3.84,3.2])
    assert [e.width for e in source] == [4]*5
    restored = SharedFieldEngine.from_dict(engine([prior,local]).to_dict())
    assert [e.width for e in restored.apply(source)] == [e.width for e in result]
    assert 'region' not in prior.to_dict()
    # Old global layers must not gain roundoff from a new neutral-blend operation.
    old_modifier = SizeModifier('tiny','constant',FieldMapping(.05,.05))
    old = engine([old_modifier]).apply([CircleElement('old',0,0,20,20)])[0]
    assert old.width == old.height == 20*old_modifier.scale(.5)

def test_region_uses_effect_input_centers_and_feather_blends_only_current_delta():
    source = [CircleElement('a',0,50,4,4),CircleElement('b',15,50,4,4)]
    move = FieldPositionModifier('move','constant',FieldMapping(10,10),FieldMapping(0,0))
    local = SizeModifier('local','axis',FieldMapping(.5,1.5),region=LinearSizeRegion(20,50,20,10,0,2))
    result = engine([move,local]).apply(source)
    assert [(e.x,e.width) for e in result] == [(10,4),(25,5)]
    edge = engine([SizeModifier('prior','constant',FieldMapping(.8,.8)),local]).apply([CircleElement('e',11,50,4,4)])[0]
    assert edge.width == pytest.approx(3.2*(1+(.55-1)*.5))

@pytest.mark.parametrize('values', [(0,10,0),(-1,10,0),(10,0,0),(10,10,6),(10,10,-1),(float('nan'),10,0)])
def test_invalid_regions_rejected(values):
    with pytest.raises(ValueError):
        LinearSizeRegion(10,20,values[0],values[1],45,values[2])

@pytest.mark.parametrize('shape', ['circle','ellipse','rect'])
@pytest.mark.parametrize('factor', [.5,2])
def test_authoritative_web_scope_and_fabric_parity(shape, factor):
    from fastapi.testclient import TestClient
    from xiaomang_pattern_lab.web import create_app
    from xiaomang_pattern_lab.contracts import PatternDocumentDTO
    doc = fixture(factor=factor)
    element_class = {'circle': CircleElement, 'ellipse': EllipseElement, 'rect': RectElement}[shape]
    doc.elements = [element_class(e.id,e.x,e.y,e.width,e.height) for e in doc.elements]
    doc.fields = [ConstantField('prior',.5).to_dict(),LinearField('axis',angle=0,start=34,end=74).to_dict()]
    doc.modifiers = [SizeModifier('prior-size','prior',FieldMapping(.8,.8)).to_dict(),
        SizeModifier('local','axis',FieldMapping(.6,1.2),region=LinearSizeRegion(54,36,40,30,0)).to_dict()]
    dto = PatternDocumentDTO.from_document(doc,'web-scope',7).to_dict()
    with TestClient(create_app()) as client:
        response = client.post('/api/v1/evaluate',json={'schema_version':'1.0','document_id':'web-scope','document':dto,'document_revision':7})
        assert response.status_code == 200, response.text
        geometry = response.json()['geometry']
        preview = client.post('/api/v1/fabric/preview',json={'document':dto,'document_revision':7})
        assert preview.status_code == 200,preview.text
    for e,g,instance in zip(doc.elements,geometry,preview.json()['instances']):
        ratio = .8 * (.6 + .6*(e.x-34)/40) if e.x >= 34 else .8
        assert g['x'] == e.x*factor and g['y'] == e.y*factor
        assert g['width'] == pytest.approx(e.width*factor*ratio)
        assert instance['cell_width_mm'] == pytest.approx(4.8*ratio)
        assert instance['height_mm'] == 3 and instance['z_mm'] == 0

@pytest.mark.parametrize('kind', SHAPES)
def test_grid_attachment_and_real_fusion(kind):
    doc = fixture('cells_with_base')
    config = doc.metadata['fabric_config']
    config['unit_cell']['type'] = kind
    config['base'] = {'type':'grid','thickness_mm':.6,'margin_mm':1,'spacing_x_mm':5,'spacing_y_mm':5,'line_width_mm':1}
    design,candidate = build(doc)
    assert candidate.report['attachment_counts']['ATTACHED'] == 9
    final = FabricFusionService().build(candidate)
    _,report = export_validated_fabric_stl(final)
    assert report['roundtrip_validation']['component_count'] == 1
    assert report['roundtrip_validation']['degenerate_face_count'] == 0

@pytest.mark.parametrize('kind', SHAPES)
def test_each_new_shape_keeps_final_pattern_and_fabric_transforms_and_density(kind):
    from xiaomang_pattern_lab.shared_fields import RotationModifier
    from xiaomang_pattern_lab.fabric_candidate import instance_matrix
    doc = fixture()
    doc.fields = [LinearField('axis',0,14,54).to_dict()]
    doc.modifiers = [SizeModifier('pattern-size','axis',FieldMapping(.8,1.2)).to_dict(),
        RotationModifier('pattern-rotation','axis',FieldMapping(10,40)).to_dict()]
    cfg = doc.metadata['fabric_config']; cfg['unit_cell']['type'] = kind
    cfg['field_modifiers'] = {
        'height':{'enabled':True,'field_id':'axis','min_height_mm':2,'max_height_mm':6},
        'scale':{'enabled':True,'field_id':'axis','min_scale':.8,'max_scale':1.2},
        'density':{'enabled':True,'field_id':'axis','threshold':.5},
        'orientation':{'enabled':True,'field_id':'axis','min_angle_deg':10,'max_angle_deg':30}}
    design,candidate = build(doc)
    enabled = [i for i in design.plan.instances if i.enabled]
    assert len(enabled) == len(candidate.cell_meshes) == 6
    for i,mesh in zip(enabled,candidate.cell_meshes):
        value = (i.x_mm-14)/40
        assert i.cell_width_mm == pytest.approx(4.8*(.8+.4*value)**2)
        assert i.height_mm == pytest.approx(2+4*value)
        assert i.rotation_deg == pytest.approx(20+50*value)
        matrix = instance_matrix(i, design.plan.cell)
        np.testing.assert_allclose(mesh.vertices,design.plan.prototype.vertices@matrix[:3,:3].T+matrix[:3,3],atol=1e-9)
        assert mesh.bounds[0,2] == 0
    _,report = export_validated_fabric_stl(FabricFusionService().build(candidate))
    assert report['roundtrip_validation']['component_count'] == 6
    assert report['roundtrip_validation']['degenerate_face_count'] == 0
