"""F4-A: one existing scalar ImageField, no new Fabric image engine."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
from ppg.foundation import Canvas, PatternDocument, Reference, RectElement
from xiaomang_pattern_lab.shared_fields import (ImageField, FieldContext, LinearField,
    FieldMapping, SizeModifier, RotationModifier, CompositeField)
from xiaomang_pattern_lab.fabric_preview import build_fabric_preview
from xiaomang_pattern_lab.contracts import PatternDocumentDTO, final_geometry
from xiaomang_pattern_lab.parameter_definitions import parameter_definitions
from xiaomang_pattern_lab.web import create_app
from xiaomang_pattern_lab.web.assets import TemporaryAssetStore
from xiaomang_pattern_lab.shared_modifiers import SharedModifierStack, PositionModifier


def black_circle_bytes():
    """Versioned fixed fixture: 101x101 white raster, radius 25 black circle."""
    image = Image.new('RGB', (101, 101), 'white')
    ImageDraw.Draw(image).ellipse((25, 25, 75, 75), fill='black')
    output = BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


def image_document(path, mode='area_fill', count=20):
    doc = PatternDocument(Canvas(100, 100, 'mm', 1), Reference('', False), [
        RectElement(f'point-{i}', 5 + i % 5 * 20, 5 + i // 5 * 20, 2, 2)
        for i in range(count)])
    # Two corner elements establish the full base bounds without a filled plaque.
    if mode == 'area_fill':
        doc.elements = [RectElement('lo', 1, 1, 2, 2), RectElement('hi', 99, 99, 2, 2)]
    doc.fields = [ImageField('image', image_path=str(path), sample_bounds=(0, 0, 100, 100),
        black_is_one=True, out_of_bounds='zero').to_dict()]
    doc.metadata['fabric_config'] = {'config_version': 1,
        'base': {'type': 'solid', 'thickness_mm': .6, 'margin_mm': 0},
        'unit_cell': {'type': 'fin', 'width_mm': 2, 'depth_mm': 1, 'height_mm': 3},
        'placement': {'mode': mode, 'spacing_x_mm': 5, 'spacing_y_mm': 5}}
    return doc


def run_preview(doc):
    dto = PatternDocumentDTO.from_document(doc, 'image-fixture', 12,
        asset_bindings={doc.fields[0]['parameters']['image_path']: 'raster'})
    return build_fabric_preview(doc, dto)


class ImageFabricF4ATests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'black-circle-v1.png'
        self.path.write_bytes(black_circle_bytes())

    def test_scalar_world_mapping_invert_mask_and_outside(self):
        field = ImageField('f', str(self.path), black_is_one=True,
            sample_bounds=(10, 20, 110, 120), out_of_bounds='zero')
        context = FieldContext((-100, -100, 500, 500))
        point = lambda x, y: RectElement('sample', x, y, 1, 1)
        self.assertEqual(field.evaluate(point(60, 70), context), 1)
        self.assertEqual(field.evaluate(point(10, 20), context), 0)
        self.assertEqual(field.evaluate(point(9, 70), context), 0)
        params = field.to_dict()['parameters']
        inverse = ImageField('inverse', **{**params, 'invert': True})
        self.assertEqual(inverse.evaluate(point(60, 70), context), 0)
        self.assertEqual(inverse.evaluate(point(9, 70), context), 0)  # outside stays zero even inverted
        mask = ImageField('mask', **{**params, 'sampling_mode': 'mask', 'threshold': .5})
        self.assertEqual(mask.evaluate(point(60, 70), context), 1)
        self.assertEqual(mask.evaluate(point(10, 20), context), 0)
        for params in ({'threshold': float('nan')}, {'threshold': 2}, {'sampling_mode': 'invalid'},
                       {'sample_bounds': (0, 0, 0, 1)}):
            with self.assertRaises(ValueError):
                ImageField('invalid', **params)

    def test_grayscale_is_continuous_and_jpeg_uses_same_sampler(self):
        gray = Path(self.temp.name) / 'gray.jpg'
        Image.new('L', (2, 2), 128).save(gray)
        field = ImageField('gray', str(gray), black_is_one=True)
        value = field.evaluate(RectElement('p', 0, 0, 1, 1), FieldContext((0, 0, 1, 1)))
        self.assertAlmostEqual(value, 127/255, places=2)

    def test_height_scale_density_combined_deterministic_and_read_only(self):
        doc = image_document(self.path)
        configs = {
            'height': {'enabled': True, 'field_id': 'image', 'min_height_mm': 1, 'max_height_mm': 8},
            'scale': {'enabled': True, 'field_id': 'image', 'min_scale': .5, 'max_scale': 2},
            'density': {'enabled': True, 'field_id': 'image', 'threshold': .5}}
        for kind in configs:
            doc.metadata['fabric_config']['field_modifiers'] = {kind: configs[kind]}
            before = deepcopy(doc.to_dict())
            payload = run_preview(doc)
            center = next(i for i in payload['instances'] if i['x_mm'] == i['y_mm'] == 47.5)
            outside = payload['instances'][0]
            if kind == 'height':
                self.assertEqual((center['height_mm'], outside['height_mm']), (8, 1))
            elif kind == 'scale':
                self.assertEqual((center['scale'], outside['scale']), (2, .5))
            else:
                self.assertTrue(center['enabled']); self.assertFalse(outside['enabled'])
            self.assertEqual(run_preview(doc)['instances'], payload['instances'])
            self.assertEqual(doc.to_dict(), before)
        doc.metadata['fabric_config']['field_modifiers'] = configs
        combined = run_preview(doc)
        center = next(i for i in combined['instances'] if i['x_mm'] == i['y_mm'] == 47.5)
        self.assertEqual((center['height_mm'], center['scale'], center['enabled']), (8, 2, True))
        self.assertEqual(combined['total_count'], 400)

    def test_composite_reuses_image_scalar(self):
        doc = image_document(self.path)
        doc.fields += [CompositeField('combo', 'image', 'image', 'multiply').to_dict()]
        doc.metadata['fabric_config']['field_modifiers'] = {
            'height': {'enabled': True, 'field_id': 'combo', 'min_height_mm': 1, 'max_height_mm': 6}}
        self.assertEqual(max(i['height_mm'] for i in run_preview(doc)['instances']), 6)

    def test_pattern_points_preserves_final_transforms_without_double_scale(self):
        doc = image_document(self.path, 'pattern_points', 20)
        doc.fields += [LinearField('linear', start=0, end=100).to_dict()]
        doc.modifiers = [SizeModifier('size', 'linear', FieldMapping(.5, 2)).to_dict(),
                         RotationModifier('rotate', 'linear', FieldMapping(-45, 45)).to_dict()]
        stack = SharedModifierStack(source_elements=deepcopy(doc.elements))
        stack.add_modifier('position', PositionModifier(mode='offset', offset_x=3, offset_y=4).to_dict())
        # Use the official stack serializer rather than reproducing transform math.
        doc.metadata['xiaomang_pattern_lab.shared_modifiers'] = stack.to_dict()
        doc.metadata['fabric_config']['field_modifiers'] = {
            'height': {'enabled': True, 'field_id': 'image', 'min_height_mm': 1, 'max_height_mm': 6},
            'scale': {'enabled': True, 'field_id': 'image', 'min_scale': .5, 'max_scale': 2}}
        before = deepcopy(doc.to_dict())
        geometry, _ = final_geometry(doc)
        payload = run_preview(doc)
        self.assertEqual(payload['total_count'], 20)
        for final, instance in zip(geometry, payload['instances']):
            self.assertAlmostEqual(instance['x_mm'], final['x'])
            self.assertAlmostEqual(instance['y_mm'], final['y'])
            self.assertAlmostEqual(instance['rotation_deg'], final['rotation'])
            self.assertAlmostEqual(instance['cell_width_mm'], 2 * (final['width'] / 2) * instance['scale'])
        self.assertEqual(doc.to_dict(), before)

    def test_mm_conversion_changes_registration_not_uv(self):
        doc = image_document(self.path)
        doc.canvas.mm_per_unit = 2
        doc.metadata['fabric_config']['placement']['spacing_x_mm'] = 10
        doc.metadata['fabric_config']['placement']['spacing_y_mm'] = 10
        doc.metadata['fabric_config']['field_modifiers'] = {
            'height': {'enabled': True, 'field_id': 'image', 'min_height_mm': 1, 'max_height_mm': 6}}
        payload = run_preview(doc)
        self.assertEqual(payload['total_count'], 400)
        self.assertEqual(max(i['height_mm'] for i in payload['instances']), 6)

    def test_asset_expiry_invalidates_cached_preview_and_reupload_recovers(self):
        store = TemporaryAssetStore()
        # Production create_app() must resolve its own uploads, not require a
        # test-only injected resolver.
        with TestClient(create_app(asset_store=store)) as client:
            def upload():
                response = client.post('/api/v1/assets', content=black_circle_bytes(),
                    headers={'Content-Type': 'image/png', 'X-Filename': 'circle.png'})
                self.assertEqual(response.status_code, 200)
                return response.json()['asset_id']
            token = upload()
            doc = image_document(self.path)
            doc.metadata['fabric_config']['field_modifiers'] = {
                'height': {'enabled': True, 'field_id': 'image', 'min_height_mm': 1, 'max_height_mm': 6}}
            dto = PatternDocumentDTO.from_document(doc, 'asset-test', 7,
                asset_bindings={str(self.path): token}).to_dict()
            body = {'document': dto, 'document_revision': 7}
            with patch('xiaomang_pattern_lab.manufacturing_service.ManufacturingService.build',
                       side_effect=AssertionError('preview must not manufacture')):
                self.assertEqual(client.post('/api/v1/fabric/preview', json=body).status_code, 200)
                store.ttl_seconds = 0
                expired = client.post('/api/v1/fabric/preview', json=body)
                self.assertEqual(expired.status_code, 422)
                self.assertEqual(expired.json()['code'], 'unresolved_asset')
                store.ttl_seconds = 1800
                dto['assets'][0]['asset_id'] = upload()
                restored = client.post('/api/v1/fabric/preview', json=body)
                self.assertEqual(restored.status_code, 200)
                self.assertEqual(restored.json()['document_revision'], 7)
                self.assertNotIn(str(self.path), restored.text)

    def test_svg_cannot_be_spoofed_as_raster_field_asset(self):
        with TestClient(create_app()) as client:
            token = client.post('/api/v1/assets', content=b'<svg xmlns="http://www.w3.org/2000/svg"/>',
                headers={'Content-Type': 'image/svg+xml'}).json()['asset_id']
            dto = PatternDocumentDTO.from_document(image_document(self.path), 'svg', 1,
                asset_bindings={str(self.path): token}).to_dict()
            dto['assets'][0]['media_type'] = 'image/png'
            response = client.post('/api/v1/evaluate', json={
                'schema_version': '1.0', 'document_id': 'svg', 'document_revision': 1, 'document': dto})
            self.assertEqual(response.status_code, 422)
            self.assertIn('PNG/JPG', response.json()['message'])

    def test_schema_and_missing_image_fail_explicitly(self):
        schema = parameter_definitions()['definitions']['field']['image']
        self.assertTrue(next(p for p in schema['parameters'] if p['id'] == 'black_is_one')['default'])
        doc = image_document(self.path)
        doc.fields[0]['parameters']['image_path'] = str(self.path.parent / 'gone.png')
        doc.metadata['fabric_config']['field_modifiers'] = {
            'height': {'enabled': True, 'field_id': 'image', 'min_height_mm': 1, 'max_height_mm': 6}}
        with self.assertRaisesRegex(ValueError, '失效'):
            run_preview(doc)

    def test_raster_field_keeps_standard_manufacturing_and_stl_path(self):
        with TestClient(create_app()) as client:
            token = client.post('/api/v1/assets', content=black_circle_bytes(),
                headers={'Content-Type': 'image/png'}).json()['asset_id']
            doc = image_document(self.path, 'pattern_points', 20)
            doc.metadata.pop('fabric_config')
            doc.modifiers = [SizeModifier('size', 'image', FieldMapping(.8, 1.2)).to_dict()]
            dto = PatternDocumentDTO.from_document(doc, 'standard-image', 3,
                asset_bindings={str(self.path): token}).to_dict()
            response = client.post('/api/v1/manufacturing/build', json={
                'schema_version': '1.0', 'document_id': 'standard-image',
                'document_revision': 3, 'document': dto, 'height_mm': 2})
            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()
            self.assertTrue(result['mesh_validation_summary']['is_watertight'])
            stl = client.get('/api/v1/manufacturing/' + result['manufacturing_result_id'] + '/model.stl')
            self.assertEqual(stl.status_code, 200)
            import trimesh
            mesh = trimesh.load(BytesIO(stl.content), file_type='stl')
            self.assertTrue(mesh.is_watertight)
            self.assertAlmostEqual(mesh.extents[2], 2)

    def test_image_orientation_is_not_silently_enabled_in_f4a(self):
        doc = image_document(self.path)
        doc.metadata['fabric_config']['field_modifiers'] = {
            'orientation': {'enabled': True, 'field_id': 'image', 'min_angle_deg': 0, 'max_angle_deg': 90}}
        with self.assertRaisesRegex(ValueError, 'F4-B'):
            run_preview(doc)
