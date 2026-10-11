from copy import deepcopy
from dataclasses import asdict
import math
import pytest
import numpy as np
from ppg.foundation import PatternDocument, Canvas, Reference, RectElement, CircleElement
from xiaomang_pattern_lab.design_controls import DEFAULTS, KEY
from xiaomang_pattern_lab.evaluation import evaluate_pattern_document
from xiaomang_pattern_lab.parametric import GridParametricModel
from xiaomang_pattern_lab.shared_fields import ConstantField, SizeModifier, FieldMapping, SharedFieldEngine, FieldRegistry
from xiaomang_pattern_lab.influence_areas import InfluenceArea
from tests.test_fabric_cells_only_1a import fixture, build
from xiaomang_pattern_lab.fabric_fusion import FabricFusionService
from xiaomang_pattern_lab.fabric_stl import export_validated_fabric_stl
from xiaomang_pattern_lab.stl_export import STLExporter
from xiaomang_pattern_lab.mesh_validation import MeshValidator


def area(type='line', id='a'):
    p = dict(x=36,y=30,length=24,width=12,angle=0,feather=2)
    if type=='curve': p=dict(x0=24,y0=30,x1=36,y1=20,x2=48,y2=30,width=12,feather=2)
    return InfluenceArea(id,type,p)


@pytest.mark.parametrize('type',['line','ellipse','curve'])
def test_true_range_preserves_previous_layer_outside_and_overlap_order(type):
    source=[RectElement(str(i),x,30,2,3,rotation=17) for i,x in enumerate([0,25,36,47,80])]
    fields=FieldRegistry([ConstantField('prior',.5),ConstantField('driver',.5)])
    prior=SizeModifier('prior','prior',FieldMapping(.8,.8))
    local=SizeModifier('local','driver',FieldMapping(.5,.5),influence_areas=(area(type),area('ellipse','b')))
    engine=SharedFieldEngine(fields,[prior,local]); result=engine.apply(source)
    assert result[0].width==result[-1].width==1.6
    assert [(e.x,e.y,e.rotation) for e in result]==[(e.x,e.y,e.rotation) for e in source]
    assert [e.width for e in SharedFieldEngine.from_dict(engine.to_dict()).apply(source)]==[e.width for e in result]
    reverse=SizeModifier('local','driver',FieldMapping(.5,.5),influence_areas=tuple(reversed(local.influence_areas)))
    assert [e.width for e in SharedFieldEngine(fields,[prior,reverse]).apply(source)]==[e.width for e in result]
    assert min(e.width for e in result)<1.6


def test_disabled_empty_limit_invalid_curve_and_parameters():
    source=[RectElement('e',36,30,2,2)]
    for areas in [(),(InfluenceArea('a','line',area().parameters,False),)]:
        assert SharedFieldEngine(FieldRegistry([ConstantField('f',.5)]),[SizeModifier('s','f',FieldMapping(.5,.5),influence_areas=areas)]).apply(source)[0].width==2
    with pytest.raises(ValueError): SizeModifier('s','f',FieldMapping(),influence_areas=tuple(area(id=str(i)) for i in range(4)))
    with pytest.raises(ValueError): InfluenceArea('a','line',{**area().parameters,'width':0})
    with pytest.raises(ValueError): InfluenceArea('a','line',{**area().parameters,'x':float('nan')})
    with pytest.raises(ValueError): InfluenceArea('a','curve',{**area('curve').parameters,'x2':24})


def test_line_perpendicular_width_and_rotated_ellipse_not_ring():
    assert area().weight(RectElement('on',36,30,2,2))==1
    assert area().weight(RectElement('outside',36,37,2,2))==0
    ellipse=area('ellipse'); assert ellipse.weight(RectElement('center',36,30,2,2))==1
    rotated=InfluenceArea('a','ellipse',{**ellipse.parameters,'angle':90})
    assert rotated.weight(RectElement('x',44,30,2,2))==0
    assert rotated.weight(RectElement('y',36,38,2,2))>0


def test_strength_zero_is_neutral_and_invert_only_affects_this_consumer():
    from xiaomang_pattern_lab.shared_fields import LinearField
    source=[RectElement(str(i),x,30,2,3,rotation=12) for i,x in enumerate([25,36,47])]
    field=LinearField('shared',0,20,50)
    neutral=SizeModifier('s','shared',FieldMapping(.5,1.5,strength=0),influence_areas=(area(),))
    assert [asdict(e) for e in SharedFieldEngine(FieldRegistry([field]),[neutral]).apply(source)]==[asdict(e) for e in source]
    direct=SizeModifier('s','shared',FieldMapping(.5,1.5),influence_areas=(area(),))
    inverted=SizeModifier('s','shared',FieldMapping(.5,1.5,invert=True),influence_areas=(area(),))
    a=SharedFieldEngine(FieldRegistry([field]),[direct]).apply(source)
    b=SharedFieldEngine(FieldRegistry([field]),[inverted]).apply(source)
    assert a[0].width<b[0].width and a[-1].width>b[-1].width
    assert field.to_dict()['parameters']['angle']==0


