"""SQLite database layer. Designed for easy swap to PostgreSQL later.

To switch to PostgreSQL:
1. Replace sqlite3 with psycopg2 or asyncpg
2. Update _get_connection() to return a Postgres connection
3. Replace ? placeholders with %s
4. The rest of the API stays the same.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator

from .models import FormResponse, FormSchema, SchemaStatus

_DB_PATH: Path | None = None


def init_db(db_path: str | Path | None = None):
    """Initialize the database, creating tables if needed."""
    global _DB_PATH
    if db_path is None:
        db_path = Path(__file__).parent.parent / "data" / "crew.db"
    _DB_PATH = Path(db_path)
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with _get_connection() as conn:
        conn.executescript(_SCHEMA_SQL)


def get_db_path() -> Path:
    if _DB_PATH is None:
        init_db()
    return _DB_PATH


@contextmanager
def _get_connection() -> Generator[sqlite3.Connection, None, None]:
    path = get_db_path()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS form_schemas (
    id TEXT NOT NULL,
    version INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    source_filename TEXT,
    schema_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (id, version)
);

CREATE TABLE IF NOT EXISTS form_responses (
    id TEXT PRIMARY KEY,
    schema_id TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    customer_name TEXT,
    answers_json TEXT NOT NULL,
    submitted_at TEXT,
    signed_off INTEGER NOT NULL DEFAULT 0,
    signed_off_at TEXT,
    FOREIGN KEY (schema_id, schema_version) REFERENCES form_schemas(id, version)
);

CREATE INDEX IF NOT EXISTS idx_schemas_status ON form_schemas(status);
CREATE INDEX IF NOT EXISTS idx_schemas_id_status ON form_schemas(id, status);
CREATE INDEX IF NOT EXISTS idx_responses_schema ON form_responses(schema_id);
"""


# --- Schema operations ---

def save_schema(schema: FormSchema) -> None:
    with _get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO form_schemas
               (id, version, name, description, status, source_filename, schema_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                schema.id,
                schema.version,
                schema.name,
                schema.description,
                schema.status.value,
                schema.source_filename,
                schema.model_dump_json(),
                schema.created_at.isoformat(),
            ),
        )


def load_schema(schema_id: str, version: int | None = None) -> FormSchema | None:
    with _get_connection() as conn:
        if version is not None:
            row = conn.execute(
                "SELECT schema_json FROM form_schemas WHERE id = ? AND version = ?",
                (schema_id, version),
            ).fetchone()
        else:
            # Load the latest version (highest version number)
            row = conn.execute(
                "SELECT schema_json FROM form_schemas WHERE id = ? ORDER BY version DESC LIMIT 1",
                (schema_id,),
            ).fetchone()
        if row is None:
            return None
        return FormSchema.model_validate_json(row["schema_json"])


def load_live_schema(schema_id: str) -> FormSchema | None:
    """Load the live (active) version of a schema."""
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT schema_json FROM form_schemas WHERE id = ? AND status = 'live' ORDER BY version DESC LIMIT 1",
            (schema_id,),
        ).fetchone()
        if row is None:
            return None
        return FormSchema.model_validate_json(row["schema_json"])


def list_schemas(status: SchemaStatus | None = None, latest_only: bool = True) -> list[FormSchema]:
    """List schemas. By default returns only the latest version of each schema."""
    with _get_connection() as conn:
        if latest_only:
            if status:
                rows = conn.execute(
                    """SELECT schema_json FROM form_schemas s1
                       WHERE status = ? AND version = (
                           SELECT MAX(version) FROM form_schemas s2
                           WHERE s2.id = s1.id AND s2.status = ?
                       )
                       ORDER BY created_at DESC""",
                    (status.value, status.value),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT schema_json FROM form_schemas s1
                       WHERE version = (
                           SELECT MAX(version) FROM form_schemas s2 WHERE s2.id = s1.id
                       )
                       ORDER BY created_at DESC""",
                ).fetchall()
        else:
            if status:
                rows = conn.execute(
                    "SELECT schema_json FROM form_schemas WHERE status = ? ORDER BY id, version DESC",
                    (status.value,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT schema_json FROM form_schemas ORDER BY id, version DESC",
                ).fetchall()
        return [FormSchema.model_validate_json(r["schema_json"]) for r in rows]


def list_schema_versions(schema_id: str) -> list[FormSchema]:
    """List all versions of a specific schema."""
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT schema_json FROM form_schemas WHERE id = ? ORDER BY version DESC",
            (schema_id,),
        ).fetchall()
        return [FormSchema.model_validate_json(r["schema_json"]) for r in rows]


def promote_schema(schema_id: str, version: int) -> None:
    """Set a schema version to live, archiving any previously live version of the same schema."""
    with _get_connection() as conn:
        # Find and archive any currently live versions, updating their schema_json too
        live_rows = conn.execute(
            "SELECT version, schema_json FROM form_schemas WHERE id = ? AND status = 'live'",
            (schema_id,),
        ).fetchall()
        for row in live_rows:
            schema = FormSchema.model_validate_json(row["schema_json"])
            schema.status = SchemaStatus.ARCHIVED
            conn.execute(
                "UPDATE form_schemas SET status = 'archived', schema_json = ? WHERE id = ? AND version = ?",
                (schema.model_dump_json(), schema_id, row["version"]),
            )
        # Promote the target version
        row = conn.execute(
            "SELECT schema_json FROM form_schemas WHERE id = ? AND version = ?",
            (schema_id, version),
        ).fetchone()
        if row:
            schema = FormSchema.model_validate_json(row["schema_json"])
            schema.status = SchemaStatus.LIVE
            conn.execute(
                "UPDATE form_schemas SET status = 'live', schema_json = ? WHERE id = ? AND version = ?",
                (schema.model_dump_json(), schema_id, version),
            )


def create_new_version(schema_id: str, source_version: int) -> FormSchema:
    """Clone an existing schema version into a new draft with an incremented version number."""
    with _get_connection() as conn:
        # Find the highest existing version for this schema
        row = conn.execute(
            "SELECT MAX(version) as max_ver FROM form_schemas WHERE id = ?",
            (schema_id,),
        ).fetchone()
        next_version = (row["max_ver"] or 0) + 1

        # Load the source version
        source_row = conn.execute(
            "SELECT schema_json FROM form_schemas WHERE id = ? AND version = ?",
            (schema_id, source_version),
        ).fetchone()
        if source_row is None:
            raise ValueError(f"Schema {schema_id} v{source_version} not found")

        schema = FormSchema.model_validate_json(source_row["schema_json"])
        schema.version = next_version
        schema.status = SchemaStatus.DRAFT
        schema.created_at = datetime.now()

        conn.execute(
            """INSERT INTO form_schemas
               (id, version, name, description, status, source_filename, schema_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                schema.id,
                schema.version,
                schema.name,
                schema.description,
                schema.status.value,
                schema.source_filename,
                schema.model_dump_json(),
                schema.created_at.isoformat(),
            ),
        )
        return schema


