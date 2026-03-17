"""Tests for schema export and import."""

import json

from app.models import (
    Condition,
    FieldType,
    FormSchema,
    Question,
    SchemaStatus,
    Section,
)
from app.schema_io import export_schema, import_schema


def _make_schema(**overrides) -> FormSchema:
    defaults = dict(
        name="Test Form",
        description="A test form",
        version=3,
        status=SchemaStatus.LIVE,
        source_filename="test.docx",
        sections=[
            Section(
                title="Section 1",
                description="First section",
                questions=[
                    Question(
                        text="What environment?",
                        field_type=FieldType.DROPDOWN,
                        options=["Prod", "Staging", "Dev"],
                        required=True,
                        help_text="Select one",
                    ),
                    Question(
                        text="Describe the setup",
                        field_type=FieldType.TEXTAREA,
                        conditions=[
                            Condition(question_id="placeholder", operator="equals", value="Prod")
                        ],
                    ),
                ],
            ),
            Section(title="Section 2", questions=[]),
        ],
    )
    defaults.update(overrides)
    return FormSchema(**defaults)


class TestExportSchema:
    def test_export_returns_valid_json(self):
        schema = _make_schema()
        result = export_schema(schema)
        data = json.loads(result)
        assert "export_version" in data
        assert "exported_at" in data
        assert "schema" in data

    def test_export_preserves_name_and_description(self):
        schema = _make_schema(name="My Form", description="Desc")
        data = json.loads(export_schema(schema))
        assert data["schema"]["name"] == "My Form"
        assert data["schema"]["description"] == "Desc"

    def test_export_preserves_sections_and_questions(self):
        schema = _make_schema()
        data = json.loads(export_schema(schema))
        sections = data["schema"]["sections"]
        assert len(sections) == 2
        assert len(sections[0]["questions"]) == 2
        assert sections[0]["questions"][0]["options"] == ["Prod", "Staging", "Dev"]

    def test_export_preserves_conditions(self):
        schema = _make_schema()
        data = json.loads(export_schema(schema))
        q2 = data["schema"]["sections"][0]["questions"][1]
        assert len(q2["conditions"]) == 1
        assert q2["conditions"][0]["operator"] == "equals"

    def test_export_preserves_source_filename(self):
        schema = _make_schema(source_filename="intake.docx")
        data = json.loads(export_schema(schema))
        assert data["schema"]["source_filename"] == "intake.docx"

    def test_export_preserves_screenshots(self):
        schema = _make_schema()
        schema.sections[0].questions[0].screenshot_b64 = "data:image/png;base64,abc123"
        data = json.loads(export_schema(schema))
        assert data["schema"]["sections"][0]["questions"][0]["screenshot_b64"] == "data:image/png;base64,abc123"


class TestImportSchema:
    def test_import_creates_draft_with_new_id(self):
        schema = _make_schema()
        json_str = export_schema(schema)
        imported = import_schema(json_str)
        assert imported.id != schema.id
        assert imported.version == 1
        assert imported.status == SchemaStatus.DRAFT

    def test_import_preserves_name_and_sections(self):
        schema = _make_schema(name="Data Movement")
        json_str = export_schema(schema)
        imported = import_schema(json_str)
        assert imported.name == "Data Movement"
        assert len(imported.sections) == 2
        assert len(imported.sections[0].questions) == 2

    def test_import_preserves_question_details(self):
        schema = _make_schema()
        json_str = export_schema(schema)
        imported = import_schema(json_str)
        q = imported.sections[0].questions[0]
        assert q.field_type == FieldType.DROPDOWN
        assert q.options == ["Prod", "Staging", "Dev"]
        assert q.help_text == "Select one"

    def test_import_preserves_conditions(self):
        schema = _make_schema()
        json_str = export_schema(schema)
        imported = import_schema(json_str)
        q2 = imported.sections[0].questions[1]
        assert len(q2.conditions) == 1
        assert q2.conditions[0].operator == "equals"

    def test_import_preserves_source_filename(self):
        schema = _make_schema(source_filename="original.docx")
        json_str = export_schema(schema)
        imported = import_schema(json_str)
        assert imported.source_filename == "original.docx"

    def test_import_raw_schema_json(self):
        """Import a raw FormSchema JSON (without export wrapper)."""
        schema = _make_schema()
        raw_json = schema.model_dump_json()
        imported = import_schema(raw_json)
        assert imported.name == schema.name
        assert imported.id != schema.id
        assert imported.status == SchemaStatus.DRAFT

    def test_import_invalid_json_raises(self):
        import pytest
        with pytest.raises(ValueError):
            import_schema('{"unrelated": true}')

    def test_import_malformed_json_raises(self):
        import pytest
        with pytest.raises(json.JSONDecodeError):
            import_schema("not json at all")

    def test_roundtrip_preserves_all_data(self):
        """Export then import should preserve all schema content."""
        original = _make_schema()
        original.sections[0].questions[0].screenshot_b64 = "data:image/png;base64,test"
        json_str = export_schema(original)
        imported = import_schema(json_str)

        # Content should match (id, version, status, created_at will differ)
        assert imported.name == original.name
        assert imported.description == original.description
        assert imported.source_filename == original.source_filename
        assert len(imported.sections) == len(original.sections)
        for orig_sec, imp_sec in zip(original.sections, imported.sections):
            assert orig_sec.title == imp_sec.title
            assert len(orig_sec.questions) == len(imp_sec.questions)
            for orig_q, imp_q in zip(orig_sec.questions, imp_sec.questions):
                assert orig_q.text == imp_q.text
                assert orig_q.field_type == imp_q.field_type
                assert orig_q.options == imp_q.options
                assert orig_q.screenshot_b64 == imp_q.screenshot_b64
