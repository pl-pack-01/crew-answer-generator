"""Settings page: connection health checks and configuration status."""

import os
import sqlite3
from pathlib import Path

import streamlit as st

from app.database import get_db_path
from app.storage import DATA_DIR, get_file_storage


def render():
    st.title("Settings")

    _render_health_checks()
    st.divider()
    _render_configuration()


def _render_health_checks():
    st.header("Connection Health")

    col1, col2, col3 = st.columns(3)

    with col1:
        _check_database()

    with col2:
        _check_file_storage()

    with col3:
        _check_anthropic_api()


def _check_database():
    st.subheader("Database")
    try:
        db_path = get_db_path()
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Check tables exist
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t["name"] for t in tables]

        # Count records
        schema_count = conn.execute("SELECT COUNT(*) as c FROM form_schemas").fetchone()["c"]
        response_count = conn.execute("SELECT COUNT(*) as c FROM form_responses").fetchone()["c"]
        conn.close()

        st.success("Connected")
        st.caption(f"**Path:** `{db_path}`")
        st.caption(f"**Tables:** {', '.join(table_names)}")
        st.caption(f"**Schemas:** {schema_count} rows")
        st.caption(f"**Responses:** {response_count} rows")

    except Exception as e:
        st.error(f"Failed: {e}")


def _check_file_storage():
    st.subheader("File Storage")
    try:
        fs = get_file_storage()
        base = Path(fs.base_dir)
        exists = base.exists()
        writable = os.access(str(base), os.W_OK) if exists else False
        file_count = len(fs.list_keys())

        if exists and writable:
            st.success("Connected")
        elif exists:
            st.warning("Read-only")
        else:
            st.error("Directory missing")

        st.caption(f"**Path:** `{base}`")
        st.caption(f"**Writable:** {'Yes' if writable else 'No'}")
        st.caption(f"**Files:** {file_count}")

    except Exception as e:
        st.error(f"Failed: {e}")


def _check_anthropic_api():
    st.subheader("Anthropic API")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key or api_key == "your-api-key-here":
        st.error("Not configured")
        st.caption("Set `ANTHROPIC_API_KEY` in your `.env` file.")
        return

    # Mask the key for display
    masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
    st.caption(f"**Key:** `{masked}`")

    if st.button("Test Connection", key="test_api"):
        try:
            import anthropic
            client = anthropic.Anthropic()
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=10,
                messages=[{"role": "user", "content": "Say OK"}],
            )
            st.success(f"Connected — {response.model}")
        except Exception as e:
            st.error(f"Failed: {e}")
    else:
        if api_key and api_key != "your-api-key-here":
            st.success("Key configured")


def _render_configuration():
    st.header("Configuration")

    data = {
        "Data directory": str(DATA_DIR),
        "Database": str(get_db_path()),
        "Upload directory": str(DATA_DIR / "uploads"),
        "Anthropic API key": "Configured" if os.environ.get("ANTHROPIC_API_KEY", "") not in ("", "your-api-key-here") else "Not set",
    }

    for label, value in data.items():
        st.text_input(label, value=value, disabled=True, key=f"cfg_{label}")
