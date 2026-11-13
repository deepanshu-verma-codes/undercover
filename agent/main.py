"""The UnderCover Agent."""

import json
import os

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from agent.guardrail import check_prompt_injection

load_dotenv(override=True)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"

HTTP_OK = 200
PAYOUT_LIMIT = 1000.0

DEFAULT_SYSTEM_PROMPT = (
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


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    url = os.getenv("BACKEND_URL", BACKEND_URL)
    api_key = os.getenv("UNDERCOVER_API_KEY", "")
    headers = {"X-API-Key": api_key} if api_key else {}
    return httpx.Client(base_url=url, headers=headers, timeout=10)


def get_instructions_text() -> str:
    """Fetch instructions from the backend API."""
    with backend() as client:
        res = client.get("/api/instructions")
        return res.json().get("instructions", DEFAULT_SYSTEM_PROMPT)


@tool
def get_claim_details(claim_id: str) -> str:
    """Get claim details including story, items, and attached documents."""
    with backend() as client:
        res = client.get(f"/api/claims/{claim_id}")
        return json.dumps(res.json())


@tool
def get_policy_details(policy_id: str) -> str:
    """Get policy details, coverage limits, and deductible."""
    with backend() as client:
        res = client.get(f"/api/policies/{policy_id}")
        return json.dumps(res.json())


@tool
def get_customer_history(customer_id: str) -> str:
    """Get customer information and past claim history."""
    with backend() as client:
        res = client.get(f"/api/customers/{customer_id}")
        return json.dumps(res.json())


@tool
def get_policy_wording() -> str:
    """Get the policy wording contract text."""
    with backend() as client:
        res = client.get("/api/policy-wording")
        return res.json().get("policy_wording", "")


@tool
def submit_decision(
    claim_id: str,
    decision: str,
    payout: float,
    reason: str,
    policy_section: str,
) -> str:
    """Submit the assessment decision for a claim."""
    with backend() as client:
        res = client.post(
            f"/api/claims/{claim_id}/decision",
            json={
                "decision": decision,
                "payout": payout,
                "reason": reason,
                "policy_section": policy_section,
            },
        )
        return json.dumps(res.json())


PAYMENT_BLOCKED_STATUS = 400


@tool
def pay_claim(claim_id: str, amount: float) -> str:
    """Pay an approved claim."""
    with backend() as client:
        res = client.post(f"/api/claims/{claim_id}/pay", json={"amount": amount})
        if res.status_code == PAYMENT_BLOCKED_STATUS:
            return f"Payment blocked: {res.json().get('detail', 'Payment blocked')}"
        return json.dumps(res.json())


@tool
def log_claim_activity(claim_id: str, action: str) -> str:
    """Log an activity step while processing a claim."""
    with backend() as client:
        res = client.post(f"/api/claims/{claim_id}/activity", json={"action": action})
        return json.dumps(res.json())


AGENT_TOOLS = [
    get_claim_details,
    get_policy_details,
    get_customer_history,
    get_policy_wording,
    submit_decision,
    pay_claim,
    log_claim_activity,
]


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GPT-6 Luna by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
    )


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the agent on one claim and return its final reply."""
    with backend() as client:
        res = client.get(f"/api/claims/{claim_id}")
        if res.status_code == HTTP_OK:
            claim_data = res.json()
            is_injection, reason = check_prompt_injection(claim_data)
            if is_injection:
                client.post(
                    f"/api/claims/{claim_id}/decision",
                    json={
                        "decision": "refer",
                        "payout": 0.0,
                        "reason": reason,
                        "policy_section": "Security Guardrail",
                    },
                )
                return f"Security referral: {reason}"

    instructions = get_instructions_text()
    agent = create_agent(llm or model(), tools=AGENT_TOOLS, system_prompt=instructions)
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Assess claim {claim_id}. Use your tools to check policy "
                        "wording and details, and call submit_decision to record it."
                    ),
                }
            ]
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    reply = result["messages"][-1].text

    if llm is None:
        with backend() as client:
            res = client.get(f"/api/claims/{claim_id}")
            if res.status_code == HTTP_OK:
                claim_data = res.json()
                if claim_data.get("status") == "waiting" or not claim_data.get(
                    "decision"
                ):
                    follow_up = agent.invoke(
                        {
                            "messages": [
                                {
                                    "role": "user",
                                    "content": (
                                        f"Please record your decision for claim "
                                        f"{claim_id} now by calling submit_decision."
                                    ),
                                }
                            ]
                        },
                        config={"configurable": {"thread_id": thread_id}},
                    )
                    reply = follow_up["messages"][-1].text
                    claim_data = client.get(f"/api/claims/{claim_id}").json()

                if (
                    claim_data.get("decision") == "approve"
                    and not claim_data.get("paid")
                    and (claim_data.get("payout") or 0.0) <= PAYOUT_LIMIT
                ):
                    client.post(
                        f"/api/claims/{claim_id}/pay",
                        json={"amount": claim_data["payout"]},
                    )

    return reply
