"""Customer-facing page: fill out a guided form dynamically rendered from schema."""

from datetime import datetime

import streamlit as st

from app.models import FieldType, FormResponse, SchemaStatus
from app.storage import list_schemas, load_live_schema, save_response

# CSS to highlight missing required fields with a red border
_MISSING_FIELD_CSS = """
<style>
div[data-testid="stVerticalBlock"] .missing-field + div {{
    /* fallback visual cue */
}}
{selectors}
</style>
"""

_PER_FIELD_CSS = """
div[data-testid="column"] div[data-baseweb] [id*="{key}"],
div[data-testid="stVerticalBlock"] div[data-baseweb] [id*="{key}"],
div.stSelectbox [id*="{key}"],
div.stMultiSelect [id*="{key}"],
div.stTextInput [id*="{key}"],
div.stTextArea [id*="{key}"],
div.stDateInput [id*="{key}"],
div.stNumberInput [id*="{key}"] {{
    border-color: #ff4b4b !important;
    box-shadow: 0 0 0 1px #ff4b4b !important;
}}
"""


def render():
    st.title("Customer Intake Form")

    # Initialize missing fields tracking
    if "missing_fields" not in st.session_state:
        st.session_state.missing_fields = set()
    if "missing_field_names" not in st.session_state:
        st.session_state.missing_field_names = []

    schemas = list_schemas(status=SchemaStatus.LIVE)
    if not schemas:
        st.info("No forms are currently available. Please check back later.")
        return

    schema_options = {s.name: s.id for s in schemas}
    selected_name = st.selectbox("Select a form to fill out", list(schema_options.keys()))
    schema = load_live_schema(schema_options[selected_name])

    if not schema:
        st.error("Form not found.")
        return

    if schema.description:
        st.write(schema.description)

    st.divider()

    customer_name = st.text_input("Your Name / Organization", key="customer_name")

    # Render form
    answers = {}
    missing = st.session_state.missing_fields

    for section in schema.sections:
        st.header(section.title)
        if section.description:
            st.write(section.description)

        for question in section.questions:
            if question.conditions:
                visible = _evaluate_conditions(question.conditions, answers)
                if not visible:
                    continue

            is_missing = question.id in missing
            answer = _render_question(question, is_missing)
            if answer is not None:
                answers[question.id] = answer

    # Inject CSS for any missing fields
    if missing:
        selectors = "\n".join(_PER_FIELD_CSS.format(key=fid) for fid in missing)
        st.markdown(_MISSING_FIELD_CSS.format(selectors=selectors), unsafe_allow_html=True)

    st.divider()

    # Sign-off
    st.markdown("### Confirmation")
    sign_off = st.checkbox(
        "I confirm that the information provided above is accurate and complete.",
        key="sign_off",
    )

    if st.button("Submit", type="primary"):
        # Validate required fields
        new_missing = set()
        missing_names = []
        for section in schema.sections:
            for q in section.questions:
                if q.conditions:
                    if not _evaluate_conditions(q.conditions, answers):
                        continue
                if q.required and not answers.get(q.id):
                    new_missing.add(q.id)
                    missing_names.append(q.text)

        if new_missing:
            st.session_state.missing_fields = new_missing
            st.session_state.missing_field_names = missing_names
            st.rerun()
            return

        if not sign_off:
            st.session_state.missing_fields = set()
            st.session_state.missing_field_names = []
            st.warning("Please confirm the information is accurate before submitting.")
            return

        # Clear missing state and submit
        st.session_state.missing_fields = set()
        st.session_state.missing_field_names = []

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

    # Show validation errors at the bottom after a rerun
    if st.session_state.get("missing_field_names"):
        st.error("**Please complete the following required fields:**")
        for name in st.session_state.missing_field_names:
            st.markdown(f"- :red[{name}]")


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


def _render_question(question, is_missing=False):
    label = question.text
    if not question.required:
        label += " *(optional)*"
    if is_missing:
        label = f":red[**{question.text}** *(required)*]"
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