def test_public_shape_seed_noncumulative_and_world_coordinates():
    doc=PatternDocument(Canvas(120,80,'px',.5,20,40),Reference(''),[CircleElement('a',30,50,4,4),RectElement('b',70,80,4,3)])
    before=deepcopy(doc.to_dict())
    doc.metadata[KEY]={'version':1,**DEFAULTS,'size_percent':120,'aspect':2,'rotation':23,'size_random':.2,'position_jitter':1,'seed':71}
    first=evaluate_pattern_document(doc); second=evaluate_pattern_document(doc)
    assert [asdict(e) for e in first]==[asdict(e) for e in second]
    assert first[0].type=='ellipse' and first[0].width/first[0].height==pytest.approx(2)
    assert all(e.rotation==23 for e in first)
    assert doc.elements[0].width==4 and before['elements']==doc.to_dict()['elements']
    doc.metadata[KEY]['seed']=72
    assert [asdict(e) for e in evaluate_pattern_document(doc)]!=[asdict(e) for e in first]
    doc.metadata[KEY]['position_jitter']=0; doc.metadata[KEY]['size_random']=0
    assert [(e.x,e.y) for e in evaluate_pattern_document(doc)]==[(e.x,e.y) for e in doc.elements]


def test_stagger_uses_grid_basis_only_no_free_import_rearrangement():
    doc=fixture(); model=GridParametricModel(rows=3,columns=3,spacing_x=12,spacing_y=10,rotation=30,offset_x=36,offset_y=30)
    doc.metadata['xiaomang_pattern_lab.parametric']={'mode':'grid','grid':model.to_dict()}
    before=evaluate_pattern_document(doc)
    doc.metadata[KEY]={'version':1,**DEFAULTS,'stagger':True}
    after=evaluate_pattern_document(doc)
    for a,b in zip(before,after):
        row=int(a.id.split(':')[1][1:]); shift=6 if row%2 else 0
        assert b.x==pytest.approx(a.x+shift*math.cos(math.pi/6))
        assert b.y==pytest.approx(a.y+shift*math.sin(math.pi/6))
    del doc.metadata['xiaomang_pattern_lab.parametric']
    assert [(e.x,e.y) for e in evaluate_pattern_document(doc)]==[(e.x,e.y) for e in doc.elements]


def test_new_public_geometry_and_scope_fabric_stl_strict_roundtrip():
    doc=fixture(factor=.5,unit='px')
    doc.metadata['fabric_config']['unit_cell'].update(width_mm=2.4,depth_mm=2.4)
    doc.metadata[KEY]={'version':1,**DEFAULTS,'size_percent':125,'size_random':.2,'position_jitter':.5,'seed':19,'aspect':1.4,'rotation':12}
    doc.fields=[ConstantField('driver',.5).to_dict(),ConstantField('height-user',.5).to_dict()]
    doc.metadata['fabric_config']['field_modifiers']={'height':{'enabled':True,'field_id':'height-user','min_height_mm':2,'max_height_mm':4}}
    doc.modifiers=[SizeModifier('managed','driver',FieldMapping(.6,1.1),influence_areas=(area('line'),)).to_dict()]
    design,candidate=build(doc)
    final=FabricFusionService().build(candidate)
    payload,report=export_validated_fabric_stl(final)
    mesh=STLExporter.reload_bytes_as_mesh_result(payload)
    validation=MeshValidator().validate(mesh)
    assert validation.is_valid and validation.is_watertight and validation.degenerate_face_count==0
    assert validation.component_count==9 and mesh.mesh.volume>0 and mesh.mesh.bounds[0,2]==0
    evaluated=evaluate_pattern_document(doc)
    for e,i in zip(evaluated,design.plan.instances):
        assert i.x_mm==pytest.approx(e.x*.5) and i.y_mm==pytest.approx(e.y*.5)
        # Source width 2: inherit the final 2D ratio once, not twice.
        assert i.cell_width_mm==pytest.approx(2.4*e.width/2)
        assert i.cell_depth_mm==pytest.approx(2.4*e.height/2)
        assert i.height_mm==3 and i.rotation_deg==e.rotation
