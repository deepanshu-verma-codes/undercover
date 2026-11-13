# Status

Pilot completed (Phases 1–6):
- `backend/`: FastAPI and SQLite database with seed ingestion from `data/`, full claim and policy read endpoints, decision recording, separate payment endpoint enforcing $1,000 threshold restriction, handler sign-off flow, activity logging, read-only agent instructions, and database reset endpoint.
- `agent/`: UnderCover Agent built with LangChain `create_agent` connecting strictly via backend API endpoints, verified with deterministic `StubModel` tests.
- `dashboard/`: React + Vite + TypeScript application compliant with UnderCover branding, claims queue with search and status filters, comprehensive claim detail view, interactive agent runner, live activity stream, decision presentation cards, handler sign-off interface, and read-only instructions modal.
- `e2e/`: Playwright test suite testing health check, queue browsing/filtering, claim detail navigation, agent execution workflow, and high-value claim handler sign-off.

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


