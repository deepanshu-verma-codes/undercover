# Plan: Claim Ingestion via Form and CSV Upload with Automated Agent Auditing

This plan adds manual claim entry via a web form and bulk claim ingestion via CSV upload to the UnderCover claims platform. Once submitted, new claims are stored in the SQLite database and can immediately be audited by the UnderCover Agent to generate policy-grounded decisions, payout calculations, and activity logs.

## Architecture and standards

- **Backend (`backend/`)**: FastAPI and SQLite. Every API operation has an `operation_id`, a one-line docstring, and no optional inputs.
  - `POST /api/claims`: creates a single claim in the database and optionally triggers the UnderCover agent for immediate audit.
  - `POST /api/claims/upload-csv`: parses and ingests multiple claims from CSV content and optionally triggers the agent on all ingested claims.
- **Agent (`agent/`)**: Executes the UnderCover Agent (`run_claim_agent`) against newly ingested claims, validating policy wording, plan coverage, and limits, and generating decision audits.
- **Dashboard (`dashboard/`)**: React, Vite, and TypeScript in strict mode (no `any`). Adheres to UnderCover brand standards (`docs/BRAND.md`).
  - "+ New Claim" modal with validation and instant agent audit toggle.
  - "Upload CSV" modal with file picker, sample template download, and batch audit execution.
- **Verification (`npm run check`)**: Python (ruff format & lint, pyright, pytest >= 80% coverage), TypeScript (prettier, eslint, tsc, vitest >= 80% coverage), and Playwright E2E tests.

---

## Phase 1: Single Claim Ingestion API (`POST /api/claims`)

### What it builds
- Pydantic models for claim creation (`ClaimCreateRequest`) with strict typing:
  - Required fields: `policy_id`, `customer_id`, `claim_type`, `incident_date`, `incident_location`, `summary`, `story`, `amount_claimed`.
  - Optional or default fields: `claim_id` (auto-generated if omitted, e.g. `CLM-1026`), `submitted_on` (defaults to current UTC date `YYYY-MM-DD`), `items` (list of item dicts or default to single item from summary and amount), `documents` (list of document dicts), and `run_agent` (boolean flag, default `false`).
- Endpoint `POST /api/claims` (`operation_id="create_claim"`):
  - Validates that `policy_id` and `customer_id` exist in the database (or provides clear error if invalid).
  - Inserts the new claim into the `claims` SQLite table with initial status `waiting`.
  - Logs a `"Claim submitted"` entry in `activities`.
  - If `run_agent=True`, immediately invokes `run_claim_agent(claim_id)` and returns the resulting claim state including `decision`, `payout`, `reason`, `policy_section`, and status.
- Unit tests in `backend/tests/test_claims.py` verifying:
  - Successful claim insertion with manual ID and auto-generated ID.
  - Default status set to `waiting`.
  - Immediate agent audit execution when `run_agent=True`.
  - Error handling for missing required fields.

### Why this approach
Direct single-claim creation provides the core schema validation and database insertion logic needed for both the manual web form and individual API integrations, ensuring data integrity before building CSV and frontend features.

### Success criteria
- [x] `uv run pytest backend/tests/test_claims.py` passes with >= 80% coverage.
- [x] `POST /api/claims` with valid data inserts a claim and returns HTTP 201 with claim status `waiting`.
- [x] `POST /api/claims` with `run_agent=True` executes the UnderCover agent and returns HTTP 201 with claim status (`decided` or `waiting_for_sign_off`) and non-empty decision fields.
- [x] `ruff check`, `ruff format --check`, and `pyright` pass cleanly.

---

## Phase 2: Bulk CSV Ingestion API (`POST /api/claims/upload-csv`)

### What it builds
- CSV ingestion payload model `CsvUploadRequest` with fields `csv_content: str` and `run_agent: bool`.
- Endpoint `POST /api/claims/upload-csv` (`operation_id="upload_claims_csv"`):
  - Parses CSV rows using standard library `csv.DictReader`.
  - Supports standard columns: `claim_id`, `policy_id`, `customer_id`, `claim_type`, `incident_date`, `incident_location`, `summary`, `story`, `amount_claimed`, `items`, `documents`.
  - Gracefully maps missing columns or simple strings to valid JSON arrays for `items` and `documents`.
  - Generates sequential unique `claim_id`s for rows lacking an explicit ID.
  - Inserts all rows into SQLite within a database transaction.
  - If `run_agent=True`, executes the UnderCover agent on each imported claim.
  - Returns a summary response `{ "imported_count": int, "claims": list[Claim], "decided_count": int }`.
- Sample CSV endpoint or utility returning a valid CSV template string for reference.
- Unit tests in `backend/tests/test_claims.py` testing CSV parsing, validation, multi-row insertion, and bulk agent execution.

### Why this approach
Accepting CSV text via a typed request model maintains simplicity and works seamlessly across both JSON API requests and browser-based file reading (via `FileReader` in the frontend) without requiring complex multipart streaming middleware.

