"""
Shared scoring contract used by every agent.

Every agent that produces a score MUST return an AgentScoreResult so that:
1. The Committee Agent can combine scores with a deterministic formula
   instead of asking an LLM to "vibe" a final number.
2. The frontend can render a breakdown (factor -> points -> reason -> source)
   for every score, so a user can see WHY a number is what it is.
3. Scores are comparable across agents (all on a 0-100 scale).

Design rules baked into this schema:
- Every score factor must carry a `reason` (no bare numbers).
- `source` is optional per-factor because not every judgment is
  source-backed (e.g. an inference from other findings), but agents
  should populate it whenever a claim traces back to a search result.
- `confidence` is separate from `score` — a low-data situation should
  lower confidence, not silently inflate/deflate the score itself.
  Downstream (Committee Agent) uses confidence to WEIGHT this agent's
  contribution to the final decision.
- `max_points` per factor lets weights be adjusted per-agent without
  changing every factor (e.g. a factor worth 30/100 vs 10/100).
"""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ScoreFactor(BaseModel):
    """One line item in a rubric — the atomic unit of justification."""

    factor: str = Field(description="Short name of what is being scored, e.g. 'TAM size'")
    points: float = Field(description="Points awarded for this factor")
    max_points: float = Field(description="Maximum possible points for this factor")
    reason: str = Field(
        description="1-2 sentence justification for the points awarded. "
        "Must reference concrete evidence, not just assert a conclusion."
    )
    source: Optional[str] = Field(
        default=None, description="URL this judgment is based on, if applicable"
    )

    @field_validator("points")
    @classmethod
    def points_within_bounds(cls, v: float, info) -> float:
        max_points = info.data.get("max_points")
        if max_points is not None and (v < 0 or v > max_points):
            raise ValueError(f"points ({v}) must be between 0 and max_points ({max_points})")
        return v


class BusinessProfile(BaseModel):
    """Company classification used to select the right weight profile
    (see agents/scoring_formula.py WEIGHT_PROFILES). Populated by the
    Research Agent, which already gathers the evidence needed to
    classify the company — avoids a duplicate LLM call.

    `category` is always derived by applying a fixed decision rule in
    code to the two boolean facts below — never taken directly from the
    LLM's own free-form judgment. See agents/research_agent.py for the
    exact rule.
    """

    category: str = Field(description="'TECH' | 'NON_TECH' | 'HYBRID'")
    is_core_product_software: Optional[bool] = Field(
        default=None,
        description="Whether the company's core product/offering IS software "
        "(not just internal tooling). None if evidence was unclear.",
    )
    is_revenue_physical_goods: Optional[bool] = Field(
        default=None,
        description="Whether revenue is primarily from physical goods/retail/"
        "FMCG. None if evidence was unclear.",
    )
    reasoning: str = Field(default="", description="1-2 sentence justification")


class AgentScoreResult(BaseModel):
    """Standard output contract for every scoring agent."""

    agent: str = Field(description="Name of the agent that produced this result")
    score: float = Field(description="Overall score for this dimension, 0-100")
    score_breakdown: List[ScoreFactor] = Field(
        description="Rubric line items that sum to `score`. Must not be empty "
        "unless status is 'failed' or 'no_data'."
    )
    summary: str = Field(description="2-4 sentence plain-language summary of the finding")
    confidence: float = Field(
        description="0-1 confidence in this score, based on quality/quantity of "
        "evidence found. Low confidence = thin or conflicting data."
    )
    sources: List[str] = Field(default_factory=list, description="All URLs consulted")
    status: str = Field(
        default="ok", description="'ok' | 'no_data' | 'failed' — lets the Committee "
        "Agent and frontend distinguish a real low score from a missing one"
    )
    error: Optional[str] = Field(default=None, description="Error message if status='failed'")
    business_profile: Optional[BusinessProfile] = Field(
        default=None,
        description="Only populated by Research Agent — company TECH/NON_TECH/"
        "HYBRID classification, consumed by the Committee Agent's scoring formula.",
    )

    @field_validator("score")
    @classmethod
    def score_within_bounds(cls, v: float) -> float:
        if not (0 <= v <= 100):
            raise ValueError(f"score must be 0-100, got {v}")
        return v

    @field_validator("confidence")
    @classmethod
    def confidence_within_bounds(cls, v: float) -> float:
        if not (0 <= v <= 1):
            raise ValueError(f"confidence must be 0-1, got {v}")
        return v


def make_failed_result(agent_name: str, error: str) -> AgentScoreResult:
    """Standard degraded-but-valid result when an agent fails.

    This is the key to error isolation: instead of raising and crashing
    the whole pipeline, a failed agent still returns something the
    Committee Agent can reason about (score=0, confidence=0, status=failed)
    and the frontend can render as "this analysis failed" rather than
    breaking the page.
    """
    return AgentScoreResult(
        agent=agent_name,
        score=0.0,
        score_breakdown=[],
        summary=f"{agent_name} could not complete analysis: {error}",
        confidence=0.0,
        sources=[],
        status="failed",
        error=error,
    )


def make_no_data_result(agent_name: str, reason: str) -> AgentScoreResult:
    """Standard result when the agent ran fine but found nothing to score.

    Distinct from `failed`: the agent itself worked, but e.g. search
    returned zero results for an obscure/new company. This should NOT
    be treated as score=0 (bad) by the Committee — it should be treated
    as "unknown", i.e. excluded or down-weighted, not penalized.
    """
    return AgentScoreResult(
        agent=agent_name,
        score=0.0,
        score_breakdown=[],
        summary=reason,
        confidence=0.0,
        sources=[],
        status="no_data",
    )


# ---------------------------------------------------------------------------
# Committee Agent output contract — deliberately NOT an AgentScoreResult,
# since the Committee produces a final verdict + narrative, not one
# combinable 0-100 dimension.
# ---------------------------------------------------------------------------

class AgentSummaryEntry(BaseModel):
    """One row in the committee's per-agent breakdown, for transparency."""

    agent: str
    score: float
    confidence: float
    status: str
    summary: str


class CommitteeResult(BaseModel):
    company: str
    category: str = Field(description="'TECH' | 'NON_TECH' | 'HYBRID' — profile used for weighting")
    final_score: float = Field(description="Deterministically computed, 0-100")
    verdict: str = Field(description="'INVEST' | 'WATCH' | 'PASS'")
    overall_confidence: float = Field(description="Average confidence across included agents")
    agent_summaries: List[AgentSummaryEntry]
    excluded_agents: List[dict] = Field(
        default_factory=list, description="Agents excluded from scoring, with reason"
    )
    significant_disagreement: bool = Field(
        default=False,
        description="True if included agents' scores spread widely (e.g. strong "
        "code, weak market) — surfaced explicitly rather than smoothed over by "
        "an average.",
    )
    disagreement_note: Optional[str] = Field(default=None)
    key_opportunities: List[str] = Field(default_factory=list)
    key_risks: List[str] = Field(default_factory=list)
    narrative: str = Field(description="LLM-written explanation of the verdict — "
                            "must justify, never override, the deterministic score")
    was_overridden: bool = Field(default=False)
    override_reason: Optional[str] = Field(default=None)
    confidence_breakdown: dict = Field(default_factory=dict)
