"""Settings page: connection health checks and configuration status."""

import os
import shutil
import sqlite3
from pathlib import Path

import streamlit as st

from app import config
from app.storage import get_file_storage, reset_file_storage


_ENV_PATH = Path(__file__).parent.parent.parent / ".env"


def _save_api_key(key: str) -> None:
    """Save API key to .env file and update the current environment."""
    os.environ["ANTHROPIC_API_KEY"] = key

    # Read existing .env or start fresh
    lines = []
    if _ENV_PATH.exists():
        lines = _ENV_PATH.read_text().splitlines()

    # Replace or append the key
    found = False
    for i, line in enumerate(lines):
        if line.startswith("ANTHROPIC_API_KEY="):
            lines[i] = f"ANTHROPIC_API_KEY={key}"
            found = True
            break
    if not found:
        lines.append(f"ANTHROPIC_API_KEY={key}")

    _ENV_PATH.write_text("\n".join(lines) + "\n")


def render():
    st.title("Settings")

    _render_health_checks()
    st.divider()
    _render_screenshot_settings()
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
        db_path = config.get_db_path()
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
        st.caption("Set your API key in the **Configuration** section below.")
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


def _render_screenshot_settings():
    from app.image_utils import DEFAULT_JPEG_QUALITY, DEFAULT_MAX_FILE_SIZE_KB, DEFAULT_MAX_WIDTH_PX

    st.header("Screenshot Settings")
    st.caption("Configure limits for question screenshot uploads. Changes apply immediately to new uploads.")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.number_input(
            "Max file size (KB)",
            min_value=50,
            max_value=5000,
            value=st.session_state.get("screenshot_max_kb", DEFAULT_MAX_FILE_SIZE_KB),
            step=50,
            key="screenshot_max_kb",
            help="Maximum size per screenshot after compression.",
        )

    with col2:
        st.number_input(
            "Max width (px)",
            min_value=200,
            max_value=3000,
            value=st.session_state.get("screenshot_max_width", DEFAULT_MAX_WIDTH_PX),
            step=100,
            key="screenshot_max_width",
            help="Images wider than this are resized down.",
        )

    with col3:
        st.number_input(
            "JPEG quality",
            min_value=20,
            max_value=100,
            value=st.session_state.get("screenshot_jpeg_quality", DEFAULT_JPEG_QUALITY),
            step=5,
            key="screenshot_jpeg_quality",
            help="Starting quality for JPEG compression (auto-reduced if needed).",
        )


def _render_configuration():
    st.header("Configuration")

    current_data_dir = config.get("data_dir")
    current_db_filename = config.get("db_filename")
    current_upload_dirname = config.get("upload_dirname")

    new_data_dir = st.text_input(
        "Data directory",
        value=current_data_dir,
        key="cfg_data_dir",
        help="Root directory for all application data (database and uploads).",
    )
    new_db_filename = st.text_input(
        "Database filename",
        value=current_db_filename,
        key="cfg_db_filename",
        help="SQLite database file name within the data directory.",
    )
    new_upload_dirname = st.text_input(
        "Upload directory name",
        value=current_upload_dirname,
        key="cfg_upload_dirname",
        help="Upload subdirectory name within the data directory.",
    )

    # --- API Key ---
    current_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    has_key = current_api_key and current_api_key != "your-api-key-here"

    if has_key and not st.session_state.get("editing_api_key"):
        masked = current_api_key[:8] + "..." + current_api_key[-4:]
        col_key, col_btn = st.columns([3, 1])
        with col_key:
            st.text_input("Anthropic API key", value=masked, disabled=True, key="cfg_api_display")
        with col_btn:
            st.write("")  # spacing
            if st.button("Change", key="cfg_api_change"):
                st.session_state["editing_api_key"] = True
                st.rerun()
    else:
        new_api_key = st.text_input(
            "Anthropic API key",
            value="",
            type="password",
            key="cfg_api_key",
            placeholder="Enter your API key" if not has_key else "Enter new API key",
            help="Your Anthropic API key. Saved to .env file.",
        )
        col_save, col_cancel = st.columns([1, 1])
        with col_save:
            if st.button("Save API Key", key="cfg_api_save", type="primary", disabled=not new_api_key):
                _save_api_key(new_api_key)
                st.session_state.pop("editing_api_key", None)
                st.success("API key saved.")
                st.rerun()
        if has_key:
            with col_cancel:
                if st.button("Cancel", key="cfg_api_cancel"):
                    st.session_state.pop("editing_api_key", None)
                    st.rerun()

    # Detect path changes
    changed = (
        new_data_dir != current_data_dir
        or new_db_filename != current_db_filename
        or new_upload_dirname != current_upload_dirname
    )

    if changed:
        old_data_dir = Path(current_data_dir)
        new_data_path = Path(new_data_dir)
        old_db = old_data_dir / current_db_filename
        new_db = new_data_path / new_db_filename
        old_uploads = old_data_dir / current_upload_dirname
        new_uploads = new_data_path / new_upload_dirname

        st.info("Configuration has changed. Choose how to apply:")

        col_save, col_move, col_cancel = st.columns(3)

        with col_save:
            if st.button("Save (don't move files)", key="cfg_save_only"):
                config.save({
                    "data_dir": new_data_dir,
                    "db_filename": new_db_filename,
                    "upload_dirname": new_upload_dirname,
                })
                reset_file_storage()
                st.success("Configuration saved. Restart the app to use the new paths.")
                st.rerun()

        with col_move:
            if st.button("Save & move files", key="cfg_save_move", type="primary"):
                try:
                    # Create new data directory
                    new_data_path.mkdir(parents=True, exist_ok=True)

                    # Move database
                    if old_db.exists() and old_db != new_db:
                        new_db.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(old_db), str(new_db))

                    # Move uploads directory
                    if old_uploads.exists() and old_uploads != new_uploads:
                        if new_uploads.exists():
                            # Merge into existing directory
                            for item in old_uploads.iterdir():
                                dest = new_uploads / item.name
                                if not dest.exists():
                                    shutil.move(str(item), str(dest))
                        else:
                            shutil.move(str(old_uploads), str(new_uploads))

                    config.save({
                        "data_dir": new_data_dir,
                        "db_filename": new_db_filename,
                        "upload_dirname": new_upload_dirname,
                    })
                    reset_file_storage()
                    st.success("Files moved and configuration saved. Restart the app to use the new paths.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to move files: {e}")

        with col_cancel:
            if st.button("Cancel", key="cfg_cancel"):
                st.rerun()
