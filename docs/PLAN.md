# Plan: The claims pilot

The UnderCover claims pilot builds a complete claims processing platform for UnderCover Travel Insurance. It introduces an AI claims agent working alongside human claims handlers, supported by a FastAPI backend with SQLite, a React dashboard, and Playwright end-to-end tests.

## Architecture and standards

- **Backend (`backend/`)**: FastAPI and SQLite. Every API operation has an `operation_id`, a one-line docstring, and no optional inputs. Paying a claim is a separate operation that takes the amount. Payment over $1,000 is strictly blocked without handler sign-off.
- **Agent (`agent/`)**: LangChain's `create_agent` on OpenRouter, with entry point `run(claim_id, thread_id)`. Reaches claims and instructions only through the backend API. Uses `openai/gpt-6-luna` with low reasoning effort by default, or `MODEL_NAME` (e.g. `openrouter/free`). Unit tests use `StubModel` without calling external models.
- **Dashboard (`dashboard/`)**: React, Vite, and TypeScript in strict mode (no `any`). Styled according to `docs/BRAND.md` using the UnderCover palette (Sea Green `#06D6A0`, Marigold `#FFC145`, Coral `#F78C6B`, Midnight `#073B4C`), rounded panels without outlines, and clear typography (Instrument Sans, JetBrains Mono).
- **Verification (`npm run check`)**: Python (ruff format & lint, pyright, pytest >= 80% coverage), TypeScript (prettier, eslint, tsc, vitest >= 80% coverage), and Playwright E2E tests.

---

## Phase 1: SQLite Database and Seed Data Ingestion

### What it builds
- SQLite schema and database access layer for claims, policies, customers, plans, company settings, and activity logs.
- Seeding module that loads initial data from `data/claims.json`, `data/policies.json`, `data/customers.json`, `data/plans.json`, `data/company.json`, and `data/policy_wording.md`.
- Read API endpoints with `operation_id`, one-line docstrings, and strict parameter typing:
  - `GET /api/claims` (`operation_id="list_claims"`): list claims with summary details and status (`waiting`, `in_progress`, `waiting_for_sign_off`, `decided`).
  - `GET /api/claims/{claim_id}` (`operation_id="get_claim"`): get full claim details including items and documents.
  - `GET /api/policies/{policy_id}` (`operation_id="get_policy"`): get policy details and plan limits.
  - `GET /api/customers/{customer_id}` (`operation_id="get_customer"`): get customer details and prior claims history.
  - `GET /api/policy-wording` (`operation_id="get_policy_wording"`): get the policy wording contract.
  - `GET /api/instructions` (`operation_id="get_instructions"`): get the agent's instructions (read-only).
  - `POST /api/reset` (`operation_id="reset_database"`): reset SQLite database to initial seed state.
- Backend unit tests covering data seeding and read endpoints.

### Why this approach
Direct SQLite with clean helper functions avoids bulky ORM abstractions while delivering fast, reliable querying for the pilot. Loading from `data/*.json` ensures the backend immediately mirrors UnderCover's real operations and enables idempotent database resets during testing.

### Success criteria
- [x] `uv run pytest backend/tests/test_database.py` passes with >= 80% coverage.
- [x] Initializing or resetting the database loads 25 claims from `data/claims.json` with status `waiting`.
- [x] `curl -s http://127.0.0.1:8000/api/claims` returns HTTP 200 with 25 claims.
- [x] `curl -s http://127.0.0.1:8000/api/claims/CLM-1001` returns HTTP 200 with customer story, items, and documents.
- [x] `curl -s http://127.0.0.1:8000/api/policy-wording` returns HTTP 200 with markdown text containing Section 1 through Section 8.
- [x] `curl -s http://127.0.0.1:8000/api/instructions` returns HTTP 200 with the agent's system instructions.

---

## Phase 2: Claim Decisions, Payment Restrictions, and Sign-Off Logic

### What it builds
- Decision handling, payment restrictions, and activity logging endpoints in `backend/`:
  - `POST /api/claims/{claim_id}/decision` (`operation_id="decide_claim"`): records decision (`approve`, `decline`, `refer`), payout amount, 2-3 sentence explanation, and relevant policy section. If approved with payout > $1,000, updates status to `waiting_for_sign_off`.
  - `POST /api/claims/{claim_id}/pay` (`operation_id="pay_claim"`): dedicated payment endpoint taking `{ "amount": float }`. Validates that payouts > $1,000 cannot be processed without handler sign-off; returns HTTP 400 Bad Request if unapproved. If approved or <= $1,000, records payment and sets status to `decided`.
  - `POST /api/claims/{claim_id}/sign-off` (`operation_id="sign_off_claim"`): allows a claims handler to sign off on a claim with payout > $1,000, unblocking the payment.
  - `GET /api/claims/{claim_id}/activity` (`operation_id="get_claim_activity"`): retrieves chronological activity logs for the claim.
  - `POST /api/claims/{claim_id}/activity` (`operation_id="log_claim_activity"`): records an agent action or status update.
