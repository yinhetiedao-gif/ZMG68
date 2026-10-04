"""Spatial derivatives are a consumer of scalar fields, not a vector Field API."""
from dataclasses import replace
import math
from .shared_fields import CompositeField, ImageField


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
    result = []
    for item in elements:
        gx = (registry.evaluate(identifier, replace(item, x=item.x+dx), context)
              - registry.evaluate(identifier, replace(item, x=item.x-dx), context))/(2*dx)
        gy = (registry.evaluate(identifier, replace(item, y=item.y+dy), context)
              - registry.evaluate(identifier, replace(item, y=item.y-dy), context))/(2*dy)
        result.append(None if math.hypot(gx, gy) <= 1e-9 else math.degrees(math.atan2(gy, gx)))
    return tuple(result)
