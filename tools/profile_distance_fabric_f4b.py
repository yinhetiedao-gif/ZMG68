"""Opt-in nested-stage profiler and reproducible browser fixtures; not Engine code."""
import importlib.util
import json
from pathlib import Path
from statistics import median
from time import perf_counter
from unittest.mock import patch
from copy import deepcopy
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.shared_fields import DistanceField, FieldRegistry
import xiaomang_pattern_lab.fabric_preview as preview
import xiaomang_pattern_lab.distance_raster as raster
import xiaomang_pattern_lab.field_gradient as gradient


def main():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('fixtures', root/'tests/test_image_fabric_f4a.py')
    fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
    output = root/'work/f4b'; output.mkdir(parents=True, exist_ok=True)
    image = output/'black-circle-v1.png'; image.write_bytes(fixture.black_circle_bytes())
    from PIL import Image, ImageDraw
    from io import BytesIO
    ring = Image.new('L', (101, 101), 255); draw = ImageDraw.Draw(ring)
    draw.ellipse((10, 10, 90, 90), fill=0); draw.ellipse((30, 30, 70, 70), fill=255)
    data = BytesIO(); ring.save(data, format='PNG'); (output/'ring-v1.png').write_bytes(data.getvalue())
    results = []
    for count, columns, rows in ((400, 20, 20), (1000, 20, 50), (5000, 50, 100)):
        document = fixture.image_document(image)
        document.fields = [DistanceField('distance', str(image), sample_bounds=(0, 0, 100, 100)).to_dict()]
        fabric = document.metadata['fabric_config']
        fabric['placement'].update(spacing_x_mm=100/columns, spacing_y_mm=100/rows)
        fabric['field_modifiers'] = {
            'height': {'enabled': True, 'field_id': 'distance', 'min_height_mm': 1, 'max_height_mm': 8},
            'scale': {'enabled': True, 'field_id': 'distance', 'min_scale': .5, 'max_scale': 2},
            'orientation': {'enabled': True, 'field_id': 'distance', 'min_angle_deg': -45, 'max_angle_deg': 45,
                'direction_mode': 'gradient', 'alignment': 'tangent', 'angle_offset_deg': 0}}
        dto = PatternDocumentDTO.from_document(document, f'distance-{count}', 12, asset_bindings={str(image): 'raster'})
        samples = []
        for run in range(6):
            if run == 0: raster._CACHE.clear()
            measured = dict(mask_creation_ms=0., distance_transform_ms=0., gradient_preparation_ms=0.,
                field_sampling_ms=0., gradient_orientation_ms=0., field_application_ms=0.)
            def timer(key, function):
                def invoke(*args, **kwargs):
                    started = perf_counter()
                    result = function(*args, **kwargs)
                    measured[key] += (perf_counter()-started)*1000
                    return result
                return invoke
            with patch.object(raster, '_foreground_mask', timer('mask_creation_ms', raster._foreground_mask)), \
                 patch.object(raster, '_boundary_distance', timer('distance_transform_ms', raster._boundary_distance)), \
                 patch.object(gradient, 'sampling_delta', timer('gradient_preparation_ms', gradient.sampling_delta)), \
                 patch.object(gradient, 'gradient_angles', timer('gradient_orientation_ms', gradient.gradient_angles)), \
                 patch.object(FieldRegistry, 'evaluate', timer('field_sampling_ms', FieldRegistry.evaluate)), \
                 patch.object(preview, 'apply_fabric_field_modifiers', timer('field_application_ms', preview.apply_fabric_field_modifiers)):
                started = perf_counter(); payload = preview.build_fabric_preview(document, dto)
                measured['total_python_ms'] = (perf_counter()-started)*1000
            measured.update(payload['timings_ms']); samples.append(measured)
            assert payload['total_count'] == count
        results.append({'instances': count, 'cold': samples[0], 'warm_median_5': {
            key: round(median(s[key] for s in samples[1:]), 3) for key in samples[0]}})
        browser = deepcopy(document.to_dict()); browser['fields'][0]['parameters']['image_path'] = ''
        (output/f'preview-{count}.pattern.json').write_text(json.dumps(browser), encoding='utf-8')
    (output/'python-performance.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results, indent=2))


if __name__ == '__main__': main()
