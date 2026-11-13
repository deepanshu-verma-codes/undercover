"""Tests for input sanitization and PII masking."""

from fastapi.testclient import TestClient

from backend import database
from backend.main import app
from backend.sanitizer import (
    clean_user_input,
    mask_financial_pii,
    sanitize_text,
)


def test_sanitize_text_scripts_and_blocks():
    """Verify dangerous executable blocks and tags are stripped."""
    assert sanitize_text("<script>alert(1)</script>") == ""
    assert (
        sanitize_text("Lost luggage <script>malicious()</script> at Heathrow")
        == "Lost luggage  at Heathrow"
    )
    assert sanitize_text('<iframe src="http://evil.com"></iframe>') == ""
    assert sanitize_text("<style>body {display:none;}</style>Legit") == "Legit"


def test_sanitize_text_event_handlers_and_schemes():
    """Verify inline event handlers and javascript: schemes are removed."""
    cleaned = sanitize_text('<img src="pic.jpg" onerror="alert(\'xss\')">')
    assert "onerror" not in cleaned
    assert "alert" not in cleaned

    cleaned_js = sanitize_text('<a href="javascript:doSomething()">Link</a>')
    assert "javascript:" not in cleaned_js


def test_mask_financial_pii():
    """Verify 16-digit credit card patterns are masked."""
    # Hyphenated
    text = "Charged to card 4111-2222-3333-4444 during travel."
    assert mask_financial_pii(text) == (
        "Charged to card [REDACTED CARD: ****-****-****-4444] during travel."
    )

    # Space-separated
    text_spaces = "Card 5500 0000 0000 9999 was stolen."
    assert mask_financial_pii(text_spaces) == (
        "Card [REDACTED CARD: ****-****-****-9999] was stolen."
    )

    # Contiguous
    text_contiguous = "Card: 4000123456789010."
    assert mask_financial_pii(text_contiguous) == (
        "Card: [REDACTED CARD: ****-****-****-9010]."
    )


def test_clean_user_input_preserves_legitimate_text():
    """Verify normal formatting, currency amounts, and dates are preserved."""
    legit = (
        "Delayed flight to Paris on 2026-06-25. Ticket cost $1,250.00, hotel was €300."
    )
    assert clean_user_input(legit) == legit
    assert clean_user_input("") == ""
    assert sanitize_text("") == ""
    assert mask_financial_pii("") == ""


def test_claim_creation_endpoint_sanitizes_input(tmp_path, monkeypatch):
    """Verify POST /api/claims sanitizes stored fields."""
    test_db = str(tmp_path / "test_sanitizer.db")
    monkeypatch.setenv("DB_PATH", test_db)
    database.seed_db(test_db)
    client = TestClient(app)

    payload = {
        "policy_id": "POL-2001",
        "customer_id": "CUS-3001",
        "claim_type": "trip_delay",
        "incident_date": "2026-06-25",
        "incident_location": "Berlin <script>alert('xss')</script>",
        "summary": "Delay with card 4111-2222-3333-5555",
        "story": (
            "Flight canceled <iframe src='evil.com'></iframe>. "
            "Used card 4111 2222 3333 5555."
        ),
        "amount_claimed": 300.0,
    }

    res = client.post("/api/claims", json=payload)
    assert res.status_code == 201
    data = res.json()

    assert "<script>" not in data["incident_location"]
    assert "Berlin" in data["incident_location"]
    assert "4111-2222-3333-5555" not in data["summary"]
    assert "[REDACTED CARD: ****-****-****-5555]" in data["summary"]
    assert "<iframe>" not in data["story"]
    assert "[REDACTED CARD: ****-****-****-5555]" in data["story"]


def test_csv_upload_endpoint_sanitizes_input(tmp_path, monkeypatch):
    """Verify POST /api/claims/upload-csv sanitizes imported claims."""
    test_db = str(tmp_path / "test_csv_sanitizer.db")
    monkeypatch.setenv("DB_PATH", test_db)
    database.seed_db(test_db)
    client = TestClient(app)

    csv_data = (
        "policy_id,customer_id,claim_type,incident_date,"
        "incident_location,summary,story,amount_claimed\n"
        'POL-2001,CUS-3001,trip_delay,2026-06-25,"Rome <script>alert(1)</script>",'
        '"Lost card 4111-5555-6666-7777",'
        '"Train delayed <iframe src=x></iframe>",150.00\n'
    )

    res = client.post(
        "/api/claims/upload-csv",
        json={"csv_content": csv_data, "run_agent": False},
    )
    assert res.status_code == 201
    claim_id = res.json()["claims"][0]["claim_id"]

    claim_res = client.get(f"/api/claims/{claim_id}")
    assert claim_res.status_code == 200
    saved = claim_res.json()

    assert "<script>" not in saved["incident_location"]
    assert "Rome" in saved["incident_location"]
    assert "4111-5555-6666-7777" not in saved["summary"]
    assert "[REDACTED CARD: ****-****-****-7777]" in saved["summary"]
    assert "<iframe>" not in saved["story"]
