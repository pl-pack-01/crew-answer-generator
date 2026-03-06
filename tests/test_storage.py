"""Tests for JSON file-based storage."""

import shutil
from datetime import datetime
from pathlib import Path

import pytest

import app.storage as storage
from app.models import FieldType, FormResponse, FormSchema, Question, Section


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path, monkeypatch):
    """Redirect storage to a temp directory for each test."""
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(storage, "SCHEMAS_DIR", tmp_path / "data" / "schemas")
    monkeypatch.setattr(storage, "RESPONSES_DIR", tmp_path / "data" / "responses")
    monkeypatch.setattr(storage, "UPLOADS_DIR", tmp_path / "data" / "uploads")


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
        storage.save_schema(schema)
        loaded = storage.load_schema("test1")
        assert loaded is not None
        assert loaded.name == "Test Form"
        assert len(loaded.sections[0].questions) == 2

    def test_load_schema_by_version(self):
        schema = _make_schema(version=1)
        storage.save_schema(schema)
        schema_v2 = _make_schema(name="Test Form Updated", version=2)
        storage.save_schema(schema_v2)

        v1 = storage.load_schema("test1", version=1)
        v2 = storage.load_schema("test1", version=2)
        latest = storage.load_schema("test1")

        assert v1.name == "Test Form"
        assert v2.name == "Test Form Updated"
        assert latest.name == "Test Form Updated"

    def test_load_nonexistent_schema(self):
        assert storage.load_schema("nonexistent") is None

    def test_list_schemas(self):
        storage.save_schema(_make_schema(name="Form A", schema_id="a"))
        storage.save_schema(_make_schema(name="Form B", schema_id="b"))
        schemas = storage.list_schemas()
        assert len(schemas) == 2
        names = {s.name for s in schemas}
        assert names == {"Form A", "Form B"}

    def test_list_schemas_empty(self):
        assert storage.list_schemas() == []

    def test_version_update_preserves_old(self):
        storage.save_schema(_make_schema(version=1))
        storage.save_schema(_make_schema(name="Updated", version=2))

        v1 = storage.load_schema("test1", version=1)
        assert v1.name == "Test Form"
        assert v1.version == 1


class TestResponseStorage:
    def test_save_and_load_response(self):
        resp = _make_response()
        storage.save_response(resp)
        loaded = storage.load_response("resp1")
        assert loaded is not None
        assert loaded.customer_name == "Acme Corp"
        assert loaded.answers["q1"] == "John"

    def test_load_nonexistent_response(self):
        assert storage.load_response("nonexistent") is None

    def test_list_responses(self):
        storage.save_response(_make_response(response_id="r1"))
        storage.save_response(_make_response(response_id="r2"))
        responses = storage.list_responses()
        assert len(responses) == 2

    def test_list_responses_filter_by_schema(self):
        storage.save_response(_make_response(schema_id="s1", response_id="r1"))
        storage.save_response(_make_response(schema_id="s2", response_id="r2"))
        responses = storage.list_responses(schema_id="s1")
        assert len(responses) == 1
        assert responses[0].schema_id == "s1"

    def test_list_responses_empty(self):
        assert storage.list_responses() == []


class TestUploadStorage:
    def test_save_upload(self):
        path = storage.save_upload("test.docx", b"fake content")
        assert path.exists()
        assert path.read_bytes() == b"fake content"
