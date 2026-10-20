"""explanation-sways-judge: judge support replies bare and explained, check the grades, re-score.

    python run.py --replay                         # no key needed; every batch under traces/
    python run.py --replay --batch main            # one batch, with the outcome criterion
    python run.py --live --trial                   # W01, both conditions, traces/trial/
    python run.py --live -n 3 --batch main         # 40 items x 2 conditions x 3 usable runs
    python run.py --live --check-labels            # second model labels every item once
    python run.py --live --check --batch main      # second model checks every run's grades
    python run.py --live --pilot --batch pilot-r1  # 5 wrong items, both conditions

Live judge runs fill a batch up to n usable runs per item and condition, so a rerun after an
interruption continues where it stopped. A failed run is kept and retried once; the batch stops on
a second failure, on quota_exceeded, or when more than one run in ten has failed.
"""

import argparse
import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

from swayed import judge
from swayed.grading import check
from swayed.grading.rules import grade
from swayed.items import BY_ID, ITEMS, WRONG, reply
from swayed.outcome import compute

ITEMS_VERSION = 3  # 1: one-order record (pilot round 0); 2: filler orders could repeat the target product
ROOT = Path(__file__).parent
JUDGE_MODEL = os.getenv("SWAYED_JUDGE_MODEL", "gpt-6-luna")
JUDGE_EFFORT = os.getenv("SWAYED_JUDGE_EFFORT", "low")
CONDITIONS = ("bare", "explained")
PILOT_SEED = 7
MAIN_BATCH = "main"


class BatchStopped(Exception):
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def pilot_items():
    return sorted(random.Random(PILOT_SEED).sample([i["id"] for i in WRONG], 5))


def call(model, ctx, effort):
    from swayed.model import ModelError, complete

    try:
        return complete(model, ctx, effort), None
    except ModelError as e:
        return None, e.code


def run_one(item, condition, run_id):
    from swayed.model import backend

    ctx = judge.context(item, reply(item, condition))
    trace = {"run_id": run_id, "item_id": item["id"], "label": item["label"],
             "condition": condition, "model": JUDGE_MODEL, "effort": JUDGE_EFFORT,
             "backend": backend(), "started_at": now(),
             "items_version": ITEMS_VERSION, "keywords": item["keywords"],
             "deciding_fact": item["deciding_fact"] or None,
             "steps": [dict(m) for m in ctx], "requests": 1, "error": None,
             "verdict": None, "reason": None}
    out, err = call(JUDGE_MODEL, ctx, JUDGE_EFFORT)
    if err:
        trace["error"] = err
        return trace
    trace["model_returned"] = out["model"]
    trace["steps"].append({"role": "assistant", "text": out["text"], "usage": out["usage"],
                           "seconds": out["seconds"]})
    trace["verdict"], trace["reason"] = judge.parse(out["text"])
    return trace


def load(root, batch=None):
    pattern = f"{batch or '*'}/*.json"
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((root / "traces").glob(pattern))]


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def live_runs(root, batch, plan):
    """plan: (item, condition, wanted usable runs). Writes every run, failed ones too."""
    out_dir = root / "traces" / batch
    out_dir.mkdir(parents=True, exist_ok=True)
    done, failed = 0, 0
    for item, condition, wanted in plan:
        stem = f"{item['id']}-{condition}"
        existing = [json.loads(p.read_text(encoding="utf-8")) for p in out_dir.glob(f"{stem}-*.json")]
        usable = sum(t["verdict"] is not None for t in existing)
        k = len(existing)
        while usable < wanted:
            for attempt in (1, 2):
                k += 1
                path = out_dir / f"{stem}-{k:02d}.json"
                trace = run_one(item, condition, f"{batch}/{path.stem}")
                write_json(path, trace)
                done += 1
                print(f"{trace['run_id']}: {trace['verdict'] or 'error ' + str(trace['error'])}",
                      file=sys.stderr, flush=True)
                if trace["verdict"] is not None:
                    usable += 1
                    break
                failed += 1
                if trace["error"] == "quota_exceeded":
                    raise BatchStopped("quota_exceeded")
                if attempt == 2:
                    raise BatchStopped(f"{path.stem} failed twice")
                if done >= 10 and failed * 10 > done:
                    raise BatchStopped(f"{failed} of {done} runs failed")


