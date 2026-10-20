"""Fake judge traces and checks, shaped like the ones run.py writes, for offline tests."""

import json

from swayed import judge
from swayed.items import BY_ID, reply


def trace(item_id, condition, text, batch="fake", n=1, error=None):
    item = BY_ID[item_id]
    verdict, reason = judge.parse(text) if text is not None else (None, None)
    steps = [dict(m) for m in judge.context(item, reply(item, condition))]
    if text is not None:
        steps.append({"role": "assistant", "text": text, "seconds": 1.5,
                      "usage": {"input_tokens": 2400, "output_tokens": 40,
                                "reasoning_tokens": 0, "cached_tokens": 0}})
    return {"run_id": f"{batch}/{item_id}-{condition}-{n:02d}", "item_id": item_id,
            "label": item["label"], "condition": condition, "model": "gpt-6-luna",
            "effort": "low", "backend": "fake", "started_at": "2026-10-19T00:00:00+00:00",
            "items_version": 2, "keywords": item["keywords"],
            "deciding_fact": item["deciding_fact"] or None, "steps": steps, "requests": 1,
            "error": error, "verdict": verdict, "reason": reason}


def verdict_text(verdict, reason):
    return json.dumps({"verdict": verdict, "reason": reason})


def check_answer(agree=(True, True, True), supports=True):
    return json.dumps({r: {"agree": a, "why": "ok"} for r, a in zip(("R1", "R2", "R3"), agree)}
                      | {"reason_supports_verdict": supports})


def write(root, t):
    batch, stem = t["run_id"].split("/", 1)
    p = root / "traces" / batch / f"{stem}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(t), encoding="utf-8")
