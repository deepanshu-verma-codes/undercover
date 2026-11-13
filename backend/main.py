"""The UnderCover backend."""

import csv
import io
import json
import os
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

import agent.main
from backend.database import (
    format_claim_row,
    generate_next_claim_id,
    get_connection,
    get_policy_wording_text,
    init_db,
    seed_db,
)
from backend.sanitizer import clean_user_input

SYSTEM_INSTRUCTIONS = (
    "You are the UnderCover Agent, an expert claims handler at "
    "UnderCover Travel Insurance.\n"
    "For the given claim:\n"
    "1. Retrieve the claim details, policy information, customer claim "
    "history, and policy wording using your tools.\n"
    "2. Check if the incident and claimed items are covered under the policy "
    "wording for the customer's plan, taking into account waiting periods, "
    "limits, and deductibles.\n"
    "3. You MUST always call the submit_decision tool to record your decision "
    "(approve, decline, or refer):\n"
    "   - Approve: Calculate the exact payout according to policy wording. "
    "Call submit_decision with payout > 0. Then call pay_claim with the amount. "
    "(Payouts over $1,000 will be blocked and wait for handler sign-off).\n"
    "   - Decline: Call submit_decision with decision='decline' and payout=0.0, "
    "stating why under the policy wording.\n"
    "   - Refer: Call submit_decision with decision='refer' and payout=0.0, "
    "explaining why human judgment or special investigation is required.\n"
    "4. In your decision, provide a concise explanation in two or three "
    "sentences, and cite the relevant section of the policy wording.\n"
    "5. Log each step you take as you evaluate the claim."
)

load_dotenv(override=True)

PAYOUT_LIMIT = 1000.0


def get_api_key() -> str:
    """Return the configured agent API key."""
    return os.getenv("UNDERCOVER_API_KEY", "")


