"""New regression samples, not a reconstruction of the missing historical SVG."""
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from ppg.foundation import SVGNormalizer, PatternDocument, save_pattern_document, load_pattern_document, pattern_document_to_svg
from ppg.foundation.region_geometry import bounds_of_polygons, filled_region_polygons
from ppg.foundation.svg_normalizer import _path_bounds
from xiaomang_pattern_lab.influence_areas import InfluenceArea
from xiaomang_pattern_lab.shared_fields import ConstantField, SizeModifier, FieldMapping, FieldRegistry, SharedFieldEngine
from xiaomang_pattern_lab.manufacturing_geometry import ManufacturingGeometryAdapter
from xiaomang_pattern_lab.mesh_validation import MeshValidator
from xiaomang_pattern_lab.stl_export import STLExporter
from xiaomang_pattern_lab.web import create_app


FIXTURE = Path(__file__).parent / 'fixtures' / 'svg_hv_bounds_regression.svg'


@pytest.mark.parametrize('path,bounds', [
    ('M12 34 H42 V54 H12 Z', (12,34,42,54)),
    ('M12 34 h30 v20 h-30 z', (12,34,42,54)),
    ('m12 34 h30 v20 h-30 z', (12,34,42,54)),
    ('M12 34 H22 42 V44 54 H12 Z', (12,34,42,54)),
    ('M12 34 h10 20 v10 10 h-30 z', (12,34,42,54)),
    ('M12 34 h30 v10 h12 z', (12,34,54,44)),
    ('M12 34 H42 V54 H12 Z M70 80 h5 v6 h-5 z', (12,34,75,86)),
    ('M31 83 H55 V107 H31 Z M37 89 V101 H49 V89 Z', (31,83,55,107)),
    ('M12 34 H42 V54', (12,34,42,54)),
    ('M12 34 h30', (12,34,42,34)),
    ('M12 34 v20', (12,34,12,54)),
    ('M1e1 2e1 h3e1 v1e1 h-3e1 z', (10,20,40,30)),
    ('M31 83 h24 v24 h-24 z M37 89 v12 h12 v-12 z', (31,83,55,107)),
    ('M10 20 C10 20 15 20 20 20 H30 v10 h-20 z', (10,20,30,30)),
])
def test_hv_bounds_commands_not_number_pairs(path, bounds):
    assert _path_bounds(path) == pytest.approx(bounds)


@pytest.mark.parametrize('mode', ['semantic', 'faithful'])
@pytest.mark.parametrize('transform,expected', [
    ('', (31,83,55,107)),
    ('translate(7 -11)', (38,72,62,96)),
    ('scale(2 3)', (62,249,110,321)),
])
def test_new_hole_sample_bounds_center_and_import_transform(tmp_path, mode, transform, expected):
    svg = FIXTURE.read_text(encoding='utf-8').replace('id="hole"', f'id="hole" transform="{transform}"')
    source = tmp_path / 'new-regression.svg'
    source.write_text(svg, encoding='utf-8')
    doc = SVGNormalizer().normalize_file(str(source), normalization_mode=mode)
    element = doc.element('hole')
    x0,y0,x1,y1 = expected
    assert (element.x,element.y,element.width,element.height) == pytest.approx(
        ((x0+x1)/2,(y0+y1)/2,x1-x0,y1-y0))
    assert bounds_of_polygons(filled_region_polygons(element)) == pytest.approx(expected)
    assert doc.canvas.mm_per_unit == .5
    assert (doc.canvas.origin_x,doc.canvas.origin_y)==(20,40)
    # The same world-space center must be used by consumer-local influence sampling.
    region = InfluenceArea('new-regression','ellipse', dict(x=(x0+x1)/2,y=(y0+y1)/2,
        length=8,width=8,angle=0,feather=0))
    assert region.weight(element)==1


def test_relative_path_not_falsely_recovered_as_absolute_rectangle(tmp_path):
    source=tmp_path/'relative.svg'
    source.write_text('<svg xmlns="http://www.w3.org/2000/svg"><path id="r" d="M12 34 h30 v10 h12 z"/></svg>')
    element=SVGNormalizer().normalize_file(str(source)).element('r')
    assert element.type=='path'
    assert (element.x,element.y,element.width,element.height)==(33,39,42,10)


