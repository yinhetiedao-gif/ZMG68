"""Supplemental NEW samples/oracles, not the missing original user file."""
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import pytest

from ppg.foundation import SVGNormalizer, pattern_document_to_svg
from ppg.foundation.region_geometry import filled_region_polygons, bounds_of_polygons
from xiaomang_pattern_lab.manufacturing_geometry import ManufacturingGeometryAdapter
from xiaomang_pattern_lab.influence_areas import InfluenceArea
from xiaomang_pattern_lab.shared_fields import ConstantField, SizeModifier, FieldMapping, SharedFieldEngine, FieldRegistry

FIXTURE=Path(__file__).parent/'fixtures'/'svg_hv_bounds_regression.svg'


@pytest.mark.parametrize('mode',['semantic','faithful'])
@pytest.mark.parametrize('text,matrix',[
    ('rotate(90)', [[0,-1,0],[1,0,0],[0,0,1]]),
    ('rotate(90 43 95)', [[0,-1,138],[1,0,52],[0,0,1]]),
    ('rotate(45 43 95)', [[2**-.5,-2**-.5,43+52*2**-.5],[2**-.5,2**-.5,95-138*2**-.5],[0,0,1]]),
    ('translate(7 -11) scale(2 3)', [[2,0,7],[0,3,-11],[0,0,1]]),
    ('scale(2 3) translate(7 -11)', [[2,0,14],[0,3,-33],[0,0,1]]),
    ('matrix(1 .2 .3 1 5 -8)', [[1,.3,5],[.2,1,-8],[0,0,1]]),
])
def test_actual_transformed_outline_bounds_center_scope_once(tmp_path,mode,text,matrix):
    source=tmp_path/'transform.svg'
    source.write_text(FIXTURE.read_text(encoding='utf-8').replace('id="hole"',f'id="hole" transform="{text}"'),encoding='utf-8')
    doc=SVGNormalizer().normalize_file(str(source),normalization_mode=mode)
    element=doc.element('hole')
    raw=np.array([[31,83,1],[55,83,1],[55,107,1],[31,107,1],[31,83,1]])
    expected=(raw@np.array(matrix).T)[:,:2]
    bounds=(*expected.min(axis=0),*expected.max(axis=0))
    np.testing.assert_allclose(filled_region_polygons(element)[0],expected,atol=1e-6,rtol=0)
    assert bounds_of_polygons(filled_region_polygons(element))==pytest.approx(bounds,abs=1e-6)
    center=(np.array([43,95,1])@np.array(matrix).T)[:2]
    assert (element.x,element.y)==pytest.approx(center,abs=1e-6)
    area=InfluenceArea('scope','ellipse',dict(x=float(center[0]),y=float(center[1]),length=4,width=4,angle=0,feather=0))
    assert area.weight(element)==1
    changed=SharedFieldEngine(FieldRegistry([ConstantField('f',.5)]),[
        SizeModifier('s','f',FieldMapping(.75,.75),influence_areas=(area,))]).apply([element])[0]
    np.testing.assert_allclose(filled_region_polygons(changed)[0],(expected-center)*.75+center,atol=1e-6,rtol=0)


def test_nested_group_composition_and_export_reimport_once(tmp_path):
    # Parent first in the SVG CTM: T(7,-11) @ S(2,3), not reverse.
    svg=FIXTURE.read_text(encoding='utf-8').replace('<path id="hole"','<g transform="translate(7 -11)"><g transform="scale(2 3)"><path id="hole"').replace('V89 Z"/>','V89 Z"/></g></g>')
    source=tmp_path/'nested.svg';source.write_text(svg,encoding='utf-8')
    doc=SVGNormalizer().normalize_file(str(source))
    item=doc.element('hole')
    assert (item.x,item.y,item.width,item.height)==pytest.approx((93,274,48,72))
    assert bounds_of_polygons(filled_region_polygons(item))==pytest.approx((69,238,117,310))
    exported=tmp_path/'nested-export.svg';pattern_document_to_svg(doc,str(exported))
    reopened=SVGNormalizer().normalize_file(str(exported))
    np.testing.assert_allclose(filled_region_polygons(reopened.element('hole')),filled_region_polygons(item),atol=1e-6)


@pytest.mark.parametrize('mode',['semantic','faithful'])
@pytest.mark.parametrize('same_winding',[False,True])
def test_evenodd_and_holes_survive_foundation_svg_export_import(tmp_path,mode,same_winding):
    source=tmp_path/'hole.svg'
    svg=FIXTURE.read_text(encoding='utf-8')
    if same_winding:
        svg=svg.replace('M37 89 V101 H49 V89 Z','M37 89 H49 V101 H37 Z')
    source.write_text(svg,encoding='utf-8')
    doc=SVGNormalizer().normalize_file(str(source),normalization_mode=mode)
    before=ManufacturingGeometryAdapter().adapt_document(doc)
    exported=tmp_path/'filled-export.svg';pattern_document_to_svg(doc,str(exported))
    path=ET.parse(exported).getroot().find('.//{http://www.w3.org/2000/svg}path[@id="hole"]')
    assert path.attrib.get('fill-rule')=='evenodd'
    reopened=SVGNormalizer().normalize_file(str(exported))
    # Foundation editable SVG historically has unitless dimensions. Here the
    # caller explicitly retains its known .5 calibration; the Web export's mm
    # round-trip is separately exercised in the real browser, not assumed.
    after=ManufacturingGeometryAdapter().adapt_elements(reopened.elements,mm_per_world_unit=doc.canvas.mm_per_unit)
    assert before.report.skipped_count==after.report.skipped_count==0
    assert len(before.geometry.polygons[0].holes)==len(after.geometry.polygons[0].holes)==1
    np.testing.assert_allclose(after.geometry.polygons[0].outer,before.geometry.polygons[0].outer,atol=1e-6)
    np.testing.assert_allclose(after.geometry.polygons[0].holes,before.geometry.polygons[0].holes,atol=1e-6)