def check_labels(root):
    from swayed.model import backend

    for item in ITEMS:
        path = root / "results" / "labels" / f"{item['id']}.json"
        if path.exists():
            continue
        ctx = check.label_context(item, item["reply_bare"])
        out, err = call(check.CHECK_MODEL, ctx, check.CHECK_EFFORT)
        parsed = check.parse_label(out["text"]) if out else None
        rec = {"item_id": item["id"], "label": item["label"], "items_version": ITEMS_VERSION,
               "model": check.CHECK_MODEL,
               "effort": check.CHECK_EFFORT, "backend": backend(), "started_at": now(),
               "requests": 1, "error": err, "input": ctx, "output": out, "parsed": parsed,
               "agrees": check.label_agrees(item, parsed)}
        write_json(path, rec)
        print(f"label {item['id']}: {'agree' if rec['agrees'] else 'DISAGREE'}"
              f"{' error ' + err if err else ''}", file=sys.stderr, flush=True)


def check_runs(root, batch):
    from swayed.model import backend

    for t in load(root, batch):
        stem = t["run_id"].split("/", 1)[1]
        path = root / "results" / batch / "checks" / f"{stem}.json"
        if path.exists():
            continue
        grades = grade(t)
        ctx = check.run_context(t, grades)
        out, err = call(check.CHECK_MODEL, ctx, check.CHECK_EFFORT)
        rec = {"run_id": t["run_id"], "model": check.CHECK_MODEL, "effort": check.CHECK_EFFORT,
               "backend": backend(), "started_at": now(), "requests": 1, "error": err,
               "grades": grades, "input": ctx, "output": out,
               "parsed": check.parse_run(out["text"]) if out else None}
        rec["disagrees_on"] = check.disagreements(rec)
        write_json(path, rec)
        print(f"check {t['run_id']}: {', '.join(rec['disagrees_on']) or 'agree'}"
              f"{' error ' + err if err else ''}", file=sys.stderr, flush=True)


def summary_lines(traces):
    lines = ["judge PASS rate by label and condition"]
    for label in ("wrong", "correct"):
        for c in CONDITIONS:
            vs = [t["verdict"] for t in traces
                  if t["label"] == label and t["condition"] == c and t["verdict"]]
            if vs:
                p = vs.count("PASS")
                lines.append(f"  {label:7} {c:9} {p:3}/{len(vs):<3} {100 * p / len(vs):5.1f}%")
    lines.append(f"  unusable or failed runs: {sum(t['verdict'] is None for t in traces)}")
    return lines


def r3_counts(graded):
    """R3 'named' per condition, as the rule gave it and after resolved checks: where a person
    accepted the second model's reading, an R3 grade it disagreed with counts the other way."""
    out = {}
    for c in CONDITIONS:
        rule = after = n = 0
        for g in graded:
            r3 = next(x["result"] for x in g["grades"] if x["rule"] == "R3")
            if g["condition"] != c or r3 == "n/a":
                continue
            ok = r3 == "pass"
            ch = g["check"]
            flip = bool(ch and "R3" in ch["disagrees_on"] and ch["resolved_by"]
                        and ch["accepted"] == "check")
            n, rule, after = n + 1, rule + ok, after + (ok != flip)
        out[c] = {"fails_of_wrong": n, "rule": rule, "after_check": after}
    return out


