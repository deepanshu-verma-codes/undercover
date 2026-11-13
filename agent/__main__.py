"""CLI entry point to run the UnderCover Agent on claims."""

import sys
from typing import Any

import httpx
from fastapi.testclient import TestClient
from langchain_core.language_models import BaseChatModel

from agent import main
from backend.main import app

HTTP_OK = 200


def get_backend() -> httpx.Client | TestClient:
    """Return a live backend client or an in-process TestClient."""
    url = main.BACKEND_URL
    try:
        with httpx.Client(base_url=url, timeout=1.0) as check:
            if check.get("/api/health").status_code == HTTP_OK:
                return httpx.Client(base_url=url, timeout=60.0)
    except (httpx.ConnectError, httpx.TimeoutException):
        return TestClient(app)
    return TestClient(app)


def process_claim(
    claim_id: str,
    llm: BaseChatModel | None = None,
) -> dict[str, Any]:
    """Run the agent on a single claim and return updated claim details."""
    with main.backend() as client:
        res = client.get(f"/api/claims/{claim_id}")
        if res.status_code != HTTP_OK:
            print(f"Claim {claim_id} not found.")
            return {}
        claim = res.json()

    summary = claim.get("summary", "")
    amount = claim.get("amount_claimed", 0.0)
    print(f"\nAssessing claim {claim_id} (${amount:.2f}) - {summary}...")

    reply = main.run(claim_id, f"thread-{claim_id}", llm=llm)
    with main.backend() as client:
        updated = client.get(f"/api/claims/{claim_id}").json()
    updated["agent_reply"] = reply

    dec = str(updated.get("decision", "undecided")).upper()
    payout = float(updated.get("payout") or 0.0)
    status = updated.get("status")
    reason = updated.get("reason", "")
    section = updated.get("policy_section", "")

    print(f"Decision: {dec} | Payout: ${payout:.2f} | Status: {status}")
    if reason:
        print(f"Reason: {reason}")
    if section:
        print(f"Policy section: {section}")
    return updated


def run_agent_cli(
    claim_ids: list[str] | None = None,
    llm: BaseChatModel | None = None,
) -> list[dict[str, Any]]:
    """Run the agent across target claims or all waiting claims."""
    main.backend = get_backend

    if claim_ids:
        targets = claim_ids
    else:
        with main.backend() as client:
            claims = client.get("/api/claims").json()
        targets = [c["claim_id"] for c in claims if c.get("status") == "waiting"]

    if not targets:
        print("No waiting claims found in queue.")
        return []

    print(f"Running UnderCover Agent on {len(targets)} claim(s)...")
    results = [process_claim(cid, llm=llm) for cid in targets]
    print(f"\nFinished processing {len(results)} claim(s).")
    return results


def main_cli() -> None:
    """Parse CLI args and execute agent."""
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "-h" in sys.argv or "--help" in sys.argv:
        print("Usage: uv run -m agent [CLAIM_ID] (e.g. uv run -m agent CLM-1001)")
        return
    run_agent_cli(args if args else None)


if __name__ == "__main__":
    main_cli()
