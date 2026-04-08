"""Admin page: upload documents, manage schemas, view responses."""

import json
import uuid

import streamlit as st

from app.html_export import generate_html_form
from app.image_utils import process_screenshot
from app.ingestion import ingest_document
from app.models import FieldType, FormResponse, Question, ResponseStatus, SchemaStatus, Section
from app.output import generate_filled_docx
from app.schema_io import export_schema_bundle, import_schema, import_schema_bundle
from app.storage import (
    archive_schema,
    create_new_version,
    delete_schema,
    fork_schema,
    get_file_storage,
    list_responses,
    list_schema_versions,
    list_schemas,
    load_live_schema,
    load_schema,
    promote_schema,
    save_response,
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

    if "upload_docx_key" not in st.session_state:
        st.session_state["upload_docx_key"] = 0

    uploaded_file = st.file_uploader("Choose a DOCX file", type=["docx"], key=f"upload_docx_{st.session_state['upload_docx_key']}")

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
                st.session_state["upload_docx_key"] += 1

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
    needs_autosave = False

    # Check for pending section/question removals (saved before rerun)
    pending_remove = st.session_state.pop(f"{key_prefix}_pending_remove", None)
    if pending_remove:
        rtype, rid = pending_remove
        if rtype == "section":
            schema.sections = [s for s in schema.sections if s.id != rid]
        elif rtype == "question":
            for sec in schema.sections:
                sec.questions = [q for q in sec.questions if q.id != rid]
        schema.name = new_name
        schema.description = new_desc or None
        save_schema(schema)
        st.rerun()
        return True

    # Check for pending screenshot removal
    pending_ss_clear = st.session_state.pop(f"{key_prefix}_pending_screenshot_clear", None)
    if pending_ss_clear:
        for sec in schema.sections:
            for q in sec.questions:
                if q.id == pending_ss_clear:
                    q.screenshot_b64 = None
        save_schema(schema)
        st.rerun()
        return True

    for section in schema.sections:
        st.divider()
        sec_key = f"{key_prefix}_s{section.id}"
        confirm_sec_key = f"{sec_key}_confirm_remove"

        col_title, col_remove = st.columns([5, 1])
        with col_title:
            sec_title = st.text_input("Section Title", value=section.title, key=f"{sec_key}_title")
        with col_remove:
            st.write("")  # spacer
            if not st.session_state.get(confirm_sec_key):
                if st.button("Remove Section", key=f"{sec_key}_remove"):
                    st.session_state[confirm_sec_key] = True
                    st.rerun()

        if st.session_state.get(confirm_sec_key):
            col_msg, col_yes, col_no = st.columns([3, 1, 1])
            with col_msg:
                st.warning("Remove this section?")
            with col_yes:
                if st.button("Yes, remove", key=f"{sec_key}_yes", type="primary"):
                    st.session_state.pop(confirm_sec_key, None)
                    st.session_state[f"{key_prefix}_pending_remove"] = ("section", section.id)
                    st.rerun()
            with col_no:
                if st.button("Cancel", key=f"{sec_key}_no"):
                    st.session_state.pop(confirm_sec_key, None)
                    st.rerun()

        sec_desc = st.text_input(
            "Section Description",
            value=section.description or "",
            key=f"{sec_key}_desc",
        )

        edited_questions = []
        for q in section.questions:
            q_key = f"{sec_key}_q{q.id}"
            if _render_question_editor(q, q_key, edited_questions, key_prefix):
                pass  # removal handled via pending_remove + rerun

        # Add question button
        if st.button("+ Add Question", key=f"{sec_key}_add_q"):
            new_q = Question(
                id=str(uuid.uuid4())[:8],
                text="New Question",
                field_type=FieldType.TEXT,
            )
            edited_questions.append(new_q)
            needs_autosave = True

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
        needs_autosave = True  # reuse flag to trigger auto-save

    # Auto-save when a section or question was added/removed
    if needs_autosave:
        schema.name = new_name
        schema.description = new_desc or None
        schema.sections = edited_sections
        save_schema(schema)
        st.rerun()
        return True

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


def _render_question_editor(q, q_key, edited_questions, key_prefix="") -> bool:
    """Render editor for a single question. Appends to edited_questions if not removed.

    Returns True if the question was removed.
    """
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

        # Screenshot
        new_screenshot = q.screenshot_b64
        if q.screenshot_b64:
            col_img, col_clear = st.columns([4, 1])
            with col_img:
                st.image(q.screenshot_b64, caption="Current screenshot", width=200)
            with col_clear:
                if st.button("Remove screenshot", key=f"{q_key}_remove_screenshot"):
                    q.screenshot_b64 = None
                    new_screenshot = None
                    # Find and save the schema immediately
                    st.session_state[f"{key_prefix}_pending_screenshot_clear"] = q.id
                    st.rerun()
        screenshot_file = st.file_uploader(
            "Upload screenshot",
            type=["png", "jpg", "jpeg", "gif"],
            key=f"{q_key}_screenshot",
        )
        if screenshot_file:
            try:
                new_screenshot = process_screenshot(screenshot_file.getvalue())
            except ValueError as e:
                st.error(str(e))

        # Remove button
        confirm_q_key = f"{q_key}_confirm_remove"
        col_spacer, col_remove = st.columns([5, 1])
        with col_remove:
            if not st.session_state.get(confirm_q_key):
                if st.button("Remove", key=f"{q_key}_remove"):
                    st.session_state[confirm_q_key] = True
                    st.rerun()

        if st.session_state.get(confirm_q_key):
            col_msg, col_yes, col_no = st.columns([3, 1, 1])
            with col_msg:
                st.warning("Remove this question?")
            with col_yes:
                if st.button("Yes, remove", key=f"{q_key}_yes", type="primary"):
                    st.session_state.pop(confirm_q_key, None)
                    st.session_state[f"{key_prefix}_pending_remove"] = ("question", q.id)
                    st.rerun()
            with col_no:
                if st.button("Cancel", key=f"{q_key}_no"):
                    st.session_state.pop(confirm_q_key, None)
                    st.rerun()

        edited_questions.append(Question(
            id=q.id,
            text=new_text,
            field_type=field_type,
            options=new_options,
            required=new_required,
            help_text=new_help or None,
            screenshot_b64=new_screenshot,
            section=q.section,
            conditions=q.conditions,
        ))
        return False


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

    # --- Import Schema ---
    with st.expander("Import Schema"):
        if "import_schema_key" not in st.session_state:
            st.session_state["import_schema_key"] = 0
        uploaded_schema = st.file_uploader(
            "Upload a schema file (.zip bundle or .json)",
            type=["zip", "json"],
            key=f"import_schema_{st.session_state['import_schema_key']}",
        )
        if uploaded_schema and st.button("Import Schema", key="btn_import_schema"):
            try:
                raw = uploaded_schema.getvalue()
                if uploaded_schema.name.endswith(".zip"):
                    schema, doc_bytes = import_schema_bundle(raw)
                    if doc_bytes is not None and schema.source_filename:
                        save_upload(schema.source_filename, doc_bytes)
                else:
                    schema = import_schema(raw.decode("utf-8-sig"))
                    doc_bytes = None
                save_schema(schema)
                total_q = sum(len(s.questions) for s in schema.sections)
                st.session_state["import_schema_key"] += 1
                doc_note = " (source document restored)" if doc_bytes is not None else ""
                st.success(
                    f"Imported **{schema.name}** v{schema.version} as draft "
                    f"with {total_q} questions across {len(schema.sections)} sections{doc_note}. "
                    f"Review and promote when ready."
                )
                st.rerun()
            except (ValueError, Exception) as e:
                st.error(f"Failed to import schema: {e}")

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

                    confirm_del_key = f"confirm_delete_{schema.id}_v{schema.version}"
                    if st.session_state.get(confirm_del_key):
                        st.warning("Delete this draft?")
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("Yes, delete", key=f"del_yes_{schema.id}_v{schema.version}", type="primary"):
                                st.session_state.pop(confirm_del_key, None)
                                delete_schema(schema.id, schema.version)
                                st.rerun()
                        with col_no:
                            if st.button("Cancel", key=f"del_no_{schema.id}_v{schema.version}"):
                                st.session_state.pop(confirm_del_key, None)
                                st.rerun()
                    else:
                        if st.button("Delete Draft", key=f"delete_{schema.id}_v{schema.version}"):
                            st.session_state[confirm_del_key] = True
                            st.rerun()

                # Export Schema bundle (available for all statuses)
                # Include the source document if it was stored locally.
                _doc_bytes = None
                if schema.source_filename:
                    _doc_bytes = get_file_storage().load(schema.source_filename)
                _bundle = export_schema_bundle(schema, _doc_bytes)
                _safe_name = schema.name.replace(" ", "_")
                st.download_button(
                    "Export Schema",
                    _bundle,
                    file_name=f"{_safe_name}_v{schema.version}_schema.zip",
                    mime="application/zip",
                    key=f"export_schema_{schema.id}_v{schema.version}",
                )

                if schema.status == SchemaStatus.LIVE:
                    if st.button("Archive", key=f"archive_{schema.id}_v{schema.version}"):
                        archive_schema(schema.id, schema.version)
                        st.success(f"v{schema.version} archived.")
                        st.rerun()

                    html_content = generate_html_form(schema)
                    st.download_button(
                        "Export as HTML",
                        html_content,
                        file_name=f"{schema.name.replace(' ', '_')}_form.html",
                        mime="text/html",
                        key=f"export_html_{schema.id}_v{schema.version}",
                    )

                if schema.status == SchemaStatus.ARCHIVED:
                    if st.button("Re-promote to Live", key=f"repromote_{schema.id}_v{schema.version}"):
                        promote_schema(schema.id, schema.version)
                        st.success(f"v{schema.version} is now **live** again!")
                        st.rerun()

            if schema.status in (SchemaStatus.LIVE, SchemaStatus.ARCHIVED):
                st.divider()
                st.markdown("**Create New Version**")
                clone_name = st.text_input(
                    "Form name",
                    value=schema.name,
                    key=f"clone_name_{schema.id}_v{schema.version}",
                    help="Keep the same name to create a new version. Change the name to fork into a separate form.",
                )
                if st.button("Create", key=f"clone_{schema.id}_v{schema.version}"):
                    if clone_name.strip() and clone_name.strip() != schema.name:
                        new_schema = fork_schema(schema.id, schema.version, clone_name.strip())
                        st.success(
                            f"New form '{new_schema.name}' (v1) created as **draft** "
                            f"from '{schema.name}' v{schema.version}."
                        )
                    else:
                        new_schema = create_new_version(schema.id, schema.version)
                        st.success(f"v{new_schema.version} created as **draft** from v{schema.version}.")
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
            update_key = f"update_docx_key_{schema.id}"
            if update_key not in st.session_state:
                st.session_state[update_key] = 0
            new_file = st.file_uploader(
                f"Upload new version for '{schema.name}'",
                type=["docx"],
                key=f"update_{schema.id}_{st.session_state[update_key]}",
            )
            if new_file and st.button("Parse New Version", key=f"btn_update_{schema.id}"):
                with st.spinner("Parsing new version..."):
                    upload_path = save_upload(new_file.name, new_file.getvalue())
                    new_schema = ingest_document(str(upload_path), new_file.name)
                    new_schema.id = schema.id
                    new_schema.version = schema.version + 1
                    save_schema(new_schema)
                    st.session_state[update_key] += 1
                    st.success(f"v{new_schema.version} created as **draft**. Review and promote when ready.")
                    st.rerun()


# --- Responses ---

def _render_responses():
    st.header("Customer Responses")

    # --- Import JSON response ---
    with st.expander("Import JSON response"):
        if "import_json_key" not in st.session_state:
            st.session_state["import_json_key"] = 0
        uploaded_json = st.file_uploader("Upload a JSON response file", type=["json"], key=f"import_json_{st.session_state['import_json_key']}")
        if uploaded_json and st.button("Import", key="btn_import_json"):
            try:
                data = json.loads(uploaded_json.getvalue())
                schema = load_schema(data["schema_id"], data["schema_version"])
                if not schema:
                    st.error(f"Schema {data['schema_id']} v{data['schema_version']} not found in the database.")
                else:
                    from datetime import datetime
                    status = ResponseStatus.SUBMITTED if data.get("status") == "submitted" else ResponseStatus.DRAFT
                    now = datetime.now()
                    response = FormResponse(
                        schema_id=data["schema_id"],
                        schema_version=data["schema_version"],
                        status=status,
                        customer_name=data.get("customer_name"),
                        answers=data.get("answers", {}),
                        submitted_at=now if status == ResponseStatus.SUBMITTED else None,
                        signed_off=data.get("signed_off", False),
                        signed_off_at=now if data.get("signed_off") else None,
                        opened_at=now,
                        first_saved_at=now,
                        completed_at=now if status == ResponseStatus.SUBMITTED else None,
                    )
                    save_response(response)
                    st.session_state["import_json_key"] += 1
                    st.success(
                        f"Imported response from **{response.customer_name or 'Unknown'}** "
                        f"for **{schema.name}** v{schema.version} ({status.value})."
                    )
                    st.rerun()
            except (json.JSONDecodeError, KeyError) as e:
                st.error(f"Invalid JSON file: {e}")

    st.divider()

    schemas = list_schemas()
    if not schemas:
        st.info("No schemas available.")
        return

    schema_options = {s.name: s.id for s in schemas}
    selected_name = st.selectbox("Filter by form", ["All"] + list(schema_options.keys()))
    schema_id = schema_options.get(selected_name) if selected_name != "All" else None

    tab_active, tab_archived = st.tabs(["Active", "Archived"])

    with tab_active:
        responses = list_responses(schema_id, exclude_status=ResponseStatus.ARCHIVED)
        if not responses:
            st.info("No active responses.")
        else:
            for resp in responses:
                _render_response_card(resp, archived=False)

    with tab_archived:
        archived = list_responses(schema_id, status=ResponseStatus.ARCHIVED)
        if not archived:
            st.info("No archived responses.")
        else:
            for resp in archived:
                _render_response_card(resp, archived=True)


def _format_duration(delta) -> str:
    """Format a timedelta as a human-readable string like '2d 3h 15m'."""
    total_seconds = int(delta.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s"
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def _response_status_badge(resp: FormResponse) -> str:
    if resp.status == ResponseStatus.ARCHIVED:
        return "⚪ Archived"
    if resp.signed_off:
        return "🟢 Signed off"
    if resp.status == ResponseStatus.SUBMITTED:
        return "🟡 Pending sign-off"
    return "⚪ Draft"


def _render_response_card(resp: FormResponse, archived: bool = False):
    from datetime import datetime

    schema = load_schema(resp.schema_id, resp.schema_version)
    form_name = schema.name if schema else resp.schema_id
    badge = _response_status_badge(resp)
    output_icon = "📄" if resp.output_generated else "—"
    label = f"{resp.customer_name or 'Unknown'} — {form_name} v{resp.schema_version} — {badge} — Output: {output_icon}"

    with st.expander(label):
        col_info, col_actions = st.columns([3, 1])

        with col_info:
            st.write(f"**Response ID:** `{resp.id}`")
            st.write(f"**Schema version:** v{resp.schema_version}")

            # Timeline
            st.write(f"**Opened:** {resp.opened_at.strftime('%Y-%m-%d %H:%M') if resp.opened_at else 'N/A'}")
            st.write(f"**First saved:** {resp.first_saved_at.strftime('%Y-%m-%d %H:%M') if resp.first_saved_at else 'N/A'}")
            st.write(f"**Completed:** {resp.completed_at.strftime('%Y-%m-%d %H:%M') if resp.completed_at else 'N/A'}")

            # Durations between stages
            if resp.opened_at and resp.first_saved_at:
                st.write(f"**Time to first save:** {_format_duration(resp.first_saved_at - resp.opened_at)}")
            if resp.first_saved_at and resp.completed_at:
                st.write(f"**First save to completion:** {_format_duration(resp.completed_at - resp.first_saved_at)}")
            if resp.opened_at and resp.completed_at:
                st.write(f"**Total duration:** {_format_duration(resp.completed_at - resp.opened_at)}")

            if resp.output_generated:
                st.write(f"**Output generated:** {resp.output_generated_at.strftime('%Y-%m-%d %H:%M') if resp.output_generated_at else 'Yes'}")

        with col_actions:
            if archived:
                if st.button("Unarchive", key=f"unarchive_{resp.id}"):
                    resp.status = ResponseStatus.SUBMITTED
                    save_response(resp)
                    st.rerun()
            else:
                if resp.status == ResponseStatus.SUBMITTED:
                    if st.button("Archive", key=f"archive_resp_{resp.id}"):
                        resp.status = ResponseStatus.ARCHIVED
                        save_response(resp)
                        st.rerun()

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

                    # Mark output as generated
                    if not resp.output_generated:
                        resp.output_generated = True
                        resp.output_generated_at = datetime.now()
                        save_response(resp)

                    with open(tmp.name, "rb") as f:
                        st.download_button(
                            "Click to download",
                            f.read(),
                            file_name=f"{form_name}_{resp.customer_name or 'response'}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"dlbtn_{resp.id}",
                        )
