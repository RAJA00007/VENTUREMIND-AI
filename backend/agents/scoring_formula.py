"""
Deterministic scoring formula for the Committee Agent.

Kept as a pure function, separate from committee_agent.py, so it can be
unit-tested with fixed inputs/outputs independent of any LLM call. This
is the "code decides the number, LLM explains the number" split that
makes the final score reproducible and auditable — the exact opposite
of the old committee_agent.py, which asked an LLM to freely invent a
score out of 100 with no fixed rule behind it.

WEIGHT_PROFILES is a business decision, not something derived
automatically — tune it based on your own diligence philosophy. It's
intentionally kept as one editable dict of dicts in one place.
"""

from typing import Optional

from core.logging import app_logger
from schemas.scoring import AgentScoreResult

# Business decision: how much each dimension matters to the final
# verdict. Each profile must sum to 100. Edit these to change diligence
# philosophy without touching any scoring logic below.
#
# Rationale for the split (see company_classifier.py for how a company
# is assigned to one of these):
# - TECH: code quality IS the core product, so it's weighted heavily.
# - NON_TECH: code is rarely the value driver (e.g. FMCG, retail) — kept
#   small but non-zero, since some tech (e-commerce backend, apps) can
#   still matter a little. Finance/Market/Competitor weighted up since
#   margins, distribution, and brand differentiation dominate outcomes.
# - HYBRID: balanced — tech-enabled businesses (marketplaces, fintech,
#   logistics) where both product execution and code matter, but neither
#   dominates. Risk weighted slightly higher since these businesses often
#   carry more regulatory/operational complexity (e.g. fintech, mobility).
WEIGHT_PROFILES = {
    "TECH": {
        "Research Agent": 8,
        "Market Agent": 12,
        "Competitor Agent": 10,
        "Founder Agent": 15,
        "Finance Agent": 13,
        "Code / GitHub Agent": 25,
        "Risk Agent": 10,
        "Prediction Agent": 7,
    },
    "NON_TECH": {
        "Research Agent": 10,
        "Market Agent": 20,
        "Competitor Agent": 15,
        "Founder Agent": 15,
        "Finance Agent": 20,
        "Code / GitHub Agent": 3,
        "Risk Agent": 10,
        "Prediction Agent": 7,
    },
    "HYBRID": {
        "Research Agent": 8,
        "Market Agent": 15,
        "Competitor Agent": 12,
        "Founder Agent": 15,
        "Finance Agent": 15,
        "Code / GitHub Agent": 15,
        "Risk Agent": 12,
        "Prediction Agent": 8,
    },
}

for _category, _weights in WEIGHT_PROFILES.items():
    assert sum(_weights.values()) == 100, f"{_category} weights must sum to 100"

# Floor applied to confidence before weighting, so a single agent with
# confidence=0 doesn't get literally zero influence in a way that could
# look like a bug — it still counts, just heavily discounted.
MIN_EFFECTIVE_CONFIDENCE = 0.05


class CombinedScoreResult:
    """Return type for combine_scores() — plain, no pydantic needed
    since this never crosses an API boundary on its own; committee_agent
    will fold this into its own response."""

    def __init__(
        self,
        final_score: float,
        overall_confidence: float,
        included_agents: list[str],
        excluded_agents: list[dict],
        per_agent_contribution: dict[str, dict],
        category_used: str,
        confidence_breakdown: Optional[dict] = None,
    ):
        self.final_score = final_score
        self.overall_confidence = overall_confidence
        self.included_agents = included_agents
        self.excluded_agents = excluded_agents
        self.per_agent_contribution = per_agent_contribution
        self.category_used = category_used
        self.confidence_breakdown = confidence_breakdown or {}


def combine_scores(
    agent_results: dict[str, AgentScoreResult],
    category: str = "HYBRID",
) -> CombinedScoreResult:
    """
    agent_results: dict mapping agent name (matching WEIGHT_PROFILES keys)
    to that agent's AgentScoreResult.
    category: "TECH" | "NON_TECH" | "HYBRID" — selects which weight
    profile to apply. Defaults to HYBRID (the safe balanced middle) if
    an unrecognized category is passed in, rather than raising, since a
    classification failure shouldn't crash the whole evaluation.

    Returns a fully deterministic combined score — no LLM involved.
    """
    weights = WEIGHT_PROFILES.get(category)
    if weights is None:
        app_logger.warning(f"Unknown category '{category}', defaulting to HYBRID weights")
        weights = WEIGHT_PROFILES["HYBRID"]

    included_agents = []
    excluded_agents = []
    per_agent_contribution = {}
    effective_weights = {}

    for agent_name, weight in weights.items():
        result = agent_results.get(agent_name)

        if result is None:
            excluded_agents.append({"agent": agent_name, "reason": "not_run"})
            continue

        if result.status in ("no_data", "failed"):
            excluded_agents.append({"agent": agent_name, "reason": result.status})
            continue

        confidence = max(result.confidence, MIN_EFFECTIVE_CONFIDENCE)
        effective_weight = weight * confidence
        effective_weights[agent_name] = effective_weight
        included_agents.append(agent_name)

    total_effective_weight = sum(effective_weights.values())

    if total_effective_weight == 0:
        # Every agent failed, had no data, or wasn't run at all.
        return CombinedScoreResult(
            final_score=0.0,
            overall_confidence=0.0,
            included_agents=[],
            excluded_agents=excluded_agents,
            per_agent_contribution={},
            category_used=category,
            confidence_breakdown={
                "raw_avg": 0.0,
                "data_coverage": 0.0,
                "agreement_factor": 0.0,
            }
        )

    final_score = 0.0
    confidences_used = []

    for agent_name in included_agents:
        result = agent_results[agent_name]
        normalized_weight = effective_weights[agent_name] / total_effective_weight
        contribution = normalized_weight * result.score
        final_score += contribution

        confidences_used.append(result.confidence)
        per_agent_contribution[agent_name] = {
            "score": result.score,
            "confidence": result.confidence,
            "base_weight": weights[agent_name],
            "normalized_weight": round(normalized_weight, 3),
            "contribution_to_final_score": round(contribution, 2),
        }

    raw_avg_confidence = sum(confidences_used) / len(confidences_used) if confidences_used else 0.0
    total_expected = len(weights)
    data_coverage = len(included_agents) / total_expected if total_expected else 1.0

    if len(included_agents) >= 2:
        scores_only = [agent_results[name].score for name in included_agents]
        spread = max(scores_only) - min(scores_only)
    else:
        spread = 0.0
    agreement_factor = 1.0 - min(spread / 100.0, 1.0)

    # Weighted confidence: 50% raw average, 25% data coverage, 25% agreement
    overall_confidence = round(
        (raw_avg_confidence * 0.5) + (data_coverage * 0.25) + (agreement_factor * 0.25),
        2
    )

    confidence_breakdown = {
        "raw_avg": round(raw_avg_confidence, 2),
        "data_coverage": round(data_coverage, 2),
        "agreement_factor": round(agreement_factor, 2),
    }

    return CombinedScoreResult(
        final_score=round(final_score, 1),
        overall_confidence=overall_confidence,
        included_agents=included_agents,
        excluded_agents=excluded_agents,
        per_agent_contribution=per_agent_contribution,
        category_used=category,
        confidence_breakdown=confidence_breakdown,
    )
