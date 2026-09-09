"""可选模型显示边界。

制造业务不依赖此接口。当前默认实现为 NullPreviewProvider；未来接入第三方
Viewer 时只能在此处适配最终制造模型的显示，不能接管生成、清理或 STL 流程。
"""
from __future__ import annotations

from typing import Any, Protocol


class PreviewProvider(Protocol):
    def load_model(self, model: Any) -> None: ...
    def open_model(self) -> None: ...
    def update_model(self, model: Any) -> None: ...
    def fit_view(self) -> None: ...
    def get_bounds(self) -> tuple[float, float, float, float, float, float] | None: ...
    def capture_preview(self) -> bytes | None: ...
    def close(self) -> None: ...


class NullPreviewProvider:
    """当前产品的无界面默认实现。所有调用均为安全无操作。"""
    def load_model(self, model: Any) -> None:
        return None

    def open_model(self) -> None:
        return None

    def update_model(self, model: Any) -> None:
        return None

    def fit_view(self) -> None:
        return None

    def get_bounds(self) -> tuple[float, float, float, float, float, float] | None:
        return None

    def capture_preview(self) -> bytes | None:
        return None

    def close(self) -> None:
        return None
