"""Admin page: upload documents, manage schemas, view responses."""

import uuid

import streamlit as st

from app.ingestion import ingest_document
from app.models import FieldType, Question, SchemaStatus, Section
from app.output import generate_filled_docx
from app.storage import (
    archive_schema,
    list_responses,
    list_schema_versions,
    list_schemas,
    load_schema,
    promote_schema,
    save_schema,
    save_upload,
)

FIELD_TYPE_OPTIONS = [ft.value for ft in FieldType]


def render():
    st.title("Admin - Document Management")

    tab_upload, tab_schemas, tab_responses = st.tabs(
        ["Upload Document", "Form Schemas", "Customer Responses"]
    )

    with tab_upload:
        _render_upload()

    with tab_schemas:
        _render_schemas()

    with tab_responses:
        _render_responses()


# --- Upload ---

def _render_upload():
    st.header("Upload a Questionnaire")
    st.write(
        "Upload a DOCX file and the system will extract questions into a structured form. "
        "The schema will be created as a **draft** — review, edit, and promote to **live** when ready."
    )

    uploaded_file = st.file_uploader("Choose a DOCX file", type=["docx"])

    if uploaded_file and st.button("Parse Document"):
        with st.spinner("Saving file..."):
            upload_path = save_upload(uploaded_file.name, uploaded_file.getvalue())

        with st.spinner("Parsing document with Claude AI..."):
            try:
                schema = ingest_document(str(upload_path), uploaded_file.name)
                save_schema(schema)
                total_q = sum(len(s.questions) for s in schema.sections)
                st.success(
                    f"Schema '{schema.name}' created as **draft** (v{schema.version}) "
                    f"with {total_q} questions across {len(schema.sections)} sections."
                )
                st.info("Go to **Form Schemas** tab to preview, edit questions, and promote to live.")

                _render_schema_preview(schema)

            except Exception as e:
                st.error(f"Failed to parse document: {e}")


# --- Preview (read-only) ---

def _render_schema_preview(schema):
    """Render a read-only preview of a schema."""
    with st.expander("Preview extracted schema", expanded=True):
        if schema.description:
            st.write(schema.description)
        for section in schema.sections:
            st.subheader(section.title)
            if section.description:
                st.caption(section.description)
            for q in section.questions:
                required = " *(required)*" if q.required else " *(optional)*"
                st.write(f"- **{q.text}** [`{q.field_type.value}`]{required}")
                if q.options:
                    st.caption(f"  Options: {', '.join(q.options)}")
                if q.help_text:
                    st.caption(f"  Help: {q.help_text}")


# --- Schema Editor ---

def _render_schema_editor(schema):
    """Render an editable form for a draft schema. Returns True if saved."""
    key_prefix = f"edit_{schema.id}_v{schema.version}"

    st.markdown("### Edit Schema")

    new_name = st.text_input("Form Name", value=schema.name, key=f"{key_prefix}_name")
    new_desc = st.text_area("Description", value=schema.description or "", key=f"{key_prefix}_desc")

    edited_sections = []

    for si, section in enumerate(schema.sections):
        st.divider()
        sec_key = f"{key_prefix}_s{si}"

        col_title, col_remove = st.columns([5, 1])
        with col_title:
            sec_title = st.text_input("Section Title", value=section.title, key=f"{sec_key}_title")
        with col_remove:
            st.write("")  # spacer
            remove_section = st.button("Remove Section", key=f"{sec_key}_remove")

        if remove_section:
            continue

        sec_desc = st.text_input(
            "Section Description",
            value=section.description or "",
            key=f"{sec_key}_desc",
        )

        edited_questions = []
        for qi, q in enumerate(section.questions):
            q_key = f"{sec_key}_q{qi}"
            _render_question_editor(q, q_key, edited_questions)

        # Add question button
        if st.button("+ Add Question", key=f"{sec_key}_add_q"):
            new_q = Question(
                id=str(uuid.uuid4())[:8],
                text="New Question",
                field_type=FieldType.TEXT,
            )
            edited_questions.append(new_q)

        edited_sections.append(Section(
            id=section.id,
            title=sec_title,
            description=sec_desc or None,
            questions=edited_questions,
        ))

    # Add section button
    st.divider()
    if st.button("+ Add Section", key=f"{key_prefix}_add_sec"):
        edited_sections.append(Section(
            id=str(uuid.uuid4())[:8],
            title="New Section",
            questions=[],
        ))

    # Save button
    st.divider()
    if st.button("Save Changes", key=f"{key_prefix}_save", type="primary"):
        schema.name = new_name
        schema.description = new_desc or None
        schema.sections = edited_sections
        save_schema(schema)
        st.success("Schema updated!")
        st.rerun()
        return True

    return False


