from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
import numpy as np
from fastapi.testclient import TestClient
from test_fabric_candidate_f5a import candidate,solid_100_fixture
from test_image_fabric_f4a import image_document,black_circle_bytes
from test_fabric_preview_f25 import document_with_points
from xiaomang_pattern_lab.fabric_plan import FabricPlanner,RegularPlacement
from xiaomang_pattern_lab.fabric_cells import UnitCellDefinition
from xiaomang_pattern_lab.fabric_preview import build_fabric_design
from xiaomang_pattern_lab.fabric_candidate import build_fabric_candidate
from xiaomang_pattern_lab.fabric_fusion import FabricFusionService,FabricFusionFailure
from xiaomang_pattern_lab.fabric_stl import export_validated_fabric_stl
from xiaomang_pattern_lab.stl_export import STLExporter
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.shared_fields import DistanceField,SizeModifier,RotationModifier,FieldMapping
from xiaomang_pattern_lab.shared_modifiers import SharedModifierStack,PositionModifier
from xiaomang_pattern_lab.web import create_app
from ppg.foundation import PatternDocument,Canvas,Reference,RectElement

class FabricStlTests(unittest.TestCase):
    def roundtrip(self,source):
        final=FabricFusionService().build(source)
        data,report=export_validated_fabric_stl(final)
        self.assertEqual(len(data),84+50*final.mesh_result.face_count)
        self.assertEqual(report['roundtrip_validation']['component_count'],1)
        self.assertTrue(report['roundtrip_validation']['is_watertight'])
        self.assertEqual(report['roundtrip_validation']['degenerate_face_count'],0)
        np.testing.assert_allclose(report['bounds_mm'],final.report['bounds_mm'],atol=report['bounds_tolerance_mm'],rtol=0)
        return data,report

    def test_basic_fin_and_1000_binary_roundtrip(self):
        self.roundtrip(candidate(solid_100_fixture()))
        plan=FabricPlanner().plan((0,0,60,60),.6,UnitCellDefinition('fin',2,1,3),RegularPlacement(6,6))
        plan=replace(plan,instances=tuple(replace(item,rotation_deg=(index%10)*9) for index,item in enumerate(plan.instances)))
        self.roundtrip(candidate(plan))
        plan=FabricPlanner().plan((0,0,60,60),.6,UnitCellDefinition('pyramid',.3,.3,3),RegularPlacement(3,1.2),preview_limit=False)
        self.assertEqual(len(plan.instances),1000)
        self.roundtrip(candidate(plan))

    def test_distance_and_pattern_points_roundtrip(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/'mask.png';path.write_bytes(black_circle_bytes())
            for mode in ('area_fill','pattern_points'):
                doc=image_document(path,mode,count=100)
                doc.fields=[DistanceField('distance',str(path),sample_bounds=(0,0,100,100)).to_dict()]
                if mode == 'pattern_points':
                    doc.fields.append({'id':'linear','type':'linear','parameters':{'angle':0,'start':0,'end':100}})
                    doc.modifiers=[SizeModifier('size','linear',FieldMapping(.8,1.5)).to_dict(),
                        RotationModifier('rotation','linear',FieldMapping(-30,30)).to_dict()]
                    stack=SharedModifierStack(source_elements=deepcopy(doc.elements))
                    stack.add_modifier('position',PositionModifier(mode='offset',offset_x=3,offset_y=-2).to_dict())
                    doc.metadata['xiaomang_pattern_lab.shared_modifiers']=stack.to_dict()
                doc.metadata['fabric_config']['field_modifiers']={
                    'height':{'enabled':True,'field_id':'distance','min_height_mm':1,'max_height_mm':8},
                    'orientation':{'enabled':True,'field_id':'distance','direction_mode':'gradient','alignment':'tangent',
                        'angle_offset_deg':12,'min_angle_deg':-45,'max_angle_deg':45}}
                dto=PatternDocumentDTO.from_document(doc,'f5c-image',1,asset_bindings={str(path):'mask'})
                before=deepcopy(dto.to_dict())
                design=build_fabric_design(doc,dto,preview_limit=False)
                source=build_fabric_candidate(design.plan,design.config.base,design.design_bounds_mm,
                    document_id=dto.document_id,document_revision=1)
                self.roundtrip(source)
                self.assertEqual(dto.to_dict(),before)

    def test_5000_remains_failed_before_export(self):
        plan=FabricPlanner().plan((0,0,60,60),.6,UnitCellDefinition('pyramid',.3,.3,3),RegularPlacement(1.2,.6),preview_limit=False)
        self.assertEqual(len(plan.instances),5000)
        with patch.object(STLExporter,'export_bytes',side_effect=AssertionError('no export')):
            with self.assertRaises(FabricFusionFailure) as caught:
                FabricFusionService().build(candidate(plan))
        self.assertEqual(caught.exception.report['stage'],'mesh_validation')
        self.assertEqual(caught.exception.report['validation_report']['degenerate_face_count'],38)

    def test_5000_api_cannot_offer_stl(self):
        doc=PatternDocument(Canvas(60,60,'mm',1),Reference('',False),[
            RectElement('lo',1,1,2,2),RectElement('hi',59,59,2,2)])
        doc.metadata['fabric_config']={'config_version':1,
            'base':{'type':'solid','thickness_mm':.6,'margin_mm':0},
            'unit_cell':{'type':'pyramid','width_mm':.3,'depth_mm':.3,'height_mm':3},
            'placement':{'mode':'area_fill','spacing_x_mm':1.2,'spacing_y_mm':.6}}
        dto=PatternDocumentDTO.from_document(doc,'f5c-5000',1)
        body={'document':dto.to_dict(),'document_revision':1}
        with patch.dict('os.environ',{'XIAOMANG_FABRIC_STL_TEST_EXPORT':'1','XIAOMANG_ENV':'development'}):
            with TestClient(create_app()) as client:
                result=client.post('/api/v1/fabric/fusion',json=body)
                self.assertEqual(result.status_code,422)
                report=result.json()['fusion_report']
                self.assertFalse(report['final_fabric_mesh_ready'])
                self.assertFalse(report['export_available'])
                self.assertEqual(report['validation_report']['degenerate_face_count'],38)
                response=client.post('/api/v1/fabric/fabric-final-'+('0'*64)+'/model.stl',json=body)
                self.assertEqual(response.status_code,422)
                self.assertNotIn('model/stl',response.headers['content-type'])

    def test_api_flag_stale_content_namespace_and_download(self):
        dto=PatternDocumentDTO.from_document(document_with_points(20),'f5c-api',1)
        body={'document':dto.to_dict(),'document_revision':1}
        with patch.dict('os.environ',{'XIAOMANG_FABRIC_STL_TEST_EXPORT':'1','XIAOMANG_ENV':'development'}):
            with TestClient(create_app()) as client:
                self.assertTrue(client.get('/api/v1/contract').json()['fabric_stl_test_export_enabled'])
                built=client.post('/api/v1/fabric/fusion',json=body)
                self.assertEqual(built.status_code,200,built.text)
                result_id=built.json()['final_fabric_mesh_id']
                self.assertTrue(built.json()['export_available'])
                url='/api/v1/fabric/'+result_id+'/model.stl'
                downloaded=client.post(url,json=body)
                self.assertEqual(downloaded.status_code,200,downloaded.text)
                self.assertEqual(downloaded.headers['content-type'],'model/stl')
                self.assertIn('xiaomang-fabric.stl',downloaded.headers['content-disposition'])
                changed=deepcopy(body);changed['document']['document']['metadata']['name']='changed'
                self.assertEqual(client.post(url,json=changed).status_code,422)
                changed=deepcopy(body);changed['document']['document_revision']=2;changed['document_revision']=2
                self.assertEqual(client.post(url,json=changed).status_code,422)
                self.assertEqual(client.get('/api/v1/manufacturing/'+result_id+'/model.stl').status_code,404)
                self.assertEqual(client.post('/api/v1/fabric/standard-id/model.stl',json=body).status_code,422)
        with patch.dict('os.environ',{'XIAOMANG_FABRIC_STL_TEST_EXPORT':'1','XIAOMANG_ENV':'production'}):
            with TestClient(create_app()) as client:
                self.assertFalse(client.get('/api/v1/contract').json()['fabric_stl_test_export_enabled'])
                response=client.post('/api/v1/fabric/fusion',json=body)
                self.assertFalse(response.json()['export_available'])
                self.assertEqual(client.post('/api/v1/fabric/unused/model.stl',json=body).status_code,403)
