"""Fixed raster/world-coordinate and real preview regressions for F4-B."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import numpy as np
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
from ppg.foundation import RectElement
from xiaomang_pattern_lab.shared_fields import DistanceField, FieldRegistry, FieldContext, FieldMapping, SizeModifier, RotationModifier
from xiaomang_pattern_lab.shared_modifiers import SharedModifierStack, PositionModifier
from xiaomang_pattern_lab.distance_raster import _edt_line, _CACHE, distance_raster
from xiaomang_pattern_lab.field_gradient import gradient_angles
from xiaomang_pattern_lab.contracts import PatternDocumentDTO, final_geometry
from xiaomang_pattern_lab.web import create_app
from xiaomang_pattern_lab.web.assets import TemporaryAssetStore
from test_image_fabric_f4a import black_circle_bytes, image_document, run_preview


def ring_bytes():
    from io import BytesIO
    image = Image.new('L', (101, 101), 255)
    draw = ImageDraw.Draw(image)
    draw.ellipse((10, 10, 90, 90), fill=0)
    draw.ellipse((30, 30, 70, 70), fill=255)
    output = BytesIO(); image.save(output, format='PNG')
    return output.getvalue()


class DistanceOrientationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'circle.png'
        self.path.write_bytes(black_circle_bytes())
        self.context = FieldContext((0, 0, 100, 100))

    def scalar(self, field, x, y):
        return field.evaluate(RectElement('point', x, y, 1, 1), self.context)

    def field(self, **kwargs):
        return DistanceField('distance', str(self.path), sample_bounds=(0, 0, 100, 100), **kwargs)

    def document(self):
        doc = image_document(self.path)
        doc.fields = [self.field().to_dict()]
        doc.metadata['fabric_config']['field_modifiers'] = {
            'height': {'enabled': True, 'field_id': 'distance', 'min_height_mm': 1, 'max_height_mm': 8},
            'scale': {'enabled': True, 'field_id': 'distance', 'min_scale': .5, 'max_scale': 2},
            'orientation': {'enabled': True, 'field_id': 'distance', 'min_angle_deg': -45,
                'max_angle_deg': 45, 'direction_mode': 'gradient', 'alignment': 'normal', 'angle_offset_deg': 12}}
        return doc

    def test_edt_matches_bruteforce_anisotropic(self):
        for spacing in (.1, 1, 3.2):
            values = np.array([np.inf, 4, np.inf, 0, 3, np.inf, 2])
            expected = [min(values[p]+spacing**2*(p-q)**2 for p in range(len(values))) for q in range(len(values))]
            np.testing.assert_allclose(_edt_line(values, spacing), expected)

    def test_two_dimensional_distance_against_exact_boundary_oracle(self):
        mask = np.zeros((9, 13), dtype=bool); mask[1:8, 2:11] = True
        mask[3, 5] = False  # hole/concavity must participate in boundary distance
        pixels = tuple(int(v) for v in np.where(mask, 0, 255).ravel())
        raster = distance_raster((13, 9, pixels), (0, 0, 24, 8), .5, 10, False)[2].reshape(mask.shape)
        padded = np.pad(mask, 1)
        boundary = mask & ~(padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:])
        by, bx = np.where(boundary)
        for y, x in zip(*np.where(mask)):
            expected = np.sqrt(np.min(((bx-x)*2)**2+(by-y)**2))/10
            self.assertAlmostEqual(raster[y, x], expected)

    def test_ring_fin_normal_tangent_gradients(self):
        self.path.write_bytes(ring_bytes())
        registry = FieldRegistry([self.field()])
        points = [RectElement(str(i), x, y, 1, 1) for i, (x, y) in enumerate(((83, 50), (50, 83), (17, 50), (50, 17)))]
        angles = gradient_angles(registry, 'distance', points, self.context)
        for angle, expected in zip(angles, (180, -90, 0, 90)):
            self.assertAlmostEqual(abs((angle-expected+180)%360-180), 0, places=5)
        self.assertEqual(self.scalar(self.field(), 50, 50), 0)  # hole stays outside

    def test_real_pattern_modifiers_and_fabric_combination_map_once(self):
        doc = self.document()
        doc.metadata['fabric_config']['placement']['mode'] = 'pattern_points'
        doc.fields.append({'id': 'linear', 'type': 'linear', 'parameters': {'angle': 0, 'start': 0, 'end': 100}})
        doc.modifiers = [SizeModifier('size', 'linear', FieldMapping(.8, 1.5)).to_dict(),
                         RotationModifier('rotation', 'linear', FieldMapping(-30, 30)).to_dict()]
        stack = SharedModifierStack(source_elements=deepcopy(doc.elements))
        stack.add_modifier('position', PositionModifier(mode='offset', offset_x=3, offset_y=-2).to_dict())
        doc.metadata['xiaomang_pattern_lab.shared_modifiers'] = stack.to_dict()
        before = deepcopy(doc.to_dict())
        geometry, _ = final_geometry(doc)
        result = run_preview(doc)
        self.assertEqual(doc.to_dict(), before)
        sources = {e.id: e for e in doc.elements}
        finals = {g['id']: g for g in geometry}
        self.assertEqual(result['total_count'], len(finals))
        registry = FieldRegistry([self.field()])
        for instance in result['instances']:
            final = finals[instance['final_geometry_id']]; source = sources[instance['source_id']]
            self.assertAlmostEqual(instance['x_mm'], final['x'])
            self.assertAlmostEqual(instance['y_mm'], final['y'])
            self.assertAlmostEqual(instance['scale_x'], final['width']/source.width)
            point = RectElement('p', instance['x_mm'], instance['y_mm'], 1, 1)
            value = registry.evaluate('distance', point, self.context)
            fabric_scale = .5+1.5*value
            self.assertAlmostEqual(instance['cell_width_mm'], 2*instance['scale_x']*fabric_scale)
            angle = gradient_angles(registry, 'distance', [point], self.context)[0]
            expected = final['rotation']+(angle+12 if angle is not None else 0)
            self.assertAlmostEqual(instance['rotation_deg'], expected)

    def test_center_edge_outside_invert_and_threshold(self):
        field = self.field()
        self.assertEqual(self.scalar(field, 50, 50), 1)
        self.assertEqual(self.scalar(field, 75, 50), 0)
        self.assertEqual(self.scalar(field, 0, 0), 0)
        inverse = self.field(invert=True)
        self.assertEqual(self.scalar(inverse, 50, 50), 0)
        self.assertEqual(self.scalar(inverse, 75, 50), 1)
        self.assertEqual(self.scalar(inverse, -1, 50), 0)
        self.assertEqual(self.scalar(inverse, 0, 0), 0)
        Image.new('L', (5, 5), 128).save(self.path)
        self.assertEqual(self.scalar(self.field(threshold=.6), 50, 50), 0)
        self.assertEqual(self.scalar(self.field(threshold=.4), 50, 50), 1)

    def test_world_mm_anisotropy_and_unit_conversion(self):
        image = Image.new('L', (11, 11), 255)
        for x in range(2, 9):
            for y in range(2, 9): image.putpixel((x, y), 0)
        image.save(self.path)
        field = DistanceField('f', str(self.path), sample_bounds=(0, 0, 20, 10), auto_normalize=False, max_distance_mm=10)
        self.assertAlmostEqual(self.scalar(field, 10, 5), .3)
        scaled = replace(field, sample_bounds=(0, 0, 10, 5), world_mm_per_unit=2)
        self.assertAlmostEqual(self.scalar(scaled, 5, 2.5), .3)
        self.assertEqual(self.scalar(field, 10, 5), self.scalar(field, 10, 5))

    def test_cache_config_and_asset_invalidation(self):
        a, b = self.field(), self.field()
        self.scalar(a, 50, 50); self.scalar(b, 50, 50)
        self.assertIs(a._distance_pixels, b._distance_pixels)
        c = self.field(invert=True); self.scalar(c, 50, 50)
        self.assertIsNot(a._distance_pixels, c._distance_pixels)
        Image.new('L', (101, 101), 255).save(self.path)
        self.assertEqual(self.scalar(self.field(), 50, 50), 0)
        self.assertLessEqual(len(_CACHE), 8)

    def test_gradient_linear_composite_and_flat_fallback(self):
        registry = FieldRegistry.from_list([
            {'id': 'linear', 'type': 'linear', 'parameters': {'angle': 30, 'start': -100, 'end': 100}},
            {'id': 'flat', 'type': 'constant', 'parameters': {'value': .5}},
            {'id': 'mix', 'type': 'composite', 'parameters': {'input_a_field_id': 'linear', 'input_b_field_id': 'flat', 'operator': 'multiply'}}])
        points = [RectElement('p', 0, 0, 1, 1)]
        self.assertAlmostEqual(gradient_angles(registry, 'linear', points, self.context)[0], 30)
        self.assertAlmostEqual(gradient_angles(registry, 'mix', points, self.context)[0], 30)
        self.assertEqual(gradient_angles(registry, 'flat', points, self.context), (None,))

    def test_height_scale_density_normal_tangent_combined_read_only(self):
        doc = self.document(); before = deepcopy(doc.to_dict())
        normal = run_preview(doc)
        self.assertEqual(doc.to_dict(), before)
        center = max(normal['instances'], key=lambda i: i['height_mm'])
        self.assertGreater(center['height_mm'], normal['instances'][0]['height_mm'])
        self.assertGreater(center['scale'], normal['instances'][0]['scale'])
        config = doc.metadata['fabric_config']['field_modifiers']
        config['orientation']['alignment'] = 'tangent'
        tangent = run_preview(doc)
        changed = [(n, t) for n, t in zip(normal['instances'], tangent['instances']) if abs(n['rotation_deg']) > .001]
        self.assertTrue(changed)
        for n, t in changed: self.assertAlmostEqual(t['rotation_deg']-n['rotation_deg'], 90)
        config['density'] = {'enabled': True, 'field_id': 'distance', 'threshold': .2}
        density = run_preview(doc)
        self.assertTrue(any(i['enabled'] for i in density['instances']))
        self.assertTrue(any(not i['enabled'] for i in density['instances']))
        self.assertEqual(run_preview(doc)['instances'], density['instances'])

    def test_pattern_points_inheritance_and_flat_preserves_rotation(self):
        doc = self.document()
        doc.metadata['fabric_config']['placement']['mode'] = 'pattern_points'
        doc.fields.append({'id': 'flat', 'type': 'constant', 'parameters': {'value': .5}})
        doc.elements = [RectElement('a', 40, 50, 4, 2, rotation=25), RectElement('b', 60, 50, 2, 4, rotation=-20)]
        doc.metadata['fabric_config']['field_modifiers']['orientation']['field_id'] = 'flat'
        result = run_preview(doc)
        self.assertEqual(len(result['instances']), 2)
        for instance, source in zip(result['instances'], doc.elements):
            self.assertAlmostEqual(instance['x_mm'], source.x)
            self.assertAlmostEqual(instance['y_mm'], source.y)
            self.assertAlmostEqual(instance['rotation_deg'], source.rotation)
        self.assertEqual(doc.elements[0].width, 4)

    def test_asset_api_expiry_and_new_server_rebind(self):
        doc = self.document()
        dto = PatternDocumentDTO.from_document(doc, 'distance-fixture', 9, asset_bindings={str(self.path): 'token'}).to_dict()
        self.assertNotIn(str(self.path), str(dto))
        for _ in range(2):
            store = TemporaryAssetStore()
            self.addCleanup(store._directory.cleanup)
            with TestClient(create_app(asset_store=store)) as client:
                asset = client.post('/api/v1/assets', content=self.path.read_bytes(), headers={'content-type': 'image/png'}).json()
                dto['assets'][0]['asset_id'] = asset['asset_id']
                result = client.post('/api/v1/fabric/preview', json={'document': dto, 'document_revision': 9})
                self.assertEqual(result.status_code, 200, result.text)
                self.assertEqual(result.json()['document_revision'], 9)
                store._items.clear()
                expired = client.post('/api/v1/fabric/preview', json={'document': dto, 'document_revision': 9})
                self.assertEqual(expired.json()['code'], 'unresolved_asset')

    def test_invalid_distance_and_orientation_parameters(self):
        for kwargs in ({'max_distance_mm': 0}, {'max_distance_mm': float('nan')}, {'threshold': 2}, {'auto_normalize': 'yes'}):
            with self.assertRaises(ValueError): self.field(**kwargs)
        doc = self.document()
        doc.metadata['fabric_config']['field_modifiers']['orientation']['alignment'] = 'invalid'
        with self.assertRaises(ValueError): run_preview(doc)
