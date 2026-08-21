"""
Committee Agent

Combines all 8 scoring agents' results into a final verdict. This is
the most heavily rebuilt agent in the system — the original version
had two serious problems:

1. It indexed into a positional list (input_data[0], [1], [2]...) to
   pull out each agent's output. Any reordering upstream would silently
   scramble which "analysis" was attributed to which agent.
2. It asked an LLM to freely invent "investment score out of 100" with
   no fixed rule behind it — non-reproducible, non-auditable, and
   exactly the "black box score" problem this whole rebuild exists to
   fix.

FIX: this agent takes agent results as a NAMED dict (no positional
indexing), computes the final score with the deterministic formula in
scoring_formula.py (zero LLM involvement in the number), and uses the
LLM ONLY to write a narrative that explains an already-fixed score. The
LLM is explicitly told the score and forbidden from stating a different
one.

Two other things the original committee lacked, added here:
- DISAGREEMENT SURFACING: if included agents' scores spread widely
  (e.g. Code Agent says 90, Market Agent says 35), that's flagged
  explicitly rather than smoothed into an average that hides it — this
  is exactly the kind of signal a human investor most needs to see.
- CONFIDENCE-AWARE VERDICT: a high score built on low-confidence
  evidence should not produce a confident "INVEST" — the verdict logic
  caps what can be claimed when overall_confidence is low.

NOTE ON OUTPUT CONTRACT: unlike every other agent, this one does NOT
return an AgentScoreResult (that contract is for one combinable 0-100
dimension; the Committee produces a final verdict + narrative, which is
a different shape). It does not inherit BaseAgent for this reason, but
mirrors the same logging/timing/error-isolation discipline.
"""

import json
import re
import time
from typing import Any, Optional

from agents.scoring_formula import combine_scores
from core.logging import app_logger
from schemas.scoring import AgentScoreResult, AgentSummaryEntry, CommitteeResult
from services.llm_service import llm_service, AllLLMProvidersFailedError
from services.trust_service import detect_disagreement, apply_verdict_safety


