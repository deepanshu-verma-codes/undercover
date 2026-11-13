"""Tests for claims decision, payment, sign-off, and activity logging."""

from fastapi.testclient import TestClient

import agent.main
from backend import database
from backend.main import app


def test_claim_decision_and_payment_flow(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_claims.db")
    monkeypatch.setenv("DB_PATH", test_db)
    database.seed_db(test_db)

    client = TestClient(app)

    # Standard claim under $1,000 (CLM-1001)
    res = client.post(
        "/api/claims/CLM-1001/decision",
        json={
            "decision": "approve",
            "payout": 420.0,
            "reason": "Flight delay covered under trip delay.",
            "policy_section": "3. Trip Delay",
        },
    )
    assert res.status_code == 200
    assert res.json()["status"] == "in_progress"
    assert res.json()["decision"] == "approve"
    assert res.json()["payout"] == 420.0

    # Pay standard claim
    res = client.post("/api/claims/CLM-1001/pay", json={"amount": 420.0})
    assert res.status_code == 200
    assert res.json()["status"] == "decided"
    assert res.json()["paid"] is True

    # High-value claim over $1,000 (CLM-1003)
    res = client.post(
        "/api/claims/CLM-1003/decision",
        json={
            "decision": "approve",
            "payout": 1500.0,
            "reason": "Medical evacuation covered under First plan.",
            "policy_section": "7. Emergency Medical",
        },
    )
    assert res.status_code == 200
    assert res.json()["status"] == "waiting_for_sign_off"

    # Attempt payment before sign-off - should fail with 400
    res = client.post("/api/claims/CLM-1003/pay", json={"amount": 1500.0})
    assert res.status_code == 400
    assert "Payout over $1,000 requires handler sign-off" in res.json()["detail"]

    # Handler signs off
    res = client.post("/api/claims/CLM-1003/sign-off")
    assert res.status_code == 200
    assert res.json()["signed_off"] is True

    # Payment after sign-off succeeds
    res = client.post("/api/claims/CLM-1003/pay", json={"amount": 1500.0})
    assert res.status_code == 200
    assert res.json()["status"] == "decided"
    assert res.json()["paid"] is True

    # Decline claim
    res = client.post(
        "/api/claims/CLM-1002/decision",
        json={
            "decision": "decline",
            "payout": 0.0,
            "reason": "Loss not covered.",
            "policy_section": "9. General exclusions",
        },
    )
    assert res.status_code == 200
    assert res.json()["status"] == "decided"

    # Activity logging and reading
    res = client.post(
        "/api/claims/CLM-1001/activity",
        json={"action": "Reading policy documentation"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    res = client.get("/api/claims/CLM-1001/activity")
    assert res.status_code == 200
    activities = res.json()
    assert len(activities) >= 2
    assert any("Reading policy" in a["action"] for a in activities)

    # Run agent endpoint test
    monkeypatch.setattr(
        agent.main, "run", lambda cid, tid: f"Agent decided claim {cid}."
    )
    res = client.post("/api/claims/CLM-1001/run")
    assert res.status_code == 200
    assert res.json()["agent_reply"] == "Agent decided claim CLM-1001."

    # Run all claims endpoint test
    res = client.post("/api/claims/run-all")
    assert res.status_code == 200
    assert "processed" in res.json()

    # 404 tests
    assert client.post("/api/claims/NONEXISTENT/run").status_code == 404
    assert (
        client.post(
            "/api/claims/NONEXISTENT/decision",
            json={
                "decision": "approve",
                "payout": 100.0,
                "reason": "test",
                "policy_section": "1",
            },
        ).status_code
        == 404
    )
    assert (
        client.post("/api/claims/NONEXISTENT/pay", json={"amount": 100.0}).status_code
        == 404
    )
    assert client.post("/api/claims/NONEXISTENT/sign-off").status_code == 404
    assert client.get("/api/claims/NONEXISTENT/activity").status_code == 404
    assert (
        client.post(
            "/api/claims/NONEXISTENT/activity", json={"action": "test"}
        ).status_code
        == 404
    )
