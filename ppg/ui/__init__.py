"""小芒造物可复用桌面 UI 组件。

界面布局、样式和交互组件在此处集中维护；业务算法仍保留在 ppg 的
geometry / generators / final_geometry 等模块中。
"""

from .components import IconButton, ParameterControl, ToolButton
from .navigation import NavigationRail
from .workspace2d import CanvasLayers, GeneratorShelf

__all__ = ["CanvasLayers", "GeneratorShelf", "IconButton", "NavigationRail", "ParameterControl", "ToolButton"]
