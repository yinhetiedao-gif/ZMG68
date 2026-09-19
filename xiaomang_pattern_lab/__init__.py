"""小芒图案实验室：可删除 UI Harness 之外的技术验证层。"""

__version__ = "0.1.0-dev"

from .session import PatternLabSession, ViewMode
from .placement_assignment import (
    AssignmentEngine,
    AssignmentSettings,
    GridSlotProvider,
    ImportedElementSlotProvider,
    PlacementAssignmentState,
    PlacementSlot,
    RandomSettings,
    ReplacementMap,
    ShapePrototypeRegistry,
)
from .shared_modifiers import SharedModifierStack
from .geometry_validation import GeometryValidationIssue, GeometryValidationReport, GeometryValidator
from .connectivity import ConnectivityAnalyzer, ConnectivityComponent, ConnectivityReport
from .manufacturing_geometry import (
    Manufacturing2DGeometry, ManufacturingConversionReport, ManufacturingConversionResult,
    ManufacturingGeometryAdapter, ManufacturingPolygon, ManufacturingSkip,
)

__all__ = [
    "PatternLabSession", "ViewMode",
    "PlacementSlot", "ImportedElementSlotProvider", "GridSlotProvider",
    "ShapePrototypeRegistry", "ReplacementMap", "AssignmentSettings",
    "RandomSettings", "AssignmentEngine", "PlacementAssignmentState",
    "SharedModifierStack",
    "GeometryValidationIssue", "GeometryValidationReport", "GeometryValidator",
    "ConnectivityAnalyzer", "ConnectivityComponent", "ConnectivityReport",
    "Manufacturing2DGeometry", "ManufacturingPolygon", "ManufacturingSkip",
    "ManufacturingConversionReport", "ManufacturingConversionResult", "ManufacturingGeometryAdapter",
]
