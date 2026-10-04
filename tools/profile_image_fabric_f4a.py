"""Opt-in real ImageField benchmark, with browser-loader fixture artifacts.

Run python -m tools.profile_image_fabric_f4a. Instrumentation is outside the
product pipeline; all sampled values come from the real Shared Field engine.
Sampling is a subset of field/plan time, not an additional additive phase.
"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from statistics import median
from time import perf_counter
from unittest.mock import patch

from xiaomang_pattern_lab.fabric_preview import build_fabric_preview
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.shared_fields import ImageField
import xiaomang_pattern_lab.fabric_preview as preview_module


def main():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('image_fixture', root / 'tests/test_image_fabric_f4a.py')
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    output = root / 'work/f4a'
    output.mkdir(parents=True, exist_ok=True)
    image = output / 'black-circle-v1.png'
    image.write_bytes(fixture.black_circle_bytes())
    results = []
    for count, columns, rows in ((400, 20, 20), (1000, 20, 50), (5000, 50, 100)):
        document = fixture.image_document(image)
        fabric = document.metadata['fabric_config']
        fabric['placement'].update(spacing_x_mm=100/columns, spacing_y_mm=100/rows)
        fabric['field_modifiers'] = {
            'height': {'enabled': True, 'field_id': 'image', 'min_height_mm': 1, 'max_height_mm': 8},
            'scale': {'enabled': True, 'field_id': 'image', 'min_scale': .5, 'max_scale': 2},
            'density': {'enabled': True, 'field_id': 'image', 'threshold': 0}}
        dto = PatternDocumentDTO.from_document(document, f'perf-{count}', 12,
            asset_bindings={str(image): 'raster'})
        build_fabric_preview(document, dto)  # Warm shared prototype/image cache.
        samples = []
        for _ in range(5):
            measured = {'image_sampling_ms': 0., 'sample_calls': 0, 'field_application_ms': 0.}
            original_sample = ImageField.evaluate
            original_apply = preview_module.apply_fabric_field_modifiers
            def sample(self, *args):
                started = perf_counter()
                value = original_sample(self, *args)
                measured['image_sampling_ms'] += (perf_counter()-started)*1000
                measured['sample_calls'] += 1
                return value
            def apply(*args):
                started = perf_counter()
                value = original_apply(*args)
                measured['field_application_ms'] += (perf_counter()-started)*1000
                return value
            with patch.object(ImageField, 'evaluate', sample), patch.object(preview_module, 'apply_fabric_field_modifiers', apply):
                started = perf_counter()
                payload = build_fabric_preview(document, dto)
                measured['total_python_ms'] = (perf_counter()-started)*1000
            assert payload['total_count'] == count and measured['sample_calls'] == count
            measured.update(payload['timings_ms'])
            samples.append(measured)
        results.append({'instances': count, 'median_5_runs': {
            key: round(median(item[key] for item in samples), 3) for key in samples[0]}})
        browser_document = deepcopy(document.to_dict())
        browser_document['fields'][0]['parameters']['image_path'] = ''
        (output / f'preview-{count}.pattern.json').write_text(
            json.dumps(browser_document, ensure_ascii=False), encoding='utf-8')
    (output / 'python-performance.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
