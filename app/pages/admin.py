"""Admin page: upload documents, manage schemas, view responses."""

import streamlit as st

from app.ingestion import ingest_document
from app.output import generate_filled_docx
from app.storage import (
    list_responses,
    list_schemas,
    load_response,
    load_schema,
    save_schema,
    save_upload,
)


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


def _render_upload():
    st.header("Upload a Questionnaire")
    st.write("Upload a DOCX file and the system will extract questions into a structured form.")

    uploaded_file = st.file_uploader("Choose a DOCX file", type=["docx"])

    if uploaded_file and st.button("Parse Document"):
        with st.spinner("Saving file..."):
            upload_path = save_upload(uploaded_file.name, uploaded_file.getvalue())

        with st.spinner("Parsing document with Claude AI..."):
            try:
                schema = ingest_document(str(upload_path), uploaded_file.name)
                save_schema(schema)
                st.success(f"Parsed successfully! Schema '{schema.name}' created with {sum(len(s.questions) for s in schema.sections)} questions across {len(schema.sections)} sections.")

                # Preview
                with st.expander("Preview extracted schema"):
                    for section in schema.sections:
                        st.subheader(section.title)
                        for q in section.questions:
                            st.write(f"- **{q.text}** ({q.field_type.value})")
                            if q.options:
                                st.write(f"  Options: {', '.join(q.options)}")

            except Exception as e:
                st.error(f"Failed to parse document: {e}")


def _render_schemas():
    st.header("Existing Form Schemas")
    schemas = list_schemas()

    if not schemas:
        st.info("No schemas yet. Upload a document to get started.")
        return

    for schema in schemas:
        with st.expander(f"{schema.name} (v{schema.version}) - {schema.source_filename}"):
            st.write(f"**ID:** {schema.id}")
            st.write(f"**Description:** {schema.description or 'N/A'}")
            st.write(f"**Created:** {schema.created_at.strftime('%Y-%m-%d %H:%M')}")
            total_q = sum(len(s.questions) for s in schema.sections)
            st.write(f"**Questions:** {total_q} across {len(schema.sections)} sections")

            for section in schema.sections:
                st.markdown(f"### {section.title}")
                for q in section.questions:
                    required = " *(required)*" if q.required else ""
                    st.write(f"- {q.text} [`{q.field_type.value}`]{required}")
                    if q.options:
                        st.caption(f"  Options: {', '.join(q.options)}")

            # Version update
            st.divider()
            new_file = st.file_uploader(
                f"Upload new version for '{schema.name}'",
                type=["docx"],
                key=f"update_{schema.id}",
            )
            if new_file and st.button("Update Schema", key=f"btn_update_{schema.id}"):
                with st.spinner("Parsing new version..."):
                    upload_path = save_upload(new_file.name, new_file.getvalue())
                    new_schema = ingest_document(str(upload_path), new_file.name)
                    new_schema.id = schema.id
                    new_schema.version = schema.version + 1
                    save_schema(new_schema)
                    st.success(f"Updated to v{new_schema.version}")
                    st.rerun()


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
        schema = load_schema(resp.schema_id)
        form_name = schema.name if schema else resp.schema_id
        status = "Signed off" if resp.signed_off else "Pending sign-off"
        label = f"{resp.customer_name or 'Unknown'} - {form_name} ({status})"

        with st.expander(label):
            st.write(f"**Response ID:** {resp.id}")
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

                # Download filled doc
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
