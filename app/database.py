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

from .models import FormResponse, FormSchema, ResponseStatus, SchemaStatus

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
        # Migrate existing tables if needed
        _migrate(conn)


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
    status TEXT NOT NULL DEFAULT 'draft',
    draft_code TEXT,
    customer_name TEXT,
    answers_json TEXT NOT NULL,
    submitted_at TEXT,
    signed_off INTEGER NOT NULL DEFAULT 0,
    signed_off_at TEXT,
    opened_at TEXT,
    first_saved_at TEXT,
    completed_at TEXT,
    output_generated INTEGER NOT NULL DEFAULT 0,
    output_generated_at TEXT,
    FOREIGN KEY (schema_id, schema_version) REFERENCES form_schemas(id, version)
);

CREATE INDEX IF NOT EXISTS idx_schemas_status ON form_schemas(status);
CREATE INDEX IF NOT EXISTS idx_schemas_id_status ON form_schemas(id, status);
CREATE INDEX IF NOT EXISTS idx_responses_schema ON form_responses(schema_id);
"""

def _migrate(conn: sqlite3.Connection):
    """Add new columns to existing tables. Safe to run repeatedly."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(form_responses)").fetchall()}
    if "status" not in cols:
        conn.execute("ALTER TABLE form_responses ADD COLUMN status TEXT NOT NULL DEFAULT 'submitted'")
    if "draft_code" not in cols:
        conn.execute("ALTER TABLE form_responses ADD COLUMN draft_code TEXT")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_responses_draft_code ON form_responses(draft_code)")
    if "output_generated" not in cols:
        conn.execute("ALTER TABLE form_responses ADD COLUMN output_generated INTEGER NOT NULL DEFAULT 0")
    if "output_generated_at" not in cols:
        conn.execute("ALTER TABLE form_responses ADD COLUMN output_generated_at TEXT")
    if "started_at" in cols:
        conn.execute("ALTER TABLE form_responses RENAME COLUMN started_at TO opened_at")
    if "opened_at" not in cols and "started_at" not in cols:
        conn.execute("ALTER TABLE form_responses ADD COLUMN opened_at TEXT")
    if "first_saved_at" not in cols:
        conn.execute("ALTER TABLE form_responses ADD COLUMN first_saved_at TEXT")
    if "completed_at" not in cols:
        conn.execute("ALTER TABLE form_responses ADD COLUMN completed_at TEXT")


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


def delete_schema(schema_id: str, version: int) -> None:
    """Delete a draft schema version. Raises ValueError if the schema is not a draft."""
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT status FROM form_schemas WHERE id = ? AND version = ?",
            (schema_id, version),
        ).fetchone()
        if row is None:
            raise ValueError(f"Schema {schema_id} v{version} not found")
        if row["status"] != "draft":
            raise ValueError("Only draft schemas can be deleted")
        conn.execute(
            "DELETE FROM form_schemas WHERE id = ? AND version = ?",
            (schema_id, version),
        )


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
               (id, schema_id, schema_version, status, draft_code, customer_name,
                answers_json, submitted_at, signed_off, signed_off_at,
                opened_at, first_saved_at, completed_at,
                output_generated, output_generated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                response.id,
                response.schema_id,
                response.schema_version,
                response.status.value,
                response.draft_code,
                response.customer_name,
                json.dumps(response.answers),
                response.submitted_at.isoformat() if response.submitted_at else None,
                1 if response.signed_off else 0,
                response.signed_off_at.isoformat() if response.signed_off_at else None,
                response.opened_at.isoformat() if response.opened_at else None,
                response.first_saved_at.isoformat() if response.first_saved_at else None,
                response.completed_at.isoformat() if response.completed_at else None,
                1 if response.output_generated else 0,
                response.output_generated_at.isoformat() if response.output_generated_at else None,
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


def list_responses(
    schema_id: str | None = None,
    status: ResponseStatus | None = None,
    exclude_status: ResponseStatus | None = None,
) -> list[FormResponse]:
    with _get_connection() as conn:
        clauses = []
        params: list = []
        if schema_id:
            clauses.append("schema_id = ?")
            params.append(schema_id)
        if status:
            clauses.append("status = ?")
            params.append(status.value)
        if exclude_status:
            clauses.append("status != ?")
            params.append(exclude_status.value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(
            f"SELECT * FROM form_responses{where} ORDER BY submitted_at DESC",
            params,
        ).fetchall()
        return [_row_to_response(r) for r in rows]


def load_draft(draft_code: str) -> FormResponse | None:
    """Load a draft response by its draft code."""
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM form_responses WHERE draft_code = ? AND status = 'draft'",
            (draft_code.strip().upper(),),
        ).fetchone()
        if row is None:
            return None
        return _row_to_response(row)


def _row_to_response(row: sqlite3.Row) -> FormResponse:
    col_names = set(row.keys())
    return FormResponse(
        id=row["id"],
        schema_id=row["schema_id"],
        schema_version=row["schema_version"],
        status=ResponseStatus(row["status"]) if row["status"] else ResponseStatus.SUBMITTED,
        draft_code=row["draft_code"],
        customer_name=row["customer_name"],
        answers=json.loads(row["answers_json"]),
        submitted_at=datetime.fromisoformat(row["submitted_at"]) if row["submitted_at"] else None,
        signed_off=bool(row["signed_off"]),
        signed_off_at=datetime.fromisoformat(row["signed_off_at"]) if row["signed_off_at"] else None,
        opened_at=datetime.fromisoformat(row["opened_at"]) if "opened_at" in col_names and row["opened_at"] else None,
        first_saved_at=datetime.fromisoformat(row["first_saved_at"]) if "first_saved_at" in col_names and row["first_saved_at"] else None,
        completed_at=datetime.fromisoformat(row["completed_at"]) if "completed_at" in col_names and row["completed_at"] else None,
        output_generated=bool(row["output_generated"]) if "output_generated" in col_names else False,
        output_generated_at=datetime.fromisoformat(row["output_generated_at"]) if "output_generated" in col_names and row["output_generated_at"] else None,
    )
