"""Server-owned asset lookup. Client-provided local paths are never accepted."""
from __future__ import annotations

from typing import Mapping, Protocol


class AssetResolver(Protocol):
    def resolve(self, asset_id: str) -> str | None: ...


class NullAssetResolver:
    def resolve(self, asset_id: str) -> str | None:
        return None


class InMemoryAssetResolver:
    """Test/development registrations only; not an upload or cloud store."""

    def __init__(self, sources: Mapping[str, str] | None = None) -> None:
        self.sources = dict(sources or {})

    def resolve(self, asset_id: str) -> str | None:
        return self.sources.get(asset_id)
