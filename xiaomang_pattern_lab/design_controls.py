"""Small, opt-in source transform adapter for the native Web design panel.

Runs before the existing field stack, always from its stable source. It does
not replace a layout, a field, or Fabric's final geometry inheritance.
"""
from copy import deepcopy
import math
import re
from dataclasses import asdict
from ppg.foundation.models import CircleElement, EllipseElement
from .placement_assignment import deterministic_unit

KEY = "web_design_controls"
DEFAULTS = dict(size_percent=100., aspect=1., rotation=0., size_random=0.,
                position_jitter=0., rotation_random=0., seed=1, stagger=False)


def apply_design_controls(document, elements):
    raw = document.metadata.get(KEY)
    if raw is None:
        return list(elements)
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise ValueError("图案控制配置版本无效。")
    values = {**DEFAULTS, **raw}
    from .parameter_definitions import parameter_definitions, validate_parameter
    for group in ("shape", "random", "stagger"):
        for definition in parameter_definitions()["definitions"]["design"][group]["parameters"]:
            validate_parameter(definition, values[definition["id"]])
    model = document.metadata.get("xiaomang_pattern_lab.parametric", {})
    grid = model.get("grid") or model.get("model") or {}
    is_grid = model.get("mode") == "grid"
    vector = grid.get("basis_u_vector")
    if not vector:
        angle = math.radians(grid.get("rotation", 0))
        vector = [grid.get("spacing_x", 1) * math.cos(angle), grid.get("spacing_x", 1) * math.sin(angle)]
    result = deepcopy(list(elements))
    for index, element in enumerate(result):
        identity = element.id
        size = values["size_percent"] / 100 * (1 + (2 * deterministic_unit(values["seed"], identity, "size") - 1) * values["size_random"])
        aspect = math.sqrt(values["aspect"])
        if isinstance(element, CircleElement) and values["aspect"] != 1:
            fields = asdict(element)
            fields.pop("type", None)
            element = result[index] = EllipseElement(**fields)
        element.width *= size * aspect
        element.height *= size / aspect
        if hasattr(element, "rx"):
            element.rx *= size * aspect
            element.ry *= size / aspect
        element.rotation += values["rotation"] + (2 * deterministic_unit(values["seed"], identity, "rotation") - 1) * values["rotation_random"]
        element.x += (2 * deterministic_unit(values["seed"], identity, "offset_x") - 1) * values["position_jitter"]
        element.y += (2 * deterministic_unit(values["seed"], identity, "offset_y") - 1) * values["position_jitter"]
        match = re.fullmatch(r"grid:r(\d+):c(\d+)", identity)
        if values["stagger"] and is_grid and match and int(match[1]) % 2:
            element.x += vector[0] / 2
            element.y += vector[1] / 2
    return result
