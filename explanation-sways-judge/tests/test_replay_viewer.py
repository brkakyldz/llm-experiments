"""--replay on a fake batch writes grades and totals and reads stored checks; the viewer builds
from the same batch with no network reference."""

import json
import re
import sys
from pathlib import Path

from fake import check_answer, trace, verdict_text, write
from swayed.grading import check
from swayed.grading.rules import grade

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_viewer  # noqa: E402
import run  # noqa: E402


def fake_batch(root):
    ts = [trace("W02", "bare", verdict_text("FAIL", "61 days, past the 60-day window.")),
          trace("W02", "explained", verdict_text("PASS", "Within the member window.")),
          trace("C01", "bare", verdict_text("PASS", "Correct.")),
          trace("C01", "explained", None, error="timeout")]
    for t in ts:
        write(root, t)
    # Stored checks for the first two runs: agrees on the first, disagrees on R3 for the second.
    for t, ans in ((ts[0], check_answer()), (ts[1], check_answer((True, True, False), False))):
        stem = t["run_id"].split("/", 1)[1]
        rec = {"run_id": t["run_id"], "model": "gpt-6-sol", "requests": 1, "error": None,
               "grades": grade(t), "input": check.run_context(t, grade(t)),
               "output": {"text": ans, "seconds": 2.0, "usage": {"input_tokens": 3000}},
               "parsed": check.parse_run(ans)}
        rec["disagrees_on"] = check.disagreements(rec)
        p = root / "results" / "fake" / "checks" / f"{stem}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rec), encoding="utf-8")
    return ts


def test_replay_on_a_fake_batch(tmp_path):
    fake_batch(tmp_path)
    graded, totals = run.replay(tmp_path, "fake")["fake"]
    assert len(graded) == 4 and totals["runs"] == 4 and totals["checked"] == 2
    assert totals["check_disagreements_unresolved"] == ["fake/W02-explained-01"]
    assert totals["reason_contradicts_verdict"] == ["fake/W02-explained-01"]
    saved = json.loads((tmp_path / "results" / "fake" / "grades.json").read_text(encoding="utf-8"))
    by = {g["run_id"]: {x["rule"]: x["result"] for x in g["grades"]} for g in saved}
    assert by["fake/W02-bare-01"] == {"R1": "pass", "R2": "pass", "R3": "pass"}
    assert by["fake/W02-explained-01"]["R2"] == "fail"
    assert by["fake/C01-explained-01"]["R1"] == "fail"
    assert "outcome" not in totals  # only the main batch is judged against the criterion


def test_replay_resolved_disagreement_is_not_open(tmp_path):
    fake_batch(tmp_path)
    p = tmp_path / "results" / "fake" / "checks" / "W02-explained-01.json"
    rec = json.loads(p.read_text(encoding="utf-8"))
    rec["resolved_by"] = "berke"
    p.write_text(json.dumps(rec), encoding="utf-8")
    _, totals = run.replay(tmp_path, "fake")["fake"]
    assert totals["check_disagreements_unresolved"] == []


def test_replay_r3_counts_follow_an_accepted_check(tmp_path):
    fake_batch(tmp_path)
    _, totals = run.replay(tmp_path, "fake")["fake"]
    assert totals["r3_named"]["bare"] == {"fails_of_wrong": 1, "rule": 1, "after_check": 1}
    p = tmp_path / "results" / "fake" / "checks" / "W02-bare-01.json"
    rec = json.loads(p.read_text(encoding="utf-8"))
    rec.update(disagrees_on=["R3"], resolved_by="berke", accepted="check")
    p.write_text(json.dumps(rec), encoding="utf-8")
    _, totals = run.replay(tmp_path, "fake")["fake"]
    assert totals["r3_named"]["bare"] == {"fails_of_wrong": 1, "rule": 1, "after_check": 0}
    assert totals["r3_named"]["explained"]["fails_of_wrong"] == 0


def test_viewer_builds_from_a_fake_batch(tmp_path):
    fake_batch(tmp_path)
    run.replay(tmp_path, "fake")
    out = tmp_path / "trace-viewer.html"
    n, _ = build_viewer.build(tmp_path, out)
    html = out.read_text(encoding="utf-8")
    assert n == 4 and "__DATA__" not in html
    assert not re.search(r"""(src|href)=["']?https?:""", html)
    blob = re.search(r"const DATA = (\{.*?\});\n", html, re.S).group(1)
    data = json.loads(blob.replace("<\\/", "</"))
    assert len(data["texts"]) >= 2  # the judge prompt and the check prompt, stored once each
    w2 = next(r for r in data["runs"] if r["id"] == "fake/W02-explained-01")
    assert w2["explanation"] and w2["check"]["disagrees_on"] == ["R3"]
    assert [x["id"] for x in w2["nodes"]] == ["root", "judge", "check"]


def test_viewer_reads_old_usage_shape():
    old = {"input_tokens": 10, "output_tokens": 2, "output_tokens_details": {"reasoning_tokens": 0},
           "input_tokens_details": {"cached_tokens": 4}, "attribution": {"x": 1}}
    assert build_viewer.counts(old) == {"input": 10, "output": 2, "reasoning": 0, "cached": 4}
