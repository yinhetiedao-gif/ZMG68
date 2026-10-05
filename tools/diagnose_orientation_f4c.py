"""Read actual production-browser payloads, preserving the original failed mask."""
import json
import math
from pathlib import Path

from ppg.foundation.models import Element
from xiaomang_pattern_lab.shared_fields import DistanceField, FieldRegistry, FieldContext
from xiaomang_pattern_lab.field_gradient import gradient_angles


def axis_delta(a, b):
    return abs((a-b+90)%180-90)


def pairs(instances):
    by = {(i['x_mm'],i['y_mm']):i for i in instances if i['enabled']}
    deltas = []
    for (x,y), item in by.items():
        for xy in ((x+1,y),(x,y+1)):
            other = by.get(xy)
            if other and min(item['height_mm'],other['height_mm']) > 3:
                deltas.append(axis_delta(item['rotation_deg'],other['rotation_deg']))
    return {'over_45_pairs':sum(d>45 for d in deltas),
            'over_75_pairs':sum(d>75 for d in deltas),'max_delta':max(deltas,default=0)}


def main():
    root = Path(__file__).resolve().parents[1]
    output = root/'work/f4c'
    read = lambda name: json.loads((output/f'{name}.json').read_text(encoding='utf-8'))
    report = {name:pairs(read(name)['payload']['instances']) for name in ('C-spine','C-spine-normal')}
    for name, offset in (('B-ring-tangent',90),('B-ring-normal',0)):
        instances = read(name)['payload']['instances']
        errors = [axis_delta(i['rotation_deg'],math.degrees(math.atan2(i['y_mm']-30,i['x_mm']-30))+offset)
                  for i in instances if i['enabled'] and i['height_mm']>3]
        report[name] = {'analytic_max_axis_error':max(errors),'mean_error':sum(errors)/len(errors)}
    data = read('D-pattern-combined')
    finals = {g['id']:g for g in data['final']['geometry']}
    instances = data['payload']['instances']
    parameters = next(f['parameters'] for f in data['request']['document']['document']['fields'] if f['type']=='distance').copy()
    parameters['image_path'] = str(output/'circle-401.png')
    registry = FieldRegistry([DistanceField('distance',**parameters)])
    points = [Element(str(k),'rect',i['x_mm'],i['y_mm'],1,1) for k,i in enumerate(instances)]
    angles = gradient_angles(registry,'distance',points,FieldContext.from_elements(points))
    report['pattern_points'] = {
        'position_error':max(max(abs(i['x_mm']-finals[i['final_geometry_id']]['x']),
                                abs(i['y_mm']-finals[i['final_geometry_id']]['y'])) for i in instances),
        'scale_x_values':sorted({round(i['scale_x'],6) for i in instances}),
        'rotation_composition_error':max(abs(i['rotation_deg']-finals[i['final_geometry_id']]['rotation']-
            (angle+90 if angle is not None else 0)) for i,angle in zip(instances,angles))}
    # Existing before-run data are optional; the tracked regression independently
    # recreates its 35-pair baseline from raw gradients when these files are absent.
    before = root/'work/f4-visual/C-spine.json'
    if before.exists():
        old = json.loads(before.read_text(encoding='utf-8'))['payload']['instances']
        new = read('C-spine')['payload']['instances']
        report['before'] = pairs(old)
        report['scalar_unchanged'] = all(all(a[k]==b[k] for k in
            ('x_mm','y_mm','height_mm','scale','enabled')) for a,b in zip(old,new)) and len(old)==len(new)
    (output/'diagnostics.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
