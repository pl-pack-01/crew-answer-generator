"""Customer-facing page: fill out a guided form dynamically rendered from schema."""

from datetime import datetime

import streamlit as st

from app.models import FieldType, FormResponse
from app.storage import list_schemas, load_schema, save_response


def render():
    st.title("Customer Intake Form")

    schemas = list_schemas()
    if not schemas:
        st.info("No forms are currently available. Please check back later.")
        return

    # Form selection
    schema_options = {s.name: s.id for s in schemas}
    selected_name = st.selectbox("Select a form to fill out", list(schema_options.keys()))
    schema = load_schema(schema_options[selected_name])

    if not schema:
        st.error("Form not found.")
        return

    if schema.description:
        st.write(schema.description)

    st.divider()

    # Customer info
    customer_name = st.text_input("Your Name / Organization", key="customer_name")

    # Render form
    answers = {}

    for section in schema.sections:
        st.header(section.title)
        if section.description:
            st.write(section.description)

        for question in section.questions:
            # Check conditions (progressive disclosure)
            if question.conditions:
                visible = _evaluate_conditions(question.conditions, answers)
                if not visible:
                    continue

            answer = _render_question(question)
            if answer is not None:
                answers[question.id] = answer

    st.divider()

    # Sign-off
    st.markdown("### Confirmation")
    sign_off = st.checkbox(
        "I confirm that the information provided above is accurate and complete.",
        key="sign_off",
    )

    if st.button("Submit", type="primary"):
        # Validate required fields
        missing = []
        for section in schema.sections:
            for q in section.questions:
                if q.conditions:
                    if not _evaluate_conditions(q.conditions, answers):
                        continue
                if q.required and not answers.get(q.id):
                    missing.append(q.text)

        if missing:
            st.error(f"Please complete the following required fields: {', '.join(missing[:5])}")
            return

        if not sign_off:
            st.warning("Please confirm the information is accurate before submitting.")
            return

        response = FormResponse(
            schema_id=schema.id,
            schema_version=schema.version,
            customer_name=customer_name or None,
            answers=answers,
            submitted_at=datetime.now(),
            signed_off=True,
            signed_off_at=datetime.now(),
        )
        save_response(response)
        st.success("Thank you! Your responses have been submitted successfully.")
        st.balloons()


def _evaluate_conditions(conditions, current_answers):
    for cond in conditions:
        current_val = current_answers.get(cond.question_id)
        if current_val is None:
            return False
        if cond.operator == "equals" and current_val != cond.value:
            return False
        if cond.operator == "not_equals" and current_val == cond.value:
            return False
        if cond.operator == "contains" and cond.value not in (current_val if isinstance(current_val, list) else [current_val]):
            return False
        if cond.operator == "in" and current_val not in cond.value:
            return False
    return True


def _render_question(question):
    label = question.text
    if not question.required:
        label += " *(optional)*"
    help_text = question.help_text

    match question.field_type:
        case FieldType.DROPDOWN:
            options = [""] + question.options
            val = st.selectbox(label, options, help=help_text, key=question.id)
            return val if val else None

        case FieldType.MULTI_SELECT:
            val = st.multiselect(label, question.options, help=help_text, key=question.id)
            return val if val else None

        case FieldType.YES_NO:
            val = st.radio(label, ["", "Yes", "No"], help=help_text, key=question.id, horizontal=True)
            return val if val else None

        case FieldType.TEXT:
            val = st.text_input(label, help=help_text, key=question.id)
            return val if val else None

        case FieldType.TEXTAREA:
            val = st.text_area(label, help=help_text, key=question.id)
            return val if val else None

        case FieldType.DATE:
            val = st.date_input(label, value=None, help=help_text, key=question.id)
            return str(val) if val else None

        case FieldType.NUMBER:
            val = st.number_input(label, value=None, help=help_text, key=question.id, step=1)
            return str(val) if val is not None else None

        case _:
            val = st.text_input(label, help=help_text, key=question.id)
            return val if val else None
