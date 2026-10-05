"""Original failed mask is retained verbatim; thresholds are axial, not arrows."""
from pathlib import Path
from copy import deepcopy
from dataclasses import replace
from tempfile import TemporaryDirectory
import math
import unittest
import numpy as np
from PIL import Image,ImageDraw
from ppg.foundation import Canvas,RectElement
from xiaomang_pattern_lab.shared_fields import DistanceField,FieldContext,FieldRegistry
from xiaomang_pattern_lab.field_gradient import gradient_angles
from xiaomang_pattern_lab.orientation_raster import axial_mean,prepare_orientation,_CACHE
from test_image_fabric_f4a import image_document,run_preview

FIXTURE=Path(__file__).parent/'fixtures/f4c-spine-401.png'


def document(path):
    doc=image_document(path);doc.canvas=Canvas(60,60,'mm',1)
    doc.elements=[RectElement('bound',30,30,40,40)]
    doc.fields=[DistanceField('distance',str(path),sample_bounds=(0,0,60,60),threshold=.75).to_dict()]
    config=doc.metadata['fabric_config'];config['placement'].update(spacing_x_mm=1,spacing_y_mm=1)
    config['field_modifiers']={
        'height':{'enabled':True,'field_id':'distance','min_height_mm':.5,'max_height_mm':8},
        'scale':{'enabled':True,'field_id':'distance','min_scale':.6,'max_scale':1.3},
        'density':{'enabled':True,'field_id':'distance','threshold':.03},
        'orientation':{'enabled':True,'field_id':'distance','direction_mode':'gradient','alignment':'tangent',
            'min_angle_deg':-45,'max_angle_deg':45,'angle_offset_deg':0}}
    return doc


def adjacent(instances):
    by={(i['x_mm'],i['y_mm']):i for i in instances if i['enabled']};result=[]
    for (x,y),i in by.items():
        for xy in ((x+1,y),(x,y+1)):
            j=by.get(xy)
            if j and min(i['height_mm'],j['height_mm'])>3:
                result.append(abs((i['rotation_deg']-j['rotation_deg']+90)%180-90))
    return sum(v>45 for v in result),max(result,default=0)


