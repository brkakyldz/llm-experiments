"""Build the self-contained HTML trace viewer from the saved traces and checks.

    python scripts/build_viewer.py                     # writes trace-viewer.html
    python scripts/build_viewer.py out.html --root DIR  # another experiment root (tests use this)

Everything shown comes from the trace files, the stored second-model checks and the code rules.
Long texts that repeat across runs (the judge and check prompts, account records) are stored once
in a text table and referenced by index, which keeps the file small. Latency is the call time the
trace recorded. The page loads nothing from the network.
"""

import argparse
import base64
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = Path(__file__).with_name("viewer_template.html")
FONTS = REPO / "assets" / "fonts"
AVATAR = REPO / "assets" / "src" / "art" / "avatar.jpg"
sys.path.insert(0, str(REPO))

from swayed.grading.rules import grade  # noqa: E402
from swayed.items import BY_ID  # noqa: E402

# Sidebar sections in order: (batch folder, heading). Batches not listed come after, by name.
HEADINGS = {"main": "Main runs", "trial": "Trial", "pilot-r1": "Pilot round 1",
            "pilot": "Pilot round 0 (first item set)"}


class Texts:
    """A table of long strings; each one is stored once and referenced as {"$t": index}."""

    def __init__(self):
        self.items, self.index = [], {}

    def ref(self, s):
        if not isinstance(s, str) or len(s) < 400:
            return s
        if s not in self.index:
            self.index[s] = len(self.items)
            self.items.append(s)
        return {"$t": self.index[s]}


def font_faces():
    """Geist and Geist Mono (SIL OFL 1.1) inlined as data URLs: the page prefers Bahnschrift,
    Segoe UI and Cascadia Mono where they are installed and falls back to these, so it loads
    nothing from the network."""
    css = []
    for family, name in (("Embedded Sans", "Geist-Variable.woff2"), ("Embedded Mono", "GeistMono-Variable.woff2")):
        p = FONTS / name
        if p.exists():
            data = base64.b64encode(p.read_bytes()).decode("ascii")
            css.append(f'@font-face{{font-family:"{family}";font-weight:100 900;'
                       f'src:url(data:font/woff2;base64,{data}) format("woff2")}}')
    return "\n".join(css)


def counts(u):
    """Token counts from either usage shape (pilot traces kept the client's full usage)."""
    u = u or {}
    return {"input": u.get("input_tokens"), "output": u.get("output_tokens"),
            "reasoning": u.get("reasoning_tokens",
                               (u.get("output_tokens_details") or {}).get("reasoning_tokens")),
            "cached": u.get("cached_tokens",
                            (u.get("input_tokens_details") or {}).get("cached_tokens"))}


def explanation_of(t, user_text):
    """The explanation paragraph, when this run's reply carries one, for highlighting."""
    item = BY_ID.get(t["item_id"])
    if t["condition"] != "explained" or not item or item["explanation"] not in user_text:
        return None
    return item["explanation"]


def llm_node(nid, name, sub, messages, out_step, texts, extra_out=None):
    node = {"id": nid, "type": "llm", "name": name, "sub": sub,
            "input": [{"role": m["role"], "content": texts.ref(m["content"])} for m in messages],
            "output": None, "seconds": None, "tokens": None, "ok": out_step is not None}
    if out_step:
        node["output"] = {"text": out_step.get("text", ""), **(extra_out or {})}
        node["seconds"] = out_step.get("seconds")
        node["tokens"] = counts(out_step.get("usage"))
    return node