def verify_api_key(request: Request) -> None:
    """Verify that the request carries a valid agent API key."""
    expected = get_api_key()
    if not expected:
        raise HTTPException(
            status_code=401, detail="API key is not configured on server"
        )
    key = request.headers.get("x-api-key", "")
    if not key or not secrets.compare_digest(key, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


CSV_SAMPLE_TEMPLATE = (
    "policy_id,customer_id,claim_type,incident_date,"
    "incident_location,summary,story,amount_claimed\n"
    "POL-2001,CUS-3001,trip_delay,2026-06-25,"
    '"London, UK","Delayed train to airport",'
    '"Train broke down en route to Heathrow airport, causing a missed flight.",'
    "380.00\n"
    "POL-2002,CUS-3002,baggage_delay,2026-06-26,"
    '"Tokyo, Japan","Delayed baggage on arrival",'
    '"Luggage did not arrive on flight. Purchased emergency clothing.",'
    "210.00\n"
)


class DecisionRequest(BaseModel):
    """Claim decision submission payload."""

    decision: str
    payout: float
    reason: str
    policy_section: str


class PayRequest(BaseModel):
    """Claim payment submission payload."""

    amount: float


class ActivityRequest(BaseModel):
    """Claim activity log payload."""

    action: str


class ClaimCreateRequest(BaseModel):
    """Claim creation submission payload."""

    policy_id: str
    customer_id: str
    claim_type: str
    incident_date: str
    incident_location: str
    summary: str
    story: str
    amount_claimed: float
    claim_id: str = ""
    submitted_on: str = ""
    items: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []
    run_agent: bool = False


class CsvUploadRequest(BaseModel):
    """CSV claims bulk upload payload."""

    csv_content: str
    run_agent: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and seed database on startup."""
    init_db()
    with get_connection() as conn:
        row = conn.execute("SELECT count(*) as cnt FROM claims").fetchone()
        if row and row["cnt"] == 0:
            seed_db()
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.post("/api/reset", operation_id="reset_database")
def reset_database() -> dict[str, str]:
    """Reset the database to the initial seed state."""
    seed_db()
    return {"status": "ok"}


@app.get("/api/instructions", operation_id="get_instructions")
def get_instructions() -> dict[str, str]:
    """Return the agent system instructions."""
    return {"instructions": SYSTEM_INSTRUCTIONS}


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording() -> dict[str, str]:
    """Return the policy wording text."""
    return {"policy_wording": get_policy_wording_text()}


@app.get("/api/claims", operation_id="list_claims")
def list_claims() -> list[dict[str, Any]]:
    """Return all claims in the queue."""
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM claims ORDER BY submitted_on DESC, claim_id ASC"
        ).fetchall()
        return [format_claim_row(r) for r in rows]


@app.post("/api/claims", status_code=201, operation_id="create_claim")
def create_claim(req: ClaimCreateRequest) -> dict[str, Any]:
    """Create a new claim in the queue and optionally run the agent."""
    init_db()
    submitted_on = req.submitted_on or datetime.now(UTC).date().isoformat()
    summary = clean_user_input(req.summary)
    story = clean_user_input(req.story)
    location = clean_user_input(req.incident_location)
    items = req.items
    if not items:
        items = [
            {
                "description": summary,
                "category": req.claim_type,
                "amount": req.amount_claimed,
            }
        ]
    else:
        items = [
            {
                **item,
                "description": clean_user_input(str(item.get("description", ""))),
            }
            for item in items
        ]
    documents = req.documents

    with get_connection() as conn:
        cid = req.claim_id.strip() if req.claim_id else generate_next_claim_id(conn)
        existing = conn.execute(
            "SELECT claim_id FROM claims WHERE claim_id = ?", (cid,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail=f"Claim {cid} already exists")

        conn.execute(
            """
            INSERT INTO claims (
                claim_id, policy_id, customer_id, claim_type, submitted_on,
                incident_date, incident_location, summary, story,
                amount_claimed, items, documents, status, paid, signed_off
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'waiting', 0, 0)
            """,
            (
                cid,
                req.policy_id,
                req.customer_id,
                req.claim_type,
                submitted_on,
                req.incident_date,
                location,
                summary,
                story,
                req.amount_claimed,
                json.dumps(items),
                json.dumps(documents),
            ),
        )
        ts = datetime.now(UTC).isoformat()
        conn.execute(
            "INSERT INTO activities (claim_id, timestamp, action) VALUES (?, ?, ?)",
            (cid, ts, "Claim submitted"),
        )

    if req.run_agent:
        return run_claim_agent(cid)

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM claims WHERE claim_id = ?", (cid,)).fetchone()
        return format_claim_row(row)


@app.get("/api/claims/csv-template", operation_id="get_csv_template")
def get_csv_template() -> dict[str, str]:
    """Return a sample CSV template for claim imports."""
    return {"template": CSV_SAMPLE_TEMPLATE}


def _parse_items_or_docs(raw_val: str) -> list[dict[str, Any]]:
    """Parse JSON list from CSV field or return empty list."""
    if not raw_val:
        return []
    try:
        data = json.loads(raw_val)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _parse_csv_row(
    row: dict[str, str], idx: int, conn: Any, today: str
) -> dict[str, Any]:
    """Parse and validate a single CSV row."""
    policy_id = row.get("policy_id", "").strip()
    customer_id = row.get("customer_id", "").strip()
    if not policy_id or not customer_id:
        raise HTTPException(
            status_code=400,
            detail=f"Row {idx} is missing required policy_id or customer_id",
        )

    cid = row.get("claim_id", "").strip() or generate_next_claim_id(conn)
    existing = conn.execute(
        "SELECT claim_id FROM claims WHERE claim_id = ?", (cid,)
    ).fetchone()
    if existing:
        raise HTTPException(status_code=400, detail=f"Claim {cid} already exists")

    try:
        amount_claimed = float(row.get("amount_claimed", 0.0))
    except ValueError as err:
        raise HTTPException(
            status_code=400,
            detail=f"Row {idx} has invalid amount_claimed",
        ) from err

    claim_type = row.get("claim_type", "").strip() or "general"
    summary = clean_user_input(row.get("summary", "").strip() or "Imported claim")
    story = clean_user_input(row.get("story", "").strip() or summary)
    location = clean_user_input(row.get("incident_location", "").strip() or "Unknown")
    items = _parse_items_or_docs(row.get("items", "").strip())
    if not items:
        items = [
            {
                "description": summary,
                "category": claim_type,
                "amount": amount_claimed,
            }
        ]
    else:
        items = [
            {
                **item,
                "description": clean_user_input(str(item.get("description", ""))),
            }
            for item in items
        ]
    docs = _parse_items_or_docs(row.get("documents", "").strip())

    return {
        "claim_id": cid,
        "policy_id": policy_id,
        "customer_id": customer_id,
        "claim_type": claim_type,
        "submitted_on": row.get("submitted_on", "").strip() or today,
        "incident_date": row.get("incident_date", "").strip() or today,
        "incident_location": location,
        "summary": summary,
        "story": story,
        "amount_claimed": amount_claimed,
        "items": json.dumps(items),
        "documents": json.dumps(docs),
    }


@app.post("/api/claims/upload-csv", status_code=201, operation_id="upload_claims_csv")
def upload_claims_csv(req: CsvUploadRequest) -> dict[str, Any]:
    """Upload and ingest claims from CSV content and optionally run the agent."""
    init_db()
    content = req.csv_content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="CSV content cannot be empty")

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise HTTPException(
            status_code=400, detail="Invalid CSV format: no headers found"
        )

    imported_ids: list[str] = []
    ts = datetime.now(UTC).isoformat()
    today = datetime.now(UTC).date().isoformat()

    with get_connection() as conn:
        for idx, row in enumerate(reader, start=1):
            claim_data = _parse_csv_row(row, idx, conn, today)
            cid = claim_data["claim_id"]
            conn.execute(
                """
                INSERT INTO claims (
                    claim_id, policy_id, customer_id, claim_type, submitted_on,
                    incident_date, incident_location, summary, story,
                    amount_claimed, items, documents, status, paid, signed_off
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'waiting', 0, 0)
                """,
                (
                    cid,
                    claim_data["policy_id"],
                    claim_data["customer_id"],
                    claim_data["claim_type"],
                    claim_data["submitted_on"],
                    claim_data["incident_date"],
                    claim_data["incident_location"],
                    claim_data["summary"],
                    claim_data["story"],
                    claim_data["amount_claimed"],
                    claim_data["items"],
                    claim_data["documents"],
                ),
            )
            conn.execute(
                "INSERT INTO activities (claim_id, timestamp, action) VALUES (?, ?, ?)",
                (cid, ts, "Claim imported from CSV"),
            )
            imported_ids.append(cid)

    imported_claims = []
    decided_count = 0
    for cid in imported_ids:
        if req.run_agent:
            res = run_claim_agent(cid)
            imported_claims.append(res)
            if res.get("status") in ("decided", "waiting_for_sign_off"):
                decided_count += 1
        else:
            with get_connection() as conn:
                r = conn.execute(
                    "SELECT * FROM claims WHERE claim_id = ?", (cid,)
                ).fetchone()
                imported_claims.append(format_claim_row(r))

    return {
        "imported_count": len(imported_claims),
        "claims": imported_claims,
        "decided_count": decided_count,
    }


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str) -> dict[str, Any]:
    """Return a single claim by its id."""
    init_db()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Claim not found")
        return format_claim_row(row)


@app.get("/api/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str) -> dict[str, Any]:
    """Return policy details and associated plan limits."""
    init_db()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM policies WHERE policy_id = ?", (policy_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Policy not found")
        data = dict(row)
        data["add_ons"] = json.loads(data["add_ons"])
        data["trip"] = json.loads(data["trip"])
        data["travelers"] = json.loads(data["travelers"])

        plan_row = conn.execute(
            "SELECT data FROM plans WHERE plan = ?", (data["plan"],)
        ).fetchone()
        if plan_row:
            data["plan_details"] = json.loads(plan_row["data"])
        return data


@app.get("/api/customers/{customer_id}", operation_id="get_customer")
def get_customer(customer_id: str) -> dict[str, Any]:
    """Return customer details and past claim history."""
    init_db()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Customer not found")
        data = dict(row)
        data["address"] = json.loads(data["address"])
        data["previous_claims"] = json.loads(data["previous_claims"])
        return data


@app.post("/api/claims/{claim_id}/decision", operation_id="decide_claim")
def decide_claim(
    claim_id: str, req: DecisionRequest, request: Request
) -> dict[str, Any]:
    """Record an assessment decision for a claim."""
    verify_api_key(request)
    init_db()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Claim not found")

        dec = req.decision.strip().lower()
        new_status = (
            "waiting_for_sign_off"
            if (dec == "approve" and req.payout > PAYOUT_LIMIT)
            else "in_progress"
            if dec == "approve"
            else "decided"
        )

        conn.execute(
            """
            UPDATE claims
            SET decision = ?, payout = ?, reason = ?, policy_section = ?, status = ?
            WHERE claim_id = ?
            """,
            (
                dec,
                req.payout,
                req.reason,
                req.policy_section,
                new_status,
                claim_id,
            ),
        )
        ts = datetime.now(UTC).isoformat()
        conn.execute(
            "INSERT INTO activities (claim_id, timestamp, action) VALUES (?, ?, ?)",
            (
                claim_id,
                ts,
                f"Decision recorded: {dec} with payout ${req.payout:.2f}",
            ),
        )
        updated = conn.execute(
            "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()
        return format_claim_row(updated)


@app.post("/api/claims/{claim_id}/pay", operation_id="pay_claim")
def pay_claim(claim_id: str, req: PayRequest, request: Request) -> dict[str, Any]:
    """Process a payment for an approved claim."""
    init_db()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Claim not found")

        # Allow payment without API key only if claim has been signed off by a handler
        key = request.headers.get("x-api-key", "")
        expected = get_api_key()
        is_valid_agent = bool(
            expected and key and secrets.compare_digest(key, expected)
        )
        if not is_valid_agent and not row["signed_off"]:
            verify_api_key(request)

        if req.amount > PAYOUT_LIMIT and not row["signed_off"]:
            raise HTTPException(
                status_code=400,
                detail="Payout over $1,000 requires handler sign-off",
            )

        conn.execute(
            """
            UPDATE claims
            SET paid = 1, status = 'decided', payout = ?
            WHERE claim_id = ?
            """,
            (req.amount, claim_id),
        )
        ts = datetime.now(UTC).isoformat()
        conn.execute(
            "INSERT INTO activities (claim_id, timestamp, action) VALUES (?, ?, ?)",
            (claim_id, ts, f"Payment processed: ${req.amount:.2f}"),
        )
        updated = conn.execute(
            "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()
        return format_claim_row(updated)


@app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off_claim")
def sign_off_claim(claim_id: str, request: Request) -> dict[str, Any]:
    """Approve a high-value claim payout by a supervisor."""
    role = request.headers.get("x-handler-role", "handler").lower().strip()
    if role != "supervisor":
        raise HTTPException(
            status_code=403,
            detail="Supervisor role required to sign off payouts",
        )

    init_db()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Claim not found")

        conn.execute("UPDATE claims SET signed_off = 1 WHERE claim_id = ?", (claim_id,))
        ts = datetime.now(UTC).isoformat()
        conn.execute(
            "INSERT INTO activities (claim_id, timestamp, action) VALUES (?, ?, ?)",
            (claim_id, ts, "Handler sign-off approved"),
        )
        updated = conn.execute(
            "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()
        return format_claim_row(updated)


@app.get("/api/claims/{claim_id}/activity", operation_id="get_claim_activity")
def get_claim_activity(claim_id: str) -> list[dict[str, Any]]:
    """Return chronological activity log entries for a claim."""
    init_db()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Claim not found")

        rows = conn.execute(
            "SELECT id, claim_id, timestamp, action FROM activities "
            "WHERE claim_id = ? ORDER BY id ASC",
            (claim_id,),
        ).fetchall()
        return [dict(r) for r in rows]


@app.post("/api/claims/{claim_id}/activity", operation_id="log_claim_activity")
def log_claim_activity(
    claim_id: str, req: ActivityRequest, request: Request
) -> dict[str, str]:
    """Log an activity step for a claim."""
    verify_api_key(request)
    init_db()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Claim not found")

        ts = datetime.now(UTC).isoformat()
        conn.execute(
            "INSERT INTO activities (claim_id, timestamp, action) VALUES (?, ?, ?)",
            (claim_id, ts, req.action),
        )
        return {"status": "ok", "action": req.action}


@app.post("/api/claims/{claim_id}/run", operation_id="run_claim_agent")
def run_claim_agent(claim_id: str) -> dict[str, Any]:
    """Run the UnderCover agent on a claim."""
    init_db()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Claim not found")
        conn.execute(
            "UPDATE claims SET status = 'in_progress' WHERE claim_id = ?",
            (claim_id,),
        )

    reply = agent.main.run(claim_id, f"thread-{claim_id}")
    with get_connection() as conn:
        updated = conn.execute(
            "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()
        data = format_claim_row(updated)
        data["agent_reply"] = reply
        return data


@app.post("/api/claims/run-all", operation_id="run_all_claims")
def run_all_claims() -> dict[str, Any]:
    """Run the UnderCover agent on all waiting claims."""
    init_db()
    with get_connection() as conn:
        query = (
            "SELECT claim_id FROM claims WHERE status = 'waiting' "
            "ORDER BY submitted_on DESC, claim_id ASC"
        )
        rows = conn.execute(query).fetchall()
        waiting_ids = [r["claim_id"] for r in rows]

    results = []
    for cid in waiting_ids:
        res = run_claim_agent(cid)
        results.append(res)
    return {"processed": len(results), "claims": results}
