"""Server-owned asset lookup. Client-provided local paths are never accepted."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from threading import Lock
from time import monotonic
from typing import Mapping, Protocol
from uuid import uuid4

from PIL import Image, UnidentifiedImageError


MAX_ASSET_BYTES = 8 * 1024 * 1024
ASSET_TTL_SECONDS = 30 * 60
ASSET_CAPACITY = 32
MEDIA_SUFFIX = {"image/png": ".png", "image/jpeg": ".jpg", "image/svg+xml": ".svg"}


@dataclass(frozen=True)
class StoredAsset:
    asset_id: str
    media_type: str
    filename: str
    path: Path
    created_at: float


class TemporaryAssetStore:
    """Bounded, per-server Alpha uploads; no client path ever becomes a filename."""

    def __init__(self, *, ttl_seconds: int = ASSET_TTL_SECONDS, capacity: int = ASSET_CAPACITY) -> None:
        self._directory = TemporaryDirectory(prefix="xiaomang-assets-")
        self._root = Path(self._directory.name)
        self._items: dict[str, StoredAsset] = {}
        self._lock = Lock()
        self.ttl_seconds = ttl_seconds
        self.capacity = capacity

    def _purge(self) -> None:
        now = monotonic()
        for identifier, item in list(self._items.items()):
            if now - item.created_at >= self.ttl_seconds:
                item.path.unlink(missing_ok=True)
                shutil.rmtree(self._root / identifier, ignore_errors=True)
                del self._items[identifier]

    def put(self, data: bytes, media_type: str, filename: str) -> StoredAsset:
        if media_type not in MEDIA_SUFFIX:
            raise ValueError("不支持的图片格式。")
        if not data or len(data) > MAX_ASSET_BYTES:
            raise OverflowError("图片为空或超过 8 MiB 限制。")
        if media_type == "image/png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("PNG 文件内容无效。")
        if media_type == "image/jpeg" and not data.startswith(b"\xff\xd8\xff"):
            raise ValueError("JPEG 文件内容无效。")
        if media_type == "image/svg+xml":
            lower = data.lower()
            if b"<!doctype" in lower or b"<!entity" in lower or b"<script" in lower:
                raise ValueError("SVG 含有不受支持的声明或脚本。")
            try:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(data)
                if root.tag.rsplit("}", 1)[-1] != "svg":
                    raise ValueError("SVG 根节点无效。")
            except ET.ParseError as error:
                raise ValueError("SVG 文件内容无效。") from error
        else:
            try:
                from io import BytesIO
                with Image.open(BytesIO(data)) as image:
                    if image.width * image.height > 20_000_000:
                        raise ValueError("图片像素数量过大。")
                    image.verify()
            except (UnidentifiedImageError, OSError) as error:
                raise ValueError("图片文件内容无效。") from error
        with self._lock:
            self._purge()
            if len(self._items) >= self.capacity:
                raise OverflowError("临时图片数量已达上限，请稍后再试。")
            identifier = uuid4().hex
            path = self._root / (identifier + MEDIA_SUFFIX[media_type])
            path.write_bytes(data)
            # The upload header may contain separators from either client OS.
            # Never echo a Windows absolute path from a Linux staging server.
            display_name = filename.replace("\\", "/").rsplit("/", 1)[-1][:120]
            item = StoredAsset(identifier, media_type, display_name, path, monotonic())
            self._items[identifier] = item
            return item

    def get(self, asset_id: str) -> StoredAsset | None:
        with self._lock:
            self._purge()
            return self._items.get(asset_id)

    def resolve(self, asset_id: str) -> str | None:
        item = self.get(asset_id)
        return str(item.path) if item else None


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
