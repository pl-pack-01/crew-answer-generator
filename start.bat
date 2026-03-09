@echo off
title CREW Answer Generator
echo.
echo  ============================================
echo    CREW Answer Generator
echo  ============================================
echo.

:: Check for Python
where python >nul 2>&1 || (
    echo  [ERROR] Python is not installed or not in PATH.
    echo.
    echo  Please install Python 3.11+ from:
    echo    https://apps.microsoft.com/detail/9nrwmjp3717k
    echo.
    echo  Make sure "Add to PATH" is checked during install.
    echo.
    pause
    exit /b 1
)

:: Show Python version
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo  Found %PYVER%

:: Create virtual environment if it doesn't exist
if not exist ".venv\Scripts\activate.bat" (
    echo.
    echo  Setting up virtual environment ^(first time only^)...
    python -m venv .venv || (
        echo  [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate virtual environment
call .venv\Scripts\activate.bat

:: Install/update dependencies
echo.
echo  Checking dependencies...
pip install -r requirements.txt --quiet --disable-pip-version-check || (
    echo  [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

:: Check for .env file
if not exist ".env" (
    if exist ".env.example" (
        echo.
        echo  [NOTE] No .env file found. Creating from .env.example...
        copy .env.example .env >nul
        echo  Please edit .env and add your Anthropic API key.
        echo  The app will work without it, but document parsing requires the API key.
        echo.
    )
)

:: Launch the app
echo.
echo  Starting CREW Answer Generator...
echo  The app will open in your browser at http://localhost:8501
echo.
echo  Press Ctrl+C to stop the server.
echo.
streamlit run app/main.py