def _extract_json(raw_text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    brace = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if brace:
        return json.loads(brace.group(0))
    raise ValueError("No JSON object found in LLM response")



class CommitteeAgent:

    def __init__(self):
        self.name = "Investment Committee Agent"

    async def execute(self, input_data: Any) -> CommitteeResult:
        """
        input_data must contain:
          - "company": str
          - "agent_results": dict[str, AgentScoreResult] — a NAMED dict,
            keyed by exact agent name (must match scoring_formula's
            WEIGHT_PROFILES keys), produced by running all 8 scoring
            agents beforehand. This agent does not run them itself —
            it is the final synthesis step in the pipeline.
        """
        start = time.monotonic()
        company = input_data["company"]
        agent_results: dict[str, AgentScoreResult] = input_data["agent_results"]

        app_logger.info(f"[{self.name}] started for '{company}'")

        try:
            result = await self._build_verdict(company, agent_results)
            duration = time.monotonic() - start
            app_logger.info(
                f"[{self.name}] finished in {duration:.2f}s "
                f"(score={result.final_score}, verdict={result.verdict})"
            )
            return result
        except AllLLMProvidersFailedError as exc:
            duration = time.monotonic() - start
            app_logger.error(f"[{self.name}] failed: All LLM providers unavailable")
            return CommitteeResult(
                company=company,
                category="HYBRID",
                final_score=0.0,
                verdict="WATCH",
                overall_confidence=0.0,
                agent_summaries=[],
                excluded_agents=[],
                significant_disagreement=False,
                disagreement_note=None,
                key_opportunities=[],
                key_risks=[],
                narrative="All LLM providers unavailable — evaluation could not be completed for this factor.",
            )
        except Exception as exc:
            duration = time.monotonic() - start
            app_logger.error(f"[{self.name}] failed after {duration:.2f}s: {exc}")
            # Error isolation, matching base_agent's philosophy: return a
            # valid-but-degraded result instead of crashing the whole
            # evaluation response.
            return CommitteeResult(
                company=company,
                category="HYBRID",
                final_score=0.0,
                verdict="WATCH",
                overall_confidence=0.0,
                agent_summaries=[],
                excluded_agents=[],
                significant_disagreement=False,
                disagreement_note=None,
                key_opportunities=[],
                key_risks=[],
                narrative=f"Committee synthesis failed to complete: {exc}. "
                          f"This verdict is not reliable — treat as WATCH pending re-run.",
            )

    async def _build_verdict(
        self, company: str, agent_results: dict[str, AgentScoreResult]
    ) -> CommitteeResult:

        # --- Category comes from Research Agent's business_profile ---------
        research_result = agent_results.get("Research Agent")
        if research_result and research_result.business_profile:
            category = research_result.business_profile.category
        else:
            app_logger.warning(
                f"[{self.name}] no business_profile available for '{company}' "
                f"— defaulting to HYBRID weight profile"
            )
            category = "HYBRID"

        # --- Deterministic score, zero LLM involvement ----------------------
        combined = combine_scores(agent_results, category=category)

        # --- Deterministic verdict from trust service safety rules ---------
        safety = apply_verdict_safety(combined.final_score, combined.overall_confidence)
        verdict = safety.verdict

        # --- Deterministic disagreement detection ---------------------------
        disagreement = detect_disagreement(agent_results)
        has_disagreement = disagreement.significant_disagreement
        disagreement_note = disagreement.disagreement_note

        agent_summaries = [
            AgentSummaryEntry(
                agent=name,
                score=result.score,
                confidence=result.confidence,
                status=result.status,
                summary=result.summary,
            )
            for name, result in agent_results.items()
        ]

        # If literally everything was excluded, there's no basis for even
        # an LLM narrative — return early rather than prompting on nothing.
        if not combined.included_agents:
            return CommitteeResult(
                company=company,
                category=category,
                final_score=0.0,
                verdict="WATCH",
                overall_confidence=0.0,
                agent_summaries=agent_summaries,
                excluded_agents=combined.excluded_agents,
                significant_disagreement=False,
                disagreement_note=None,
                key_opportunities=[],
                key_risks=[],
                narrative=(
                    f"No agent produced usable data for '{company}' (all agents "
                    f"returned no_data or failed). Cannot make an investment "
                    f"assessment — this requires re-evaluation, not a PASS "
                    f"decision, since PASS would imply evidence of weakness "
                    f"that we don't actually have."
                ),
                was_overridden=safety.was_overridden,
                override_reason=safety.override_reason,
                confidence_breakdown=combined.confidence_breakdown,
            )

        # --- LLM writes ONLY the narrative, given the fixed number ----------
        findings_block = "\n\n".join(
            f"--- {name} (score={r.score}/100, confidence={r.confidence}, status={r.status}) ---\n{r.summary}"
            for name, r in agent_results.items()
        )

        disagreement_context = (
            f"\nNOTE: significant disagreement was detected between agents: {disagreement_note}\n"
            if has_disagreement else ""
        )

        prompt = f"""You are writing the narrative portion of a VC investment committee
report for '{company}'. The final score and verdict have ALREADY been
computed by a fixed formula and are NOT yours to change:

FINAL SCORE (fixed, do not alter): {combined.final_score}/100
VERDICT (fixed, do not alter): {verdict}
COMPANY CATEGORY: {category}
OVERALL CONFIDENCE: {combined.overall_confidence}
{disagreement_context}
Your job is ONLY to explain WHY this score/verdict makes sense given the
findings below — write the opportunity case and the risk case, and identify
2-4 key opportunities and 2-4 key risks. Do not state a different score or
verdict anywhere in your output, including the narrative text.

AGENT FINDINGS:
{findings_block}

Return ONLY a JSON object, no markdown fences, no preamble:
{{
  "narrative": "3-5 sentence explanation of why this score/verdict fits the evidence",
  "key_opportunities": ["<short phrase>", ...],
  "key_risks": ["<short phrase>", ...]
}}"""

        try:
            from core.config import settings
            parsed = await llm_service.generate_structured(prompt, bypass_cache=getattr(settings, "EVALUATION_MODE", False))
            narrative = parsed.get("narrative", "")
            key_opportunities = parsed.get("key_opportunities", [])
            key_risks = parsed.get("key_risks", [])
        except Exception as exc:
            # Narrative generation failing should NOT take down the whole
            # committee result — the deterministic score/verdict are still
            # valid and useful without prose around them.
            app_logger.warning(f"[{self.name}] narrative generation failed: {exc}")
            narrative = (
                f"Score: {combined.final_score}/100, Verdict: {verdict}. "
                f"(Narrative generation failed — see per-agent summaries above for detail.)"
            )
            key_opportunities = []
            key_risks = []

        return CommitteeResult(
            company=company,
            category=category,
            final_score=combined.final_score,
            verdict=verdict,
            overall_confidence=combined.overall_confidence,
            agent_summaries=agent_summaries,
            excluded_agents=combined.excluded_agents,
            significant_disagreement=has_disagreement,
            disagreement_note=disagreement_note,
            key_opportunities=key_opportunities,
            key_risks=key_risks,
            narrative=narrative,
            was_overridden=safety.was_overridden,
            override_reason=safety.override_reason,
            confidence_breakdown=combined.confidence_breakdown,
        )
