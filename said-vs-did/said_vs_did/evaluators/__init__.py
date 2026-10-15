from dataclasses import dataclass

from .outcome import OutcomeResult, check_outcome
from .trajectory import TrajectoryResult, check_trajectory


@dataclass
class Scorecard:
    judge: dict  # stored LLM verdict: passed, score, reason
    outcome: OutcomeResult
    trajectory: TrajectoryResult

    @property
    def said_vs_did_conflict(self) -> bool:
        return not self.trajectory.rule("R3").passed


def score(trace: dict) -> Scorecard:
    """Score one trace. Only the deterministic checks run here; the judge verdict and the
    extracted claims were stored in the trace by the live run, so this needs no API key."""
    llm = trace["llm_evals"]
    return Scorecard(
        judge=llm["judge"],
        outcome=check_outcome(trace["initial_state"], trace["final_state"], trace["expected_refunds"]),
        trajectory=check_trajectory(trace, llm["claims"]["claims"]),
    )
