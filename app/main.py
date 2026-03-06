"""Main Streamlit application entry point."""

import sys
from pathlib import Path

# Ensure the project root is on the Python path so 'app' is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="CREW Answer Generator",
    page_icon="📋",
    layout="wide",
)

# Initialize database on first run
from app.storage import setup
setup()

# Sidebar navigation
page = st.sidebar.radio(
    "Navigation",
    ["Customer Intake", "Admin"],
    index=0,
)

if page == "Customer Intake":
    from app.views.customer import render
    render()
elif page == "Admin":
    from app.views.admin import render
    render()