def test_scope_keeps_outside_and_correct_hole_size_center_and_mm():
    doc=SVGNormalizer().normalize_file(str(FIXTURE))
    region=InfluenceArea('new','ellipse',dict(x=43,y=95,length=8,width=8,angle=0,feather=0))
    effect=SizeModifier('new-size','new-field',FieldMapping(.75,.75),influence_areas=(region,))
    output=SharedFieldEngine(FieldRegistry([ConstantField('new-field',.5)]),[effect]).apply(doc.elements)
    assert (output[0].x,output[0].y,output[0].width,output[0].height)==(43,95,18,18)
    assert output[1]==doc.elements[1]
    doc.modifiers=[effect.to_dict()];doc.fields=[ConstantField('new-field',.5).to_dict()]
    converted=ManufacturingGeometryAdapter().adapt_document(doc)
    assert converted.report.skipped_count==0
    hole=next(p for p in converted.geometry.polygons if p.source_element_id=='hole')
    assert hole.bounds==pytest.approx((17,43,26,52))
    assert len(hole.holes)==1


@pytest.mark.parametrize('local_scope', [False, True])
def test_new_sample_http_import_evaluate_manufacture_and_stl_readback(tmp_path, local_scope):
    with TestClient(create_app()) as client:
        uploaded=client.post('/api/v1/assets',content=FIXTURE.read_bytes(),headers={
            'Content-Type':'image/svg+xml','X-Filename':'new-hv-regression.svg'})
        assert uploaded.status_code==200,uploaded.text
        imported=client.post('/api/v1/import',json={'asset_id':uploaded.json()['asset_id']})
        assert imported.status_code==200,imported.text
        dto=imported.json()
        hole=next(e for e in dto['document']['elements'] if e['id']=='hole')
        assert (hole['x'],hole['y'],hole['width'],hole['height'])==(43,95,24,24)
        if local_scope:
            region=InfluenceArea('new','ellipse',dict(x=43,y=95,length=8,width=8,angle=0,feather=0))
            dto['document']['fields']=[ConstantField('new-field',.5).to_dict()]
            dto['document']['modifiers']=[SizeModifier('new-size','new-field',FieldMapping(.75,.75),
                influence_areas=(region,)).to_dict()]
        body={'schema_version':'1.0','document_id':dto['document_id'],
            'document':dto,'document_revision':dto['document_revision'],'height_mm':2}
        evaluated=client.post('/api/v1/evaluate',json=body)
        assert evaluated.status_code==200,evaluated.text
        evaluated_hole=next(e for e in evaluated.json()['geometry'] if e['id']=='hole')
        size=9 if local_scope else 12
        assert (evaluated_hole['x'],evaluated_hole['y'],evaluated_hole['width'],evaluated_hole['height'])==(21.5,47.5,size,size)
        result=client.post('/api/v1/manufacturing/build',json=body)
        assert result.status_code==200,result.text
        download=client.get('/api/v1/manufacturing/'+result.json()['manufacturing_result_id']+'/model.stl')
        assert download.status_code==200,download.text
        file=tmp_path/'new-hv-regression.stl';file.write_bytes(download.content)
    mesh=STLExporter.reload_as_mesh_result(file)
    report=MeshValidator().validate(mesh)
    assert report.is_valid and report.is_watertight and report.component_count==2
    assert report.degenerate_face_count==0 and mesh.mesh.volume>0 and mesh.mesh.is_winding_consistent
    expected_bounds=[[17,27.5,0],[45.5,52,2]] if local_scope else [[15.5,27.5,0],[45.5,53.5,2]]
    np.testing.assert_allclose(mesh.mesh.bounds, expected_bounds,atol=1e-6)
    # Outer square 24² minus inner square 12²; L shape 16*8+10*6.
    assert mesh.mesh.volume==pytest.approx((432*(.75**2 if local_scope else 1)+188)*.25*2)
    assert mesh.mesh.euler_number==2  # one holed solid and one simply connected solid


def test_saved_legacy_project_not_recalculated_or_migrated(tmp_path):
    doc=SVGNormalizer().normalize_file(str(FIXTURE))
    old=doc.to_dict()
    # Deliberately retain historical incorrect anchor/size, not a new import.
    old['elements'][0].update(x=60,y=70,width=60,height=70,base_x=60,base_y=70,base_width=60,base_height=70)
    legacy=PatternDocument.from_dict(deepcopy(old))
    before=deepcopy(legacy.to_dict())
    target=tmp_path/'existing.pattern.json'
    save_pattern_document(legacy,str(target))
    assert load_pattern_document(str(target)).to_dict()==before
    # Explicit foundation metadata in an existing application SVG also wins
    # over new-import bounds; do not silently reinterpret that saved project.
    exported=tmp_path/'existing.svg'
    pattern_document_to_svg(legacy,str(exported))
    restored=SVGNormalizer().normalize_file(str(exported))
    for key in ('x','y','width','height','rotation','base_x','base_y','base_width','base_height','path_data','source_transform'):
        assert getattr(restored.element('hole'),key)==getattr(legacy.element('hole'),key)
    assert legacy.to_dict()==before
