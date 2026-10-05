"""Opt-in F4-C nested timings (preparation is included in orientation total)."""
import importlib.util
import json
import math
import shutil
from pathlib import Path
from statistics import median
from time import perf_counter
from unittest.mock import patch

from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.shared_fields import DistanceField
import xiaomang_pattern_lab.fabric_preview as preview
import xiaomang_pattern_lab.distance_raster as distance
import xiaomang_pattern_lab.orientation_raster as orientation
import xiaomang_pattern_lab.field_gradient as gradient


def main():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('fixtures', root/'tests/test_image_fabric_f4a.py')
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    output = root/'work/f4c'
    output.mkdir(parents=True, exist_ok=True)
    image = output/'black-circle-v1.png'
    image.write_bytes(fixture.black_circle_bytes())
    # Reproducible production-browser sources; the failed S is copied verbatim.
    from PIL import Image, ImageDraw
    for kind in ('circle','ring'):
        raster = Image.new('L',(401,401),255)
        draw = ImageDraw.Draw(raster)
        draw.ellipse((401*.12,401*.12,401*.88,401*.88),fill=0)
        if kind == 'ring':
            draw.ellipse((401*.28,401*.28,401*.72,401*.72),fill=255)
        raster.save(output/f'{kind}-401.png')
    shutil.copyfile(root/'tests/fixtures/f4c-spine-401.png',output/'spine-401.png')
    raster = Image.new('L',(25,25),255)
    points = [(25*(.5+.23*math.sin(2*math.pi*(t/300-.5))),25*(.08+.84*t/300)) for t in range(301)]
    ImageDraw.Draw(raster).line(points,fill=0,width=round(25*.16),joint='curve')
    raster.save(output/'spine-25.png')
    report = []
    for count, columns, rows in ((400,20,20),(1000,20,50),(5000,50,100)):
        doc = fixture.image_document(image)
        doc.fields = [DistanceField('distance',str(image),sample_bounds=(0,0,100,100)).to_dict()]
        config = doc.metadata['fabric_config']
        config['placement'].update(spacing_x_mm=100/columns,spacing_y_mm=100/rows)
        config['field_modifiers'] = {
            'height': {'enabled':True,'field_id':'distance','min_height_mm':1,'max_height_mm':8},
            'scale': {'enabled':True,'field_id':'distance','min_scale':.5,'max_scale':2},
            'orientation': {'enabled':True,'field_id':'distance','min_angle_deg':-45,'max_angle_deg':45,
                            'direction_mode':'gradient','alignment':'tangent','angle_offset_deg':0}}
        dto = PatternDocumentDTO.from_document(doc,f'distance-{count}',12,asset_bindings={str(image):'raster'})
        runs = []
        for run in range(6):
            if run == 0:
                distance._CACHE.clear()
                orientation._CACHE.clear()
            measured = {'orientation_preparation_ms':0.,'orientation_total_ms':0.}
            def timer(key, function):
                def invoke(*args, **kwargs):
                    started = perf_counter()
                    result = function(*args, **kwargs)
                    measured[key] += (perf_counter()-started)*1000
                    return result
                return invoke
            with patch.object(orientation,'prepare_orientation',timer('orientation_preparation_ms',orientation.prepare_orientation)), \
                 patch.object(gradient,'gradient_angles',timer('orientation_total_ms',gradient.gradient_angles)):
                started = perf_counter()
                payload = preview.build_fabric_preview(doc,dto)
                measured['plan_total_ms'] = (perf_counter()-started)*1000
            assert payload['total_count'] == count
            measured['orientation_sampling_ms'] = measured['orientation_total_ms']-measured['orientation_preparation_ms']
            runs.append(measured)
        report.append({'count':count,'cold':runs[0],
            'warm_median_5':{key:round(median(r[key] for r in runs[1:]),3) for key in runs[0]}})
    (output/'python-performance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
