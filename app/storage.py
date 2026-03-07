"""Storage facade. Delegates to SQLite for data and LocalFileStorage for uploads.

This module maintains the same public API so existing code (admin, customer pages)
continues to work with minimal changes.
"""

from __future__ import annotations

from pathlib import Path

from .database import (
    archive_schema,
    create_new_version,
    delete_schema,
    fork_schema,
    init_db,
    list_responses,
    list_schema_versions,
    list_schemas,
    load_draft,
    load_live_schema,
    load_response,
    load_schema,
    promote_schema,
    save_response,
    save_schema,
)
from .file_storage import LocalFileStorage
from .models import FormResponse, FormSchema, ResponseStatus, SchemaStatus

DATA_DIR = Path(__file__).parent.parent / "data"

_file_storage: LocalFileStorage | None = None


def get_file_storage() -> LocalFileStorage:
    global _file_storage
    if _file_storage is None:
        _file_storage = LocalFileStorage(DATA_DIR / "uploads")
    return _file_storage


def setup(db_path: str | Path | None = None):
    """Initialize database and file storage. Call once at app startup."""
    init_db(db_path)
    get_file_storage()


def save_upload(filename: str, content: bytes) -> Path:
    """Save an uploaded file. Returns the full local path."""
    fs = get_file_storage()
    fs.save(filename, content)
    return Path(fs.full_path(filename))


# Re-export database functions for backward compatibility
__all__ = [
    "setup",
    "save_schema",
    "load_schema",
    "load_live_schema",
    "list_schemas",
    "list_schema_versions",
    "promote_schema",
    "archive_schema",
    "create_new_version",
    "delete_schema",
    "fork_schema",
    "save_response",
    "load_response",
    "load_draft",
    "list_responses",
    "ResponseStatus",
    "save_upload",
    "get_file_storage",
    "SchemaStatus",
]
