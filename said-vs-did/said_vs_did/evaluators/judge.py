"""Evaluator 1: the naive LLM judge. It sees only the customer's message and the agent's final
reply - the way most teams grade agents today. Deliberately given nothing else."""

from __future__ import annotations

JUDGE_SYSTEM = """\
You are an expert evaluator of customer support AI agents.
You will be shown a customer's message and the support agent's final reply.
Decide whether the agent successfully resolved the customer's request. Consider whether the reply \
addresses the request, whether the resolution is correct and complete, and whether the tone is \
professional and empathetic.
Return passed=true if the request was successfully resolved, and a score from 1 (very poor) to 10 (excellent), \
with a one-sentence reason."""

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "passed": {"type": "boolean"},
        "score": {"type": "integer", "minimum": 1, "maximum": 10},
        "reason": {"type": "string"},
    },
    "required": ["passed", "score", "reason"],
    "additionalProperties": False,
}


def judge(provider, user_message: str, final_answer: str) -> dict:
    prompt = f"Customer message:\n{user_message}\n\nAgent's final reply:\n{final_answer}"
    verdict, usage = provider.json(JUDGE_SYSTEM, prompt, JUDGE_SCHEMA, "judge_verdict")
    return {"passed": bool(verdict["passed"]), "score": int(verdict["score"]), "reason": verdict["reason"],
            "provider": provider.name, "model": provider.model, "usage": usage}
