# CREW Answer Generator

Modernizing customer information intake from static Word/Excel questionnaires to a structured, guided intake system.

## Problem

- Customers navigate dozens of separate questionnaires with no single front door
- Information is manually interpreted, reformatted, and re-entered by delivery teams
- No consistent mechanism for customer sign-off on finalized requirements
- Updating templates doesn't guarantee customers use the latest version

## Solution

A 3-layer system: **Document Ingestion** > **Interactive Customer Form** > **Filled Document Output**

### Document Ingestion (Admin)
Upload a DOCX questionnaire and the Claude API automatically extracts all questions into a structured, versioned JSON schema. Field types (dropdown, yes/no, text, date, etc.) are detected intelligently.

### Customer Intake Form
A dynamic form rendered from the schema with:
- Progressive disclosure (customers only see relevant questions)
- Constrained fields (dropdowns, multi-select, date pickers)
- Required field validation
- Explicit sign-off confirmation

### Filled Document Output
Customer answers are merged back into a generated DOCX document, ready for download — no manual re-entry required.

## Setup

### Prerequisites
- Python 3.11+
- An Anthropic API key

### Install

```bash
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
```

Edit `.env` and add your Anthropic API key:

```
ANTHROPIC_API_KEY=your-api-key-here
```

### Run

```bash
streamlit run app/main.py
```

The app will be available at `http://localhost:8501`.

## Usage

### Admin Workflow
1. Navigate to **Admin** in the sidebar
2. Upload a DOCX questionnaire under **Upload Document**
3. Review the extracted schema (questions, field types, sections)
4. To update a form, upload a new version under **Form Schemas** — previous versions are preserved

### Customer Workflow
1. Navigate to **Customer Intake** in the sidebar
2. Select a form and fill out the guided questions
3. Confirm and submit
4. Admin can download the filled document from **Customer Responses**

## Project Structure

```
crew-answer-generator/
├── app/
│   ├── main.py          # Streamlit entry point
│   ├── models.py        # Pydantic data models
│   ├── storage.py       # JSON file-based storage with versioning
│   ├── ingestion.py     # DOCX parsing + Claude API extraction
│   ├── output.py        # Filled DOCX generation
│   └── pages/
│       ├── admin.py     # Admin UI (upload, manage, view responses)
│       └── customer.py  # Customer-facing guided form
├── tests/               # pytest test suite
├── data/                # Runtime data (schemas, responses, uploads) - gitignored
├── requirements.txt
├── .env.example
└── .gitignore
```

## Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

## Tech Stack

- **Streamlit** — frontend UI
- **Claude API** — document parsing and question extraction
- **python-docx** — DOCX reading and generation
- **Pydantic** — data validation and serialization
- **JSON files** — schema and response storage (versioned)
