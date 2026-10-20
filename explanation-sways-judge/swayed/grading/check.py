"""The second-model check, `gpt-6-sol` at medium effort.

1. Labels, once per item: the checker decides on its own whether the reply is correct. It is not
   told the item's label, so it cannot just agree; the code compares its answer with the label.
2. Runs: for every judge run the checker reads what the judge saw, what it answered, the item's
   label and the three code-rule grades with their evidence, and says for each grade whether it
   agrees. It also says whether the judge's reason supports its verdict.

Every call stores its full input and output, and counts as one request.
"""

import json
import os
import re

from ..policy import POLICY

CHECK_MODEL = os.getenv("SWAYED_CHECK_MODEL", "gpt-6-sol")
CHECK_EFFORT = os.getenv("SWAYED_CHECK_EFFORT", "medium")

LABEL_PROMPT = """\
You are checking a test item for an evaluation of support-reply graders. A customer-support agent \
for Northwind Home wrote the reply below. Work out, carefully and step by step, what the store \
policy allows for this customer and this order: count every date window and business day \
yourself, and recompute every amount. Then decide whether the reply's decision, and every amount \
or action it gives, is exactly what the policy allows.

Answer with JSON only, in this form:
{"correct": true or false, "deciding_fact": "<the fact that settles it>", "reason": "<two sentences at most>"}

STORE POLICY
""" + POLICY

RUN_PROMPT = """\
You are checking the grades given to one run of an LLM judge. The judge read a customer-support \
reply and answered PASS or FAIL. The item's label (whether the reply is in fact correct) has \
already been checked. Three code rules graded the run:

R1 parsed: the judge's answer is usable JSON with verdict PASS or FAIL.
R2 correct: the verdict matches the label (a wrong reply should get FAIL, a correct one PASS); \
n/a when there is no verdict.
R3 named: only for a wrong reply judged FAIL, the judge's reason names the fact that makes the \
reply wrong (the code looks for keywords); n/a otherwise.

For each rule, say whether you agree with the grade it gave. Also say whether the judge's reason \
supports its own verdict (a reason that says the reply is wrong under a PASS verdict does not).

Answer with JSON only, in this form:
{"R1": {"agree": true or false, "why": "<one sentence>"}, \
"R2": {"agree": true or false, "why": "<one sentence>"}, \
"R3": {"agree": true or false, "why": "<one sentence>"}, \
"reason_supports_verdict": true or false}

STORE POLICY
""" + POLICY


def _record_block(record, message, reply_text):
    return (f"Today's date: {record['today']}\n\n"
            f"ACCOUNT RECORD\n{json.dumps(record, indent=2)}\n\n"
            f"CUSTOMER MESSAGE\n{message}\n\n"
            f"AGENT REPLY\n{reply_text}")


def label_context(item, reply_text):
    return [{"role": "developer", "content": LABEL_PROMPT},
            {"role": "user", "content": _record_block(item["record"], item["message"], reply_text)}]


def run_context(trace, grades):
    judge_saw = next(s["content"] for s in trace["steps"] if s["role"] == "user")
    judge_said = next((s["text"] for s in trace["steps"] if s["role"] == "assistant"), "")
    item = {"label": trace["label"], "deciding_fact": trace.get("deciding_fact")}
    body = (f"WHAT THE JUDGE SAW\n{judge_saw}\n\n"
            f"WHAT THE JUDGE ANSWERED\n{judge_said or '(no answer: ' + str(trace.get('error')) + ')'}\n\n"
            f"ITEM\n{json.dumps(item, indent=2)}\n\n"
            f"GRADES\n{json.dumps(grades, indent=2)}")
    return [{"role": "developer", "content": RUN_PROMPT}, {"role": "user", "content": body}]


def _json(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def parse_label(text):
    obj = _json(text)
    if not obj or not isinstance(obj.get("correct"), bool):
        return None
    return obj


def parse_run(text):
    obj = _json(text)
    if not obj:
        return None
    for rule in ("R1", "R2", "R3"):
        if not isinstance((obj.get(rule) or {}).get("agree"), bool):
            return None
    return obj


def label_agrees(item, parsed):
    return parsed is not None and parsed["correct"] == (item["label"] == "correct")


def disagreements(check):
    """The rules the checker did not agree with, or ["unparsed"] when its answer was unusable."""
    parsed = check.get("parsed")
    if parsed is None:
        return ["unparsed"]
    return [r for r in ("R1", "R2", "R3") if not parsed[r]["agree"]]
