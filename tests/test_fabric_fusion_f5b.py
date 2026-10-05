from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from unittest.mock import patch
import numpy as np
from fastapi.testclient import TestClient

from test_fabric_candidate_f5a import candidate,solid_100_fixture
from test_image_fabric_f4a import image_document,black_circle_bytes
from xiaomang_pattern_lab.fabric_base import BaseDefinition
from xiaomang_pattern_lab.fabric_cells import UnitCellDefinition
from xiaomang_pattern_lab.fabric_plan import FabricPlanner,RegularPlacement
from xiaomang_pattern_lab.fabric_preview import build_fabric_design
from xiaomang_pattern_lab.fabric_candidate import build_fabric_candidate
from xiaomang_pattern_lab.fabric_fusion import FabricFusionService,FabricFusionFailure
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.shared_fields import DistanceField,SizeModifier,RotationModifier,FieldMapping
from xiaomang_pattern_lab.shared_modifiers import SharedModifierStack,PositionModifier
from xiaomang_pattern_lab.web import create_app


class FusionTests(unittest.TestCase):
    def test_solid_true_union_coplanar_volume_and_bounds(self):
        original=candidate(solid_100_fixture())
        vertices=original.mesh.vertices.copy()
        final=FabricFusionService().build(original)
        self.assertTrue(final.report['final_fabric_mesh_ready'])
        self.assertEqual(final.report['connected_component_count'],1)
        self.assertEqual(final.report['validation_report']['degenerate_face_count'],0)
        self.assertAlmostEqual(final.report['volume_mm3'],2160+100*4)
        self.assertEqual(final.report['interface_overlap_mm'],0)
        np.testing.assert_allclose(final.mesh_result.mesh.bounds,original.mesh.bounds,atol=1e-6)
        np.testing.assert_array_equal(vertices,original.mesh.vertices)
        # Union retriangulates the base around attachment footprints, so face
        # count need not decrease. Actual connectivity and volume prove fusion.
        self.assertTrue(final.mesh_result.mesh.is_watertight)

    def test_all_cell_types_and_fin_outward_winding(self):
        for kind in ('pyramid','cone','fin','double_tower','cylinder'):
            plan=FabricPlanner().plan((0,0,60,60),.6,UnitCellDefinition(kind,2,2,3),RegularPlacement(6,6))
            self.assertGreater(plan.prototype.volume,0)
            final=FabricFusionService().build(candidate(plan))
            self.assertEqual(final.report['connected_component_count'],1)
            self.assertTrue(final.report['watertight'])
            self.assertEqual(final.report['validation_report']['error_count'],0)
            self.assertEqual(final.report['interface_overlap_mm'],0)

    def test_grid_valid_and_detached_blocks_before_backend(self):
        plan=solid_100_fixture()
        base=BaseDefinition('grid',.6,0,6,6,1)
        placed=replace(plan,instances=tuple(replace(item,x_mm=item.x_mm-3,y_mm=item.y_mm-3) for item in plan.instances))
        final=FabricFusionService().build(candidate(placed,base))
        self.assertEqual(final.report['connected_component_count'],1)
        detached=candidate(plan,base)
        with patch.object(FabricFusionService,'_union',side_effect=AssertionError('must block')):
            with self.assertRaises(FabricFusionFailure) as caught:
                FabricFusionService().build(detached)
        self.assertEqual(caught.exception.report['stage'],'preflight')
        self.assertEqual(len(caught.exception.report['instances']),100)

    def test_cell_cell_overlap_really_unions_volume(self):
        plan=solid_100_fixture()
        a=plan.instances[0]
        plan=replace(plan,instances=(a,replace(a,id='overlap',x_mm=a.x_mm+.5)))
        original=candidate(plan)
        final=FabricFusionService().build(original)
        self.assertEqual(final.report['connected_component_count'],1)
        self.assertLess(final.report['volume_mm3'],original.mesh.volume)

    def test_marginal_gap_cannot_claim_connected_or_extend_cells(self):
        plan=solid_100_fixture()
        item=plan.instances[0]
        plan=replace(plan,instances=(replace(item,z_mm=item.z_mm+5e-6),))
        source=candidate(plan)
        self.assertEqual(source.report['attachments'][0]['status'],'MARGINAL')
        with self.assertRaises(FabricFusionFailure) as caught:
            FabricFusionService().build(source)
        self.assertEqual(caught.exception.report['stage'],'connectivity')
        self.assertEqual(caught.exception.report['solid_component_count'],2)

    def test_invalid_transform_and_inward_solid_block(self):
        plan=solid_100_fixture()
        plan=replace(plan,instances=(replace(plan.instances[0],scale_x=0),))
        with patch.object(FabricFusionService,'_union',side_effect=AssertionError('must block')):
            with self.assertRaises(FabricFusionFailure) as caught:
                FabricFusionService().build(candidate(plan))
        self.assertEqual(caught.exception.report['stage'],'preflight')
        source=candidate(solid_100_fixture())
        inward=source.cell_meshes[0].copy()
        inward.faces=inward.faces[:,::-1]
        source=replace(source,cell_meshes=(inward,*source.cell_meshes[1:]))
        with self.assertRaises(FabricFusionFailure) as caught:
            FabricFusionService().build(source)
        self.assertEqual(caught.exception.report['stage'],'boolean_input')

    def test_cache_report_isolation_and_expiry(self):
        source=candidate(solid_100_fixture())
        service=FabricFusionService(ttl_seconds=0)
        self.assertFalse(service.build(source).report['cache_hit'])
        self.assertFalse(service.build(source).report['cache_hit'])
        service=FabricFusionService()
        first=service.build(source)
        first.report['validation_report']['error_count']=99
        self.assertEqual(service.build(source).report['validation_report']['error_count'],0)

    def test_cache_determinism_and_revision_key(self):
        source=candidate(solid_100_fixture())
        service=FabricFusionService()
        first=service.build(source)
        with patch.object(FabricFusionService,'_union',side_effect=AssertionError('cached')):
            second=service.build(source)
        self.assertTrue(second.report['cache_hit'])
        np.testing.assert_array_equal(first.mesh_result.mesh.vertices,second.mesh_result.mesh.vertices)
        independent=FabricFusionService().build(source)
        np.testing.assert_array_equal(first.mesh_result.mesh.vertices,independent.mesh_result.mesh.vertices)
        np.testing.assert_array_equal(first.mesh_result.mesh.faces,independent.mesh_result.mesh.faces)
        changed=replace(source,report={**source.report,'document_revision':8})
        self.assertFalse(service.build(changed).report['cache_hit'])

    def test_distance_height_orientation_and_pattern_points(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/'circle.png';path.write_bytes(black_circle_bytes())
            for mode in ('area_fill','pattern_points'):
                doc=image_document(path,mode,count=100)
                doc.fields=[DistanceField('distance',str(path),sample_bounds=(0,0,100,100)).to_dict(),
                    {'id':'linear','type':'linear','parameters':{'angle':0,'start':0,'end':100}}]
                doc.modifiers=[SizeModifier('size','linear',FieldMapping(.8,1.5)).to_dict(),
                    RotationModifier('rotation','linear',FieldMapping(-30,30)).to_dict()]
                stack=SharedModifierStack(source_elements=deepcopy(doc.elements))
                stack.add_modifier('position',PositionModifier(mode='offset',offset_x=3,offset_y=-2).to_dict())
                doc.metadata['xiaomang_pattern_lab.shared_modifiers']=stack.to_dict()
                doc.metadata['fabric_config']['field_modifiers']={
                    'height':{'enabled':True,'field_id':'distance','min_height_mm':1,'max_height_mm':8},
                    'orientation':{'enabled':True,'field_id':'distance','direction_mode':'gradient',
                        'alignment':'tangent','angle_offset_deg':12,'min_angle_deg':-45,'max_angle_deg':45}}
                dto=PatternDocumentDTO.from_document(doc,'f5b-distance',4,asset_bindings={str(path):'raster'})
                before=dto.to_dict()
                design=build_fabric_design(doc,dto,preview_limit=False)
                original=build_fabric_candidate(design.plan,design.config.base,design.design_bounds_mm,
                    document_id=dto.document_id,document_revision=4)
                final=FabricFusionService().build(original)
                self.assertTrue(final.report['final_fabric_mesh_ready'])
                np.testing.assert_allclose(final.mesh_result.mesh.bounds,original.mesh.bounds,atol=1e-6)
                self.assertEqual(dto.to_dict(),before)

    def test_api_failure_snapshot_and_no_stl_route(self):
        from test_fabric_preview_f25 import document_with_points
        doc=document_with_points(20)
        dto=PatternDocumentDTO.from_document(doc,'fusion-api',1)
        with TemporaryDirectory() as folder, patch.dict('os.environ',{'XIAOMANG_DEV_MANUFACTURING_SNAPSHOTS':'1'}):
            with TestClient(create_app(failure_snapshot_dir=Path(folder))) as client:
                result=client.post('/api/v1/fabric/fusion',json={'document':dto.to_dict(),'document_revision':1})
                self.assertEqual(result.status_code,200,result.text)
                self.assertFalse(result.json()['export_available'])
                self.assertEqual(client.get('/api/v1/manufacturing/'+result.json()['final_fabric_mesh_id']+'/model.stl').status_code,404)
                doc.metadata['fabric_config']['base']={'type':'grid','thickness_mm':.6,'margin_mm':10,
                    'spacing_x_mm':100,'spacing_y_mm':100,'line_width_mm':.1}
                dto=PatternDocumentDTO.from_document(doc,'fusion-api',2)
                failure=client.post('/api/v1/fabric/fusion',json={'document':dto.to_dict(),'document_revision':2})
                self.assertEqual(failure.status_code,422,failure.text)
                report=failure.json()['fusion_report']
                self.assertEqual(report['stage'],'preflight')
                snapshot=json.loads((Path(folder)/(report['failure_id']+'.json')).read_text(encoding='utf-8'))
                self.assertEqual(snapshot['document_revision'],2)
                self.assertEqual(snapshot['validation_summary']['fabric_fusion']['backend'],'manifold3d-mesh64')

    def test_snapshot_disabled_and_identifier_cannot_escape_directory(self):
        from test_fabric_preview_f25 import document_with_points
        from xiaomang_pattern_lab.web.failure_snapshot import save_manufacturing_failure
        doc=document_with_points(20)
        doc.metadata['fabric_config']['base']={'type':'grid','thickness_mm':.6,'margin_mm':10,
            'spacing_x_mm':100,'spacing_y_mm':100,'line_width_mm':.1}
        dto=PatternDocumentDTO.from_document(doc,'fusion-no-snapshot',1)
        with TemporaryDirectory() as folder, patch.dict('os.environ',{'XIAOMANG_DEV_MANUFACTURING_SNAPSHOTS':'0'}):
            with TestClient(create_app(failure_snapshot_dir=Path(folder))) as client:
                response=client.post('/api/v1/fabric/fusion',json={'document':dto.to_dict(),'document_revision':1})
                self.assertEqual(response.status_code,422)
                self.assertTrue(response.json()['fusion_report']['failure_id'])
                self.assertEqual(list(Path(folder).iterdir()),[])
            with self.assertRaises(ValueError):
                save_manufacturing_failure(Path(folder),dto,.6,'test',{},failure_id='../outside')