def _render_question_editor(q, q_key, edited_questions):
    """Render editor for a single question. Appends to edited_questions if not removed."""
    with st.container(border=True):
        col1, col2, col3 = st.columns([4, 2, 1])

        with col1:
            new_text = st.text_input("Question", value=q.text, key=f"{q_key}_text")
        with col2:
            current_idx = FIELD_TYPE_OPTIONS.index(q.field_type.value)
            new_type = st.selectbox(
                "Type",
                FIELD_TYPE_OPTIONS,
                index=current_idx,
                key=f"{q_key}_type",
            )
        with col3:
            new_required = st.checkbox("Required", value=q.required, key=f"{q_key}_req")

        # Options (for dropdown/multi_select)
        field_type = FieldType(new_type)
        new_options = q.options
        if field_type in (FieldType.DROPDOWN, FieldType.MULTI_SELECT):
            options_str = st.text_input(
                "Options (comma-separated)",
                value=", ".join(q.options),
                key=f"{q_key}_opts",
            )
            new_options = [o.strip() for o in options_str.split(",") if o.strip()]

        # Help text
        new_help = st.text_input("Help Text", value=q.help_text or "", key=f"{q_key}_help")

        # Remove button
        col_spacer, col_remove = st.columns([5, 1])
        with col_remove:
            if st.button("Remove", key=f"{q_key}_remove"):
                return  # skip appending = question removed

        edited_questions.append(Question(
            id=q.id,
            text=new_text,
            field_type=field_type,
            options=new_options,
            required=new_required,
            help_text=new_help or None,
            section=q.section,
            conditions=q.conditions,
        ))


# --- Schemas list ---

def _status_badge(status: SchemaStatus) -> str:
    match status:
        case SchemaStatus.DRAFT:
            return "🟡 Draft"
        case SchemaStatus.LIVE:
            return "🟢 Live"
        case SchemaStatus.ARCHIVED:
            return "⚪ Archived"


