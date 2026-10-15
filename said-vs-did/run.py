"""said-vs-did: run the support agent live, or re-score the saved traces.

    python run.py --replay                         # no API key needed
    python run.py --live -n 5 --batch mybatch      # real model calls, writes traces/mybatch/
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from said_vs_did.evaluators import score
from said_vs_did.report import scorecard, summary

ROOT = Path(__file__).parent
TRACES = ROOT / "traces"


def live(args) -> list[tuple[str, dict]]:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    from said_vs_did.agent import run_agent
    from said_vs_did.evaluators.claims import extract_claims
    from said_vs_did.evaluators.judge import judge
    from said_vs_did.providers import Config, cost_usd, make_provider
    from said_vs_did.scenarios import SCENARIOS

    cfg = Config.from_env()
    agent = make_provider(cfg.agent_provider, cfg.agent_model, cfg.reasoning_effort)
    evaluator = make_provider(cfg.eval_provider, cfg.eval_model)
    out_dir = TRACES / args.batch
    out_dir.mkdir(parents=True, exist_ok=True)
    names = list(SCENARIOS) if args.scenario == "all" else [args.scenario]

    saved = []
    for scen_name in names:
        for _ in range(args.n):
            k = 1 + len(list(out_dir.glob(f"{scen_name}-*.json")))
            path = out_dir / f"{scen_name}-{k:02d}.json"
            started = datetime.now(timezone.utc).isoformat(timespec="seconds")
            print(f"running {args.batch}/{path.stem} ...", file=sys.stderr, flush=True)
            trace = run_agent(agent, SCENARIOS[scen_name])
            trace["llm_evals"] = {
                "judge": judge(evaluator, trace["user_message"], trace["final_answer"]),
                "claims": extract_claims(evaluator, trace["final_answer"]),
            }
            trace = {"run_id": f"{args.batch}/{path.stem}", "started_at": started, **trace}
            usage = trace["usage"]
            usage["evaluators"] = {k: sum(v["usage"].get(k, 0) for v in trace["llm_evals"].values())
                                   for k in ("input_tokens", "output_tokens")}
            costs = [cost_usd(agent.model, usage["agent"]), cost_usd(evaluator.model, usage["evaluators"])]
            usage["cost_usd"] = round(sum(costs), 6) if None not in costs else None
            path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  saved {path.relative_to(ROOT)}  tokens in/out agent {usage['agent']['input_tokens']}/"
                  f"{usage['agent']['output_tokens']}  cost ${usage['cost_usd']}", file=sys.stderr, flush=True)
            saved.append((trace["run_id"], trace))
    return saved


def load_traces(args) -> list[tuple[str, dict]]:
    pattern = f"{args.batch or '*'}/*.json"
    out = []
    for p in sorted(TRACES.glob(pattern)):
        trace = json.loads(p.read_text(encoding="utf-8"))
        if args.scenario in ("all", trace["scenario"]):
            out.append((f"{p.parent.name}/{p.stem}", trace))
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true", help="run the agent against a real model and save traces")
    mode.add_argument("--replay", action="store_true", help="re-score saved traces (no API key needed)")
    ap.add_argument("--scenario", default="all", choices=["all", "owner", "counterfactual"])
    ap.add_argument("-n", type=int, default=5, help="runs per scenario in --live mode (default 5)")
    ap.add_argument("--batch", default=None,
                    help="trace folder under traces/ (live default: new-runs; replay default: every batch)")
    ap.add_argument("--summary-only", action="store_true", help="print only the summary")
    args = ap.parse_args()

    if args.live:
        args.batch = args.batch or "new-runs"
        runs = live(args)
    else:
        runs = load_traces(args)
        if not runs:
            print("no traces found under traces/", file=sys.stderr)
            return 1

    results = []
    for name, trace in runs:
        card = score(trace)
        results.append((name, trace, card))
        if not args.summary_only:
            print(scorecard(name, trace, card) + "\n")
    print(summary(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
