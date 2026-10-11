"""Portable P2 recipes: existing evaluate, influence weights and STL exporters only."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import json
import math
import sys
import xml.etree.ElementTree as ET
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from ppg.foundation import PatternDocument, Canvas, Reference
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.evaluation import evaluate_pattern_document, parametric_model_from_document
from xiaomang_pattern_lab.design_controls import apply_design_controls
from xiaomang_pattern_lab.influence_areas import InfluenceArea
from xiaomang_pattern_lab.fabric_preview import build_fabric_design
from xiaomang_pattern_lab.shared_fields import NoiseField, FieldContext
from xiaomang_pattern_lab.manufacturing_geometry import ManufacturingGeometryAdapter

IDS = ('local-breath', 'coral-grains', 'ripple-center')
def fixture(id):
    return PatternDocumentDTO.from_dict(json.loads((ROOT / 'tests/fixtures/pattern_presets' / (id+'.pattern.json')).read_text(encoding='utf8')))

@pytest.mark.parametrize('id', IDS)
def test_deterministic_graph_final_geometry_and_real_thumbnail(id):
    dto = fixture(id); doc = dto.to_document(); before = deepcopy(dto.to_dict())
    first = evaluate_pattern_document(doc); second = evaluate_pattern_document(doc)
    assert [asdict(e) for e in first] == [asdict(e) for e in second]
    assert dto.to_dict() == before and len(first) == (121 if id == 'coral-grains' else 81)
    svg = ET.parse(ROOT / 'web/src/document/patternPresetThumbnails' / (id+'.svg')).getroot()
    shapes = list(svg.findall('.//{http://www.w3.org/2000/svg}circle')) or list(svg.findall('.//{http://www.w3.org/2000/svg}ellipse'))
    assert len(shapes) == len(first)
    for element, shape in zip(first, shapes):
        np.testing.assert_allclose([element.x, element.y], [float(shape.get('cx')), float(shape.get('cy'))], atol=1e-8, rtol=0)
        if shape.tag.endswith('ellipse'):
            np.testing.assert_allclose([element.width / 2, element.height / 2], [float(shape.get('rx')), float(shape.get('ry'))], atol=1e-8, rtol=0)
        else:
            assert element.width / 2 == pytest.approx(float(shape.get('r')))

def test_local_breath_true_outside_preservation_curve_combination_disable():
    doc = fixture('local-breath').to_document(); source = apply_design_controls(doc, parametric_model_from_document(doc).generate())
    areas = doc.modifiers[0]['influence_areas']
    for mode in ('ellipse', 'curve', 'both', 'disabled'):
        for area in areas: area['enabled'] = mode == 'both' or area['type'] == mode
        final = evaluate_pattern_document(doc)
        weights = [max(InfluenceArea(**a).weight(e) for a in areas) for e in source]
        for e, f, weight in zip(source, final, weights):
            assert (e.x, e.y, e.rotation) == (f.x, f.y, f.rotation)
            assert f.width == pytest.approx(e.width * (1 + .30 * weight))
            if weight == 0: assert asdict(e) == asdict(f)
        reverse = deepcopy(doc); reverse.modifiers[0]['influence_areas'].reverse()
        assert [asdict(e) for e in final] == [asdict(e) for e in evaluate_pattern_document(reverse)]
        if mode != 'disabled': assert max(weights) > 0

def test_coral_noise_and_public_random_seed_repetition_without_accumulation():
    doc = fixture('coral-grains').to_document(); source = parametric_model_from_document(doc).generate()
    controlled = apply_design_controls(doc, source); final = evaluate_pattern_document(doc)
    assert all(e.type == 'ellipse' for e in final)
    field = NoiseField('probe', **doc.fields[0]['parameters']); context = FieldContext.from_elements(controlled)
    values = [field.evaluate(e, context) for e in controlled]
    assert max(values) - min(values) > .1
    for e, f, value in zip(controlled, final, values):
        assert (f.x, f.y, f.rotation) == (e.x, e.y, e.rotation)
        assert f.width == pytest.approx(e.width * (.60 + .52 * value))
    changed = deepcopy(doc); changed.fields[0]['parameters']['seed'] = 28
    assert [e.width for e in evaluate_pattern_document(changed)] != [e.width for e in final]
    assert [asdict(e) for e in evaluate_pattern_document(doc)] == [asdict(e) for e in final]

def test_radial_center_radius_exterior_and_no_position_or_rotation_change():
    doc = fixture('ripple-center').to_document(); source = parametric_model_from_document(doc).generate()
    record = doc.metadata['web_pattern_preset']; layers = doc.metadata['xiaomang_pattern_lab.shared_modifiers']['modifiers']
    layer = next(l for l in layers if l['id'] == record['radial_layer_id']); p = layer['parameters']
    p['radius'] = 18
    final = evaluate_pattern_document(doc); outside = 0
    for e, f in zip(source, final):
        distance = math.hypot(e.x-p['center_x'], e.y-p['center_y'])
        ratio = 1.25 + (.65-1.25) * min(distance/18, 1)
        assert (e.x, e.y, e.rotation) == (f.x, f.y, f.rotation)
        assert f.width == pytest.approx(e.width*ratio)
        if distance >= 18: outside += 1; assert f.width == pytest.approx(e.width*.65)
    assert outside > 0

@pytest.mark.parametrize('id', IDS)
def test_original_and_fin_final_mm_size_inherited_once_height_not_rebound(id):
    dto = fixture(id); doc = dto.to_document(); final = evaluate_pattern_document(doc)
    doc.fields.append({'id':'height-user','type':'constant','parameters':{'value':.5}})
    config = {'config_version':1, 'shape_source':'original', 'output_mode':'cells_only',
        'base':{'type':'solid','thickness_mm':.6,'margin_mm':0}, 'original_shape':{'size_scale':1,'height_mm':2},
        'field_modifiers':{'height':{'enabled':True,'field_id':'height-user','min_height_mm':2,'max_height_mm':4}}}
    doc.metadata['fabric_config'] = config
    original = build_fabric_design(doc, PatternDocumentDTO.from_document(doc,'original',1), preview_limit=False)
    converted = ManufacturingGeometryAdapter().adapt_evaluated_document(doc, final)
    for e, i in zip(final, original.plan.instances):
        assert (i.x_mm, i.y_mm, i.z_mm, i.height_mm) == (e.x, e.y, 0, 3)
        # Original contours already bake source rotation once; it is NOT a
        # second instance rotation. Compare the actual transformed boundary.
        boundary = np.array([p for polygon in converted.geometry.polygons if polygon.source_element_id == e.id for p in polygon.outer])
        prototype = original.plan.contour_prototypes[i.id]
        actual = prototype.vertices[:,:2] * [i.cell_width_mm, i.cell_depth_mm] + [i.x_mm, i.y_mm]
        assert np.linalg.norm(boundary[:,None,:]-actual[None,:,:],axis=2).min(axis=1).max() < 1e-9
        np.testing.assert_allclose(np.ptp(actual,axis=0), np.ptp(boundary,axis=0),atol=1e-9,rtol=0)
    config.update(shape_source='unit_cell',unit_cell={'type':'fin','width_mm':4,'depth_mm':2,'height_mm':3,'size_mode':'follow_pattern'},placement={'mode':'pattern_points','spacing_x_mm':5,'spacing_y_mm':5})
    fin = build_fabric_design(doc, PatternDocumentDTO.from_document(doc,'fin',2), preview_limit=False)
    base_width = doc.metadata['xiaomang_pattern_lab.parametric']['grid']['element_width']
    base_height = doc.metadata['xiaomang_pattern_lab.parametric']['grid']['element_height']
    for e, i in zip(final, fin.plan.instances):
        assert i.cell_width_mm == pytest.approx(4*e.width/base_width)
        assert i.cell_depth_mm == pytest.approx(2*e.height/base_height)
        assert i.height_mm == 3 and i.rotation_deg == e.rotation

def generate(source_dir):
    """Build portable fixtures and real thumbnails from TS-produced DTOs."""
    from ppg.foundation.svg_exporter import pattern_document_to_svg
    for id in IDS:
        source = Path(source_dir)/(id+'.json')
        data = json.loads(source.read_text(encoding='utf8')); dto = PatternDocumentDTO.from_dict(data)
        doc = dto.to_document(); final = evaluate_pattern_document(doc)
        target = ROOT/'tests/fixtures/pattern_presets'/(id+'.pattern.json')
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
        path = ROOT/'web/src/document/patternPresetThumbnails'/(id+'.svg')
        pattern_document_to_svg(PatternDocument(doc.canvas, Reference(''), final), path)
        print(id, len(final), str(path))

if __name__ == '__main__':
    generate(sys.argv[1])
