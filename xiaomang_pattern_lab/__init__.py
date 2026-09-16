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

__all__ = [
    "PatternLabSession", "ViewMode",
    "PlacementSlot", "ImportedElementSlotProvider", "GridSlotProvider",
    "ShapePrototypeRegistry", "ReplacementMap", "AssignmentSettings",
    "RandomSettings", "AssignmentEngine", "PlacementAssignmentState",
    "SharedModifierStack",
]