### Success criteria
- [x] `uv run pytest backend/tests/test_claims.py` passes with >= 80% coverage.
- [x] Uploading valid CSV data via `POST /api/claims/upload-csv` successfully ingests multiple claims.
- [x] Uploading with `run_agent=True` audits all newly imported claims and returns their decisions.
- [x] Missing optional columns in CSV rows are handled with safe fallbacks.
- [x] `ruff check`, `ruff format --check`, and `pyright` pass cleanly.

---

## Phase 3: Dashboard "+ New Claim" Form Modal

### What it builds
- React component `NewClaimModal.tsx` in `dashboard/src/components/`:
  - Accessible dialog modal adhering to UnderCover brand guidelines (`docs/BRAND.md`) with rounded panels, Sea Green primary buttons, and Midnight text.
  - Input fields for: Policy ID (select or text input), Customer ID, Claim Type (dropdown: trip_cancellation, trip_delay, medical, baggage_delay, baggage_loss, personal_liability), Incident Date, Incident Location, Amount Claimed, Summary, and Story.
  - Checkbox toggle: "Run UnderCover Agent immediately for audit" (checked by default).
  - Validation ensuring required fields are non-empty and amount is positive.
- Integration into `ClaimsQueue.tsx` and `App.tsx`:
  - "+ New Claim" button in queue action bar.
  - On submission: calls `POST /api/claims`, refreshes the claims queue, and highlights or selects the created claim.
  - Displays loading state while agent audit is executing.
- Vitest unit tests in `dashboard/src/App.test.tsx` verifying modal opening, form filling, submission, and queue update.

### Why this approach
A dedicated modal keeps the claims queue uncluttered while offering handlers a quick, frictionless way to submit new claims and immediately view the agent's audit decision.

### Success criteria
- [x] Clicking "+ New Claim" opens the form modal.
- [x] Submitting the form posts to `/api/claims` and adds the new claim to the queue.
- [x] When "Run UnderCover Agent" is checked, the new claim shows an audit status (`decided` or `waiting_for_sign_off`) upon creation.
- [x] Form displays validation errors when required fields are missing.
- [x] Vitest tests pass with >= 80% coverage on new/updated components.

---

## Phase 4: Dashboard "Upload CSV" Modal & Template Download

### What it builds
- React component `UploadCsvModal.tsx` in `dashboard/src/components/`:
  - Drag-and-drop / file selector for `.csv` files.
  - Parses and displays a preview table of claims to be imported.
  - "Download Template" button that generates and downloads a sample CSV file with correct headers.
  - Checkbox: "Run agent on imported claims immediately".
  - "Upload & Process" button that submits CSV data to `POST /api/claims/upload-csv`.
  - Progress feedback showing number of imported claims and audit progress.
- Integration into `ClaimsQueue.tsx`:
  - "Upload CSV" button beside "+ New Claim".
  - Auto-refreshes queue and displays success notification banner upon completion.
- Vitest tests in `dashboard/src/App.test.tsx` covering CSV file reading, preview display, and upload submission.

### Why this approach
Giving handlers a preview before ingestion prevents accidental bulk imports, while providing a downloadable CSV template ensures handlers know the expected format.

### Success criteria
- [x] Clicking "Upload CSV" opens the upload modal.
- [x] Selecting a CSV file parses and previews rows in the modal.
- [x] Clicking "Download Template" triggers a CSV file download with sample headers.
- [x] Submitting the modal ingests the claims, executes agent audits if selected, and updates the queue.
- [x] Vitest tests pass with >= 80% coverage.

---

## Phase 5: End-to-End Verification and Status Documentation

### What it builds
- Playwright E2E test in `e2e/claim-ingestion.spec.ts`:
  - Test 1: Handlers can open "+ New Claim", fill out the form, submit with agent audit enabled, and see the audited claim in the queue with decision details.
  - Test 2: Handlers can open "Upload CSV", upload a sample CSV file, process it, and verify the batch of claims appears in the queue.
- Updates to `docs/STATUS.md` documenting:
  - New API endpoints (`POST /api/claims`, `POST /api/claims/upload-csv`).
  - Dashboard UI controls for manual entry and CSV upload.
  - How to run and test the new ingestion features.
- Full system verification using `npm run check`.

### Why this approach
Full E2E automation verifies that the backend, agent, and frontend interact properly in real browser sessions without regressions in existing sign-off or queue workflows.

### Success criteria
- [x] `uv run pytest` passes with >= 80% coverage across backend and agent.
- [x] `vitest run --root dashboard --coverage` passes with >= 80% coverage.
- [x] `npx playwright test` passes all tests including `claim-ingestion.spec.ts`.
- [x] `npm run check` passes with zero errors and clean formatting.
- [x] `docs/STATUS.md` is updated with complete usage instructions.
