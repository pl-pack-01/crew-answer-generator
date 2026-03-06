"""Tests for the storage facade (delegates to database + file storage)."""

from datetime import datetime
from pathlib import Path

import pytest

from app.database import init_db
from app.file_storage import LocalFileStorage
from app.models import FieldType, FormResponse, FormSchema, Question, SchemaStatus, Section
from app.storage import (
    list_responses,
    list_schemas,
    load_schema,
    promote_schema,
    save_response,
    save_schema,
    save_upload,
)


@pytest.fixture(autouse=True)
def setup_storage(tmp_path, monkeypatch):
    """Initialize DB and file storage in temp directory for each test."""
    init_db(tmp_path / "test.db")
    fs = LocalFileStorage(tmp_path / "uploads")
    monkeypatch.setattr("app.storage._file_storage", fs)


def _make_schema(name="Test Form", schema_id="test1", version=1):
    return FormSchema(
        id=schema_id,
        name=name,
        version=version,
        sections=[
            Section(
                title="General",
                questions=[
                    Question(id="q1", text="Name?", field_type=FieldType.TEXT),
                    Question(id="q2", text="Env?", field_type=FieldType.DROPDOWN, options=["Prod", "Dev"]),
                ],
            )
        ],
    )


def _make_response(schema_id="test1", version=1, response_id="resp1"):
    return FormResponse(
        id=response_id,
        schema_id=schema_id,
        schema_version=version,
        customer_name="Acme Corp",
        answers={"q1": "John", "q2": "Prod"},
        submitted_at=datetime.now(),
        signed_off=True,
        signed_off_at=datetime.now(),
    )


class TestSchemaStorage:
    def test_save_and_load_schema(self):
        schema = _make_schema()
        save_schema(schema)
        loaded = load_schema("test1")
        assert loaded is not None
        assert loaded.name == "Test Form"
        assert len(loaded.sections[0].questions) == 2

    def test_load_schema_by_version(self):
        save_schema(_make_schema(version=1))
        save_schema(_make_schema(name="Test Form Updated", version=2))

        v1 = load_schema("test1", version=1)
        v2 = load_schema("test1", version=2)
        latest = load_schema("test1")

        assert v1.name == "Test Form"
        assert v2.name == "Test Form Updated"
        assert latest.name == "Test Form Updated"

    def test_load_nonexistent_schema(self):
        assert load_schema("nonexistent") is None

    def test_list_schemas(self):
        save_schema(_make_schema(name="Form A", schema_id="a"))
        save_schema(_make_schema(name="Form B", schema_id="b"))
        schemas = list_schemas()
        assert len(schemas) == 2
        names = {s.name for s in schemas}
        assert names == {"Form A", "Form B"}

    def test_list_schemas_empty(self):
        assert list_schemas() == []

    def test_version_update_preserves_old(self):
        save_schema(_make_schema(version=1))
        save_schema(_make_schema(name="Updated", version=2))

        v1 = load_schema("test1", version=1)
        assert v1.name == "Test Form"
        assert v1.version == 1

    def test_promote_and_list_live(self):
        save_schema(_make_schema())
        promote_schema("test1", 1)
        live = list_schemas(status=SchemaStatus.LIVE)
        assert len(live) == 1
        assert live[0].status == SchemaStatus.LIVE


class TestResponseStorage:
    def test_save_and_load_response(self):
        save_schema(_make_schema())
        resp = _make_response()
        save_response(resp)
        loaded = list_responses()
        assert len(loaded) == 1
        assert loaded[0].customer_name == "Acme Corp"
        assert loaded[0].answers["q1"] == "John"

    def test_list_responses(self):
        save_schema(_make_schema())
        save_response(_make_response(response_id="r1"))
        save_response(_make_response(response_id="r2"))
        responses = list_responses()
        assert len(responses) == 2

    def test_list_responses_filter_by_schema(self):
        save_schema(_make_schema(schema_id="s1"))
        save_schema(_make_schema(schema_id="s2"))
        save_response(_make_response(schema_id="s1", response_id="r1"))
        save_response(_make_response(schema_id="s2", response_id="r2"))
        responses = list_responses(schema_id="s1")
        assert len(responses) == 1
        assert responses[0].schema_id == "s1"

    def test_list_responses_empty(self):
        assert list_responses() == []


class TestUploadStorage:
    def test_save_upload(self):
        path = save_upload("test.docx", b"fake content")
        assert path.exists()
        assert path.read_bytes() == b"fake content"
