"""Spatial derivatives are a consumer of scalar fields, not a vector Field API."""
from dataclasses import replace
import math
from .shared_fields import CompositeField, ImageField, DistanceField


def sampling_delta(registry, identifier, context, seen=frozenset()):
    field = registry.get(identifier)
    if identifier in seen:
        raise ValueError("梯度场循环引用。")
    if isinstance(field, ImageField):
        image = field._prepared_pixels or field._pixels()
        if image is not None:
            x0, y0, x1, y1 = field.sample_bounds or context.bounds
            return (max((x1-x0)/max(image[0]-1, 1), 1e-6),
                    max((y1-y0)/max(image[1]-1, 1), 1e-6))
    if isinstance(field, CompositeField):
        deltas = [sampling_delta(registry, child, context, seen | {identifier})
                  for child in (field.input_a_field_id, field.input_b_field_id)
                  if child in {item['id'] for item in registry.to_list()}]
        if deltas:
            return min(x for x, _ in deltas), min(y for _, y in deltas)
    return .01, .01  # world mm, independent of viewport and instance count


def gradient_angles(registry, identifier, elements, context):
    dx, dy = sampling_delta(registry, identifier, context)
    field = registry.get(identifier)
    prepared = None
    if isinstance(field, DistanceField):
        from .orientation_raster import prepare_orientation, stabilized_angle
        prepared = prepare_orientation(field, field.sample_bounds or context.bounds)
    result = []
    for item in elements:
        gx = (registry.evaluate(identifier, replace(item, x=item.x+dx), context)
              - registry.evaluate(identifier, replace(item, x=item.x-dx), context))/(2*dx)
        gy = (registry.evaluate(identifier, replace(item, y=item.y+dy), context)
              - registry.evaluate(identifier, replace(item, y=item.y-dy), context))/(2*dy)
        magnitude = math.hypot(gx, gy)
        angle = math.degrees(math.atan2(gy, gx))
        result.append(stabilized_angle(prepared, field.sample_bounds or context.bounds,
            item.x, item.y, angle, magnitude) if prepared is not None else
            None if magnitude <= 1e-9 else angle)
    return tuple(result)
