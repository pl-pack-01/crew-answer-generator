"""Tests for SQLite database layer."""

from datetime import datetime

import pytest

from app.database import (
    archive_schema,
    init_db,
    list_responses,
    list_schema_versions,
    list_schemas,
    load_live_schema,
    load_response,
    load_schema,
    promote_schema,
    save_response,
    save_schema,
)
from app.models import FieldType, FormResponse, FormSchema, Question, SchemaStatus, Section


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    """Each test gets its own SQLite database."""
    db_path = tmp_path / "test.db"
    init_db(db_path)


def _make_schema(name="Test Form", schema_id="test1", version=1, status=SchemaStatus.DRAFT):
    return FormSchema(
        id=schema_id,
        name=name,
        version=version,
        status=status,
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


class TestSchemaOperations:
    def test_save_and_load(self):
        schema = _make_schema()
        save_schema(schema)
        loaded = load_schema("test1")
        assert loaded is not None
        assert loaded.name == "Test Form"
        assert loaded.status == SchemaStatus.DRAFT
        assert len(loaded.sections[0].questions) == 2

    def test_load_specific_version(self):
        save_schema(_make_schema(version=1))
        save_schema(_make_schema(name="Updated", version=2))
        v1 = load_schema("test1", version=1)
        v2 = load_schema("test1", version=2)
        assert v1.name == "Test Form"
        assert v2.name == "Updated"

    def test_load_latest_version(self):
        save_schema(_make_schema(version=1))
        save_schema(_make_schema(name="Updated", version=2))
        latest = load_schema("test1")
        assert latest.name == "Updated"
        assert latest.version == 2

    def test_load_nonexistent(self):
        assert load_schema("nope") is None

    def test_list_schemas_latest_only(self):
        save_schema(_make_schema(schema_id="a", name="Form A", version=1))
        save_schema(_make_schema(schema_id="a", name="Form A v2", version=2))
        save_schema(_make_schema(schema_id="b", name="Form B", version=1))
        schemas = list_schemas()
        assert len(schemas) == 2
        names = {s.name for s in schemas}
        assert "Form A v2" in names
        assert "Form B" in names

    def test_edit_draft_schema_in_place(self):
        """Editing a draft should overwrite the same (id, version) row."""
        schema = _make_schema()
        save_schema(schema)

        # Simulate admin editing: change name, add a question, change field type
        loaded = load_schema("test1")
        loaded.name = "Edited Form"
        loaded.sections[0].questions[0].text = "Full Name?"
        loaded.sections[0].questions.append(
            Question(id="q3", text="Region?", field_type=FieldType.DROPDOWN, options=["US", "EU", "APAC"])
        )
        save_schema(loaded)

        reloaded = load_schema("test1")
        assert reloaded.name == "Edited Form"
        assert reloaded.version == 1  # same version, not a new one
        assert len(reloaded.sections[0].questions) == 3
        assert reloaded.sections[0].questions[0].text == "Full Name?"
        assert reloaded.sections[0].questions[2].options == ["US", "EU", "APAC"]

    def test_edit_preserves_status(self):
        schema = _make_schema(status=SchemaStatus.DRAFT)
        save_schema(schema)
        loaded = load_schema("test1")
        loaded.name = "Changed"
        save_schema(loaded)
        reloaded = load_schema("test1")
        assert reloaded.status == SchemaStatus.DRAFT

    def test_remove_question_from_schema(self):
        schema = _make_schema()
        save_schema(schema)
        loaded = load_schema("test1")
        loaded.sections[0].questions = [loaded.sections[0].questions[0]]  # keep only q1
        save_schema(loaded)
        reloaded = load_schema("test1")
        assert len(reloaded.sections[0].questions) == 1
        assert reloaded.sections[0].questions[0].id == "q1"

    def test_add_section_to_schema(self):
        schema = _make_schema()
        save_schema(schema)
        loaded = load_schema("test1")
        loaded.sections.append(Section(
            title="New Section",
            questions=[Question(id="q5", text="New Q?", field_type=FieldType.TEXT)],
        ))
        save_schema(loaded)
        reloaded = load_schema("test1")
        assert len(reloaded.sections) == 2
        assert reloaded.sections[1].title == "New Section"

    def test_remove_section_from_schema(self):
        schema = _make_schema()
        schema.sections.append(Section(title="Extra", questions=[]))
        save_schema(schema)
        loaded = load_schema("test1")
        loaded.sections = [loaded.sections[0]]  # keep only first
        save_schema(loaded)
        reloaded = load_schema("test1")
        assert len(reloaded.sections) == 1

    def test_list_schemas_by_status(self):
        save_schema(_make_schema(schema_id="a", status=SchemaStatus.DRAFT))
        save_schema(_make_schema(schema_id="b", status=SchemaStatus.LIVE))
        drafts = list_schemas(status=SchemaStatus.DRAFT)
        live = list_schemas(status=SchemaStatus.LIVE)
        assert len(drafts) == 1
        assert len(live) == 1
        assert drafts[0].id == "a"
        assert live[0].id == "b"

    def test_list_schemas_empty(self):
        assert list_schemas() == []

    def test_list_schema_versions(self):
        save_schema(_make_schema(version=1))
        save_schema(_make_schema(version=2))
        save_schema(_make_schema(version=3))
        versions = list_schema_versions("test1")
        assert len(versions) == 3
        assert versions[0].version == 3  # newest first
        assert versions[2].version == 1


class TestSchemaPromotion:
    def test_promote_to_live(self):
        save_schema(_make_schema())
        promote_schema("test1", 1)
        schema = load_schema("test1")
        assert schema.status == SchemaStatus.LIVE

    def test_promote_archives_previous_live(self):
        save_schema(_make_schema(version=1, status=SchemaStatus.LIVE))
        save_schema(_make_schema(version=2))
        promote_schema("test1", 2)

        v1 = load_schema("test1", version=1)
        v2 = load_schema("test1", version=2)
        assert v1.status == SchemaStatus.ARCHIVED
        assert v2.status == SchemaStatus.LIVE

    def test_load_live_schema(self):
        save_schema(_make_schema(version=1, status=SchemaStatus.DRAFT))
        save_schema(_make_schema(version=2, status=SchemaStatus.LIVE))
        save_schema(_make_schema(version=3, status=SchemaStatus.DRAFT))

        live = load_live_schema("test1")
        assert live is not None
        assert live.version == 2
        assert live.status == SchemaStatus.LIVE

    def test_load_live_schema_none_when_no_live(self):
        save_schema(_make_schema(status=SchemaStatus.DRAFT))
        assert load_live_schema("test1") is None

    def test_archive_schema(self):
        save_schema(_make_schema(status=SchemaStatus.LIVE))
        archive_schema("test1", 1)
        schema = load_schema("test1")
        assert schema.status == SchemaStatus.ARCHIVED

    def test_repromote_archived(self):
        save_schema(_make_schema(status=SchemaStatus.ARCHIVED))
        promote_schema("test1", 1)
        schema = load_schema("test1")
        assert schema.status == SchemaStatus.LIVE


class TestResponseOperations:
    def test_save_and_load(self):
        save_schema(_make_schema())
        resp = _make_response()
        save_response(resp)
        loaded = load_response("resp1")
        assert loaded is not None
        assert loaded.customer_name == "Acme Corp"
        assert loaded.answers["q1"] == "John"

    def test_load_nonexistent(self):
        assert load_response("nope") is None

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

    def test_response_with_list_answers(self):
        save_schema(_make_schema())
        resp = FormResponse(
            id="r1",
            schema_id="test1",
            schema_version=1,
            answers={"q1": "John", "q2": ["Prod", "Dev"]},
            submitted_at=datetime.now(),
        )
        save_response(resp)
        loaded = load_response("r1")
        assert loaded.answers["q2"] == ["Prod", "Dev"]
