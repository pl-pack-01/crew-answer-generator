"""JSON file-based storage for form schemas and responses."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .models import FormResponse, FormSchema

DATA_DIR = Path(__file__).parent.parent / "data"
SCHEMAS_DIR = DATA_DIR / "schemas"
RESPONSES_DIR = DATA_DIR / "responses"
UPLOADS_DIR = DATA_DIR / "uploads"


def _ensure_dirs():
    for d in [SCHEMAS_DIR, RESPONSES_DIR, UPLOADS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def save_schema(schema: FormSchema) -> Path:
    _ensure_dirs()
    path = SCHEMAS_DIR / f"{schema.id}_v{schema.version}.json"
    path.write_text(schema.model_dump_json(indent=2), encoding="utf-8")
    # Also write a "latest" pointer
    latest = SCHEMAS_DIR / f"{schema.id}_latest.json"
    latest.write_text(schema.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_schema(schema_id: str, version: int | None = None) -> FormSchema | None:
    _ensure_dirs()
    if version:
        path = SCHEMAS_DIR / f"{schema_id}_v{version}.json"
    else:
        path = SCHEMAS_DIR / f"{schema_id}_latest.json"
    if not path.exists():
        return None
    return FormSchema.model_validate_json(path.read_text(encoding="utf-8"))


def list_schemas() -> list[FormSchema]:
    _ensure_dirs()
    schemas = []
    for path in SCHEMAS_DIR.glob("*_latest.json"):
        schemas.append(FormSchema.model_validate_json(path.read_text(encoding="utf-8")))
    schemas.sort(key=lambda s: s.created_at, reverse=True)
    return schemas


def save_response(response: FormResponse) -> Path:
    _ensure_dirs()
    path = RESPONSES_DIR / f"{response.id}.json"
    path.write_text(response.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_response(response_id: str) -> FormResponse | None:
    _ensure_dirs()
    path = RESPONSES_DIR / f"{response_id}.json"
    if not path.exists():
        return None
    return FormResponse.model_validate_json(path.read_text(encoding="utf-8"))


def list_responses(schema_id: str | None = None) -> list[FormResponse]:
    _ensure_dirs()
    responses = []
    for path in RESPONSES_DIR.glob("*.json"):
        r = FormResponse.model_validate_json(path.read_text(encoding="utf-8"))
        if schema_id is None or r.schema_id == schema_id:
            responses.append(r)
    responses.sort(key=lambda r: r.submitted_at or datetime.min, reverse=True)
    return responses


def save_upload(filename: str, content: bytes) -> Path:
    _ensure_dirs()
    path = UPLOADS_DIR / filename
    path.write_bytes(content)
    return path
