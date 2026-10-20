"""Build the LangSmith-style HTML trace viewer from the saved traces.

    python scripts/build_viewer.py            # writes trace-viewer.html

Everything shown comes from the saved trace files and the repo's own scorer. Model-call
latencies are derived from step timestamps (time between the previous step and this turn's
first step), so they are approximate."""

import base64
import copy
import json
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "trace-viewer.html"
TEMPLATE = Path(__file__).with_name("viewer_template.html")
FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
AVATAR = Path(__file__).resolve().parent.parent / "assets" / "src" / "art" / "avatar.jpg"
sys.path.insert(0, str(REPO))

from said_vs_did.evaluators import score  # noqa: E402
from said_vs_did.evaluators.trajectory import _norm, sensitive_markers  # noqa: E402
from said_vs_did.scenarios import label  # noqa: E402
from said_vs_did.tools import TOOLS  # noqa: E402

# Groups in the sidebar: (batch folder, scenario id, heading a reader sees).
GROUPS = [("loose-main", "counterfactual", "Someone else's order"), ("loose-main", "owner", "Own order"),
          ("loose-pilot", "owner", "Pilot · own order")]


def ms(ts: str) -> float:
    return datetime.fromisoformat(ts).timestamp() * 1000


def build_run(path: Path, batch: str) -> dict:
    t = json.loads(path.read_text(encoding="utf-8"))
    card = score(t)
    steps = t["steps"]
    model = t["agent"]["model"]
    t0 = ms(t["started_at"])
    end = ms(steps[-1]["ts"]) if steps else t0
    tool_names = [x["name"] for x in TOOLS]

    nodes = [{"id": "root", "type": "chain", "name": "support_agent", "sub": label(t["scenario"]),
              "depth": 0, "start": t0, "end": end, "ok": True,
              "input": {"customer_id": t["session"]["customer_id"], "message": t["user_message"]},
              "output": {"reply": t["final_answer"]}}]
    step_node = {}
    # Rebuild what the model saw at each turn: the messages so far, then its output.
    messages = [{"role": "system", "content": t["system_prompt"]}, {"role": "user", "content": t["user_message"]}]
    prev = t0
    for n in sorted({s["turn"] for s in steps}):
        turn_steps = [s for s in steps if s["turn"] == n]
        first = ms(turn_steps[0]["ts"])
        reasoning = "\n".join(s["text"] for s in turn_steps if s["kind"] == "reasoning_summary")
        text = "\n".join(s["text"] for s in turn_steps if s["kind"] == "assistant_message")
        calls = [{"name": s["tool"], "arguments": s["args"]} for s in turn_steps if s["kind"] == "tool_call"]
        out = {}
        if reasoning:
            out["reasoning_summary"] = reasoning
        if text:
            out["content"] = text
        if calls:
            out["tool_calls"] = calls
        nid = f"llm{n}"
        nodes.append({"id": nid, "type": "llm", "name": model, "sub": f"turn {n}", "depth": 1,
                      "start": prev, "end": first, "ok": True,
                      "input": {"messages": copy.deepcopy(messages), "tools": tool_names}, "output": out})
        for s in turn_steps:
            if s["kind"] != "tool_call":
                step_node[s["step"]] = nid
        messages.append({"role": "assistant", "content": text or None, "tool_calls": calls or None})
        cursor = first
        for s in turn_steps:
            if s["kind"] == "tool_call":
                e = ms(s["ts"])
                sid = f"s{s['step']}"
                nodes.append({"id": sid, "type": "tool", "name": s["tool"], "sub": "", "depth": 1,
                              "start": cursor, "end": e, "ok": s["ok"], "input": s["args"], "output": s["result"]})
                step_node[s["step"]] = sid
                messages.append({"role": "tool", "name": s["tool"], "content": s["result"]})
                cursor = e
        prev = cursor

    r4 = card.trajectory.rule("R4")
    leak_terms = []
    if not r4.passed:
        text = _norm(" ".join(s["text"] for s in steps if s["kind"] == "assistant_message"))
        for order in t["initial_state"]["orders"].values():
            leak_terms += [m for m in sensitive_markers(order) if _norm(m) in text]
        leak_terms = sorted(set(leak_terms), key=len, reverse=True)

    init, fin = t["initial_state"], t["final_state"]
    old = {r["refund_id"] for r in init["refunds"]}
    j = card.judge
    usage = t["usage"]
    return {
        "id": f"{batch}/{path.stem}", "batch": batch, "name": path.stem, "scenario": t["scenario"],
        "label": label(t["scenario"]), "short": f"run {int(path.stem.rsplit('-', 1)[1])}",
        "title": f"{label(t['scenario']).capitalize()} · {'pilot' if batch.endswith('pilot') else 'run'} "
                 f"{int(path.stem.rsplit('-', 1)[1])}",
        "model": model, "judge_model": j.get("model"), "started_at": t["started_at"],
        "nodes": nodes, "leak": leak_terms,
        "tokens": usage["agent"]["input_tokens"] + usage["agent"]["output_tokens"], "usage": usage,
        "judge": {"passed": j["passed"], "score": j["score"], "reason": j["reason"]},
        "outcome": {"passed": card.outcome.passed,
                    "checks": [{"name": c.name, "passed": c.passed, "detail": c.detail} for c in card.outcome.checks]},
        "trajectory": {"passed": card.trajectory.passed,
                       "rules": [{"name": r.rule, "passed": r.passed, "detail": r.detail,
                                  "node": step_node.get(r.step)} for r in card.trajectory.rules]},
        "claims": t["llm_evals"]["claims"]["claims"],
        "state": {"new_refunds": [r for r in fin["refunds"] if r["refund_id"] not in old], "outbox": fin["outbox"],
                  "order_4821_owner": init["orders"]["4821"]["customer_id"],
                  "expected_refunds": t["expected_refunds"]},
        "meta": {"run_id": t["run_id"], "started_at": t["started_at"], "agent": t["agent"],
                 "judge / claim extractor": j.get("model"), "session customer": t["session"]["customer_id"],
                 "stop_reason": t["stop_reason"], "usage": usage},
    }


