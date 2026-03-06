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

## Development Plan

# CREW: Modernizing Customer Information Intake

**From Static Word Forms → Structured, Guided, Auditable Intake**

> This tool ingests existing Word/PDF questionnaires, converts them into guided customer-facing forms with dropdowns and constrained fields, and outputs pre-filled documents upon submission — eliminating manual re-entry and version drift.

---

## The Problem

| Pain Point | Impact |
|---|---|
| Dozens of separate questionnaires, no single entry point | Customer confusion, inconsistent experience |
| Customers manually fill Word/PDF documents | Incomplete answers, free-text where structure is needed |
| CTLs/CSDMs manually re-interpret and re-enter data | Wasted time, transcription errors |
| No auditable sign-off mechanism | Scope creep, delivery disputes |
| Template updates don't reach customers | Teams working from stale versions |

---

## End-to-End Flow

```
Admin uploads DOCX/PDF form
        ↓
AI extracts all questions → versioned JSON schema stored
        ↓
Customer opens dynamic guided form (rendered from schema)
        ↓
Customer completes dropdowns, constrained fields, sign-off
        ↓
System generates pre-filled DOCX + PDF confirmation
        ↓
Delivery team receives structured handoff artifact
```

---

## Phase 1 — Document Ingestion & Schema Extraction
**Timeline: Weeks 1–2**

An admin uploads an existing Word or PDF questionnaire. The Claude AI layer parses the document, identifies every question, and maps each to a field type — yes/no answers become dropdowns, state fields become state pickers, free text becomes textareas. The result is a versioned JSON schema stored in the system.

**Components:**
- Admin upload interface (drag & drop DOCX/PDF)
- Claude API: document parsing → structured JSON schema
- Version store: each upload gets a version number + timestamp
- Active version flag — admin promotes a version to "live"
- Preview: admin sees the generated form before publishing

**Output:** A versioned JSON schema representing every question in the original document.

**Tech:** Claude API, Node.js/Express, file storage (S3 or local), SQLite/Postgres

---

## Phase 2 — Guided Customer Intake Form
**Timeline: Weeks 2–4**

The JSON schema from Phase 1 drives a dynamic web-based intake form. Early routing questions (solution area, environment type) determine which downstream questions appear. Customers only see what's relevant to them. All list-type fields render as dropdowns. Responses auto-save so customers can return mid-session.

**Components:**
- Dynamic form renderer (reads schema, builds UI automatically)
- Progressive disclosure engine: question visibility rules based on prior answers
- Constrained field types: dropdowns, multi-select, date pickers, textareas
- Auto-save: partial responses preserved across sessions
- Explicit sign-off step: customer confirms requirements are complete before submitting

**Output:** A structured, validated JSON response object keyed to the active schema version.

**Tech:** React, Tailwind CSS, React Hook Form or Zustand, backend response storage

---

## Phase 3 — Filled Document Output
**Timeline: Weeks 3–5**

Once a customer submits, the system maps their answers back to the original document template and generates a pre-filled Word document. This eliminates CTL/CSDM manual re-entry entirely. The completed document is emailed to both the customer (as confirmation) and the delivery team (as a structured handoff artifact).

**Components:**
- Answer-to-field mapping engine (links JSON response back to document placeholders)
- DOCX generation: pre-filled questionnaire via docxtemplater
- PDF export for read-only confirmation copy
- Download link + email delivery on submission
- Audit trail: submitter, schema version, timestamp

**Output:** A completed, pre-filled DOCX matching the original questionnaire format, with all customer answers inserted.

**Tech:** docxtemplater, pdf-lib or LibreOffice, Node.js generation service, SendGrid or internal SMTP

---

## Phase 4 — Version Management & Governance
**Timeline: Ongoing**

A lightweight admin console lets the team upload new document versions at any time. In-progress customer sessions stay on the version they started. New sessions always use the active version. All prior versions are archived and accessible for historical reference.

**Components:**
- Admin console: upload, preview, promote to live
- Version history: see which responses used which schema version
- In-progress session protection: customers mid-form are not affected by new uploads
- Change diff: see what questions changed between versions
- Rollback: re-promote any prior version if needed

**Output:** A governed, auditable version history ensuring delivery teams always know which intake version a customer responded to.

**Tech:** React admin dashboard, jsondiffpatch, immutable versioned response records in DB

---

## Delivery Timeline

| Week | Work |
|---|---|
| Week 1 | Backend setup, file upload endpoint, Claude API parsing integration |
| Week 2 | Schema storage + versioning, admin upload UI, form preview |
| Week 3 | Dynamic form renderer, progressive disclosure engine, auto-save |
| Week 4 | Submission + sign-off flow, DOCX output generation, email delivery |
| Week 5 | Admin console, version management UI, end-to-end testing |

---

## Pilot Recommendation

Start with **Data Movement or External Integrations** — the highest-friction intake area, with the most naturally structured field types (IPs, endpoints, protocols, environment names all map cleanly to dropdowns). This matches the incremental path outlined in the CREW action plan.

1. Upload the existing data movement questionnaire
2. Review the AI-generated schema — adjust any misclassified fields
3. Publish the form to 2–3 pilot customers
4. Measure: time to complete vs. old method, CTL re-entry time eliminated, submission completeness
5. Iterate schema, then expand to the next intake area

---

## Tech Stack Summary

| Layer | Technology |
|---|---|
| Document parsing | Claude API (vision + text extraction) |
| Schema storage | JSON + SQLite or Postgres |
| Admin UI | React |
| Customer form UI | React (dynamic schema renderer) |
| DOCX output | docxtemplater |
| PDF output | pdf-lib or LibreOffice |
| Backend API | Node.js / Express |
| Email delivery | SendGrid or internal SMTP |