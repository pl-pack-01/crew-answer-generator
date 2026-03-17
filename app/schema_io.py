"""Schema export and import for sharing form schemas between instances."""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from .models import FormSchema, SchemaStatus

# Current export format version — bump if the format changes
_EXPORT_VERSION = 1


def export_schema(schema: FormSchema) -> str:
    """Serialize a FormSchema to a portable JSON string.

    The export includes the full schema definition (sections, questions,
    conditions, screenshots) wrapped with metadata for safe import.
    """
    payload = {
        "export_version": _EXPORT_VERSION,
        "exported_at": datetime.now().isoformat(),
        "schema": json.loads(schema.model_dump_json()),
    }
    return json.dumps(payload, indent=2)


def import_schema(json_str: str) -> FormSchema:
    """Deserialize a JSON string into a new draft FormSchema.

    Always creates a fresh schema with a new ID and version 1 to avoid
    collisions with existing schemas in the database.
    """
    data = json.loads(json_str)

    # Support both wrapped (export_version + schema) and raw FormSchema JSON
    if "export_version" in data and "schema" in data:
        schema_data = data["schema"]
    elif "sections" in data and "name" in data:
        schema_data = data
    else:
        raise ValueError(
            "Invalid schema file. Expected an exported schema JSON "
            "with 'export_version' and 'schema' keys, or a raw FormSchema."
        )

    schema = FormSchema.model_validate(schema_data)

    # Assign new identity so it doesn't collide with the source
    schema.id = str(uuid.uuid4())[:8]
    schema.version = 1
    schema.status = SchemaStatus.DRAFT
    schema.created_at = datetime.now()

    return schema
