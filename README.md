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
Upload a DOCX questionnaire and the Claude API automatically extracts all questions into a structured, versioned schema stored in SQLite. Field types (dropdown, yes/no, text, date, etc.) are detected intelligently. Admins can edit any question before promoting to live.

### Customer Intake Form
A dynamic form rendered from the schema with:
- Progressive disclosure (customers only see relevant questions)
- Constrained fields (dropdowns, multi-select, date pickers)
- Required field validation
- Explicit sign-off confirmation
- Only **live** schemas are visible to customers

### Filled Document Output
Customer answers are merged back into a generated DOCX document, ready for download — no manual re-entry required. Each response is permanently tied to the schema version it was submitted against.

## Setup

### Prerequisites
- Python 3.11+ ([Windows](https://apps.microsoft.com/detail/9nrwmjp3717k) · [macOS/Linux](https://www.python.org/downloads/)) — make sure "Add to PATH" is checked during install
- An Anthropic API key ([get one here](https://console.anthropic.com/)) — needed for document parsing, optional for everything else

### Quick Start (Recommended)

The launcher script handles everything automatically — virtual environment, dependencies, and starting the app.

**Windows:** Double-click `start.bat` (or run it from a terminal)

**macOS/Linux:**
```bash
chmod +x start.sh   # first time only
./start.sh
```

On first run, the script will:
1. Create a virtual environment
2. Install all dependencies
3. Create a `.env` file from the example (edit it to add your API key)
4. Launch the app in your browser

### Manual Setup

If you prefer to set things up manually:

**Windows:**
```powershell
git clone <repo-url>
cd crew-answer-generator
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Edit .env and add your Anthropic API key
streamlit run app/main.py
```

**macOS/Linux:**
```bash
git clone <repo-url>
cd crew-answer-generator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your Anthropic API key
streamlit run app/main.py
```

### After Launch

The app will be available at `http://localhost:8501`.

## Usage

### Admin Workflow
1. Navigate to **Admin** in the sidebar
2. **Upload Document** — upload a DOCX, Claude AI parses it into a structured schema (created as **draft**)
3. **Form Schemas** — review the extracted questions, edit anything (text, field types, options, sections), then **Promote to Live**
4. **Create New Version** — clone a live or archived schema into a new editable draft. Keep the same name to create a new version, or change the name to fork it into an independent form (still linked to the original source document)
5. Upload new versions at any time — previous versions are preserved and archived automatically
6. **Export as HTML** — download a self-contained HTML form for any live schema. Send it to customers to fill out offline — no hosting required
7. **Customer Responses** — view submissions, download filled DOCX documents, or **Import JSON** responses returned from exported HTML forms
8. **Settings** — view connection health (database, file storage, Anthropic API), configure screenshot upload limits, and manage data storage paths (with option to move existing files)

### Customer Workflow (Online)
1. Navigate to **Customer Intake** in the sidebar
2. Select a form (only live schemas appear) and fill out the guided questions
3. **Save Draft** at any time — a unique draft code is generated (e.g. `A1B2C3D4`) that can be used to resume later
4. To resume, expand **Resume a saved draft** and enter the draft code
5. Confirm accuracy and submit
6. Admin can download the filled document from **Customer Responses**

### Customer Workflow (Offline via HTML Export)
1. Admin exports a live form as a standalone HTML file and sends it to the customer
2. Customer opens the HTML file in any browser — no install or internet required
3. Customer fills out the form, with progressive disclosure and validation built in
4. Customer clicks **Submit** (or **Save Draft**) to download a JSON file
5. Customer sends the JSON file back to the admin
6. Admin imports the JSON file via **Customer Responses > Import JSON response**

## Project Structure

```
crew-answer-generator/
├── app/
│   ├── main.py          # Streamlit entry point
│   ├── models.py        # Pydantic data models (Question, Section, FormSchema, FormResponse)
│   ├── database.py      # SQLite storage layer (swappable to PostgreSQL)
│   ├── file_storage.py  # File storage abstraction (local, swappable to S3)
│   ├── storage.py       # Facade over database + file storage
│   ├── ingestion.py     # DOCX parsing + Claude API extraction
│   ├── output.py        # Filled DOCX generation
│   ├── html_export.py   # Self-contained HTML form generator
│   ├── image_utils.py   # Screenshot processing (resize, compress, base64)
│   ├── config.py        # Persistent app configuration (data paths)
│   └── views/
│       ├── admin.py     # Admin UI (upload, edit, promote, view responses)
│       ├── customer.py  # Customer-facing guided form
│       └── settings.py  # Settings, screenshot config, path management & health checks
├── tests/               # pytest test suite (83 tests)
├── data/                # Runtime data (SQLite DB, uploads) — gitignored, path configurable
├── .streamlit/
│   ├── config.toml      # Streamlit UI settings
│   └── app_config.json  # Local path configuration — gitignored
├── start.bat            # One-click launcher (Windows)
├── start.sh             # One-click launcher (macOS/Linux)
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

| Layer | Technology |
|---|---|
| Frontend UI | Streamlit (Python) |
| Document parsing | Claude API (text extraction + field type detection) |
| DOCX reading/generation | python-docx |
| Data validation | Pydantic |
| Database | SQLite (designed for PostgreSQL swap) |
| File storage | Local filesystem (designed for S3 swap) |

## Development Plan

### End-to-End Flow

```
Admin uploads DOCX form
        ↓
AI extracts all questions → versioned schema stored in SQLite (draft)
        ↓
Admin reviews, edits questions, promotes to live
        ↓
Customer opens dynamic guided form (rendered from live schema)
        ↓
Customer completes dropdowns, constrained fields, sign-off
        ↓
System generates pre-filled DOCX
        ↓
Delivery team receives structured handoff artifact
```

### Phase 1 — Document Ingestion & Schema Extraction [COMPLETE]

Admin uploads an existing Word questionnaire. The Claude AI layer parses the document, identifies every question, and maps each to a field type. The result is a versioned schema stored in SQLite.

- Admin upload interface (DOCX)
- Claude API: document parsing to structured schema
- SQLite storage with version tracking
- Draft/live/archived status lifecycle
- Admin can edit questions, field types, options, sections before promoting
- Preview before publish

### Phase 2 — Guided Customer Intake Form [COMPLETE]

The schema drives a dynamic Streamlit form. Routing questions determine which downstream questions appear. Only live schemas are visible to customers.

- Dynamic form renderer (reads schema, builds UI automatically)
- Progressive disclosure: question visibility rules based on prior answers
- Constrained field types: dropdowns, multi-select, date pickers, textareas
- Explicit sign-off step
- Responses tied to specific schema version

### Phase 3 — Filled Document Output [COMPLETE]

Customer answers are mapped back and a pre-filled DOCX is generated. Responses are permanently tied to the schema version they were submitted against.

- DOCX generation with all Q&A pairs, section headings, customer info
- Download from admin responses tab
- Audit trail: submitter, schema version, timestamp, sign-off status

### Phase 4 — Version Management & Governance [COMPLETE]

Admin console for full lifecycle management. New uploads create new draft versions. Promoting a version automatically archives the previous live version.

- Upload new versions — previous versions preserved
- Create new version from any live or archived schema (clone into editable draft)
- Fork a schema into a new independent form with a different name (retains link to original source document)
- Promote / archive / re-promote workflow
- Version history visible per schema
- Responses reference the exact version they were submitted against

### Phase 5 — Draft Save & Resume [COMPLETE]

Customers can save their progress at any time and resume later using a unique draft code. Drafts are stored in the database alongside submitted responses.

- Save Draft button generates a unique 8-character code
- Resume a draft by entering the code on the Customer Intake page
- Saved answers pre-fill all form fields on resume
- Submitting a draft transitions it to submitted status
- Draft code is unique per response — no account or login required

### Phase 6 — HTML Export & JSON Import [COMPLETE]

Forms can be distributed to customers as self-contained HTML files — no hosting, no install, no internet required. Customers fill them out in any browser and return a JSON file.

- Export any live schema as a standalone HTML form (single file, all CSS/JS inline)
- HTML form supports all field types, progressive disclosure, and validation
- Submit downloads a JSON file; Save Draft downloads a partial JSON file
- Import JSON responses back into the system via the admin Customer Responses tab
- Imported responses are linked to the correct schema and version

### Phase 7 — Question Screenshots [COMPLETE]

Admins can attach a screenshot to any question as a visual hint for customers. Images are stored as base64 inside the schema JSON — no extra files or tables.

- Upload PNG/JPG/GIF screenshots per question in the admin schema editor
- Images auto-resized and compressed to stay within configurable limits
- Customers see a "Screenshot" popover button next to questions that have one
- HTML export embeds screenshots as base64 data URIs with a clickable dialog
- Configurable limits in Settings: max file size (default 500KB), max width (default 800px), JPEG quality (default 85)

### Phase 8 — Configurable Storage Paths [COMPLETE]

Data directory, database filename, and upload directory are configurable from the Settings page. Changes can optionally move existing files to the new location.

- Edit data directory, database filename, and upload directory in Settings
- **Save (don't move files)** — point the app at a new location without touching existing files
- **Save & move files** — relocate the database and uploads to the new path automatically
- Configuration persisted in `.streamlit/app_config.json` (gitignored, machine-specific)
- Defaults remain `data/crew.db` and `data/uploads/` if no config file exists

### Remaining Work

- PDF export for read-only confirmation copy
- Email delivery on submission (SendGrid or internal SMTP)
- Change diff: see what questions changed between versions
- Rollback: re-promote any prior version (partially implemented — archived versions can be re-promoted)

## Pilot Recommendation

Start with **Data Movement or External Integrations** — the highest-friction intake area, with the most naturally structured field types (IPs, endpoints, protocols, environment names all map cleanly to dropdowns).

1. Upload the existing data movement questionnaire
2. Review the AI-generated schema — adjust any misclassified fields in the editor
3. Promote to live and share with 2-3 pilot customers
4. Measure: time to complete vs. old method, CTL re-entry time eliminated, submission completeness
5. Iterate schema, then expand to the next intake area
