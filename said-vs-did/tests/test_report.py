from said_vs_did.evaluators import score
from said_vs_did.report import scorecard, summary

import fake_traces as ft


def test_scorecard_points_at_the_failing_step():
    trace = ft.skipped_session()
    trace.update({"agent": {"provider": "fake", "model": "fake"},
                  "llm_evals": {"judge": {"passed": True, "score": 9, "reason": "Resolved.", "model": "fake"},
                                "claims": {"claims": []}}})
    card = score(trace)
    text = scorecard("t/owner-01", trace, card)
    assert "R1 authorization" in text and "-> step 3: process_refund" in text
    s = summary([("t/owner-01", trace, card)])
    assert "judge passed          1/1" in s and "trajectory passed     0/1" in s
