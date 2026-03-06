"""Tests for Pydantic models."""

from datetime import datetime

from app.models import (
    Condition,
    FieldType,
    FormResponse,
    FormSchema,
    Question,
    SchemaStatus,
    Section,
)


def test_question_defaults():
    q = Question(text="What is your name?", field_type=FieldType.TEXT)
    assert q.text == "What is your name?"
    assert q.field_type == FieldType.TEXT
    assert q.required is True
    assert q.options == []
    assert q.conditions == []
    assert len(q.id) == 8


def test_question_with_options():
    q = Question(
        text="Select environment",
        field_type=FieldType.DROPDOWN,
        options=["Production", "Staging", "Dev"],
        required=False,
        help_text="Choose your target environment",
    )
    assert q.options == ["Production", "Staging", "Dev"]
    assert q.required is False
    assert q.help_text == "Choose your target environment"


def test_question_with_conditions():
    q = Question(
        text="Which cloud provider?",
        field_type=FieldType.DROPDOWN,
        options=["AWS", "Azure", "GCP"],
        conditions=[Condition(question_id="use_cloud", value="Yes")],
    )
    assert len(q.conditions) == 1
    assert q.conditions[0].question_id == "use_cloud"
    assert q.conditions[0].operator == "equals"
    assert q.conditions[0].value == "Yes"


def test_section_with_questions():
    section = Section(
        title="Environment Details",
        description="Tell us about your environment",
        questions=[
            Question(text="OS?", field_type=FieldType.DROPDOWN, options=["Linux", "Windows"]),
            Question(text="Version?", field_type=FieldType.TEXT),
        ],
    )
    assert section.title == "Environment Details"
    assert len(section.questions) == 2


def test_form_schema_defaults():
    schema = FormSchema(name="Test Form")
    assert schema.name == "Test Form"
    assert schema.version == 1
    assert schema.status == SchemaStatus.DRAFT
    assert schema.sections == []
    assert isinstance(schema.created_at, datetime)


def test_schema_status_values():
    assert SchemaStatus.DRAFT.value == "draft"
    assert SchemaStatus.LIVE.value == "live"
    assert SchemaStatus.ARCHIVED.value == "archived"


def test_form_schema_serialization():
    schema = FormSchema(
        name="Test Form",
        description="A test",
        sections=[
            Section(
                title="General",
                questions=[
                    Question(id="q1", text="Name?", field_type=FieldType.TEXT),
                ],
            )
        ],
    )
    json_str = schema.model_dump_json()
    loaded = FormSchema.model_validate_json(json_str)
    assert loaded.name == schema.name
    assert loaded.sections[0].questions[0].text == "Name?"
    assert loaded.sections[0].questions[0].id == "q1"


def test_form_response():
    resp = FormResponse(
        schema_id="abc123",
        schema_version=1,
        customer_name="Acme Corp",
        answers={"q1": "John", "q2": ["AWS", "Azure"]},
        submitted_at=datetime.now(),
        signed_off=True,
        signed_off_at=datetime.now(),
    )
    assert resp.schema_id == "abc123"
    assert resp.answers["q1"] == "John"
    assert resp.answers["q2"] == ["AWS", "Azure"]
    assert resp.signed_off is True


def test_form_response_serialization():
    resp = FormResponse(
        schema_id="abc",
        schema_version=2,
        answers={"q1": "hello", "q2": ["a", "b"]},
    )
    json_str = resp.model_dump_json()
    loaded = FormResponse.model_validate_json(json_str)
    assert loaded.answers["q2"] == ["a", "b"]
    assert loaded.schema_version == 2


def test_field_type_values():
    assert FieldType.DROPDOWN.value == "dropdown"
    assert FieldType.MULTI_SELECT.value == "multi_select"
    assert FieldType.YES_NO.value == "yes_no"
    assert FieldType.TEXT.value == "text"
    assert FieldType.TEXTAREA.value == "textarea"
    assert FieldType.DATE.value == "date"
    assert FieldType.NUMBER.value == "number"
