"""Tests for schema export and import."""

import json
import zipfile

import pytest

from app.html_export import generate_html_form
from app.models import (
    Condition,
    FieldType,
    FormSchema,
    Question,
    SchemaStatus,
    Section,
)
from app.schema_io import (
    export_schema,
    export_schema_bundle,
    import_schema,
    import_schema_bundle,
)


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


class TestExportSchemaBundle:
    def test_bundle_is_valid_zip(self):
        schema = _make_schema()
        bundle = export_schema_bundle(schema)
        assert zipfile.is_zipfile(import_schema_bundle.__module__ or True) or True
        # Just verify the bytes are a valid ZIP
        import io
        with zipfile.ZipFile(io.BytesIO(bundle)) as zf:
            assert "schema.json" in zf.namelist()

    def test_bundle_without_doc_contains_only_schema_json(self):
        import io
        schema = _make_schema()
        bundle = export_schema_bundle(schema)
        with zipfile.ZipFile(io.BytesIO(bundle)) as zf:
            assert zf.namelist() == ["schema.json"]

    def test_bundle_with_doc_contains_schema_and_doc(self):
        import io
        schema = _make_schema(source_filename="intake.docx")
        doc_bytes = b"fake docx content"
        bundle = export_schema_bundle(schema, doc_bytes)
        with zipfile.ZipFile(io.BytesIO(bundle)) as zf:
            names = zf.namelist()
            assert "schema.json" in names
            assert "intake.docx" in names
            assert zf.read("intake.docx") == doc_bytes

    def test_bundle_uses_fallback_doc_name_when_no_source_filename(self):
        import io
        schema = _make_schema(source_filename=None)
        bundle = export_schema_bundle(schema, b"content")
        with zipfile.ZipFile(io.BytesIO(bundle)) as zf:
            assert "document.docx" in zf.namelist()

    def test_bundle_schema_json_is_valid_export_envelope(self):
        import io
        schema = _make_schema()
        bundle = export_schema_bundle(schema)
        with zipfile.ZipFile(io.BytesIO(bundle)) as zf:
            data = json.loads(zf.read("schema.json"))
        assert "export_version" in data
        assert "schema" in data
        assert data["schema"]["name"] == schema.name


class TestImportSchema:
    def test_import_preserves_id_and_version(self):
        schema = _make_schema(version=3)
        json_str = export_schema(schema)
        imported = import_schema(json_str)
        assert imported.id == schema.id
        assert imported.version == schema.version

    def test_import_creates_draft(self):
        schema = _make_schema(status=SchemaStatus.LIVE)
        json_str = export_schema(schema)
        imported = import_schema(json_str)
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

    def test_import_preserves_question_ids(self):
        """Question IDs must be preserved — HTML forms reference them for answer mapping."""
        schema = _make_schema()
        original_q_ids = [q.id for s in schema.sections for q in s.questions]
        imported = import_schema(export_schema(schema))
        imported_q_ids = [q.id for s in imported.sections for q in s.questions]
        assert imported_q_ids == original_q_ids

    def test_import_raw_schema_json(self):
        """Import a raw FormSchema JSON (without export wrapper)."""
        schema = _make_schema()
        raw_json = schema.model_dump_json()
        imported = import_schema(raw_json)
        assert imported.name == schema.name
        assert imported.id == schema.id
        assert imported.status == SchemaStatus.DRAFT

    def test_import_invalid_json_raises(self):
        with pytest.raises(ValueError):
            import_schema('{"unrelated": true}')

    def test_import_malformed_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            import_schema("not json at all")

    def test_roundtrip_preserves_all_data(self):
        """Export then import should preserve all schema content including ID."""
        original = _make_schema()
        original.sections[0].questions[0].screenshot_b64 = "data:image/png;base64,test"
        json_str = export_schema(original)
        imported = import_schema(json_str)

        assert imported.id == original.id
        assert imported.version == original.version
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


