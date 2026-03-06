"""Main Streamlit application entry point."""

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
    from app.pages.customer import render
    render()
elif page == "Admin":
    from app.pages.admin import render
    render()
