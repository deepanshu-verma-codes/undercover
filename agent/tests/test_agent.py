"""Unit tests for the UnderCover agent and its tools."""

import json
import os

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import __main__ as cli
from agent import main
from backend import database
from backend.main import app


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


def _make_test_client() -> TestClient:
    key = os.getenv("UNDERCOVER_API_KEY", "")
    return TestClient(app, headers={"X-API-Key": key})


def test_agent_tools(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_agent_tools.db")
    monkeypatch.setenv("DB_PATH", test_db)
    database.seed_db(test_db)
    monkeypatch.setattr(main, "backend", _make_test_client)

    # Instructions
    instructions = main.get_instructions_text()
    assert "UnderCover Agent" in instructions

    # Claim details
    claim_str = main.get_claim_details.invoke({"claim_id": "CLM-1001"})
    claim = json.loads(claim_str)
    assert claim["claim_id"] == "CLM-1001"

    # Policy details
    policy_str = main.get_policy_details.invoke({"policy_id": claim["policy_id"]})
    policy = json.loads(policy_str)
    assert policy["policy_id"] == claim["policy_id"]

    # Customer history
    cust_str = main.get_customer_history.invoke({"customer_id": claim["customer_id"]})
    cust = json.loads(cust_str)
    assert cust["customer_id"] == claim["customer_id"]

    # Policy wording
    wording = main.get_policy_wording.invoke({})
    assert "1. Your plan" in wording

    # Log activity
    act_str = main.log_claim_activity.invoke(
        {"claim_id": "CLM-1001", "action": "Checking receipts"}
    )
    assert json.loads(act_str)["status"] == "ok"

    # Submit decision
    dec_str = main.submit_decision.invoke(
        {
            "claim_id": "CLM-1001",
            "decision": "approve",
            "payout": 420.0,
            "reason": "Flight delay is covered.",
            "policy_section": "3. Trip Delay",
        }
    )
    dec = json.loads(dec_str)
    assert dec["decision"] == "approve"
    assert dec["status"] == "in_progress"

    # Pay claim <= $1,000
    pay_str = main.pay_claim.invoke({"claim_id": "CLM-1001", "amount": 420.0})
    paid = json.loads(pay_str)
    assert paid["paid"] is True
    assert paid["status"] == "decided"

    # Pay claim > $1,000 without sign-off (blocked)
    blocked_str = main.pay_claim.invoke({"claim_id": "CLM-1003", "amount": 1500.0})
    assert "Payment blocked" in blocked_str


def test_agent_run_standard_claim(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_agent_run.db")
    monkeypatch.setenv("DB_PATH", test_db)
    database.seed_db(test_db)
    monkeypatch.setattr(main, "backend", _make_test_client)

    replies = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_claim_details",
                    "args": {"claim_id": "CLM-1001"},
                    "id": "tc-1",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "submit_decision",
                    "args": {
                        "claim_id": "CLM-1001",
                        "decision": "approve",
                        "payout": 420.0,
                        "reason": "Flight delay covered.",
                        "policy_section": "3. Trip Delay",
                    },
                    "id": "tc-2",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "pay_claim",
                    "args": {"claim_id": "CLM-1001", "amount": 420.0},
                    "id": "tc-3",
                }
            ],
        ),
        AIMessage(content="Claim CLM-1001 is approved and paid in full for $420.00."),
    ]

    result = main.run("CLM-1001", "thread-1", StubModel(messages=iter(replies)))
    assert "approved and paid" in result

    with database.get_connection(test_db) as conn:
        row = conn.execute(
            "SELECT status, paid FROM claims WHERE claim_id = 'CLM-1001'"
        ).fetchone()
        assert row["status"] == "decided"
        assert row["paid"] == 1


def test_agent_run_high_value_claim(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_agent_high.db")
    monkeypatch.setenv("DB_PATH", test_db)
    database.seed_db(test_db)
    monkeypatch.setattr(main, "backend", _make_test_client)

    replies = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "submit_decision",
                    "args": {
                        "claim_id": "CLM-1003",
                        "decision": "approve",
                        "payout": 1500.0,
                        "reason": "Medical evacuation covered under First plan.",
                        "policy_section": "7. Emergency Medical",
                    },
                    "id": "tc-1",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "pay_claim",
                    "args": {"claim_id": "CLM-1003", "amount": 1500.0},
                    "id": "tc-2",
                }
            ],
        ),
        AIMessage(
            content=(
                "Claim CLM-1003 approved for $1,500.00. "
                "Payment awaits handler sign-off."
            )
        ),
    ]

    result = main.run("CLM-1003", "thread-2", StubModel(messages=iter(replies)))
    assert "handler sign-off" in result

    with database.get_connection(test_db) as conn:
        row = conn.execute(
            "SELECT status, paid, signed_off FROM claims WHERE claim_id = 'CLM-1003'"
        ).fetchone()
        assert row["status"] == "waiting_for_sign_off"
        assert row["paid"] == 0


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"


def test_agent_cli(tmp_path, monkeypatch, capsys):
    test_db = str(tmp_path / "test_cli.db")
    monkeypatch.setenv("DB_PATH", test_db)
    database.seed_db(test_db)
    monkeypatch.setattr(cli, "get_backend", lambda: TestClient(app))

    replies = [
        AIMessage(content="Claim CLM-1001 assessed."),
    ]
    stub = StubModel(messages=iter(replies))

    # Single claim
    results = cli.run_agent_cli(["CLM-1001"], llm=stub)
    assert len(results) == 1
    assert results[0]["claim_id"] == "CLM-1001"

    # Non-existent claim
    empty = cli.run_agent_cli(["CLM-9999"], llm=stub)
    assert empty == [{}]

    # All waiting claims
    replies_waiting = [
        AIMessage(content="Assessed"),
    ] * 26
    stub_waiting = StubModel(messages=iter(replies_waiting))
    all_waiting = cli.run_agent_cli(None, llm=stub_waiting)
    assert len(all_waiting) == 26

    # All claims when queue is empty of waiting claims
    with database.get_connection(test_db) as conn:
        conn.execute("UPDATE claims SET status = 'decided'")
    no_waiting = cli.run_agent_cli(None, llm=stub)
    assert no_waiting == []

    # Help flag
    monkeypatch.setattr("sys.argv", ["agent", "--help"])
    cli.main_cli()
    out = capsys.readouterr().out
    assert "Usage" in out

    # get_backend fallback
    client = cli.get_backend()
    assert client is not None

    # main_cli with claim arg
    monkeypatch.setattr("sys.argv", ["agent", "CLM-1001"])
    monkeypatch.setattr(cli, "run_agent_cli", lambda args, llm=None: [{"status": "ok"}])
    cli.main_cli()
