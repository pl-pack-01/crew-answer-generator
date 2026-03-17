# CREW Answer Generator

Modernizing customer information intake from static Word/Excel questionnaires to a structured, guided intake system.

**Docker image:** `ghcr.io/pl-pack-01/crew-answer-generator`

```bash
docker pull ghcr.io/pl-pack-01/crew-answer-generator:main
```

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
Customer answers are merged back into a generated DOCX document, ready for download — no manual re-entry required. All questions from the schema are included; questions hidden by progressive disclosure are marked as *N/A — Not applicable based on responses*. Each response is permanently tied to the schema version it was submitted against.

## Setup

### Prerequisites
- Python 3.11+ ([Windows](https://apps.microsoft.com/detail/9nrwmjp3717k) · [macOS/Linux](https://www.python.org/downloads/)) — make sure "Add to PATH" is checked during install
- An Anthropic API key ([get one here](https://console.anthropic.com/)) — needed for document parsing, optional for everything else. Enter it in **Settings** after launching the app

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
3. Create a `.env` file from the example
4. Launch the app in your browser
5. Go to **Settings** in the sidebar and enter your Anthropic API key

### Manual Setup

If you prefer to set things up manually:

**Windows:**
```powershell
git clone <repo-url>
cd crew-answer-generator
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app/main.py
# Go to Settings in the sidebar to enter your Anthropic API key
```

**macOS/Linux:**
```bash
git clone <repo-url>
cd crew-answer-generator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app/main.py
# Go to Settings in the sidebar to enter your Anthropic API key
```

### Docker

Build and run as a container — no Python install required.

```bash
docker build -t crew-answer-generator .
docker run -d -p 8501:8501 -e ANTHROPIC_API_KEY=your-key-here -v crew-data:/app/data --name crew crew-answer-generator
```

The `-d` flag runs the container in the background — no terminal needed. The `-v crew-data:/app/data` volume mount persists the database and uploaded files across container restarts.

```bash
docker logs crew        # view logs
docker stop crew        # stop the container
docker start crew       # restart it later
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
7. **Export Schema** — download a schema as JSON to share with other team members or instances. Available for any schema status (draft, live, archived)
8. **Import Schema** — upload a schema JSON file (from another CTL or instance) to create a new draft. Review, edit, and promote as usual
9. **Customer Responses** — view active and archived submissions, download filled DOCX documents, track output generation status, archive completed responses, or **Import JSON** responses returned from exported HTML forms
10. **Settings** — view connection health (database, file storage, Anthropic API), set your Anthropic API key, configure screenshot upload limits, and manage data storage paths (with option to move existing files)

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
│   ├── schema_io.py     # Schema export/import (JSON serialization for sharing)
│   ├── config.py        # Persistent app configuration (data paths)
│   └── views/
│       ├── admin.py     # Admin UI (upload, edit, promote, view responses)
│       ├── customer.py  # Customer-facing guided form
│       └── settings.py  # Settings, screenshot config, path management & health checks
├── tests/               # pytest test suite
├── data/                # Runtime data (SQLite DB, uploads) — gitignored, path configurable
├── .streamlit/
│   ├── config.toml      # Streamlit UI settings
│   └── app_config.json  # Local path configuration — gitignored
├── .github/
│   └── workflows/
│       └── build.yml    # CI/CD: test, build Docker image, push to GHCR
├── start.bat            # One-click launcher (Windows)
├── start.sh             # One-click launcher (macOS/Linux)
├── Dockerfile           # Container image definition
├── .dockerignore        # Files excluded from Docker build
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
- Questions hidden by progressive disclosure marked as *N/A — Not applicable*
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

### Phase 9 — Response Archival & Output Tracking [COMPLETE]

Customer responses can be archived once completed and tracked for whether the output document has been generated.

- **Active / Archived tabs** in Customer Responses — separate views for current and completed work
- **Archive** a submitted response to move it out of the active list
- **Unarchive** from the Archived tab to restore a response to active
- **Output tracking** — the system records when a filled DOCX document is first downloaded, shown with a document icon in the response list
- Response status badges: Draft, Pending sign-off, Signed off, Archived

### Phase 10 — Response Timeline Tracking [COMPLETE]

Each customer response tracks three timestamps for feedback loop measurement, visible in the admin Customer Responses view.

- **Opened** — when the customer first selects/opens the form
- **First saved** — when they first save a draft or submit
- **Completed** — when they sign off and submit
- **Durations** calculated between each stage:
  - Time to first save (how long before first interaction)
  - First save to completion (revision/review time across sessions)
  - Total duration (end-to-end from open to sign-off)

### Phase 11 — UI-Configurable API Key [COMPLETE]

The Anthropic API key can be set directly from the Settings page — no need to manually edit `.env` files.

- Password-masked input field with Change/Save/Cancel flow
- Key saved to `.env` file and applied immediately (no restart needed)
- Health check section shows masked key and links to Configuration for setup

### Phase 12 — Docker & CI/CD [COMPLETE]

Containerized deployment with automated build pipeline and release management via GitHub Actions.

- Dockerfile using Python 3.11 slim, optimized layer caching, built-in healthcheck
- GitHub Actions workflow with 4 jobs: **test → version → build → release**
- Pull requests run tests and build the image (without pushing) to catch failures early
- Push to `main` auto-increments the minor version (e.g., `v1.3.0` → `v1.4.0`), builds and pushes the Docker image to GHCR, and creates a GitHub Release with auto-generated release notes
- For a major version bump, push the tag manually (`git tag v2.0.0 && git push origin v2.0.0`) — subsequent pushes to `main` continue from the new major (e.g., `v2.1.0`)
- Build cache via GitHub Actions cache for faster subsequent builds

### Phase 13 — Schema Export & Import [COMPLETE]

Schemas can be exported as JSON and shared between team members or instances. Specialized CTLs can build schemas and distribute them to other teams.

- **Export Schema** button available on all schemas (draft, live, archived) — downloads a portable JSON file
- **Import Schema** in the Form Schemas tab — upload a JSON file to create a new draft
- Imported schemas get a fresh ID and start at version 1 to avoid collisions
- Full roundtrip fidelity: sections, questions, field types, options, conditions, help text, and screenshots are all preserved
- Also accepts raw FormSchema JSON (without the export wrapper) for flexibility

### Remaining Work

- PDF export for read-only confirmation copy
- Email delivery on submission (SendGrid or internal SMTP)
- Change diff: see what questions changed between versions
- Rollback: re-promote any prior version (partially implemented — archived versions can be re-promoted)

## Security Considerations for Hosted Deployment

Running locally, the app is only accessible on your machine. Hosting it on a network or the internet introduces additional attack surfaces. Address the following before deploying.

### Authentication & Authorization

- **Add authentication** — Streamlit has no built-in auth. Use an identity provider (SSO/LDAP/Azure AD) or a reverse proxy (NGINX, Caddy) with authentication middleware in front of the app.
- **Role separation** — enforce admin vs. customer access server-side. Ensure customers cannot reach admin endpoints or API routes by manipulating the URL or session state.

### Transport Security

- **Enforce HTTPS** — all traffic must be encrypted in transit. Use a reverse proxy with TLS termination (e.g., NGINX + Let's Encrypt, or Azure App Service built-in TLS).
- **Secure cookies** — if using session-based auth, ensure cookies are marked `Secure`, `HttpOnly`, and `SameSite`.

### API Key & Secrets Management

- **Never expose the Anthropic API key to the client.** The current `.env` approach is acceptable for local use but should be replaced with a secrets manager (Azure Key Vault, AWS Secrets Manager, or environment variables injected at deploy time) for hosted environments.
- **Rotate keys** regularly and monitor usage for anomalies.

### File Upload Hardening

- **Validate file types** — restrict uploads to expected formats (DOCX, PNG, JPG, GIF) by checking both extension and MIME type.
- **Enforce file size limits** — prevent denial of service from oversized uploads.
- **Scan uploads** — consider antivirus/malware scanning for uploaded documents.
- **Store uploads outside the web root** — ensure uploaded files are not directly accessible via URL.

### Database

- **SQLite is not suitable for concurrent network access.** For hosted deployment, migrate to PostgreSQL or MySQL (the storage layer is already designed for this swap — see [database.py](app/database.py)).
- **Parameterized queries** — audit all SQL for injection vulnerabilities. The current codebase uses parameterized queries, but any new queries must follow the same pattern.
- **Backups** — implement automated database backups.

### Session & Multi-Tenancy

- **Streamlit session isolation** — Streamlit was not designed as a multi-tenant production server. Session state can leak between users under edge conditions. Test thoroughly under concurrent load.
- **Rate limiting** — add rate limiting at the reverse proxy layer to prevent abuse.
- **CSRF protection** — Streamlit does not provide CSRF tokens. A reverse proxy or WAF can help mitigate this.

### Network & Infrastructure

- **Prefer internal/VPN access** — the simplest mitigation is to host behind a VPN or on an internal network, limiting exposure to trusted users only.
- **Firewall rules** — restrict inbound access to only necessary ports (443 for HTTPS).
- **Logging & monitoring** — enable access logs, error logs, and alerting for suspicious activity (failed logins, unusual upload patterns, high request volume).

### Data Protection

- **Encryption at rest** — customer intake responses may contain sensitive business information. Enable disk encryption or database-level encryption.
- **Data retention policy** — define how long responses and uploaded documents are kept. The archive feature supports this workflow but automatic purging is not yet implemented.
- **Access audit trail** — log who accessed what data and when.

### Recommended Hosting Architecture

```
Internet / VPN
       ↓
 Reverse Proxy (NGINX/Caddy)
 ├─ TLS termination
 ├─ Authentication (SSO/LDAP)
 ├─ Rate limiting
 └─ CSRF / WAF rules
       ↓
 Streamlit App (internal only, no direct exposure)
       ↓
 PostgreSQL + File Storage (encrypted, backed up)
       ↓
 Secrets Manager (API keys, DB credentials)
```

## Pilot Recommendation

Start with **Data Movement or External Integrations** — the highest-friction intake area, with the most naturally structured field types (IPs, endpoints, protocols, environment names all map cleanly to dropdowns).

1. Upload the existing data movement questionnaire
2. Review the AI-generated schema — adjust any misclassified fields in the editor
3. Promote to live and share with 2-3 pilot customers
4. Measure: time to complete vs. old method, CTL re-entry time eliminated, submission completeness
5. Iterate schema, then expand to the next intake area