def build_run(t, checks, texts):
    batch, stem = t["run_id"].split("/", 1)
    grades = grade(t)
    msgs = [s for s in t["steps"] if s["role"] != "assistant"]
    out = next((s for s in t["steps"] if s["role"] == "assistant"), None)
    user_text = next(s["content"] for s in msgs if s["role"] == "user")
    judge = llm_node("judge", t["model"], "judge", msgs, out, texts)
    nodes = [{"id": "root", "type": "chain", "name": "judge_run",
              "sub": f"{t['item_id']} · {t['condition']}", "ok": t["error"] is None,
              "seconds": judge["seconds"],
              "input": {"item_id": t["item_id"], "label": t["label"], "condition": t["condition"],
                        "deciding_fact": t.get("deciding_fact")},
              "output": {"verdict": t["verdict"], "reason": t["reason"], "error": t["error"]}},
             judge]
    c = checks.get(t["run_id"])
    check = None
    if c:
        out_c = {"text": c["output"]["text"], "seconds": c["output"].get("seconds"),
                 "usage": c["output"].get("usage")} if c.get("output") else None
        nodes.append(llm_node("check", c["model"], "second-model check", c["input"], out_c, texts,
                              {"parsed": c.get("parsed")}))
        check = {"disagrees_on": c["disagrees_on"], "parsed": c.get("parsed"),
                 "resolved_by": c.get("resolved_by"), "resolution": c.get("resolution"),
                 "error": c.get("error")}
    n = int(stem.rsplit("-", 1)[1])
    return {"id": t["run_id"], "batch": batch, "item": t["item_id"], "label": t["label"],
            "condition": t["condition"], "n": n,
            "title": f"{t['item_id']} · {t['condition']} · run {n}",
            "verdict": t["verdict"], "reason": t["reason"], "error": t["error"],
            "explanation": explanation_of(t, user_text),
            "grades": grades, "check": check, "nodes": nodes,
            "meta": {k: t.get(k) for k in ("run_id", "started_at", "model", "model_returned",
                                            "effort", "backend", "items_version", "requests",
                                            "error")}
            | {"tokens": judge["tokens"], "keywords": t.get("keywords")}}


def build(root, out_path):
    texts = Texts()
    runs = []
    batches = sorted({p.parent.name for p in (root / "traces").glob("*/*.json")},
                     key=lambda b: (list(HEADINGS).index(b) if b in HEADINGS else 99, b))
    groups = []
    for b in batches:
        checks = {}
        for p in sorted((root / "results" / b / "checks").glob("*.json")):
            c = json.loads(p.read_text(encoding="utf-8"))
            checks[c["run_id"]] = c
        traces = [json.loads(p.read_text(encoding="utf-8"))
                  for p in sorted((root / "traces" / b).glob("*.json"))]
        for label in ("wrong", "correct"):
            ids = []
            for t in sorted((t for t in traces if t["label"] == label),
                            key=lambda t: (t["item_id"], t["condition"], t["run_id"])):
                runs.append(build_run(t, checks, texts))
                ids.append(runs[-1]["id"])
            if ids:
                groups.append({"label": f"{HEADINGS.get(b, b)} · {label} replies", "batch": b,
                               "runs": ids})
    if not runs:
        raise SystemExit("no traces under traces/")
    totals = {}
    for b in batches:
        p = root / "results" / b / "totals.json"
        if p.exists():
            totals[b] = json.loads(p.read_text(encoding="utf-8"))
    default = next((r["id"] for r in runs if r["batch"] == "main"), runs[0]["id"])
    data = {"groups": groups, "runs": runs, "texts": texts.items, "totals": totals,
            "default": default}
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page = TEMPLATE.read_text(encoding="utf-8").replace("/*__FONTS__*/", font_faces())
    avatar = ("data:image/jpeg;base64," + base64.b64encode(AVATAR.read_bytes()).decode("ascii")
              if AVATAR.exists() else "data:,")
    page = page.replace("__AVATAR__", avatar)
    out_path.write_text(page.replace("__DATA__", blob), encoding="utf-8")
    return len(runs), out_path.stat().st_size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default=None)
    ap.add_argument("--root", default=str(REPO))
    a = ap.parse_args()
    root = Path(a.root)
    out = Path(a.out) if a.out else root / "trace-viewer.html"
    n, size = build(root, out)
    print(f"{n} runs -> {out} ({size // 1024} KB)")


if __name__ == "__main__":
    main()