def replay(root, batch=None):
    """Regrade saved traces with the code rules, read stored checks, write results/<batch>/."""
    traces = load(root, batch)
    if not traces:
        return None
    out = {}
    for b in sorted({t["run_id"].split("/", 1)[0] for t in traces}):
        ts = [t for t in traces if t["run_id"].startswith(b + "/")]
        graded = [{"run_id": t["run_id"], "item_id": t["item_id"], "label": t["label"],
                   "condition": t["condition"], "verdict": t["verdict"], "reason": t["reason"],
                   "error": t["error"], "grades": grade(t)} for t in ts]
        checks = {}
        for p in sorted((root / "results" / b / "checks").glob("*.json")):
            c = json.loads(p.read_text(encoding="utf-8"))
            checks[c["run_id"]] = c
        for g in graded:
            c = checks.get(g["run_id"])
            g["check"] = None if c is None else {
                "disagrees_on": c["disagrees_on"], "resolved_by": c.get("resolved_by"),
                "accepted": c.get("accepted"),
                "reason_supports_verdict": (c["parsed"] or {}).get("reason_supports_verdict")}
        unresolved = [g["run_id"] for g in graded
                      if g["check"] and g["check"]["disagrees_on"] and not g["check"]["resolved_by"]]
        totals = {"batch": b, "runs": len(ts), "judge_requests": sum(t["requests"] for t in ts),
                  "check_requests": sum(c["requests"] for c in checks.values()),
                  "checked": sum(g["check"] is not None for g in graded),
                  "check_disagreements_unresolved": unresolved,
                  "reason_contradicts_verdict": [g["run_id"] for g in graded if g["check"]
                                                 and g["check"]["reason_supports_verdict"] is False],
                  "r3_named": r3_counts(graded),
                  "summary": summary_lines(ts)}
        if b == MAIN_BATCH:
            totals["outcome"] = compute(ts)
        write_json(root / "results" / b / "grades.json", graded)
        write_json(root / "results" / b / "totals.json", totals)
        out[b] = (graded, totals)
    labels = [json.loads(p.read_text(encoding="utf-8"))
              for p in sorted((root / "results" / "labels").glob("*.json"))]
    if labels:
        write_json(root / "results" / "labels-summary.json", {
            "checked": len(labels), "requests": sum(x["requests"] for x in labels),
            "disagree": [x["item_id"] for x in labels if not x["agrees"]
                         and not x.get("resolved_by")]})
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true", help="make model calls, save their records")
    mode.add_argument("--replay", action="store_true", help="re-score saved traces offline")
    ap.add_argument("--pilot", action="store_true", help="with --live: the five-item pilot")
    ap.add_argument("--trial", action="store_true", help="with --live: W01, both conditions")
    ap.add_argument("--check-labels", action="store_true", help="with --live: label check")
    ap.add_argument("--check", action="store_true", help="with --live: check a batch's grades")
    ap.add_argument("-n", type=int, default=3, help="usable runs per item and condition")
    ap.add_argument("--batch", default=None, help="folder under traces/")
    args = ap.parse_args()

    if args.live:
        try:
            if args.check_labels:
                check_labels(ROOT)
            elif args.check:
                check_runs(ROOT, args.batch or MAIN_BATCH)
            elif args.pilot:
                live_runs(ROOT, args.batch or "pilot",
                          [(BY_ID[i], c, 1) for i in pilot_items() for c in CONDITIONS])
            elif args.trial:
                live_runs(ROOT, "trial", [(BY_ID["W01"], c, 1) for c in CONDITIONS])
            else:
                live_runs(ROOT, args.batch or "new-runs",
                          [(i, c, args.n) for i in ITEMS for c in CONDITIONS])
        except BatchStopped as e:
            print(f"batch stopped: {e}", file=sys.stderr)
            replay(ROOT, args.batch)
            return 2

    batch = None if args.check_labels else (args.batch or ("trial" if args.trial else None))
    result = replay(ROOT, batch)
    if not result:
        print("no traces found under traces/", file=sys.stderr)
        return 1
    for b, (graded, totals) in result.items():
        print(f"\n== {b}")
        for g in graded:
            r = {x["rule"]: x["result"] for x in g["grades"]}
            flag = ""
            if g["check"]:
                flag = " check:" + (",".join(g["check"]["disagrees_on"]) or "agree")
            print(f"{g['run_id']:30} {g['label']:7} {str(g['verdict']):5} R1 {r['R1']:4} "
                  f"R2 {r['R2']:4} R3 {r['R3']:4}{flag}  {g['reason'] or ''}")
        print("\n".join(totals["summary"]))
        if "outcome" in totals:
            o = totals["outcome"]
            print(f"  outcome {o['outcome']}: wrong explained - bare = {o['wrong_diff_pp']} pp, "
                  f"flips {len(o['flips'])}, reverse {len(o['reverse_flips'])}; "
                  f"correct explained - bare = {o['correct_diff_pp']} pp")
        if totals["checked"]:
            print(f"  checked {totals['checked']}/{totals['runs']}, unresolved disagreements "
                  f"{len(totals['check_disagreements_unresolved'])}, reason contradicts verdict "
                  f"{len(totals['reason_contradicts_verdict'])}")
        for c, r in totals["r3_named"].items():
            if r["fails_of_wrong"]:
                print(f"  R3 named {c:9} rule {r['rule']}/{r['fails_of_wrong']}, "
                      f"after check {r['after_check']}/{r['fails_of_wrong']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
