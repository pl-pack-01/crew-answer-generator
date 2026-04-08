"""Schema export and import for sharing form schemas between instances."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime

from .models import FormSchema, SchemaStatus

# Current export format version — bump if the format changes
_EXPORT_VERSION = 1


def export_schema(schema: FormSchema) -> str:
    """Serialize a FormSchema to a portable JSON string (schema only, no document)."""
    payload = {
        "export_version": _EXPORT_VERSION,
        "exported_at": datetime.now().isoformat(),
        "schema": json.loads(schema.model_dump_json()),
    }
    return json.dumps(payload, indent=2)


def export_schema_bundle(schema: FormSchema, doc_bytes: bytes | None = None) -> bytes:
    """Export a schema + optional source document as a ZIP bundle.

    The ZIP contains schema.json (the standard export envelope) and, if provided,
    the original source document (DOCX) so recipients can re-generate new versions
    from the same source file.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("schema.json", export_schema(schema))
        if doc_bytes is not None:
            doc_name = schema.source_filename or "document.docx"
            zf.writestr(doc_name, doc_bytes)
    return buf.getvalue()


def import_schema(json_str: str) -> FormSchema:
    """Deserialize a JSON string into a draft FormSchema.

    Preserves the original schema ID and version so that HTML forms
    distributed from the source environment remain linkable — customer
    responses embed schema_id + schema_version and must match the DB.
    """
    data = json.loads(json_str)

    # Support both wrapped (export_version + schema) and raw FormSchema JSON
    if "export_version" in data and "schema" in data:
        schema_data = data["schema"]
    elif "sections" in data and "name" in data:
        schema_data = data
    else:
        found = list(data.keys()) if isinstance(data, dict) else type(data).__name__
        raise ValueError(
            "Invalid schema file. Expected an exported schema JSON "
            "with 'export_version' and 'schema' keys, or a raw FormSchema "
            f"with 'name' and 'sections' keys. Got: {found}"
        )

    schema = FormSchema.model_validate(schema_data)

    # Preserve original ID and version — do NOT regenerate them.
    # HTML forms embed these values; responses only link if DB IDs match.
    schema.status = SchemaStatus.DRAFT
    schema.created_at = datetime.now()

    return schema


def import_schema_bundle(zip_bytes: bytes) -> tuple[FormSchema, bytes | None]:
    """Import a schema (and optional source document) from a ZIP bundle.

    Returns ``(schema, doc_bytes)`` where ``doc_bytes`` is ``None`` when
    no document was included in the bundle.
    """
    buf = io.BytesIO(zip_bytes)
    with zipfile.ZipFile(buf, "r") as zf:
        names = zf.namelist()
        if "schema.json" not in names:
            raise ValueError("Invalid bundle: schema.json not found inside ZIP.")
        schema_json = zf.read("schema.json").decode("utf-8")
        schema = import_schema(schema_json)
        doc_names = [n for n in names if n != "schema.json"]
        doc_bytes = zf.read(doc_names[0]) if doc_names else None
    return schema, doc_bytes
