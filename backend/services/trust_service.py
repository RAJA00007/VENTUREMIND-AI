from typing import List, Optional
from pydantic import BaseModel
from schemas.scoring import AgentScoreResult

class DisagreementResult(BaseModel):
    significant_disagreement: bool
    disagreement_note: Optional[str] = None
    conflicting_agents: List[str] = []
    spread: float = 0.0

class VerdictSafetyResult(BaseModel):
    verdict: str
    was_overridden: bool
    original_verdict: str
    override_reason: Optional[str] = None

def detect_disagreement(agent_results: dict[str, AgentScoreResult]) -> DisagreementResult:
    """Computed in code, not asserted by an LLM — a spread in scores is
    an objective fact once you have the numbers."""
    DISAGREEMENT_SPREAD_THRESHOLD = 35
    scored = [
        (name, r.score) for name, r in agent_results.items()
        if getattr(r, "status", "ok") == "ok"
    ]
    if len(scored) < 2:
        return DisagreementResult(
            significant_disagreement=False,
            disagreement_note=None,
            conflicting_agents=[],
            spread=0.0
        )

    scores_only = [s for _, s in scored]
    spread = max(scores_only) - min(scores_only)

    if spread < DISAGREEMENT_SPREAD_THRESHOLD:
        return DisagreementResult(
            significant_disagreement=False,
            disagreement_note=None,
            conflicting_agents=[],
            spread=spread
        )

    highest = max(scored, key=lambda x: x[1])
    lowest = min(scored, key=lambda x: x[1])
    note = (
        f"{highest[0]} scored this highly ({highest[1]}) while {lowest[0]} scored "
        f"it much lower ({lowest[1]}) — a {spread:.0f}-point spread. This is not "
        f"averaged away; both signals should be weighed independently."
    )
    return DisagreementResult(
        significant_disagreement=True,
        disagreement_note=note,
        conflicting_agents=[highest[0], lowest[0]],
        spread=spread
    )

def apply_verdict_safety(score: float, confidence: float) -> VerdictSafetyResult:
    """Fixed rule, not an LLM judgment call. Confidence caps/overrides the verdict."""
    INVEST_THRESHOLD = 75
    WATCH_THRESHOLD = 50
    CONFIDENCE_CAP = 0.60

    # Determine original verdict based purely on score
    if score >= INVEST_THRESHOLD:
        original = "INVEST"
    elif score >= WATCH_THRESHOLD:
        original = "WATCH"
    else:
        original = "PASS"

    # Apply verdict safety rules based on confidence
    if original == "INVEST" and confidence < CONFIDENCE_CAP:
        return VerdictSafetyResult(
            verdict="WATCH",
            was_overridden=True,
            original_verdict=original,
            override_reason=f"Verdict INVEST downgraded to WATCH due to low confidence ({confidence * 100:.0f}%)"
        )
    elif original == "PASS" and confidence < 0.40:
        return VerdictSafetyResult(
            verdict="WATCH",
            was_overridden=True,
            original_verdict=original,
            override_reason=f"Verdict PASS upgraded to WATCH due to very low confidence ({confidence * 100:.0f}%)"
        )
    
    return VerdictSafetyResult(
        verdict=original,
        was_overridden=False,
        original_verdict=original,
        override_reason=None
    )

def compute_confidence(agent_results: dict[str, AgentScoreResult], category: str = "HYBRID") -> float:
    """Returns the confidence score computed in the single source of truth (scoring_formula)."""
    from agents.scoring_formula import combine_scores
    combined = combine_scores(agent_results, category=category)
    return combined.overall_confidence
