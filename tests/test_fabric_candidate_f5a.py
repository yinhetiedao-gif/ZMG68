"""Tracked F5-A manufacturing fixtures; contact is never fusion."""
from dataclasses import replace
import unittest
from copy import deepcopy
from tempfile import TemporaryDirectory
from pathlib import Path
import numpy as np
from fastapi.testclient import TestClient
from xiaomang_pattern_lab.fabric_base import BaseDefinition
from xiaomang_pattern_lab.fabric_cells import UnitCellDefinition
from xiaomang_pattern_lab.fabric_plan import FabricPlanner, RegularPlacement
from xiaomang_pattern_lab.fabric_candidate import build_fabric_candidate, instance_matrix
from xiaomang_pattern_lab.fabric_preview import build_fabric_design, build_fabric_preview
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.web import create_app
from test_fabric_preview_f25 import document_with_points


def solid_100_fixture():
    return FabricPlanner().plan((0, 0, 60, 60), .6,
        UnitCellDefinition('pyramid', 2, 2, 3), RegularPlacement(6, 6), preview_limit=False)


def candidate(plan, base=None):
    return build_fabric_candidate(plan, base or BaseDefinition('solid', .6, 0),
        (0, 0, 60, 60), document_id='f5a-fixture', document_revision=7)


class CandidateTests(unittest.TestCase):
    def test_solid_100_actual_bounds_and_unfused(self):
        result = candidate(solid_100_fixture())
        self.assertEqual(result.report['attachment_counts']['ATTACHED'], 100)
        np.testing.assert_allclose(result.mesh.bounds, [[0, 0, 0], [60, 60, 3.6]])
        self.assertFalse(result.report['fused'])
        self.assertFalse(result.report['export_available'])
        self.assertEqual(result.report['components']['prefusion_components'], 101)

    def test_grid_hole_detached(self):
        result = candidate(solid_100_fixture(), BaseDefinition('grid', .6, 0, 6, 6, 1))
        self.assertEqual(result.report['attachment_counts']['DETACHED'], 100)
        self.assertEqual(result.report['attachments'][0]['contact_area_mm2'], 0)

    def test_grid_material_and_tiny_contact(self):
        plan = solid_100_fixture()
        item = replace(plan.instances[0], x_mm=6, y_mm=6)
        result = candidate(replace(plan,instances=(item,)),BaseDefinition('grid',.6,0,6,6,1))
        self.assertEqual(result.report['attachment_counts']['ATTACHED'],1)
        tiny = replace(item,x_mm=60.9999,y_mm=30)
        result = candidate(replace(plan,instances=(tiny,)))
        self.assertEqual(result.report['attachment_counts']['MARGINAL'],1)
        self.assertGreater(result.report['attachments'][0]['contact_area_mm2'],0)

    def test_penetration_measures_actual_base_top_section(self):
        plan = solid_100_fixture()
        item = replace(plan.instances[0],z_mm=.3)
        result = candidate(replace(plan,instances=(item,)))
        entry = result.report['attachments'][0]
        self.assertEqual(entry['status'],'ATTACHED')
        self.assertAlmostEqual(entry['overlap_depth_mm'],.3)
        # Pyramid cross section at 0.3 above bottom is 0.9x in each axis.
        self.assertAlmostEqual(entry['contact_area_mm2'],4*.9**2)

    def test_transform_parity_and_enabled_only(self):
        plan = solid_100_fixture()
        item = replace(plan.instances[0], rotation_deg=30, scale_x=2, scale_y=.5,
                       cell_width_mm=4, cell_depth_mm=1, height_mm=8)
        plan = replace(plan, instances=(item, replace(plan.instances[1], enabled=False)))
        result = candidate(plan)
        expected_matrix = np.array([[np.sqrt(3),-.25,0,item.x_mm],
            [1,np.sqrt(3)/4,0,item.y_mm],[0,0,8/3,.6],[0,0,0,1]])
        np.testing.assert_allclose(instance_matrix(item,plan.cell),expected_matrix,atol=1e-12)
        expected = plan.prototype.vertices @ expected_matrix[:3,:3].T + expected_matrix[:3,3]
        np.testing.assert_allclose(result.cell_meshes[0].vertices, expected)
        self.assertEqual(result.report['enabled_instance_count'], 1)
        self.assertEqual(result.report['bounds_mm'][1][2], 8.6)
        self.assertEqual(result.instance_transforms[0]['source_id'], item.source_id)

    def test_invalid_and_near_contact_preserve_ids(self):
        plan = solid_100_fixture()
        cases = [(replace(plan.instances[0], height_mm=0), 'INVALID'),
                 (replace(plan.instances[0], z_mm=.7), 'DETACHED'),
                 (replace(plan.instances[0], z_mm=.600005), 'MARGINAL'),
                 (replace(plan.instances[0], x_mm=float('nan')), 'INVALID'),
                 (replace(plan.instances[0], z_mm=-.1), 'INVALID')]
        for item, state in cases:
            with self.subTest(state=state):
                result = candidate(replace(plan, instances=(item,)))
                self.assertEqual(result.report['attachments'][0]['status'], state)
                self.assertEqual(result.report['attachments'][0]['instance_id'], item.id)

    def test_all_prototypes_and_determinism(self):
        for kind in ('cylinder','cone','pyramid','double_tower','fin'):
            plan = FabricPlanner().plan((0,0,60,60),.6,UnitCellDefinition(kind,2,2,3),RegularPlacement(6,6))
            a, b = candidate(plan), candidate(plan)
            np.testing.assert_array_equal(a.mesh.vertices,b.mesh.vertices)
            np.testing.assert_array_equal(a.mesh.faces,b.mesh.faces)
            self.assertEqual(a.report['attachment_counts']['ATTACHED'],100)

    def test_full_plan_is_not_preview_cap(self):
        args = ((0,0,60,100),.6,UnitCellDefinition('pyramid',.3,.3,3),RegularPlacement(1,1))
        self.assertEqual(len(FabricPlanner().plan(*args).instances),5000)
        self.assertEqual(len(FabricPlanner().plan(*args,preview_limit=False).instances),6000)

    def test_sampled_preview_keeps_full_pattern_field_context(self):
        from xiaomang_pattern_lab.fabric_plan import FabricPlacementPoint
        from xiaomang_pattern_lab.fabric_field_modifiers import apply_fabric_field_modifiers
        points = [FabricPlacementPoint(str(i),str(i),float(i%60),float(i//60)) for i in range(6000)]
        # This interior ID is omitted by deterministic preview sampling and
        # supplies the extreme center. Context must still include it.
        points[5] = replace(points[5],x_mm=-100)
        cell = UnitCellDefinition('pyramid',.3,.3,3)
        preview = FabricPlanner().plan_points(points,.6,cell)
        full = FabricPlanner().plan_points(points,.6,cell,preview_limit=False)
        document = document_with_points(20)
        document.fields = [{'id':'linear','type':'linear','parameters':{'angle':0}}]
        config = {'height':{'enabled':True,'field_id':'linear','min_height_mm':1,'max_height_mm':8}}
        preview = apply_fabric_field_modifiers(preview,document,config)
        full = apply_fabric_field_modifiers(full,document,config)
        by_id = {item.id:item for item in full.instances}
        for shown in preview.instances:
            self.assertEqual(shown,by_id[shown.id])

    def test_api_and_pattern_points_parity_read_only(self):
        document = document_with_points(20)
        dto = PatternDocumentDTO.from_document(document, 'candidate-parity', 12)
        before = dto.to_dict()
        design = build_fabric_design(document, dto, preview_limit=False)
        preview = build_fabric_preview(document, dto)
        result = build_fabric_candidate(design.plan,design.config.base,design.design_bounds_mm,
            document_id=dto.document_id,document_revision=12)
        for shown, actual in zip(preview['instances'], result.instance_transforms):
            for key in ('x_mm','y_mm','z_mm','rotation_deg','scale_x','scale_y','enabled','cell_width_mm','cell_depth_mm'):
                self.assertEqual(shown[key], actual[key])
            self.assertEqual(shown['cell_height_mm'],actual['height_mm'])
        with TestClient(create_app()) as client:
            response = client.post('/api/v1/fabric/candidate', json={'document':before,'document_revision':12})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['enabled_instance_count'],20)
            self.assertFalse(response.json()['export_available'])
            stale = client.post('/api/v1/fabric/candidate', json={'document':before,'document_revision':11})
            self.assertNotEqual(stale.status_code,200)
        self.assertEqual(dto.to_dict(),before)

    def test_image_distance_gradient_and_pattern_modifiers_parity(self):
        from test_image_fabric_f4a import image_document, black_circle_bytes
        from xiaomang_pattern_lab.shared_fields import DistanceField, SizeModifier, RotationModifier, FieldMapping
        from xiaomang_pattern_lab.shared_modifiers import SharedModifierStack, PositionModifier
        with TemporaryDirectory() as folder:
            path = Path(folder)/'circle.png'
            path.write_bytes(black_circle_bytes())
            for kind in ('image','distance'):
                doc = image_document(path, mode='pattern_points')
                if kind == 'distance':
                    doc.fields = [DistanceField('image',str(path),sample_bounds=(0,0,100,100)).to_dict()]
                doc.fields.append({'id':'linear','type':'linear','parameters':{'angle':0,'start':0,'end':100}})
                doc.modifiers = [SizeModifier('size','linear',FieldMapping(.8,1.5)).to_dict(),
                    RotationModifier('rotation','linear',FieldMapping(-30,30)).to_dict()]
                stack = SharedModifierStack(source_elements=deepcopy(doc.elements))
                stack.add_modifier('position',PositionModifier(mode='offset',offset_x=3,offset_y=-2).to_dict())
                doc.metadata['xiaomang_pattern_lab.shared_modifiers'] = stack.to_dict()
                doc.metadata['fabric_config']['field_modifiers'] = {
                    'height':{'enabled':True,'field_id':'image','min_height_mm':1,'max_height_mm':8},
                    'scale':{'enabled':True,'field_id':'image','min_scale':.5,'max_scale':2},
                    'density':{'enabled':True,'field_id':'linear','threshold':.3},
                    **({'orientation':{'enabled':True,'field_id':'image','direction_mode':'gradient',
                        'alignment':'tangent','angle_offset_deg':12,'min_angle_deg':-45,'max_angle_deg':45}} if kind=='distance' else {})}
                dto = PatternDocumentDTO.from_document(doc,'f5a-image',4,asset_bindings={str(path):'raster'})
                preview = build_fabric_preview(doc,dto)
                design = build_fabric_design(doc,dto,preview_limit=False)
                result = build_fabric_candidate(design.plan,design.config.base,design.design_bounds_mm,
                    document_id=dto.document_id,document_revision=4)
                shown = [i for i in preview['instances'] if i['enabled']]
                self.assertEqual(len(shown),len(result.cell_meshes))
                for image, actual in zip(shown,result.instance_transforms):
                    for key in ('x_mm','y_mm','rotation_deg','cell_width_mm','cell_depth_mm','enabled'):
                        self.assertEqual(image[key],actual[key])
                    self.assertEqual(image['cell_height_mm'],actual['height_mm'])