def _render_schemas():
    st.header("Form Schemas")

    status_filter = st.selectbox(
        "Filter by status",
        ["All", "Draft", "Live", "Archived"],
        index=0,
    )
    status_map = {"Draft": SchemaStatus.DRAFT, "Live": SchemaStatus.LIVE, "Archived": SchemaStatus.ARCHIVED}
    status = status_map.get(status_filter)

    schemas = list_schemas(status=status)

    if not schemas:
        st.info("No schemas found. Upload a document to get started.")
        return

    for schema in schemas:
        badge = _status_badge(schema.status)
        label = f"{schema.name} (v{schema.version}) — {badge}"
        with st.expander(label):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**ID:** `{schema.id}`")
                st.write(f"**Description:** {schema.description or 'N/A'}")
                st.write(f"**Source:** {schema.source_filename or 'N/A'}")
                st.write(f"**Created:** {schema.created_at.strftime('%Y-%m-%d %H:%M')}")
                total_q = sum(len(s.questions) for s in schema.sections)
                st.write(f"**Questions:** {total_q} across {len(schema.sections)} sections")

            with col2:
                if schema.status == SchemaStatus.DRAFT:
                    if st.button("Promote to Live", key=f"promote_{schema.id}_v{schema.version}", type="primary"):
                        promote_schema(schema.id, schema.version)
                        st.success(f"v{schema.version} is now **live**!")
                        st.rerun()

                if schema.status == SchemaStatus.LIVE:
                    if st.button("Archive", key=f"archive_{schema.id}_v{schema.version}"):
                        archive_schema(schema.id, schema.version)
                        st.success(f"v{schema.version} archived.")
                        st.rerun()

                if schema.status == SchemaStatus.ARCHIVED:
                    if st.button("Re-promote to Live", key=f"repromote_{schema.id}_v{schema.version}"):
                        promote_schema(schema.id, schema.version)
                        st.success(f"v{schema.version} is now **live** again!")
                        st.rerun()

            # Draft schemas get the full editor; live/archived get read-only preview
            if schema.status == SchemaStatus.DRAFT:
                _render_schema_editor(schema)
            else:
                _render_schema_preview(schema)

            # Version history
            versions = list_schema_versions(schema.id)
            if len(versions) > 1:
                st.divider()
                st.markdown("**Version History**")
                for v in versions:
                    vbadge = _status_badge(v.status)
                    st.write(f"- v{v.version} — {vbadge} — {v.created_at.strftime('%Y-%m-%d %H:%M')}")

            # Upload new version
            st.divider()
            new_file = st.file_uploader(
                f"Upload new version for '{schema.name}'",
                type=["docx"],
                key=f"update_{schema.id}",
            )
            if new_file and st.button("Parse New Version", key=f"btn_update_{schema.id}"):
                with st.spinner("Parsing new version..."):
                    upload_path = save_upload(new_file.name, new_file.getvalue())
                    new_schema = ingest_document(str(upload_path), new_file.name)
                    new_schema.id = schema.id
                    new_schema.version = schema.version + 1
                    save_schema(new_schema)
                    st.success(f"v{new_schema.version} created as **draft**. Review and promote when ready.")
                    st.rerun()


# --- Responses ---

def _render_responses():
    st.header("Customer Responses")

    schemas = list_schemas()
    if not schemas:
        st.info("No schemas available.")
        return

    schema_options = {s.name: s.id for s in schemas}
    selected_name = st.selectbox("Filter by form", ["All"] + list(schema_options.keys()))
    schema_id = schema_options.get(selected_name) if selected_name != "All" else None

    responses = list_responses(schema_id)

    if not responses:
        st.info("No responses yet.")
        return

    for resp in responses:
        schema = load_schema(resp.schema_id, resp.schema_version)
        form_name = schema.name if schema else resp.schema_id
        status = "Signed off" if resp.signed_off else "Pending sign-off"
        label = f"{resp.customer_name or 'Unknown'} - {form_name} v{resp.schema_version} ({status})"

        with st.expander(label):
            st.write(f"**Response ID:** `{resp.id}`")
            st.write(f"**Submitted:** {resp.submitted_at.strftime('%Y-%m-%d %H:%M') if resp.submitted_at else 'N/A'}")
            st.write(f"**Schema version:** v{resp.schema_version}")

            if schema:
                st.markdown("### Answers")
                for section in schema.sections:
                    st.markdown(f"**{section.title}**")
                    for q in section.questions:
                        answer = resp.answers.get(q.id, "(no answer)")
                        if isinstance(answer, list):
                            answer = ", ".join(answer)
                        st.write(f"- {q.text}: **{answer}**")

                if st.button("Download Filled Document", key=f"dl_{resp.id}"):
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                        generate_filled_docx(schema, resp, tmp.name)
                        with open(tmp.name, "rb") as f:
                            st.download_button(
                                "Click to download",
                                f.read(),
                                file_name=f"{form_name}_{resp.customer_name or 'response'}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"dlbtn_{resp.id}",
                            )