def fork_schema(schema_id: str, source_version: int, new_name: str) -> FormSchema:
    """Fork a schema into a new independent form (new ID, version 1) with a new name.

    Preserves the source_filename so the fork stays tied to the original document.
    """
    import uuid

    with _get_connection() as conn:
        source_row = conn.execute(
            "SELECT schema_json FROM form_schemas WHERE id = ? AND version = ?",
            (schema_id, source_version),
        ).fetchone()
        if source_row is None:
            raise ValueError(f"Schema {schema_id} v{source_version} not found")

        schema = FormSchema.model_validate_json(source_row["schema_json"])
        schema.id = str(uuid.uuid4())[:8]
        schema.name = new_name
        schema.version = 1
        schema.status = SchemaStatus.DRAFT
        schema.created_at = datetime.now()

        conn.execute(
            """INSERT INTO form_schemas
               (id, version, name, description, status, source_filename, schema_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                schema.id,
                schema.version,
                schema.name,
                schema.description,
                schema.status.value,
                schema.source_filename,
                schema.model_dump_json(),
                schema.created_at.isoformat(),
            ),
        )
        return schema


def archive_schema(schema_id: str, version: int) -> None:
    """Archive a schema version."""
    with _get_connection() as conn:
        conn.execute(
            "UPDATE form_schemas SET status = 'archived' WHERE id = ? AND version = ?",
            (schema_id, version),
        )
        row = conn.execute(
            "SELECT schema_json FROM form_schemas WHERE id = ? AND version = ?",
            (schema_id, version),
        ).fetchone()
        if row:
            schema = FormSchema.model_validate_json(row["schema_json"])
            schema.status = SchemaStatus.ARCHIVED
            conn.execute(
                "UPDATE form_schemas SET schema_json = ? WHERE id = ? AND version = ?",
                (schema.model_dump_json(), schema_id, version),
            )


# --- Response operations ---

def save_response(response: FormResponse) -> None:
    with _get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO form_responses
               (id, schema_id, schema_version, customer_name, answers_json, submitted_at, signed_off, signed_off_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                response.id,
                response.schema_id,
                response.schema_version,
                response.customer_name,
                json.dumps(response.answers),
                response.submitted_at.isoformat() if response.submitted_at else None,
                1 if response.signed_off else 0,
                response.signed_off_at.isoformat() if response.signed_off_at else None,
            ),
        )


def load_response(response_id: str) -> FormResponse | None:
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM form_responses WHERE id = ?",
            (response_id,),
        ).fetchone()
        if row is None:
            return None
        return _row_to_response(row)


def list_responses(schema_id: str | None = None) -> list[FormResponse]:
    with _get_connection() as conn:
        if schema_id:
            rows = conn.execute(
                "SELECT * FROM form_responses WHERE schema_id = ? ORDER BY submitted_at DESC",
                (schema_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM form_responses ORDER BY submitted_at DESC",
            ).fetchall()
        return [_row_to_response(r) for r in rows]


def _row_to_response(row: sqlite3.Row) -> FormResponse:
    return FormResponse(
        id=row["id"],
        schema_id=row["schema_id"],
        schema_version=row["schema_version"],
        customer_name=row["customer_name"],
        answers=json.loads(row["answers_json"]),
        submitted_at=datetime.fromisoformat(row["submitted_at"]) if row["submitted_at"] else None,
        signed_off=bool(row["signed_off"]),
        signed_off_at=datetime.fromisoformat(row["signed_off_at"]) if row["signed_off_at"] else None,
    )
