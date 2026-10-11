"""Existing scalar fields → the same Size consumer/range and manufacturing.
No new field math or validator exceptions are introduced by the Web shortcut.
"""
from copy import deepcopy
import pytest
from ppg.foundation import CircleElement, EllipseElement, RectElement
from xiaomang_pattern_lab.shared_fields import (FieldContext, FieldRegistry, SharedFieldEngine,
    SizeModifier, FieldMapping, LinearSizeRegion, ConstantField, LinearField, WaveField,
    StripeField, CheckerField, NoiseField)
from tests.test_fabric_cells_only_1a import fixture, build

FIELDS = [LinearField('effect', 30, 10, 80), WaveField('effect', angle=25, wavelength=34, phase=.3),
    StripeField('effect', angle=15, period=26, duty_cycle=.45),
    CheckerField('effect', cell_width=13, cell_height=11),
    NoiseField('effect', scale=23, seed=19, octaves=3)]

@pytest.mark.parametrize('field', FIELDS, ids=['linear','wave','stripe','checker','noise'])
@pytest.mark.parametrize('shape', [CircleElement, EllipseElement, RectElement])
def test_varied_samples_size_parity_centers_rotation_and_determinism(field, shape):
    source = [shape(str(i), 14+i%5*12, 24+i//5*8, 2, 3, rotation=17) for i in range(20)]
    original = deepcopy(source)
    context = FieldContext((10,20,70,60))
    samples = [field.evaluate(e, context) for e in source]
    assert max(samples)-min(samples) > .1  # Verify input sampling, not just labels.
    engine = SharedFieldEngine(FieldRegistry([field]), [SizeModifier('size','effect',FieldMapping(.6,1.2))])
    final = engine.apply(source)
    assert [e.width for e in final] == pytest.approx([e.width*(.6+.6*v) for e,v in zip(source,samples)])
    assert [(e.x,e.y,e.rotation) for e in final] == [(e.x,e.y,e.rotation) for e in source]
    assert [e.width for e in engine.apply(source)] == [e.width for e in final]
    assert [e.width for e in source] == [e.width for e in original]

@pytest.mark.parametrize('field', FIELDS, ids=['linear','wave','stripe','checker','noise'])
def test_local_range_blends_this_layer_only_and_preserves_prior_size_outside(field):
    source = [RectElement(str(i),x,24,2,3,rotation=13) for i,x in enumerate([0,14,26,38,50,70])]
    fields = FieldRegistry([ConstantField('prior', .5), field])
    region = LinearSizeRegion(32,24,38,12,0,2)
    prior = SizeModifier('prior-size','prior',FieldMapping(.8,.8))
    local = SizeModifier('managed-size','effect',FieldMapping(.6,1.2),region=region)
    result = SharedFieldEngine(fields,[prior,local]).apply(source)
    context = FieldContext((0,24,70,24))
    expected = [e.width*.8*(1+region.weight(e)*(.6+.6*field.evaluate(e,context)-1)) for e in source]
    assert [e.width for e in result] == pytest.approx(expected)
    assert result[0].width == result[-1].width == 1.6  # min_output is not neutral!
    assert [(e.x,e.y,e.rotation) for e in result] == [(e.x,e.y,e.rotation) for e in source]
    reopened = SharedFieldEngine.from_dict(SharedFieldEngine(fields,[prior,local]).to_dict())
    assert [e.width for e in reopened.apply(source)] == [e.width for e in result]

def test_pattern_points_inherits_2d_size_once_without_changing_fabric_height():
    doc = fixture(factor=.5, unit='svg')
    field = WaveField('size-wave', angle=15, wavelength=34, phase=.3)
    doc.fields = [field.to_dict(), ConstantField('height-user', .5).to_dict()]
    doc.modifiers = [SizeModifier('size','size-wave',FieldMapping(.6,1.2)).to_dict()]
    cfg = doc.metadata['fabric_config']
    cfg['unit_cell'].update(width_mm=2,depth_mm=2)
    cfg['field_modifiers'] = {'height': {'enabled':True,'field_id':'height-user','min_height_mm':2,'max_height_mm':4}}
    before = deepcopy(doc.to_dict()); design,candidate = build(doc)
    for element,instance in zip(doc.elements,design.plan.instances):
        value = field.evaluate(element,FieldContext((0,0,0,0)))
        assert instance.x_mm == element.x*.5 and instance.y_mm == element.y*.5
        assert instance.cell_width_mm == pytest.approx(2*(.6+.6*value))
        assert instance.height_mm == 3 and instance.z_mm == 0
    assert doc.to_dict() == before
    assert len(candidate.cell_meshes) == 9