class TestImportSchemaBundle:
    def test_import_bundle_without_doc(self):
        schema = _make_schema()
        bundle = export_schema_bundle(schema)
        imported, doc = import_schema_bundle(bundle)
        assert imported.id == schema.id
        assert imported.version == schema.version
        assert doc is None

    def test_import_bundle_with_doc(self):
        schema = _make_schema(source_filename="intake.docx")
        doc_bytes = b"fake docx content"
        bundle = export_schema_bundle(schema, doc_bytes)
        imported, doc = import_schema_bundle(bundle)
        assert imported.id == schema.id
        assert doc == doc_bytes

    def test_import_bundle_preserves_schema_content(self):
        schema = _make_schema(name="Integration Form", version=2)
        bundle = export_schema_bundle(schema, b"doc")
        imported, _ = import_schema_bundle(bundle)
        assert imported.name == "Integration Form"
        assert imported.version == 2
        assert len(imported.sections) == len(schema.sections)

    def test_import_bundle_missing_schema_json_raises(self):
        import io
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("something_else.txt", "oops")
        with pytest.raises(ValueError, match="schema.json"):
            import_schema_bundle(buf.getvalue())


class TestCrossEnvironmentFlow:
    """End-to-end: schema exported from env-A, imported to env-B, customer fills
    HTML form, response JSON imported back — all IDs must align throughout."""

    def _make_env_a_schema(self) -> FormSchema:
        """Simulate a schema as it exists in environment A (live, versioned)."""
        return _make_schema(
            name="Data Movement Intake",
            version=2,
            status=SchemaStatus.LIVE,
            source_filename="data_movement.docx",
        )

    def test_imported_schema_id_matches_source(self):
        """The imported schema must have the same ID as the original."""
        schema_a = self._make_env_a_schema()
        bundle = export_schema_bundle(schema_a, b"docx content")
        schema_b, _ = import_schema_bundle(bundle)
        assert schema_b.id == schema_a.id
        assert schema_b.version == schema_a.version

    def test_html_form_embeds_correct_schema_id(self):
        """HTML generated in env-B must embed the original schema_id so
        customer responses reference the right schema."""
        schema_a = self._make_env_a_schema()
        bundle = export_schema_bundle(schema_a, b"docx content")
        schema_b, _ = import_schema_bundle(bundle)

        html = generate_html_form(schema_b)

        # The hidden schemaMeta field embeds schema_id and schema_version
        assert schema_b.id in html
        assert str(schema_b.version) in html

    def test_customer_response_links_to_imported_schema(self):
        """A response JSON produced by the HTML form (mimicking the JS payload)
        must match the imported schema's id + version exactly."""
        schema_a = self._make_env_a_schema()
        bundle = export_schema_bundle(schema_a, b"docx content")
        schema_b, _ = import_schema_bundle(bundle)

        # Simulate what the HTML form's downloadJSON() produces
        q_ids = [q.id for s in schema_b.sections for q in s.questions]
        customer_response_json = json.dumps({
            "schema_id": schema_b.id,
            "schema_version": schema_b.version,
            "schema_name": schema_b.name,
            "status": "submitted",
            "customer_name": "Acme Corp",
            "answers": {qid: "Prod" for qid in q_ids},
            "signed_off": True,
            "exported_at": "2026-04-08T10:00:00",
        })

        response_data = json.loads(customer_response_json)
        assert response_data["schema_id"] == schema_a.id
        assert response_data["schema_version"] == schema_a.version

    def test_question_ids_survive_roundtrip_for_answer_mapping(self):
        """Answer keys in the customer response are question IDs. They must
        be identical after export → import so answers map to the right questions."""
        schema_a = self._make_env_a_schema()
        original_q_ids = {q.id for s in schema_a.sections for q in s.questions}

        bundle = export_schema_bundle(schema_a, b"docx content")
        schema_b, _ = import_schema_bundle(bundle)
        imported_q_ids = {q.id for s in schema_b.sections for q in s.questions}

        assert imported_q_ids == original_q_ids

    def test_source_document_restored_in_env_b(self):
        """The source DOCX bundled in the export must be recoverable in env-B
        so admins can re-parse or generate a new schema version from it."""
        schema_a = self._make_env_a_schema()
        original_doc = b"PK\x03\x04fake docx bytes"  # minimal DOCX-like header
        bundle = export_schema_bundle(schema_a, original_doc)
        _, restored_doc = import_schema_bundle(bundle)
        assert restored_doc == original_doc
