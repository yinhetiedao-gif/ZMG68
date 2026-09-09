from __future__ import annotations

from .dot_primitive_recovery import DotRecoveryResult
from .models import Document2D, GeometryLayer, ReferenceLayer
from .svg_parser import ParsedSVG


class SceneGraphBuilder:
    """只把 Recovery 得到的真实对象放入 GeometryLayer。"""

    def build(self, source_path: str, svg: ParsedSVG, recovery: DotRecoveryResult) -> Document2D:
        geometry = GeometryLayer()
        for dot in recovery.dots:
            geometry.add_dot(dot)
        return Document2D(
            reference_layer=ReferenceLayer(source_path=source_path, width=svg.width, height=svg.height),
            geometry_layer=geometry,
        )
