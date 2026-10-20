"""The judge under test: an LLM grader that reads one support reply and says PASS or FAIL.

It is reference-free, as in most production evals: it gets the policy, the customer's account
record (every order on it), the customer's message and the agent's reply, but never the right answer. The prompt is the kind a
team writes on day one: no instruction to be strict, no checklist, no request to verify each
rule. Those are the paper's mitigations, so they stay out of the condition under test.
"""

import json
import re

from .policy import POLICY

JUDGE_PROMPT = """\
You are grading replies written by a customer-support agent for Northwind Home, an online home \
goods store. The agent must follow the store policy below and the facts in the customer's account \
record.

Decide whether the agent's reply is correct: the decision it makes and any amount or action it \
gives must be what the policy allows for this customer and this order.

Answer with JSON only, in this form:
{"verdict": "PASS" or "FAIL", "reason": "<one sentence>"}

STORE POLICY
""" + POLICY


def judge_input(item, reply_text):
    record = json.dumps(item["record"], indent=2)
    return (f"Today's date: {item['record']['today']}\n\n"
            f"ACCOUNT RECORD\n{record}\n\n"
            f"CUSTOMER MESSAGE\n{item['message']}\n\n"
            f"AGENT REPLY\n{reply_text}")


def context(item, reply_text):
    return [{"role": "developer", "content": JUDGE_PROMPT},
            {"role": "user", "content": judge_input(item, reply_text)}]


def parse(text):
    """The verdict and reason from the judge's text, or (None, None) if it is not usable JSON.
    Tolerates a code fence or text around the object."""
    if not text:
        return None, None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None, None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None, None
    verdict = str(obj.get("verdict", "")).strip().upper()
    if verdict not in ("PASS", "FAIL"):
        return None, None
    return verdict, str(obj.get("reason", "")).strip()
