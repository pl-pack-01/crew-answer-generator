"""Customer-facing page: fill out a guided form dynamically rendered from schema."""

from datetime import datetime

import streamlit as st

from app.models import FieldType, FormResponse, ResponseStatus, SchemaStatus
from app.storage import list_schemas, load_draft, load_live_schema, save_response

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

    # --- Resume a draft ---
    with st.expander("Resume a saved draft"):
        draft_code_input = st.text_input(
            "Enter your draft code",
            key="draft_code_input",
            placeholder="e.g. A1B2C3D4",
        )
        if st.button("Resume", key="resume_draft"):
            if draft_code_input.strip():
                draft = load_draft(draft_code_input)
                if draft:
                    st.session_state.active_draft = draft
                    st.session_state.missing_fields = set()
                    st.session_state.missing_field_names = []
                    st.rerun()
                else:
                    st.error("Draft not found. Check the code and try again.")
            else:
                st.warning("Please enter a draft code.")

    st.divider()

    # --- Check for an active draft in session ---
    active_draft: FormResponse | None = st.session_state.get("active_draft")

    if active_draft:
        schema = load_live_schema(active_draft.schema_id)
        if not schema:
            st.error("The form for this draft is no longer available.")
            if st.button("Clear draft"):
                st.session_state.pop("active_draft", None)
                st.rerun()
            return
        st.info(f"Resuming draft **{active_draft.draft_code}** for **{schema.name}**")
    else:
        # --- Select a form ---
        schemas = list_schemas(status=SchemaStatus.LIVE)
        if not schemas:
            st.info("No forms are currently available. Please check back later.")
            return

        schema_options = {s.name: s.id for s in schemas}
        selected_name = st.selectbox("Select a form to fill out", list(schema_options.keys()),
                                     index=None, placeholder="Choose a form...")

        if not selected_name:
            return

        schema = load_live_schema(schema_options[selected_name])
        if not schema:
            st.error("Form not found.")
            return

    if schema.description:
        st.write(schema.description)

    st.divider()

    # Pre-fill from draft if resuming
    draft_answers = active_draft.answers if active_draft else {}
    draft_customer = active_draft.customer_name if active_draft else ""

    customer_name = st.text_input(
        "Your Name / Organization",
        value=draft_customer or "",
        key="customer_name",
    )

    # Render form fields
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
            default_val = draft_answers.get(question.id)
            answer = _render_question(question, is_missing, default_val)
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

    # Action buttons
    col_submit, col_save = st.columns([1, 1])

    with col_submit:
        submit_clicked = st.button("Submit", type="primary")

    with col_save:
        save_draft_clicked = st.button("Save Draft")

    # --- Save draft ---
    if save_draft_clicked:
        draft = _build_draft(schema, active_draft, customer_name, answers)
        save_response(draft)
        st.session_state.active_draft = draft
        st.success(f"Draft saved! Your draft code is **{draft.draft_code}**. Use it to resume later.")

    # --- Submit ---
    if submit_clicked:
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

        draft = _build_draft(schema, active_draft, customer_name, answers)
        draft.status = ResponseStatus.SUBMITTED
        draft.submitted_at = datetime.now()
        draft.signed_off = True
        draft.signed_off_at = datetime.now()
        save_response(draft)

        st.session_state.pop("active_draft", None)
        st.success("Thank you! Your responses have been submitted successfully.")
        st.balloons()

    # Show validation errors at the bottom after a rerun
    if st.session_state.get("missing_field_names"):
        st.error("**Please complete the following required fields:**")
        for name in st.session_state.missing_field_names:
            st.markdown(f"- :red[{name}]")


def _build_draft(schema, existing_draft, customer_name, answers) -> FormResponse:
    """Create or update a draft FormResponse."""
    if existing_draft:
        existing_draft.customer_name = customer_name or None
        existing_draft.answers = answers
        return existing_draft
    return FormResponse(
        schema_id=schema.id,
        schema_version=schema.version,
        customer_name=customer_name or None,
        answers=answers,
    )


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


def _render_question(question, is_missing=False, default_value=None):
    label = question.text
    if not question.required:
        label += " *(optional)*"
    if is_missing:
        label = f":red[**{question.text}** *(required)*]"
    help_text = question.help_text

    # Show screenshot popover if available
    if question.screenshot_b64:
        with st.popover("Screenshot", use_container_width=False):
            st.image(question.screenshot_b64, use_container_width=True)

    match question.field_type:
        case FieldType.DROPDOWN:
            options = [""] + question.options
            idx = options.index(default_value) if default_value in options else 0
            val = st.selectbox(label, options, index=idx, help=help_text, key=question.id)
            return val if val else None

        case FieldType.MULTI_SELECT:
            defaults = default_value if isinstance(default_value, list) else []
            val = st.multiselect(label, question.options, default=defaults, help=help_text, key=question.id)
            return val if val else None

        case FieldType.YES_NO:
            options = ["", "Yes", "No"]
            idx = options.index(default_value) if default_value in options else 0
            val = st.radio(label, options, index=idx, help=help_text, key=question.id, horizontal=True)
            return val if val else None

        case FieldType.TEXT:
            val = st.text_input(label, value=default_value or "", help=help_text, key=question.id)
            return val if val else None

        case FieldType.TEXTAREA:
            val = st.text_area(label, value=default_value or "", help=help_text, key=question.id)
            return val if val else None

        case FieldType.DATE:
            val = st.date_input(label, value=None, help=help_text, key=question.id)
            return str(val) if val else None

        case FieldType.NUMBER:
            val = st.number_input(label, value=None, help=help_text, key=question.id, step=1)
            return str(val) if val is not None else None

        case _:
            val = st.text_input(label, value=default_value or "", help=help_text, key=question.id)
            return val if val else None
