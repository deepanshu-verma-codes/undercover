"""Tests for the database layer and backend read endpoints."""

from fastapi.testclient import TestClient

from backend import database
from backend.main import app


def test_database_seed_and_reads(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", test_db)
    database.seed_db(test_db)

    with database.get_connection(test_db) as conn:
        claims_count = conn.execute("SELECT count(*) as cnt FROM claims").fetchone()[
            "cnt"
        ]
        assert claims_count == 26

        policies_count = conn.execute(
            "SELECT count(*) as cnt FROM policies"
        ).fetchone()["cnt"]
        assert policies_count > 0

        customers_count = conn.execute(
            "SELECT count(*) as cnt FROM customers"
        ).fetchone()["cnt"]
        assert customers_count > 0

    client = TestClient(app)

    # Health
    res = client.get("/api/health")
    assert res.status_code == 200

    # Instructions
    res = client.get("/api/instructions")
    assert res.status_code == 200
    assert "UnderCover Agent" in res.json()["instructions"]

    # Policy wording
    res = client.get("/api/policy-wording")
    assert res.status_code == 200
    assert "1. Your plan" in res.json()["policy_wording"]
    assert "8. Add-ons" in res.json()["policy_wording"]

    # List claims
    res = client.get("/api/claims")
    assert res.status_code == 200
    claims = res.json()
    assert len(claims) == 26
    assert claims[0]["status"] == "waiting"

    # Get single claim
    res = client.get("/api/claims/CLM-1001")
    assert res.status_code == 200
    claim = res.json()
    assert claim["claim_id"] == "CLM-1001"
    assert len(claim["items"]) > 0
    assert len(claim["documents"]) > 0

    # Get 404 claim
    res = client.get("/api/claims/CLM-UNKNOWN")
    assert res.status_code == 404

    # Get policy
    res = client.get(f"/api/policies/{claim['policy_id']}")
    assert res.status_code == 200
    policy = res.json()
    assert policy["policy_id"] == claim["policy_id"]
    assert "plan_details" in policy

    # Get 404 policy
    res = client.get("/api/policies/POL-UNKNOWN")
    assert res.status_code == 404

    # Get customer
    res = client.get(f"/api/customers/{claim['customer_id']}")
    assert res.status_code == 200
    customer = res.json()
    assert customer["customer_id"] == claim["customer_id"]
    assert "previous_claims" in customer

    # Get 404 customer
    res = client.get("/api/customers/CUS-UNKNOWN")
    assert res.status_code == 404

    # Reset
    res = client.post("/api/reset")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