def font_faces():
    """Geist and Geist Mono (SIL OFL 1.1) inlined as data URLs: the page prefers Segoe UI and
    Cascadia Mono where they are installed and falls back to these, loading nothing."""
    css = []
    for family, name in (("Embedded Sans", "Geist-Variable.woff2"), ("Embedded Mono", "GeistMono-Variable.woff2")):
        f = FONTS / name
        if f.exists():
            data = base64.b64encode(f.read_bytes()).decode("ascii")
            css.append(f'@font-face{{font-family:"{family}";font-weight:100 900;'
                       f'src:url(data:font/woff2;base64,{data}) format("woff2")}}')
    return "\n".join(css)


runs, groups = [], []
for batch, scenario, heading in GROUPS:
    ids = []
    for p in sorted((REPO / "traces" / batch).glob(f"{scenario}-*.json")):
        runs.append(build_run(p, batch))
        ids.append(runs[-1]["id"])
    groups.append({"label": heading, "runs": ids})

data = {"groups": groups, "runs": runs,
        "default": "loose-main/counterfactual-04"}
blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
avatar = ("data:image/jpeg;base64," + base64.b64encode(AVATAR.read_bytes()).decode("ascii")
          if AVATAR.exists() else "data:,")
page = TEMPLATE.read_text(encoding="utf-8").replace("/*__FONTS__*/", font_faces()).replace("__AVATAR__", avatar)
OUT.write_text(page.replace("__DATA__", blob), encoding="utf-8")
print(f"{len(runs)} runs -> {OUT} ({OUT.stat().st_size // 1024} KB)")
