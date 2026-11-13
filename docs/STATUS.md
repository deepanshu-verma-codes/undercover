# Status

Pilot completed (Phases 1–6) & Enterprise Security & Guardrails (Phases 1–5):
- `backend/`: FastAPI and SQLite database with seed ingestion from `data/` and `data/security/` (including adversarial test claim `CLM-1901`), full claim and policy read endpoints, claim creation endpoint (`POST /api/claims`), bulk CSV import endpoint (`POST /api/claims/upload-csv`) with template download (`GET /api/claims/csv-template`), input sanitization and PII data masking (`backend/sanitizer.py`) stripping dangerous HTML/XSS vectors and redacting 16-digit credit card patterns, Role-Based Access Control (RBAC) enforcing supervisor privileges (`X-Handler-Role: supervisor`) on high-value sign-offs (`POST /api/claims/{id}/sign-off`), API key authentication on agent endpoints (`X-API-Key` with constant-time comparison), decision recording, separate payment endpoint enforcing $1,000 threshold restriction and supervisor sign-off authorization, activity logging, read-only agent instructions, and database reset endpoint.
- `agent/`: UnderCover Agent built with LangChain `create_agent` connecting strictly via backend API endpoints, verified with deterministic `StubModel` tests. Features a pre-execution prompt injection guardrail (`agent/guardrail.py`) that intercepts adversarial prompt injections (such as `CLM-1901`), bypassing the LLM and routing directly to human referral under policy section "Security Guardrail" with $0 payout.
- `dashboard/`: React + Vite + TypeScript application compliant with UnderCover branding, claims queue with search and status filters, role selector header toggle (`Handler` vs `Supervisor`), "+ New Claim" manual entry modal and "Upload CSV" bulk ingestion modal with instant agent audit option and sample template download, comprehensive claim detail view, interactive agent runner, live activity stream, decision presentation cards, role-aware handler/supervisor sign-off interface, and read-only instructions modal.
- `e2e/`: Playwright test suite testing health check, queue browsing/filtering, claim detail navigation, agent execution workflow, high-value claim handler/supervisor sign-off, manual claim submission with instant agent audit, bulk CSV claim ingestion, adversarial prompt injection defense, supervisor privilege escalation enforcement, and stored XSS sanitization.

## Enterprise Security & Guardrails

1. **API Key Authentication**:
   - `UNDERCOVER_API_KEY`: Secret key loaded from `.env`.
   - Requires `X-API-Key` on backend agent mutation endpoints (`POST /api/claims/{id}/decision`, `POST /api/claims/{id}/pay`, `POST /api/claims/{id}/activity`) using constant-time comparison (`secrets.compare_digest`).
   - `GET /api/health` and dashboard read endpoints remain publicly accessible.

2. **Pre-Execution Prompt Injection Guardrail**:
   - `agent/guardrail.py` detects adversarial instructions (such as executive pre-approval overrides or commands to ignore policy limits in `CLM-1901` and custom inputs) prior to invoking the LLM.
   - Malicious claims bypass LLM evaluation and are recorded as `decision="refer"`, `payout=0.0`, `policy_section="Security Guardrail"`, with activity logged: `"Security Guardrail flagged claim for human review"`.

3. **Input Sanitization & Data Masking**:
   - `backend/sanitizer.py` cleans `summary`, `story`, `incident_location`, and items on both manual claim submission and bulk CSV upload.
   - Strips executable HTML blocks (`<script>`, `<iframe>`, `<style>`, `<object>`), standalone tags, inline event handlers, and `javascript:` pseudoprotocols.
   - Automatically masks 16-digit credit card patterns as `[REDACTED CARD: ****-****-****-XXXX]` to protect PII from entering LLM logs and storage.

4. **Role-Based Access Control (RBAC)**:
   - Evaluates `X-Handler-Role` header on `POST /api/claims/{id}/sign-off`.
   - Restricts sign-offs for claims exceeding $1,000 to `supervisor` role. Non-supervisors receive HTTP 403 Forbidden.
   - Dashboard features a role switch (`Handler` / `Supervisor`) in the header that dynamically enables/disables sign-off actions and displays feedback in the UI.

## How to run it

1. Install dependencies:
   ```bash
   uv sync
   npm install
   ```
2. Start the development environment (backend on port 8000 and dashboard on port 5173):
   ```bash
   npm run dev
   ```
3. Run the full verification test suite:
   ```bash
   npm run check
   ```
4. Reset the database (resets all claims to `waiting` and clears decisions/logs):
   ```bash
   npm run db:reset
   ```
   *(Alternatively: `uv run -m backend.database` or `curl -X POST http://127.0.0.1:8000/api/reset` when the backend is running).*
5. Run the LangChain agent to check claims:
   ```bash
   # Assess all waiting claims in the queue:
   npm run agent

   # Assess a specific claim:
   npm run agent -- CLM-1001

   # (Direct uv commands: uv run -m agent or uv run -m agent CLM-1001)
   ```
6. Add new claims and run automated audits:
   - **Via Dashboard**: Click **+ New Claim** to open the manual entry modal or **Upload CSV** to batch import claims. Keep "Run UnderCover Agent immediately" checked to generate automated audit decisions instantly.
   - **Via API**:
     - Create single claim: `POST /api/claims` with `{ "policy_id": "...", "customer_id": "...", "amount_claimed": 250.0, "run_agent": true, ... }`
     - Bulk CSV upload: `POST /api/claims/upload-csv` with `{ "csv_content": "...", "run_agent": true }`
     - Download CSV template: `GET /api/claims/csv-template`


