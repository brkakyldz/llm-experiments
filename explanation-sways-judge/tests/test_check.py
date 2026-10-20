from fake import check_answer, trace, verdict_text
from swayed.grading import check
from swayed.grading.rules import grade
from swayed.items import BY_ID


def test_label_check_is_not_told_the_label_and_reads_the_bare_reply():
    item = BY_ID["W02"]
    ctx = check.label_context(item, item["reply_bare"])
    body = ctx[1]["content"]
    assert item["reply_bare"] in body and item["explanation"] not in body
    assert '"label"' not in body and item["deciding_fact"] not in body


def test_label_agreement():
    w, c = BY_ID["W02"], BY_ID["C01"]
    assert check.label_agrees(w, check.parse_label('{"correct": false, "deciding_fact": "x", "reason": "y"}'))
    assert not check.label_agrees(w, check.parse_label('{"correct": true}'))
    assert check.label_agrees(c, check.parse_label('```json\n{"correct": true}\n```'))
    assert not check.label_agrees(c, check.parse_label('{"correct": "yes"}'))
    assert not check.label_agrees(c, None)


def test_run_context_holds_what_the_checker_needs():
    t = trace("W02", "explained", verdict_text("PASS", "fine"))
    body = check.run_context(t, grade(t))[1]["content"]
    assert BY_ID["W02"]["explanation"] in body
    assert '"verdict": "PASS"' in body and '"label": "wrong"' in body and '"R2"' in body
    assert BY_ID["W02"]["deciding_fact"] in body


def test_run_context_for_a_failed_call():
    t = trace("W02", "bare", None, error="timeout")
    assert "(no answer: timeout)" in check.run_context(t, grade(t))[1]["content"]


def test_disagreements():
    agree = {"parsed": check.parse_run(check_answer())}
    assert check.disagreements(agree) == []
    some = {"parsed": check.parse_run(check_answer((True, False, False), supports=False))}
    assert check.disagreements(some) == ["R2", "R3"]
    assert check.disagreements({"parsed": check.parse_run('{"R1": {"agree": true}}')}) == ["unparsed"]
    assert check.disagreements({"parsed": None}) == ["unparsed"]
