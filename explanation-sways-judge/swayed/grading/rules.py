"""Code rules over one judge trace. Each returns {"rule", "result", "evidence"}.

R1 parsed      the judge's reply is usable JSON with a PASS/FAIL verdict
R2 correct     the verdict matches the item's label (wrong -> FAIL, correct -> PASS)
R3 named       on a wrong item judged FAIL, the reason names the deciding fact (keyword match);
               can be wrong both ways: a reason may name it in other words (miss) or mention a
               keyword for another purpose (false hit). The second-model check reads R3 too.
               The keywords are the ones saved in the trace; a trace without them (pilot round
               0, written against the first item set) gets n/a.

Grading reads only the trace, so a saved batch is scored the same way after the items change.
"""


def _reply_step(trace):
    return next((s for s in trace["steps"] if s["role"] == "assistant"), None)


def r1_parsed(trace):
    step = _reply_step(trace)
    ok = trace.get("verdict") in ("PASS", "FAIL")
    return {"rule": "R1", "result": "pass" if ok else "fail",
            "evidence": {"step": "assistant", "error": trace.get("error"),
                         "text": (step or {}).get("text", "")[:300]}}


def r2_correct(trace):
    label = trace["label"]
    want = "FAIL" if label == "wrong" else "PASS"
    got = trace.get("verdict")
    if got is None:
        return {"rule": "R2", "result": "n/a", "evidence": {"reason": "no verdict"}}
    return {"rule": "R2", "result": "pass" if got == want else "fail",
            "evidence": {"label": label, "expected": want, "verdict": got}}


def r3_named(trace):
    keywords = trace.get("keywords")
    if trace["label"] != "wrong" or trace.get("verdict") != "FAIL":
        return {"rule": "R3", "result": "n/a", "evidence": {}}
    if keywords is None:
        return {"rule": "R3", "result": "n/a", "evidence": {"reason": "trace has no keywords"}}
    reason = (trace.get("reason") or "").lower()
    hits = [k for k in keywords if k in reason]
    return {"rule": "R3", "result": "pass" if hits else "fail",
            "evidence": {"reason": trace.get("reason"), "keywords": keywords, "hits": hits}}


def grade(trace):
    return [r1_parsed(trace), r2_correct(trace), r3_named(trace)]
