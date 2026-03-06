"""File storage abstraction. Local filesystem now, swappable to S3/Azure Blob later."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class FileStorageBackend(ABC):
    """Abstract interface for file storage. Implement this for S3, Azure Blob, etc."""

    @abstractmethod
    def save(self, key: str, content: bytes) -> str:
        """Save file content. Returns the storage key/path."""
        ...

    @abstractmethod
    def load(self, key: str) -> bytes | None:
        """Load file content by key. Returns None if not found."""
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        ...

    @abstractmethod
    def list_keys(self, prefix: str = "") -> list[str]:
        """List all keys matching the prefix."""
        ...


class LocalFileStorage(FileStorageBackend):
    """Store files on the local filesystem."""

    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.base_dir / key

    def save(self, key: str, content: bytes) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return str(path)

    def load(self, key: str) -> bytes | None:
        path = self._path(key)
        if not path.exists():
            return None
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def list_keys(self, prefix: str = "") -> list[str]:
        keys = []
        search_dir = self.base_dir / prefix if prefix else self.base_dir
        if not search_dir.exists():
            return keys
        for path in search_dir.rglob("*"):
            if path.is_file():
                keys.append(str(path.relative_to(self.base_dir)))
        return keys

    def full_path(self, key: str) -> str:
        """Get the absolute filesystem path. Local-only convenience method."""
        return str(self._path(key).resolve())
