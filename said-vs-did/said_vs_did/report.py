"""Terminal scorecards: one per run, then a summary per batch and scenario."""

from __future__ import annotations

import json
import sys
import textwrap
from collections import defaultdict

from .evaluators import Scorecard
from .scenarios import label

COLOR = sys.stdout.isatty()
W = 78


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if COLOR else text


def mark(passed: bool) -> str:
    return _c("PASS", "32;1") if passed else _c("FAIL", "31;1")


def _short(value, n: int = 90) -> str:
    s = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 3] + "..."


def step_line(step: dict) -> str:
    if step["kind"] == "tool_call":
        args = ", ".join(f"{k}={v!r}" for k, v in step["args"].items())
        status = "ok" if step["ok"] else "error"
        return f"step {step['step']}: {step['tool']}({_short(args, 70)}) -> {status} {_short(step['result'], 70)}"
    return f"step {step['step']}: {step['kind']} \"{_short(step['text'], 110)}\""


def path_summary(steps: list[dict]) -> list[str]:
    out = []
    for s in steps:
        if s["kind"] == "tool_call":
            arg = ", ".join(str(v) for k, v in s["args"].items() if k in ("order_id", "customer_id", "amount"))
            res = ""
            if s["ok"] and s["tool"] == "get_current_session":
                res = f" = {s['result'].get('customer_id')}"
            elif s["ok"] and s["tool"] == "get_order_details":
                res = f" owner {s['result'].get('customer_id')}"
            elif s["ok"] and s["tool"] == "search_internal_docs":
                arg = repr(s["args"].get("query", ""))
                res = " -> " + (",".join(r["doc_id"] for r in s["result"].get("results", [])) or "none")
            out.append(f"{s['step']}. {s['tool']}({arg}){res}{'' if s['ok'] else ' [error]'}")
        elif s["kind"] == "assistant_message":
            out.append(f"{s['step']}. {'final reply' if s.get('final') else 'message'}")
    return out


def scorecard(name: str, trace: dict, card: Scorecard) -> str:
    steps = {s["step"]: s for s in trace["steps"]}
    a, j = trace["agent"], card.judge
    lines = ["=" * W,
             f"{name}  |  {label(trace['scenario'])}  |  "
             f"agent: {a['provider']}/{a['model']}  |  judge: {j['model']}",
             "-" * W,
             f"Customer ({trace['session']['customer_id']}): {trace['user_message']}",
             "Path: " + "  ".join(path_summary(trace["steps"]))]
    lines += textwrap.wrap("Final reply: " + " ".join(trace["final_answer"].split()), W,
                           subsequent_indent="             ")
    lines.append("")
    lines.append(f"JUDGE       {mark(j['passed'])}  {j['score']}/10  {_short(j['reason'], 52)}")
    lines.append(f"OUTCOME     {mark(card.outcome.passed)}")
    for c in card.outcome.checks:
        lines.append(f"   {c.name:<22}{mark(c.passed)}  {_short(c.detail, 46)}")
    lines.append(f"TRAJECTORY  {mark(card.trajectory.passed)}")
    for r in card.trajectory.rules:
        if r.passed:
            lines.append(f"   {r.rule:<22}{mark(r.passed)}  {_short(r.detail, 46)}")
        else:
            lines.append(f"   {r.rule:<22}{mark(r.passed)}")
            for w in textwrap.wrap(r.detail, W - 9):
                lines.append(f"         {w}")
            if r.step in steps:
                lines.append(f"         -> {step_line(steps[r.step])}")
    return "\n".join(lines)


def summary(results: list[tuple[str, dict, Scorecard]]) -> str:
    groups: dict[tuple[str, str], list[tuple[dict, Scorecard]]] = defaultdict(list)
    for name, trace, card in results:
        groups[(name.split("/")[0], trace["scenario"])].append((trace, card))
    lines = ["", "=" * W, "SUMMARY", "=" * W]
    for (batch, scenario), items in groups.items():
        n = len(items)
        judged = sum(c.judge["passed"] for _, c in items)
        mean = sum(c.judge["score"] for _, c in items) / n
        fails = {r: sum(not c.trajectory.rule(r).passed for _, c in items) for r in ("R1", "R2", "R3", "R4")}
        model = items[0][0]["agent"]["model"]
        lines += [
            f"batch {batch}  |  {label(scenario)}  |  agent {model}  |  N={n}",
            f"   judge passed          {judged}/{n}   (mean score {mean:.1f}/10)",
            f"   outcome passed        {sum(c.outcome.passed for _, c in items)}/{n}",
            f"   trajectory passed     {sum(c.trajectory.passed for _, c in items)}/{n}   "
            f"(runs failing R1 {fails['R1']}, R2 {fails['R2']}, R3 {fails['R3']}, R4 {fails['R4']})",
            f"   said-vs-did conflict  {sum(c.said_vs_did_conflict for _, c in items)}/{n}",
            f"   judge PASS, but outcome or trajectory FAIL   "
            f"{sum(c.judge['passed'] and not (c.outcome.passed and c.trajectory.passed) for _, c in items)}/{n}",
            f"   judge FAIL, but outcome and trajectory PASS  "
            f"{sum(not c.judge['passed'] and c.outcome.passed and c.trajectory.passed for _, c in items)}/{n}",
            "",
        ]
    return "\n".join(lines)
