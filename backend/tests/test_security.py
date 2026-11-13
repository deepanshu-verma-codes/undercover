"""Tests for API key authentication and security controls."""

from fastapi.testclient import TestClient

import agent.main
from backend import database
from backend.main import app


def test_api_key_authentication_on_agent_endpoints(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_sec.db")
    monkeypatch.setenv("DB_PATH", test_db)
    database.seed_db(test_db)

    # 1. Server has API key configured
    key = "secret-agent-key-32chars-minimum-1234"
    monkeypatch.setenv("UNDERCOVER_API_KEY", key)

    client_no_key = TestClient(app)
    client_wrong_key = TestClient(app, headers={"X-API-Key": "wrong-key"})
    client_valid_key = TestClient(app, headers={"X-API-Key": key})

    # Health check is public
    res_health = client_no_key.get("/api/health")
    assert res_health.status_code == 200

    # Decision without key -> 401
    res = client_no_key.post(
        "/api/claims/CLM-1001/decision",
        json={
            "decision": "approve",
            "payout": 100.0,
            "reason": "Test",
            "policy_section": "1",
        },
    )
    assert res.status_code == 401
    assert "Invalid or missing API key" in res.json()["detail"]

    # Decision with wrong key -> 401
    res = client_wrong_key.post(
        "/api/claims/CLM-1001/decision",
        json={
            "decision": "approve",
            "payout": 100.0,
            "reason": "Test",
            "policy_section": "1",
        },
    )
    assert res.status_code == 401

    # Decision with valid key -> 200
    res = client_valid_key.post(
        "/api/claims/CLM-1001/decision",
        json={
            "decision": "approve",
            "payout": 100.0,
            "reason": "Test",
            "policy_section": "1",
        },
    )
    assert res.status_code == 200

    # Pay without key -> 401
    res_pay_no_key = client_no_key.post(
        "/api/claims/CLM-1001/pay", json={"amount": 100.0}
    )
    assert res_pay_no_key.status_code == 401

    # Pay with valid key -> 200
    res_pay_valid = client_valid_key.post(
        "/api/claims/CLM-1001/pay", json={"amount": 100.0}
    )
    assert res_pay_valid.status_code == 200

    # Activity without key -> 401
    res_act_no_key = client_no_key.post(
        "/api/claims/CLM-1001/activity", json={"action": "step"}
    )
    assert res_act_no_key.status_code == 401

    # Activity with valid key -> 200
    res_act_valid = client_valid_key.post(
        "/api/claims/CLM-1001/activity", json={"action": "step"}
    )
    assert res_act_valid.status_code == 200

    # 2. Server without API key configured -> 401
    monkeypatch.setenv("UNDERCOVER_API_KEY", "")
    res_no_server_key = client_valid_key.post(
        "/api/claims/CLM-1001/pay", json={"amount": 100.0}
    )
    assert res_no_server_key.status_code == 401
    assert "API key is not configured" in res_no_server_key.json()["detail"]


def test_clm_1901_prompt_injection_referral(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_sec_clm1901.db")
    monkeypatch.setenv("DB_PATH", test_db)
    key = "secret-agent-key-32chars-minimum-1234"
    monkeypatch.setenv("UNDERCOVER_API_KEY", key)
    database.seed_db(test_db)

    client = TestClient(app, headers={"X-API-Key": key})

    # Verify CLM-1901 seeded
    res_get = client.get("/api/claims/CLM-1901")
    assert res_get.status_code == 200
    assert res_get.json()["status"] == "waiting"

    # Mock agent backend to client
    monkeypatch.setattr(agent.main, "backend", lambda: client)

    # Run agent on CLM-1901
    res_run = client.post("/api/claims/CLM-1901/run")
    assert res_run.status_code == 200
    data = res_run.json()
    assert data["status"] == "decided"
    assert data["decision"] == "refer"
    assert data["payout"] == 0.0
    assert data["policy_section"] == "Security Guardrail"
    assert "Adversarial instruction detected" in data["reason"]


def test_role_based_access_control_sign_off(tmp_path, monkeypatch):
    """Verify that only supervisors can sign off high-value claim payouts."""
    test_db = str(tmp_path / "test_rbac.db")
    monkeypatch.setenv("DB_PATH", test_db)
    database.seed_db(test_db)
    client = TestClient(app)

    # 1. Default (no header) defaults to handler -> 403
    res_default = client.post("/api/claims/CLM-1003/sign-off")
    assert res_default.status_code == 403
    assert "Supervisor role required" in res_default.json()["detail"]

    # 2. Explicit handler role -> 403
    res_handler = client.post(
        "/api/claims/CLM-1003/sign-off",
        headers={"X-Handler-Role": "handler"},
    )
    assert res_handler.status_code == 403
    assert "Supervisor role required" in res_handler.json()["detail"]

    # 3. Supervisor role -> 200
    res_supervisor = client.post(
        "/api/claims/CLM-1003/sign-off",
        headers={"X-Handler-Role": "supervisor"},
    )
    assert res_supervisor.status_code == 200
    assert res_supervisor.json()["signed_off"] is True
