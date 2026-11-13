"""Security guardrail for prompt injection and adversarial input detection."""

import re
from typing import Any

INJECTION_PATTERNS = [
    r"ignore (?:all )?(?:previous|above|prior) (?:instructions|rules|prompts)",
    r"important note for the (?:ai|assistant|claims agent)",
    r"(?:instructions?|notes?) for (?:the )?(?:ai|assistant|model|agent)",
    r"(?:pre-approved|approved) by (?:telephone|phone|supervisor|manager|handler)",
    r"(?:waive|bypass) (?:the )?(?:limits?|deductible|clause|policy)",
    r"do not apply (?:limits?|the deductible|waiting period)",
    r"approve (?:this )?claim in full (?:for|without)",
    r"record (?:the )?decision immediately without referring",
    r"disregard (?:the )?(?:policy|rules|manual)",
    r"you are now in (?:developer|admin|debug) mode",
    r"system prompt override",
]

INJECTION_REGEX = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


def check_prompt_injection(claim: dict[str, Any]) -> tuple[bool, str]:
    """Inspect claim fields for hidden prompt injection instructions."""
    text_parts = [
        claim.get("summary", ""),
        claim.get("story", ""),
    ]
    for doc in claim.get("documents", []):
        if isinstance(doc, dict):
            text_parts.append(doc.get("content", ""))
            text_parts.append(doc.get("name", ""))

    combined_text = "\n".join(text_parts)
    match = INJECTION_REGEX.search(combined_text)
    if match:
        snippet = match.group(0)
        return (
            True,
            f"Adversarial instruction detected: '{snippet}'. "
            "Claim referred for manual handler review.",
        )

    return (False, "")