- Backend unit tests verifying decision recording, the $1,000 payout restriction, and sign-off workflows.

### Why this approach
Separating payment into its own dedicated operation fulfills the core tech stack requirement. Enforcing the $1,000 limit strictly at the API layer ensures that even if an AI agent attempts to pay an unauthorized amount, the system safely blocks the transaction.

### Success criteria
- [x] `uv run pytest backend/tests/test_claims.py` passes with >= 80% coverage.
- [x] Calling `POST /api/claims/CLM-1001/decision` with `approve` and payout $420 sets status to `in_progress` (awaiting payment).
- [x] Calling `POST /api/claims/CLM-1001/pay` with amount 420 succeeds and updates status to `decided`.
- [x] Calling `POST /api/claims/CLM-1003/decision` with `approve` and payout $1,500 updates status to `waiting_for_sign_off`.
- [x] Calling `POST /api/claims/CLM-1003/pay` with amount 1500 before sign-off returns HTTP 400 Bad Request ("Payout over $1,000 requires handler sign-off").
- [x] Calling `POST /api/claims/CLM-1003/sign-off` succeeds, and a subsequent call to `POST /api/claims/CLM-1003/pay` succeeds and sets status to `decided`.
- [x] `POST /api/claims/{claim_id}/activity` logs an action, and `GET /api/claims/{claim_id}/activity` returns the logged step.

---

## Phase 3: UnderCover Agent and LangChain Tool Integration

### What it builds
- Full agent implementation in `agent/main.py` using LangChain `create_agent` with OpenRouter model (`openai/gpt-6-luna` or `MODEL_NAME`).
- HTTP-based tools connecting the agent exclusively to the backend API:
  - `get_claim_details(claim_id: str)`: fetches claim story, items claimed, and document content.
  - `get_policy_details(policy_id: str)`: fetches policyholder plan and coverage limits.
  - `get_customer_history(customer_id: str)`: fetches past claims and customer details.
  - `get_policy_wording()`: fetches the policy wording contract.
  - `submit_decision(claim_id: str, decision: str, payout: float, reason: str, policy_section: str)`: submits the final decision.
  - `pay_claim(claim_id: str, amount: float)`: attempts payment for approved claims.
  - `log_claim_activity(claim_id: str, action: str)`: records current step for the live handler view.
- Agent system prompt instructing the agent to evaluate the claim against policy wording, calculate exact payout, explain in 2-3 sentences with the cited policy section, and pay approved claims.
- Backend endpoint `POST /api/claims/{claim_id}/run` (`operation_id="run_claim_agent"`): initiates agent execution on a claim.
- Agent unit tests in `agent/tests/test_agent.py` using `StubModel` to simulate LLM tool calls and decisions without external API calls.

### Why this approach
The agent accesses data strictly through the backend's published API, keeping domain logic and authorization checks cleanly separated. Using `StubModel` in unit tests ensures 100% deterministic test execution, rapid feedback in pre-commit hooks, and zero token costs during CI.

### Success criteria
- [x] `uv run pytest agent/tests/test_agent.py` passes with >= 80% coverage.
- [x] Agent correctly uses `StubModel` to invoke tools in sequence: reading claim, policy, and policy wording.
- [x] When agent approves a claim under $1,000, it calls `pay_claim` successfully and finishes with status `decided`.
- [x] When agent approves a claim over $1,000, `pay_claim` fails with a sign-off requirement, and the claim correctly remains in `waiting_for_sign_off`.
- [x] Calling `POST /api/claims/{claim_id}/run` executes the agent and records activity logs in SQLite.

---

## Phase 4: Dashboard Queue and Claim Detail Screens

### What it builds
- Brand-compliant React/TypeScript UI in `dashboard/src/`:
  - Styling aligned with `docs/BRAND.md`: fonts (Instrument Sans, JetBrains Mono), palette (Sea Green `#06D6A0`, Marigold `#FFC145`, Coral `#F78C6B`, Midnight `#073B4C`, Sea Mist `#CDD8DB`), rounded panels without single-edge borders, and clean status badges.
  - Header with UnderCover branding, claims queue counters, and an "Agent Instructions" viewer toggle.
  - Queue View (`ClaimsQueue`):
    - Table displaying Claim ID, Customer, Claim Type, Amount Claimed, Submitted Date, and Status (`waiting`, `in_progress`, `waiting_for_sign_off`, `decided`).
    - Status filtering tabs and claim search input.
  - Claim Detail View (`ClaimDetail`):
    - Comprehensive claim summary, customer story, itemized expenses table, and attached documents list.
    - Associated policy details (plan name, coverage limits, deductible) and customer prior claims history.
  - Read-Only Instructions Modal (`AgentInstructions`):
    - Displays the agent's active system prompt and operating rules fetched from `GET /api/instructions`.
