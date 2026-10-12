"""P3 configuration uses existing fields, maps and geometry without new algorithms."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import json
import sys
import math
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ppg.foundation import PatternDocument, Reference
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.evaluation import evaluate_pattern_document, parametric_model_from_document
from xiaomang_pattern_lab.shared_fields import CheckerField, SpiralField, FieldContext, FieldMapping

def fixture(id):
    return PatternDocumentDTO.from_dict(json.loads((ROOT/'tests/fixtures/pattern_presets'/f'{id}.pattern.json').read_text(encoding='utf8')))

def test_checker_two_consumers_alternating_neighbours_double_cells_diagonal_and_neutral_xy():
    doc = fixture('digital-weave').to_document(); before = deepcopy(doc.to_dict())
    source = parametric_model_from_document(doc).generate()
    for size, angle in ((5.2, 0), (10.4, 0), (5.2, 45)):
        doc.fields[0]['parameters'].update(cell_width=size,cell_height=size,angle=angle)
        field = CheckerField('probe', **doc.fields[0]['parameters']); ctx = FieldContext.from_elements(source)
        values = [field.evaluate(e,ctx) for e in source]; final = evaluate_pattern_document(doc)
        assert set(values)=={0,1} and len(final)==100 and all(e.type=='rect' for e in final)
        if size==5.2 and angle==0:
            assert all(values[i]!=values[i+1] for i in range(100) if i%10!=9)
            assert all(values[i]!=values[i+10] for i in range(90))
        if size==10.4: assert values[0]==values[1] and values[1]!=values[2]
        for s,f,v in zip(source,final,values):
            assert (s.x,s.y)==(f.x,f.y)
            assert f.width==pytest.approx(3.8*(.86+.20*v))
            assert f.height==pytest.approx(1.5*(.86+.20*v))
            assert f.rotation==pytest.approx(90*v)
        assert [asdict(e) for e in final]==[asdict(e) for e in evaluate_pattern_document(doc)]
    doc.fields[0]['parameters'].update(cell_width=5.2,cell_height=5.2,angle=0)
    assert doc.to_dict()==before

def generate(source_dir):
    from ppg.foundation.svg_exporter import pattern_document_to_svg
    for id in ('digital-weave','vortex-scales'):
        source = Path(source_dir)/f'{id}.json'
        if not source.exists(): continue
        data=json.loads(source.read_text(encoding='utf8')); dto=PatternDocumentDTO.from_dict(data)
        doc=dto.to_document(); final=evaluate_pattern_document(doc)
        (ROOT/'tests/fixtures/pattern_presets'/f'{id}.pattern.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        target=ROOT/'web/src/document/patternPresetThumbnails'/f'{id}.svg'
        pattern_document_to_svg(PatternDocument(doc.canvas,Reference(''),final),target)
        print(id, len(final), target)

@pytest.mark.parametrize('turns,phase,direction', [(3,.15,1),(1.6,.45,1),(5,.15,-1)])
def test_vortex_real_ellipses_dual_mapping_positions_and_deterministic_variants(turns,phase,direction):
    doc = fixture('vortex-scales').to_document()
    original = deepcopy(doc.to_dict())
    doc.fields[0]['parameters'].update(turns=turns,phase=phase,direction=direction)
    source = parametric_model_from_document(doc).generate()
    field = SpiralField('probe', **doc.fields[0]['parameters'])
    ctx = FieldContext.from_elements(source)
    values = [field.evaluate(e,ctx) for e in source]
    final = evaluate_pattern_document(doc)
    assert len(final)==144 and all(e.type=='ellipse' for e in final)
    assert max(values)-min(values) > .9
    size = FieldMapping(.74,1.04,remap_curve='bell')
    rotation = FieldMapping(0,180,remap_curve='linear')
    for s,e,v in zip(source,final,values):
        assert (s.x,s.y)==(e.x,e.y)
        assert e.width == pytest.approx(3.4*size.evaluate(v,neutral=1))
        assert e.height == pytest.approx(1.6*size.evaluate(v,neutral=1))
        assert e.rotation == pytest.approx(rotation.evaluate(v,neutral=0))
        assert .74 <= e.width/3.4 <= 1.04
    assert [asdict(e) for e in final] == [asdict(e) for e in evaluate_pattern_document(doc)]
    # Even Grid deliberately samples around the polar centre, not at its singular point.
    assert min(math.hypot(e.x-30,e.y-30) for e in source) == pytest.approx(math.sqrt(2)*2.3)
    doc.fields[0]['parameters'].update(turns=3,phase=.15,direction=1)
    assert doc.to_dict()==original

def test_vortex_wrap_continuity_is_shape_specific_and_existing_bell_rotation_handles_asymmetry():
    from ppg.foundation import RectElement
    field = SpiralField('spiral',center_x=30,center_y=30,turns=3,phase=.15)
    ctx = FieldContext((3,3,57,57))
    diagonal=math.hypot(54,54)
    radius=12
    theta=2*math.pi*(-.15-3*radius/diagonal)
    while theta < -math.pi: theta+=2*math.pi
    while theta > math.pi: theta-=2*math.pi
    probes=[RectElement(str(i),30+radius*math.cos(theta+d),30+radius*math.sin(theta+d),3.4,1.6)
            for i,d in enumerate((-1e-7,1e-7))]
    values=[field.evaluate(e,ctx) for e in probes]
    assert min(values)<1e-6 and max(values)>1-1e-6
    mapping=FieldMapping(.74,1.04,remap_curve='bell')
    assert abs(mapping.evaluate(values[0],neutral=1)-mapping.evaluate(values[1],neutral=1))<1e-6
    angles=[FieldMapping(0,180).evaluate(v,neutral=0) for v in values]
    assert abs((angles[0]-angles[1]+90)%180-90)<1e-4  # Ellipse / rectangle only, modulo 180.
    # An asymmetric L has no 180-degree equivalence: default linear mapping cannot claim continuity.
    l_shape=[(0,0),(3,0),(3,1),(1,1),(1,2),(0,2)]
    def rotated(angle):
        r=math.radians(angle)
        return [(x*math.cos(r)-y*math.sin(r),x*math.sin(r)+y*math.cos(r)) for x,y in l_shape]
    assert max(math.hypot(x-a,y-b) for (x,y),(a,b) in zip(rotated(angles[0]),rotated(angles[1])))>5
    bell_angles=[FieldMapping(0,180,remap_curve='bell').evaluate(v,neutral=0) for v in values]
    assert max(math.hypot(x-a,y-b) for (x,y),(a,b) in zip(rotated(bell_angles[0]),rotated(bell_angles[1])))<1e-5

def test_vortex_nonzero_origin_non_square_half_mm_world_sampling_and_output_positions():
    from xiaomang_pattern_lab.manufacturing_geometry import ManufacturingGeometryAdapter
    doc=fixture('vortex-scales').to_document()
    doc.canvas=type(doc.canvas)(120,80,'svg',.5,20,40)
    grid=doc.metadata['xiaomang_pattern_lab.parametric']['grid']
    grid.update(offset_x=70,offset_y=100,spacing_x=9.2,spacing_y=9.2,element_width=6.8,element_height=3.2)
    doc.fields[0]['parameters'].update(center_x=70,center_y=100)
    source=parametric_model_from_document(doc).generate(); final=evaluate_pattern_document(doc)
    conversion=ManufacturingGeometryAdapter().adapt_evaluated_document(doc,final)
    assert conversion.report.skipped_count==0 and conversion.geometry.polygon_count==144
    assert all((s.x,s.y)==(e.x,e.y) for s,e in zip(source,final))
    for e,p in zip(final,conversion.geometry.polygons):
        assert (p.bounds[0]+p.bounds[2])/2 == pytest.approx(e.x*.5)
        assert (p.bounds[1]+p.bounds[3])/2 == pytest.approx(e.y*.5)
    # Whole source extent uses the same normalisation under an explicit scale conversion.
    normal=fixture('vortex-scales').to_document(); normal_final=evaluate_pattern_document(normal)
    assert [e.width*.5 for e in final]==pytest.approx([e.width for e in normal_final])
    assert [e.rotation for e in final]==pytest.approx([e.rotation for e in normal_final])
if __name__=='__main__': generate(sys.argv[1])
