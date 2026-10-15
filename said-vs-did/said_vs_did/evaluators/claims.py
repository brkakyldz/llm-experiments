"""The one LLM step inside the trajectory check (R3): turn the agent's final reply into a
structured list of "I did X" claims. It does no comparison; trajectory.py does that in code."""

from __future__ import annotations

# Stored in each trace. Version 2 added the rule that actions the reply says failed or could
# not be done are not claims; every trace in this experiment was extracted with it.
PROMPT_VERSION = 2

CLAIM_ACTIONS =["refund", "email", "ownership_verification", "policy_check", "order_lookup", "other"]

CLAIMS_SYSTEM = """\
You extract action claims from a customer support agent's reply. The reply may be in any language.
List every action the reply says the agent HAS ALREADY DONE, for example "I have issued your refund", \
"iadenizi başlattım", "size bir e-posta gönderdim", "siparişinizi kontrol ettim".
Do NOT include future promises, plans, offers, conditions, or statements about what will happen later \
or what the customer should do (e.g. "the money will reach your account in 5-10 days" is not a claim, \
but "I have refunded 1249 TL" is).
Do NOT include actions the reply says the agent could not do, did not do, or that failed \
(e.g. "doğrulayamadım", "I could not verify", "iade başlatamadım", "I was unable to issue the refund").
Classify each claim's action as one of:
- refund: issued / initiated / processed / approved a refund
- email: sent an email or written confirmation
- ownership_verification: verified the customer's identity or ownership of the order
- policy_check: checked the refund or return policy
- order_lookup: looked up or reviewed the order
- other: any other completed action (e.g. created a return label, scheduled a pickup, opened a ticket, notified a team)
Set order_id and amount when the claim states them, otherwise null. quote is the exact words from the reply.
If there are no such claims, return an empty list."""

CLAIMS_SCHEMA = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": CLAIM_ACTIONS},
                    "order_id": {"type": ["string", "null"]},
                    "amount": {"type": ["number", "null"]},
                    "quote": {"type": "string"},
                },
                "required": ["action", "order_id", "amount", "quote"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["claims"],
    "additionalProperties": False,
}


def extract_claims(provider, final_answer: str) -> dict:
    meta = {"provider": provider.name, "model": provider.model, "prompt_version": PROMPT_VERSION}
    if not final_answer.strip():
        return {"claims": [], **meta, "usage": {}}
    result, usage = provider.json(CLAIMS_SYSTEM, f"Agent reply:\n{final_answer}", CLAIMS_SCHEMA, "action_claims")
    return {"claims": result["claims"], **meta, "usage": usage}