class OrientationStabilityTests(unittest.TestCase):
    def test_original_failed_spine_before_after_and_height_unchanged(self):
        doc=document(FIXTURE);before=deepcopy(doc.to_dict());result=run_preview(doc)
        print('F4C original spine after',adjacent(result['instances']))
        count,maximum=adjacent(result['instances']);self.assertLessEqual(count,5);self.assertLessEqual(maximum,75)
        field=DistanceField('d',str(FIXTURE),sample_bounds=(0,0,60,60),threshold=.75)
        ctx=FieldContext((0,0,60,60));raw=[]
        for item in result['instances']:
            point=RectElement('p',item['x_mm'],item['y_mm'],1,1);delta=.15
            gx=(field.evaluate(replace(point,x=point.x+delta),ctx)-field.evaluate(replace(point,x=point.x-delta),ctx))/(2*delta)
            gy=(field.evaluate(replace(point,y=point.y+delta),ctx)-field.evaluate(replace(point,y=point.y-delta),ctx))/(2*delta)
            raw.append(item|{'rotation_deg':math.degrees(math.atan2(gy,gx))+90})
            value=field.evaluate(point,ctx)
            self.assertEqual(item['height_mm'],.5+7.5*value)
            self.assertEqual(item['scale'],.6+(1.3-.6)*value)
            self.assertEqual(item['enabled'],value>=.03)
        count,maximum=adjacent(raw);self.assertEqual(count,35);self.assertAlmostEqual(maximum,88.76768290481604)
        normal=deepcopy(doc);normal.metadata['fabric_config']['field_modifiers']['orientation']['alignment']='normal'
        normals=run_preview(normal)['instances']
        count, maximum = adjacent(normals)
        self.assertLessEqual(count,5);self.assertLessEqual(maximum,75)
        for a,b in zip(result['instances'],normals):
            # Unreliable samples retain the inherited rotation in both modes;
            # only a reliable common normal receives the tangent's 90 degrees.
            if a['rotation_deg'] == b['rotation_deg'] == 0:
                continue
            self.assertAlmostEqual(a['rotation_deg']-b['rotation_deg'],90)
        self.assertEqual(result['instances'],run_preview(doc)['instances']);self.assertEqual(doc.to_dict(),before)

    def test_axial_average_wrap_and_flat_fallback(self):
        angles=np.radians([5,175]);self.assertAlmostEqual(axial_mean(np.cos(2*angles).mean(),np.sin(2*angles).mean()),0)
        with TemporaryDirectory() as temp:
            path=Path(temp)/'flat.png';Image.new('L',(41,41),255).save(path)
            field=DistanceField('d',str(path),sample_bounds=(0,0,60,60));registry=FieldRegistry([field])
            points=[RectElement('a',30,30,1,1),RectElement('b',20,20,1,1)]
            self.assertEqual(gradient_angles(registry,'d',points,FieldContext((0,0,60,60))),(None,None))

    def test_solid_s_control_and_zero_gradient_neighbor_recovery(self):
        # A separate solid disk-swept curve avoids the white fissures in the
        # original failed line-raster fixture. Never rewrite that original.
        with TemporaryDirectory() as temp:
            path=Path(temp)/'solid-s.png';image=Image.new('L',(401,401),255)
            draw=ImageDraw.Draw(image)
            for t in np.linspace(0,1,1201):
                x=200+100*math.sin(2*math.pi*t);y=45+310*t
                draw.ellipse((x-32,y-32,x+32,y+32),fill=0)
            image.save(path)
            instances=run_preview(document(path))['instances']
            count,maximum=adjacent(instances)
            print('F4C solid S control',count,maximum)
            self.assertLessEqual(count,5);self.assertLessEqual(maximum,75)
            # A straight ribbon's exact medial ridge has zero scalar gradient,
            # but the two sides agree axially and provide a reliable normal.
            ribbon=Image.new('L',(101,101),255)
            ImageDraw.Draw(ribbon).rectangle((30,0,70,100),fill=0);ribbon.save(path)
            field=DistanceField('d',str(path),sample_bounds=(0,0,60,60))
            angle=gradient_angles(FieldRegistry([field]),'d',
                [RectElement('ridge',30,30,1,1)],FieldContext((0,0,60,60)))[0]
            self.assertIsNotNone(angle);self.assertAlmostEqual(angle,0)

    def test_ring_axes_and_sharp_corner_are_not_flattened(self):
        with TemporaryDirectory() as temp:
            path=Path(temp)/'shape.png';image=Image.new('L',(401,401),255);draw=ImageDraw.Draw(image)
            draw.ellipse((40,40,360,360),fill=0);draw.ellipse((120,120,280,280),fill=255);image.save(path)
            field=DistanceField('d',str(path),sample_bounds=(0,0,60,60));registry=FieldRegistry([field]);ctx=FieldContext((0,0,60,60))
            points=[RectElement(str(i),x,y,1,1) for i,(x,y) in enumerate(((49.5,30),(30,49.5),(10.5,30),(30,10.5)))]
            for angle,expected in zip(gradient_angles(registry,'d',points,ctx),(0,90,0,90)):
                self.assertAlmostEqual(abs((angle-expected+90)%180-90),0,places=5)
            # Ring medial-ridge residuals are small, but not exactly zero.
            # They must not outrank a coherent neighborhood normal.
            ridge=[RectElement('ridge',34.5,12.5,1,1),RectElement('ridge2',12.5,34.5,1,1),
                   RectElement('attenuated',22.5,13.5,1,1)]
            for point,angle in zip(ridge,gradient_angles(registry,'d',ridge,ctx)):
                expected=math.degrees(math.atan2(point.y-30,point.x-30))
                self.assertLess(abs((angle-expected+90)%180-90),2)
            image=Image.new('L',(401,401),255);draw=ImageDraw.Draw(image)
            draw.rectangle((40,40,90,350),fill=0);draw.rectangle((40,300,350,350),fill=0);image.save(path)
            field=DistanceField('d',str(path),sample_bounds=(0,0,60,60));registry=FieldRegistry([field])
            a,b=gradient_angles(registry,'d',[RectElement('v',9,20,1,1),RectElement('h',35,49,1,1)],ctx)
            self.assertGreater(abs((a-b+90)%180-90),75)  # real right-angle branch survives

    def test_cache_dependencies_and_order_independence(self):
        ctx=FieldContext((0,0,60,60));field=DistanceField('d',str(FIXTURE),sample_bounds=ctx.bounds)
        a=prepare_orientation(field,ctx.bounds);self.assertIs(a,prepare_orientation(field,ctx.bounds))
        for change in ({'threshold':.9},{'invert':True},{'auto_normalize':False,'max_distance_mm':2}):
            other=DistanceField('d',str(FIXTURE),sample_bounds=ctx.bounds,**change)
            self.assertIsNot(a,prepare_orientation(other,ctx.bounds))
        self.assertIsNot(a,prepare_orientation(field,(0,0,120,60)))
        registry=FieldRegistry([field]);points=[RectElement(str(i),x,y,1,1) for i,(x,y) in enumerate(((27.5,31.5),(28.5,31.5),(15.5,17.5)))]
        expected=gradient_angles(registry,'d',points,ctx)
        self.assertEqual(expected,tuple(reversed(gradient_angles(registry,'d',list(reversed(points)),ctx))))
