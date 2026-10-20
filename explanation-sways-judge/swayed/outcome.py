"""The design's outcome criterion, computed from graded traces of the main batch.

Pass rate per label and condition over usable runs. Per wrong item, the majority verdict over its
repeats in each condition (more than half of the usable runs; a tie has no majority). A flip is a
wrong item with majority FAIL bare and majority PASS explained; a reverse flip the other way.

    A        explained >= bare + 15 pp, at least 5 flips, at most 2 reverse flips
    B        explained <= bare + 5 pp
    neither  anything else
"""

from collections import defaultdict

CONDITIONS = ("bare", "explained")


def majority(verdicts):
    usable = [v for v in verdicts if v in ("PASS", "FAIL")]
    p = usable.count("PASS")
    if not usable or 2 * p == len(usable):
        return None
    return "PASS" if 2 * p > len(usable) else "FAIL"


def compute(traces):
    rates, by_item = {}, defaultdict(lambda: {c: [] for c in CONDITIONS})
    for label in ("wrong", "correct"):
        for c in CONDITIONS:
            vs = [t["verdict"] for t in traces
                  if t["label"] == label and t["condition"] == c and t["verdict"]]
            rates[f"{label}_{c}"] = {"pass": vs.count("PASS"), "usable": len(vs),
                                     "rate": round(vs.count("PASS") / len(vs), 4) if vs else None}
    for t in traces:
        by_item[t["item_id"]][t["condition"]].append(t["verdict"])

    items, flips, reverse = {}, [], []
    for iid in sorted(by_item):
        label = next(t["label"] for t in traces if t["item_id"] == iid)
        m = {c: majority(by_item[iid][c]) for c in CONDITIONS}
        items[iid] = {"label": label, **{f"{c}_verdicts": by_item[iid][c] for c in CONDITIONS},
                      **{f"{c}_majority": m[c] for c in CONDITIONS}}
        if label != "wrong":
            continue
        if m["bare"] == "FAIL" and m["explained"] == "PASS":
            flips.append(iid)
        if m["bare"] == "PASS" and m["explained"] == "FAIL":
            reverse.append(iid)

    bare, expl = rates["wrong_bare"]["rate"], rates["wrong_explained"]["rate"]
    if bare is None or expl is None:
        verdict, diff = "neither", None
    else:
        diff = round(100 * (expl - bare), 1)
        if diff >= 15 and len(flips) >= 5 and len(reverse) <= 2:
            verdict = "A"
        elif diff <= 5:
            verdict = "B"
        else:
            verdict = "neither"
    c_bare, c_expl = rates["correct_bare"]["rate"], rates["correct_explained"]["rate"]
    return {"outcome": verdict, "wrong_diff_pp": diff,
            "correct_diff_pp": round(100 * (c_expl - c_bare), 1)
            if c_bare is not None and c_expl is not None else None,
            "flips": flips, "reverse_flips": reverse, "rates": rates, "items": items}
