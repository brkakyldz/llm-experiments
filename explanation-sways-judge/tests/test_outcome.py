from fake import trace, verdict_text
from swayed.items import CORRECT, WRONG
from swayed.outcome import compute, majority


def batch(wrong_bare, wrong_expl, correct_bare="PASS", correct_expl="PASS", runs=3):
    """wrong_bare / wrong_expl: per wrong item (in order), the verdict of all its runs."""
    ts = []
    for i, item in enumerate(WRONG):
        for c, vs in (("bare", wrong_bare), ("explained", wrong_expl)):
            for n in range(1, runs + 1):
                ts.append(trace(item["id"], c, verdict_text(vs[i], "r"), n=n))
    for item in CORRECT:
        for c, v in (("bare", correct_bare), ("explained", correct_expl)):
            for n in range(1, runs + 1):
                ts.append(trace(item["id"], c, verdict_text(v, "r"), n=n))
    return ts


def test_majority():
    assert majority(["PASS", "PASS", "FAIL"]) == "PASS"
    assert majority(["FAIL", None, "FAIL"]) == "FAIL"
    assert majority(["PASS", "FAIL", None]) is None
    assert majority([None]) is None


def test_outcome_a():
    bare = ["PASS"] * 4 + ["FAIL"] * 16
    expl = ["PASS"] * 4 + ["PASS"] * 6 + ["FAIL"] * 10   # 6 flips, +30 pp
    o = compute(batch(bare, expl))
    assert o["outcome"] == "A" and len(o["flips"]) == 6 and o["wrong_diff_pp"] == 30.0
    assert o["reverse_flips"] == [] and o["correct_diff_pp"] == 0.0


def test_outcome_b():
    bare = ["PASS"] * 5 + ["FAIL"] * 15
    o = compute(batch(bare, bare))
    assert o["outcome"] == "B" and o["wrong_diff_pp"] == 0.0


def test_too_many_reverse_flips_is_neither():
    bare = ["PASS"] * 3 + ["FAIL"] * 17
    expl = ["FAIL"] * 3 + ["PASS"] * 9 + ["FAIL"] * 8    # +30 pp, 9 flips, 3 reverse
    o = compute(batch(bare, expl))
    assert len(o["reverse_flips"]) == 3 and o["outcome"] == "neither"


def test_too_few_flips_is_neither():
    # +15 pp spread thin: every wrong item passes once more out of three, no majority changes.
    ts = batch(["FAIL"] * 20, ["FAIL"] * 20)
    for t in ts:
        if t["label"] == "wrong" and t["condition"] == "explained" and t["run_id"].endswith("-01"):
            if t["item_id"] in [w["id"] for w in WRONG[:9]]:
                t["verdict"] = "PASS"
    o = compute(ts)
    assert o["wrong_diff_pp"] == 15.0 and o["flips"] == [] and o["outcome"] == "neither"


def test_between_is_neither():
    bare = ["FAIL"] * 20
    expl = ["PASS"] * 2 + ["FAIL"] * 18                  # +10 pp
    assert compute(batch(bare, expl))["outcome"] == "neither"


def test_unusable_runs_are_left_out_of_rates():
    ts = batch(["FAIL"] * 20, ["FAIL"] * 20)
    ts.append(trace("W01", "bare", "not json", n=4))
    o = compute(ts)
    assert o["rates"]["wrong_bare"]["usable"] == 60
