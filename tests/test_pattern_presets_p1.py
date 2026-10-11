"""Portable documents produced by the Web recipe constructor; existing engines only."""
from copy import deepcopy
from pathlib import Path
import json
import xml.etree.ElementTree as ET
import numpy as np
import pytest
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.evaluation import evaluate_pattern_document, parametric_model_from_document
from xiaomang_pattern_lab.fabric_preview import build_fabric_design
from xiaomang_pattern_lab.fabric_candidate import build_fabric_candidate
from xiaomang_pattern_lab.fabric_fusion import FabricFusionService
from xiaomang_pattern_lab.fabric_stl import export_validated_fabric_stl
from xiaomang_pattern_lab.stl_export import STLExporter
from xiaomang_pattern_lab.mesh_validation import MeshValidator

ROOT = Path(__file__).resolve().parents[1]
IDS = ('precision-stagger', 'spectrum-fade', 'diagonal-tide')
def preset(id):
    return PatternDocumentDTO.from_dict(json.loads((ROOT / 'tests/fixtures/pattern_presets' / (id+'.pattern.json')).read_text(encoding='utf8')))

@pytest.mark.parametrize('id', IDS)
def test_deterministic_editable_graph_and_actual_thumbnail(id):
    dto = preset(id); before = deepcopy(dto.to_dict()); doc = dto.to_document()
    result = evaluate_pattern_document(doc)
    assert len(result) == 81
    assert [e.to_dict() if hasattr(e, 'to_dict') else vars(e) for e in result] == [e.to_dict() if hasattr(e, 'to_dict') else vars(e) for e in evaluate_pattern_document(doc)]
    assert dto.to_dict() == before and doc.metadata['web_pattern_preset']['id'] == id
    circles = ET.parse(ROOT/'web/src/document/patternPresetThumbnails'/(id+'.svg')).getroot().findall('{http://www.w3.org/2000/svg}circle')
    assert len(circles) == 81
    for e, c in zip(result, circles):
        np.testing.assert_allclose([e.x, e.y, e.width/2], [float(c.get('cx')), float(c.get('cy')), float(c.get('r'))], atol=1e-8, rtol=0)
    if id == 'precision-stagger':
        assert doc.fields == doc.modifiers == []
        assert result[9].x - result[0].x == 3 and result[9].y - result[0].y == pytest.approx(5.2)
    else:
        source = parametric_model_from_document(doc).generate()
        assert [(e.x,e.y,e.rotation) for e in result] == [(e.x,e.y,e.rotation) for e in source]
        assert max(e.width for e in result) - min(e.width for e in result) > 1.5
        assert len(doc.fields) == len(doc.modifiers) == 1

@pytest.mark.parametrize('id', ('spectrum-fade', 'diagonal-tide'))
def test_original_and_pattern_points_preserve_final_size_once_and_height_binding(id):
    dto = preset(id); doc = dto.to_document(); final = evaluate_pattern_document(doc)
    doc.fields.append({'id':'height-user','type':'wave','parameters':{'angle':0,'wavelength':36,'phase':0,'amplitude':1,'offset':0,'invert':False}})
    doc.metadata['fabric_config'] = {'config_version':1, 'shape_source':'original', 'output_mode':'cells_only',
        'base':{'type':'solid','thickness_mm':.6,'margin_mm':0}, 'original_shape':{'size_scale':1,'height_mm':2},
        'field_modifiers':{'height':{'enabled':True,'field_id':'height-user','min_height_mm':2,'max_height_mm':6}}}
    design = build_fabric_design(doc, PatternDocumentDTO.from_document(doc,'original',1), preview_limit=False)
    for e, i in zip(final, design.plan.instances):
        assert i.x_mm == e.x and i.y_mm == e.y and i.z_mm == 0
        assert i.cell_width_mm == pytest.approx(e.width) and i.cell_depth_mm == pytest.approx(e.height)
    heights = [i.height_mm for i in design.plan.instances]
    doc.metadata['fabric_config'].update(shape_source='unit_cell', unit_cell={'type':'fin','width_mm':4,'depth_mm':2,'height_mm':3,'size_mode':'follow_pattern'},
        placement={'mode':'pattern_points','spacing_x_mm':5,'spacing_y_mm':5})
    cells = build_fabric_design(doc, PatternDocumentDTO.from_document(doc,'fin',2), preview_limit=False)
    for e, i in zip(final, cells.plan.instances):
        assert i.cell_width_mm == pytest.approx(4*e.width/3.4)
        assert i.cell_depth_mm == pytest.approx(2*e.height/3.4)
        assert i.x_mm == e.x and i.y_mm == e.y and i.rotation_deg == e.rotation
    assert [i.height_mm for i in cells.plan.instances] == heights

def test_representative_original_fabric_stl_roundtrip_keeps_all_independent_units():
    dto = preset('diagonal-tide'); doc = dto.to_document()
    doc.metadata['fabric_config'] = {'config_version':1, 'shape_source':'original', 'output_mode':'cells_only',
        'base':{'type':'solid','thickness_mm':.6,'margin_mm':0}, 'original_shape':{'size_scale':1,'height_mm':2}}
    dto = PatternDocumentDTO.from_document(doc,'stl-presets',1)
    design = build_fabric_design(doc,dto,preview_limit=False)
    candidate = build_fabric_candidate(design.plan,design.config.base,design.design_bounds_mm,document_id=dto.document_id,document_revision=1,output_mode='cells_only')
    fused = FabricFusionService().build(candidate)
    payload, exported = export_validated_fabric_stl(fused)
    mesh = STLExporter.reload_bytes_as_mesh_result(payload); report = MeshValidator().validate(mesh)
    assert report.is_valid and report.is_watertight and report.component_count == 81
    assert report.degenerate_face_count == 0 and mesh.mesh.is_winding_consistent and mesh.mesh.volume > 0
    assert mesh.mesh.bounds[0,2] == 0 and mesh.mesh.bounds[1,2] == 2
    assert exported['roundtrip_validation']['component_count'] == 81

@pytest.mark.parametrize('id', ('spectrum-fade', 'diagonal-tide'))
def test_nonzero_world_origin_rectangular_board_and_half_mm_scale(id):
    doc = preset(id).to_document(); before = evaluate_pattern_document(doc)
    doc.canvas.width,doc.canvas.height,doc.canvas.mm_per_unit,doc.canvas.origin_x,doc.canvas.origin_y = 140,100,.5,20,40
    model = doc.metadata['xiaomang_pattern_lab.parametric']['grid']
    for key in ('spacing_x','spacing_y','element_width','element_height'):
        model[key] *= 2
    model['offset_x'],model['offset_y'] = 80,100  # physical translation +10,+20 mm
    for field in doc.fields:
        if field['type']=='linear':
            field['parameters']['start'] = field['parameters']['start']*2 + 20
            field['parameters']['end'] = field['parameters']['end']*2 + 20
        else:
            # Wave is world-anchored: compensate physical translation in phase.
            import math
            angle = math.radians(field['parameters']['angle'])
            field['parameters']['phase'] -= 2*math.pi*(10*math.cos(angle)+20*math.sin(angle))/field['parameters']['wavelength']
            field['parameters']['wavelength'] *= 2
    result = evaluate_pattern_document(doc)
    np.testing.assert_allclose([[e.x*.5-10,e.y*.5-20,e.width*.5,e.height*.5] for e in result],
                               [[e.x,e.y,e.width,e.height] for e in before],atol=1e-10,rtol=0)
