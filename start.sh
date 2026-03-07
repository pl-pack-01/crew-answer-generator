#!/usr/bin/env bash
set -e

echo
echo "  ============================================"
echo "    CREW Answer Generator"
echo "  ============================================"
echo

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "  [ERROR] Python 3 is not installed."
    echo
    echo "  Install it with:"
    echo "    brew install python@3.11"
    echo "  Or download from https://www.python.org/downloads/"
    echo
    exit 1
fi

# Show Python version
PYVER=$(python3 --version 2>&1)
echo "  Found $PYVER"

# Create virtual environment if it doesn't exist
if [ ! -f ".venv/bin/activate" ]; then
    echo
    echo "  Setting up virtual environment (first time only)..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install/update dependencies
echo
echo "  Checking dependencies..."
pip install -r requirements.txt --quiet --disable-pip-version-check

# Check for .env file
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    echo
    echo "  [NOTE] No .env file found. Creating from .env.example..."
    cp .env.example .env
    echo "  Please edit .env and add your Anthropic API key."
    echo "  The app will work without it, but document parsing requires the API key."
    echo
fi

# Launch the app
echo
echo "  Starting CREW Answer Generator..."
echo "  The app will open in your browser at http://localhost:8501"
echo
echo "  Press Ctrl+C to stop the server."
echo
streamlit run app/main.py
