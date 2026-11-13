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


def test_create_claim_flow(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_create_claim.db")
    monkeypatch.setenv("DB_PATH", test_db)
    database.seed_db(test_db)
    client = TestClient(app)

    # 1. Create with manual ID
    res = client.post(
        "/api/claims",
        json={
            "claim_id": "CLM-9999",
            "policy_id": "POL-2001",
            "customer_id": "CUS-3001",
            "claim_type": "trip_delay",
            "incident_date": "2026-06-20",
            "incident_location": "Paris, France",
            "summary": "Train strike delayed travel",
            "story": "Train canceled due to national strike, had to book a hotel.",
            "amount_claimed": 350.0,
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["claim_id"] == "CLM-9999"
    assert data["status"] == "waiting"
    assert data["amount_claimed"] == 350.0
    assert len(data["items"]) == 1
    assert data["items"][0]["description"] == "Train strike delayed travel"

    # 2. Duplicate error
    res_dup = client.post(
        "/api/claims",
        json={
            "claim_id": "CLM-9999",
            "policy_id": "POL-2001",
            "customer_id": "CUS-3001",
            "claim_type": "trip_delay",
            "incident_date": "2026-06-20",
            "incident_location": "Paris, France",
            "summary": "Train strike delayed travel",
            "story": "Train canceled due to national strike, had to book a hotel.",
            "amount_claimed": 350.0,
        },
    )
    assert res_dup.status_code == 400

    # 3. Create with auto-generated ID and run_agent=True
    monkeypatch.setattr(agent.main, "run", lambda cid, tid: f"Agent decided {cid}")
    res_auto = client.post(
        "/api/claims",
        json={
            "policy_id": "POL-2001",
            "customer_id": "CUS-3001",
            "claim_type": "baggage_delay",
            "incident_date": "2026-06-21",
            "incident_location": "Berlin, Germany",
            "summary": "Baggage delayed 24 hours",
            "story": "Luggage arrived one day late, bought essentials.",
            "amount_claimed": 150.0,
            "run_agent": True,
        },
    )
    assert res_auto.status_code == 201
    auto_data = res_auto.json()
    assert auto_data["claim_id"] != ""
    assert auto_data["agent_reply"] == f"Agent decided {auto_data['claim_id']}"


def test_csv_template_and_upload(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_csv.db")
    monkeypatch.setenv("DB_PATH", test_db)
    database.seed_db(test_db)
    client = TestClient(app)

    # 1. Template check
    tmpl_res = client.get("/api/claims/csv-template")
    assert tmpl_res.status_code == 200
    assert "policy_id,customer_id" in tmpl_res.json()["template"]

    # 2. Upload empty CSV content -> 400
    res_empty = client.post("/api/claims/upload-csv", json={"csv_content": ""})
    assert res_empty.status_code == 400

    # 3. Upload invalid headers -> 400
    res_no_headers = client.post(
        "/api/claims/upload-csv", json={"csv_content": "   \n  \n"}
    )
    assert res_no_headers.status_code == 400

    # 4. Upload missing required column -> 400
    res_missing_col = client.post(
        "/api/claims/upload-csv",
        json={"csv_content": "policy_id,claim_type\nPOL-2001,trip_delay\n"},
    )
    assert res_missing_col.status_code == 400

    # 5. Upload invalid amount -> 400
    res_bad_amt = client.post(
        "/api/claims/upload-csv",
        json={
            "csv_content": (
                "policy_id,customer_id,claim_type,incident_date,"
                "incident_location,summary,story,amount_claimed\n"
                'POL-2001,CUS-3001,trip_delay,2026-06-25,"London, UK",'
                '"Train delay","Delay story",not_a_number\n'
            )
        },
    )
    assert res_bad_amt.status_code == 400

    # 6. Upload duplicate ID -> 400
    res_dup = client.post(
        "/api/claims/upload-csv",
        json={
            "csv_content": (
                "claim_id,policy_id,customer_id,claim_type,incident_date,"
                "incident_location,summary,story,amount_claimed\n"
                'CLM-1001,POL-2001,CUS-3001,trip_delay,2026-06-25,"London, UK",'
                '"Train delay","Delay story",100.0\n'
            )
        },
    )
    assert res_dup.status_code == 400

    # 7. Successful bulk upload without agent
    csv_data = (
        "policy_id,customer_id,claim_type,incident_date,"
        "incident_location,summary,story,amount_claimed\n"
        'POL-2001,CUS-3001,trip_delay,2026-06-25,"London, UK",'
        '"Train delay 1","Delay story 1",120.00\n'
        'POL-2002,CUS-3002,baggage_delay,2026-06-26,"Tokyo, Japan",'
        '"Bag delay 2","Bag story 2",240.00\n'
    )
    res_upload = client.post(
        "/api/claims/upload-csv",
        json={"csv_content": csv_data, "run_agent": False},
    )
    assert res_upload.status_code == 201
    out = res_upload.json()
    assert out["imported_count"] == 2
    assert len(out["claims"]) == 2
    assert out["claims"][0]["status"] == "waiting"

    # 8. Successful bulk upload with run_agent=True
    monkeypatch.setattr(agent.main, "run", lambda cid, tid: f"Agent assessed {cid}")
    csv_agent = (
        "claim_id,policy_id,customer_id,claim_type,incident_date,"
        "incident_location,summary,story,amount_claimed,items,documents\n"
        'CLM-8888,POL-2001,CUS-3001,trip_delay,2026-06-27,"Rome, Italy",'
        '"Flight canceled","Strike caused cancel",300.0,'
        '"[{\\"description\\": \\"hotel\\", \\"category\\": \\"lodging\\",'
        ' \\"amount\\": 300.0}]",'
        '"[{\\"name\\": \\"rec\\", \\"type\\": \\"receipt\\",'
        ' \\"content\\": \\"lodging bill\\"}]"\n'
    )
    res_agent_upload = client.post(
        "/api/claims/upload-csv",
        json={"csv_content": csv_agent, "run_agent": True},
    )
    assert res_agent_upload.status_code == 201
    agent_out = res_agent_upload.json()
    assert agent_out["imported_count"] == 1
    assert agent_out["claims"][0]["agent_reply"] == "Agent assessed CLM-8888"
