"""Read actual browser files, compare all transformed points and sampled heights.
No repair, replacement STL or optional graph engine is used.
"""
import json
import math
from dataclasses import asdict
from pathlib import Path
import numpy as np
import trimesh
from ppg.foundation import RectElement
from xiaomang_pattern_lab.shared_fields import RingField, FieldContext
from xiaomang_pattern_lab.stl_export import STLExporter
from xiaomang_pattern_lab.mesh_validation import MeshValidator


def main():
    out = Path('work/center-height-1b-20261010')
    results = []
    for name in ('center-default-original', 'center-offcenter-original', 'center-fin'):
        data = (out / (name+'.stl')).read_bytes()
        plan = json.loads((out / (name+'-preview.json')).read_text(encoding='utf-8'))
        document = json.loads((out / (name+'-document.json')).read_text(encoding='utf-8'))['document']
        final = json.loads((out / (name+'-final.json')).read_text(encoding='utf-8'))
        mesh = STLExporter.reload_bytes_as_mesh_result(data)
        report = MeshValidator().validate(mesh)
        assert report.is_valid and report.is_watertight and report.degenerate_face_count == 0
        assert report.component_count == final['connected_component_count'] == plan['count'] == 100
        assert mesh.mesh.volume > 0 and mesh.mesh.is_winding_consistent and mesh.mesh.bounds[0, 2] == 0
        np.testing.assert_allclose(mesh.mesh.bounds, final['bounds_mm'], atol=1e-5, rtol=0)
        triangles = mesh.mesh.vertices[mesh.mesh.faces]
        covered = np.zeros(len(triangles), dtype=int)
        each = []
        cfg = document['metadata']['fabric_config']
        height = cfg['field_modifiers']['height']
        raw = next(f for f in document['fields'] if f['id'] == height['field_id'])
        field = RingField(raw['id'], **raw['parameters'])
        context = FieldContext((0, 0, 0, 0))
        for item in plan['instances']:
            proto = plan['contour_prototypes'][item['id']] if plan['shape_source'] == 'original' else plan['prototype']
            angle = math.radians(item['rotation_deg'])
            sx = item['cell_width_mm']/item['base_width_mm']
            sy = item['cell_depth_mm']/item['base_depth_mm']
            sz = item['height_mm']/item['base_height_mm']
            matrix = np.array([[math.cos(angle)*sx, -math.sin(angle)*sy, 0],
                               [math.sin(angle)*sx, math.cos(angle)*sy, 0], [0, 0, sz]])
            expected = np.array(proto['vertices']) @ matrix.T + [item['x_mm'], item['y_mm'], item['z_mm']]
            lo, hi = expected.min(axis=0), expected.max(axis=0)
            selected = ((triangles >= lo-1e-5) & (triangles <= hi+1e-5)).all(axis=(1, 2))
            faces = triangles[selected]
            assert len(faces) == len(proto['faces'])
            covered += selected
            actual, inverse = np.unique(faces.reshape(-1, 3), axis=0, return_inverse=True)
            source = np.unique(expected, axis=0)
            assert len(actual) == len(source)
            assert np.linalg.norm(actual[:, None, :]-source[None, :, :], axis=2).min(axis=1).max() < 1e-5
            component = trimesh.Trimesh(vertices=actual, faces=inverse.reshape(-1, 3), process=False)
            assert component.is_watertight and component.is_winding_consistent and component.volume > 0
            value = field.evaluate(RectElement(item['id'], item['x_mm'], item['y_mm'], 1, 1), context)
            expected_height = height['min_height_mm']+(height['max_height_mm']-height['min_height_mm'])*value
            measured_height = np.ptp(actual[:, 2])
            assert abs(measured_height-expected_height) < 1e-5
            if item['source_id'] == 'hole' and plan['shape_source'] == 'original':
                assert component.euler_number == 0
            each.append({'source_id': item['source_id'], 'bottom_z': float(actual[:, 2].min()),
                'height_mm': float(measured_height), 'expected_height_mm': expected_height,
                'euler_number': component.euler_number, 'volume_mm3': component.volume, 'all_vertices_match': True})
        assert (covered == 1).all()
        results.append({'name': name, 'bytes': len(data), 'triangles': len(mesh.mesh.faces),
            'dimensions_mm': np.ptp(mesh.mesh.bounds, axis=0).tolist(), 'each_element': each,
            'validation': asdict(report)})
    (out/'stl-readback.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps([{'file': r['name'], 'bytes': r['bytes'], 'components': r['validation']['component_count'],
        'degenerate': r['validation']['degenerate_face_count'], 'dimensions_mm': r['dimensions_mm']} for r in results], indent=2))


if __name__ == '__main__':
    main()
