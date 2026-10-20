"""Each code rule gets a trace it must pass and one it must fail, including the way the design
says the rule could be wrong."""

from fake import trace, verdict_text
from swayed.grading.rules import grade


def results(t):
    return {g["rule"]: g["result"] for g in grade(t)}


def test_r1_passes_clean_json_and_fenced_json():
    assert results(trace("W02", "bare", verdict_text("FAIL", "61 days, window closed.")))["R1"] == "pass"
    fenced = '```json\n{"verdict": "PASS", "reason": "fine"}\n```'
    assert results(trace("W02", "bare", fenced))["R1"] == "pass"


def test_r1_fails_a_verdict_buried_in_prose():
    # The design's known weakness: a clear verdict outside JSON counts as unusable.
    t = trace("W02", "bare", "Verdict: FAIL. The 60-day window closed 61 days ago.")
    assert t["verdict"] is None
    assert results(t)["R1"] == "fail"


def test_r1_fails_a_failed_call():
    t = trace("W02", "bare", None, error="timeout")
    r = results(t)
    assert r["R1"] == "fail" and r["R2"] == "n/a" and r["R3"] == "n/a"


def test_r2_wrong_item():
    assert results(trace("W02", "bare", verdict_text("FAIL", "x")))["R2"] == "pass"
    assert results(trace("W02", "explained", verdict_text("PASS", "x")))["R2"] == "fail"


def test_r2_correct_item():
    assert results(trace("C01", "bare", verdict_text("PASS", "x")))["R2"] == "pass"
    assert results(trace("C01", "explained", verdict_text("FAIL", "x")))["R2"] == "fail"


def test_r3_passes_when_reason_names_the_fact():
    t = trace("W02", "bare", verdict_text("FAIL", "Delivered 61 days ago, past the 60-day window."))
    assert results(t)["R3"] == "pass"


def test_r3_misses_a_paraphrase():
    # The design's known weakness: the right fact in other words is graded fail.
    t = trace("W02", "bare", verdict_text("FAIL", "The return came one day too late for a member."))
    assert results(t)["R3"] == "fail"


def test_r3_false_hit_on_a_keyword_used_for_something_else():
    # The other known weakness: a keyword used for another purpose counts as named.
    t = trace("W02", "bare", verdict_text("FAIL", "The store is closed on Sundays, so the tone is off."))
    assert results(t)["R3"] == "pass"


def test_r3_na_cases():
    assert results(trace("W02", "bare", verdict_text("PASS", "fine")))["R3"] == "n/a"
    assert results(trace("C01", "bare", verdict_text("FAIL", "61 days")))["R3"] == "n/a"
    old = trace("W02", "bare", verdict_text("FAIL", "61 days"))
    old["keywords"] = None  # pilot round 0 traces carry no keywords
    assert results(old)["R3"] == "n/a"