- TypeScript unit tests with Vitest and `@testing-library/react`.

### Why this approach
Presenting the claims queue with immediate status filters and detailed claim records gives claims handlers full visibility into operational backlog. Building the read-only instructions modal fulfills the operational requirement to audit agent behavior directly from the dashboard.

### Success criteria
- [x] `npm run check:ts` passes (prettier, eslint, tsc, vitest >= 80% coverage).
- [x] In the browser (`http://localhost:5173/`), the dashboard displays the UnderCover header and the queue table with 25 claims.
- [x] Status badges show correct brand colors (e.g. Sea Green for decided, Marigold for waiting for sign-off, Coral for in progress).
- [x] Clicking a claim in the table navigates to that claim's full detail screen with story, items, and attached documents.
- [x] Clicking "Agent Instructions" opens the modal displaying the read-only agent prompt.

---

## Phase 5: Agent Execution Stream, Decision Presentation, and Handler Sign-Off

### What it builds
- Interactive components on the Claim Detail page:
  - "Run Agent" trigger button connected to `POST /api/claims/{claim_id}/run`.
  - Step-by-Step Activity Log (`ActivityStream`): renders real-time or polled actions taken by the agent (e.g., checking policy wording, calculating deductible, attempting payout).
  - Decision Presentation Card (`DecisionCard`):
    - Displays decision outcome (`Approved`, `Declined`, `Referred`).
    - Payout amount formatted in USD currency (e.g. `$420.00`).
    - 2-3 sentence explanation and policy section reference badge.
  - Handler Sign-off Interface (`SignOffAction`):
    - When a claim is in `waiting_for_sign_off`, displays an alert banner explaining that payout exceeds the $1,000 threshold.
    - Provides a "Sign off and Pay" button that invokes `POST /api/claims/{claim_id}/sign-off` and completes the payout via `POST /api/claims/{claim_id}/pay`.
- Component unit tests covering user actions, activity stream rendering, decision card states, and sign-off flows.

### Why this approach
Claims handlers need transparency into how the AI arrived at its conclusion and must retain authoritative control over high-value payments. The activity log reveals every tool call, and the sign-off workflow allows handlers to review the agent's reasoning before releasing payouts over $1,000.

### Success criteria
- [x] Vitest component tests for `ClaimDetail`, `ActivityStream`, and `DecisionCard` pass with >= 80% coverage.
- [x] Clicking "Run Agent" on a waiting claim triggers the agent and populates the activity stream with tool steps.
- [x] On completion of a claim under $1,000, the decision card displays the approved payout, concise reason, and policy section.
- [x] On completion of a claim over $1,000, the status badge reflects `waiting_for_sign_off` and the sign-off banner appears.
- [x] Clicking "Sign off and Pay" unblocks the payment, successfully transitions the claim status to `decided`, and updates the dashboard.

---

## Phase 6: End-to-End Test Suite and System Verification

### What it builds
- Comprehensive Playwright end-to-end test suite in `e2e/`:
  - `e2e/queue.spec.ts`: tests queue loading, claim count, status filtering, and navigation.
  - `e2e/claim-detail.spec.ts`: tests claim details, policy information, documents, and instructions view.
  - `e2e/agent-workflow.spec.ts`: tests running the agent on a standard claim (<= $1,000), viewing the activity stream, and verifying the automatic transition to `decided`.
  - `e2e/sign-off-flow.spec.ts`: tests running the agent on a high-value claim (> $1,000), verifying the `waiting_for_sign_off` state, executing the handler sign-off, and verifying final payment to `decided`.
- Full project verification through `npm run check`.

### Why this approach
End-to-end tests exercise the complete integration between the FastAPI backend, SQLite database, LangChain agent harness, and React frontend, ensuring all operational requirements and business constraints are met prior to user sign-off.

### Success criteria
- [x] `npx playwright test` runs and passes all e2e test specifications.
- [x] `npm run check:python` passes with zero ruff format/lint errors, zero pyright type issues, and >= 80% pytest coverage.
- [x] `npm run check:ts` passes with prettier formatting, zero eslint errors, zero tsc errors, and >= 80% vitest coverage.
- [x] `npm run check` exits with code 0 across Python, TypeScript, and Playwright suites.
