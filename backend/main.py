"""The UnderCover backend."""

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import agent.main
from backend.database import (
    format_claim_row,
    get_connection,
    get_policy_wording_text,
    init_db,
    seed_db,
)

SYSTEM_INSTRUCTIONS = (
    "You are the UnderCover Agent, an expert claims handler at "
    "UnderCover Travel Insurance.\n"
    "For the given claim:\n"
    "1. Retrieve the claim details, policy information, customer claim "
    "history, and policy wording.\n"
    "2. Check if the incident and claimed items are covered under the policy "
    "wording for the customer's plan, taking into account waiting periods, "
    "limits, and deductibles.\n"
    "3. Decide whether to approve, decline, or refer the claim:\n"
    "   - Approve: Calculate the exact payout according to the policy wording. "
    "Submit the decision. If approved, attempt to pay the claim. If the payout "
    "exceeds $1,000, explain that payment requires handler sign-off.\n"
    "   - Decline: State clearly that the claim is declined and why under the "
    "policy wording.\n"
    "   - Refer: Refer when the claim requires human judgment or special "
    "investigation.\n"
    "4. In your decision, provide a concise explanation in two or three "
    "sentences, and cite the relevant section of the policy wording.\n"
    "5. Log each step you take as you evaluate the claim."
)

PAYOUT_LIMIT = 1000.0


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
def decide_claim(claim_id: str, req: DecisionRequest) -> dict[str, Any]:
    """Record an assessment decision for a claim."""
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
def pay_claim(claim_id: str, req: PayRequest) -> dict[str, Any]:
    """Process a payment for an approved claim."""
    init_db()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Claim not found")

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
def sign_off_claim(claim_id: str) -> dict[str, Any]:
    """Approve a high-value claim payout by a handler."""
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
def log_claim_activity(claim_id: str, req: ActivityRequest) -> dict[str, str]:
    """Log an activity step for a claim."""
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

    reply = agent.main.run(claim_id, f"thread-{claim_id}")
    with get_connection() as conn:
        updated = conn.execute(
            "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()
        data = format_claim_row(updated)
        data["agent_reply"] = reply
        return data
