"""
Risk Agent

Identifies business, technical, market, founder, and legal/regulatory
risks and scores overall investment safety on a 0-100 rubric.

CRITICAL FIX FROM PREVIOUS VERSION: the old agent had NO search of its
own — it only received whatever `input_data` the orchestrator passed in
(likely a raw dump of other agents' outputs) and confidently generated
"risks" from that alone. For a "skeptical VC" persona, skepticism is
worthless without independent evidence to be skeptical WITH. This is
the single highest-hallucination-risk agent in the system: fabricated
risks (e.g. "the founder's prior venture failed") could be actively
defamatory and mislead a real investment decision.

Fixes:
1. This agent now runs its OWN targeted searches for red flags
   (lawsuits, controversies, regulatory issues, negative press) rather
   than relying solely on other agents' summaries.
2. Other agents' findings (if provided) are passed in as clearly
   labeled, structured sections — never a raw dict dump.
3. Every risk flag MUST cite either a source URL or explicitly say it
   is an inferred/general risk (not documented) — the two are scored
   and labeled differently so a reader can't mistake speculation for
   a documented fact.
4. Scored 0-100, where HIGHER = SAFER (fewer/less severe risks). This
   direction is intentional so the Committee Agent can combine it with
   other "higher = better" agent scores using the same formula, without
   needing to invert it. Documented clearly here to prevent future
   confusion.
"""

import asyncio
import json
import re
from typing import Any, List, Optional

from agents.base_agent import BaseAgent
from core.logging import app_logger
from schemas.scoring import AgentScoreResult, ScoreFactor, make_no_data_result
from services.llm_service import llm_service
from tools.search_tool import search_tool


# NOTE: max_points here represent the BEST case (i.e. "no risk found in
# this category"). Points are deducted as documented risks accumulate.
RUBRIC = [
    {"factor": "Business/operational risk", "max_points": 20,
     "guidance": "Deduct points only for DOCUMENTED business risks (e.g. reported "
                 "churn, failed pivots, dependency on a single customer/partner). "
                 "Do not deduct for generic/hypothetical risks every startup faces."},
    {"factor": "Technical risk", "max_points": 15,
     "guidance": "Deduct for documented technical issues (e.g. reported outages, "
                 "security incidents, unscalable architecture claims from credible "
                 "sources). Award full points if no technical evidence is negative."},
    {"factor": "Market risk", "max_points": 20,
     "guidance": "Deduct for documented market headwinds (regulatory threats, "
                 "shrinking demand, commoditization). Award full points if no "
                 "negative market evidence is found."},
    {"factor": "Founder/team risk", "max_points": 25,
     "guidance": "Deduct ONLY for explicitly documented concerns (e.g. reported "
                 "prior venture failure, publicly reported disputes, departures). "
                 "NEVER infer character or competence issues that aren't documented. "
                 "Award full points if no negative founder evidence is found."},
    {"factor": "Legal/regulatory risk", "max_points": 20,
     "guidance": "Deduct for documented lawsuits, regulatory investigations, "
                 "compliance issues. Award full points if none are found."},
]

MAX_TOTAL_POINTS = sum(f["max_points"] for f in RUBRIC)  # = 100


def _build_queries(company_name: str) -> List[str]:
    """This agent's own independent evidence search — the fix for the
    original version having no data source of its own."""
    return [
        f"{company_name} lawsuit controversy",
        f"{company_name} negative reviews complaints",
        f"{company_name} regulatory investigation compliance",
        f"{company_name} layoffs shutdown problems",
    ]


def _format_other_findings(other_findings: Optional[dict]) -> str:
    """Format other agents' findings as clearly labeled sections instead
    of dumping a raw dict/object into the prompt as a string."""
    if not other_findings:
        return "(no findings from other agents were provided)"

    sections = []
    for agent_name, result in other_findings.items():
        summary = getattr(result, "summary", None) or (
            result.get("summary") if isinstance(result, dict) else str(result)
        )
        sections.append(f"--- {agent_name} ---\n{summary}")
    return "\n\n".join(sections)


def _extract_json(raw_text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    brace = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if brace:
        return json.loads(brace.group(0))
    raise ValueError("No JSON object found in LLM response")


class RiskAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="Risk Agent",
            role="Investment risk analyst",
        )

    async def run(self, input_data: Any) -> AgentScoreResult:
        company = input_data["company"]
        # Other agents' AgentScoreResult objects, if the orchestrator
        # passes them in (e.g. {"research": <result>, "market": <result>}).
        other_findings = input_data.get("other_findings")

        queries = _build_queries(company)

        async def _safe_search(query: str):
            try:
                return await search_tool.search(query)
            except Exception as exc:
                app_logger.warning(f"[Risk Agent] search failed for '{query}': {exc}")
                return None

        search_results = await asyncio.gather(*[_safe_search(q) for q in queries])

        all_results = []
        for hits in search_results:
            if hits:
                all_results.extend(hits if isinstance(hits, list) else [hits])

        other_findings_block = _format_other_findings(other_findings)

        # Unlike other agents, absence of negative evidence is NOT a
        # no_data situation here — "we searched for red flags and found
        # none" is itself a meaningful, scoreable result (full points).
        # We only bail out if we have neither our own search results NOR
        # any other agent's findings to reason about at all.
        if not all_results and not other_findings:
            return make_no_data_result(
                self.name,
                f"No evidence available (own search and other agent findings both "
                f"empty) to assess risk for '{company}'.",
            )

        evidence_block = "\n\n".join(f"- {item}" for item in all_results) or (
            "(no negative evidence found in independent search)"
        )
        rubric_text = "\n".join(
            f"- {f['factor']} (max {f['max_points']} points = LOWEST risk in this "
            f"category): {f['guidance']}"
            for f in RUBRIC
        )

        prompt = f"""You are a skeptical VC risk analyst evaluating '{company}'. Score
against the exact rubric below. IMPORTANT: higher points = LOWER risk (award
full points for a category if no negative evidence is found — do not assume
risk exists just because you can't rule it out).

Only deduct points for a DOCUMENTED concern from the evidence below. If you
mention a risk that is not directly supported by evidence, label it clearly
as "general/inferred risk" (common to this type of company) rather than
presenting it as a specific fact about '{company}'. Never state a specific
negative claim (e.g. a named lawsuit, a named failure) unless it appears in
the evidence.

RUBRIC:
{rubric_text}

INDEPENDENT RISK SEARCH EVIDENCE:
{evidence_block}

FINDINGS FROM OTHER AGENTS:
{other_findings_block}

Return ONLY a single valid JSON object, no markdown fences, no preamble, in
exactly this shape:

{{
  "summary": "2-4 sentence plain-language summary of the risk profile",
  "confidence": 0.0-1.0,
  "score_breakdown": [
    {{
      "factor": "<exact factor name from rubric>",
      "points": <number, 0 to max_points for that factor>,
      "max_points": <number>,
      "reason": "1-2 sentences: cite the specific documented risk that caused "
                "a deduction, or state 'no negative evidence found' for full points",
      "source": "<url if applicable, else null>"
    }}
  ],
  "sources": ["<all urls actually used>"]
}}

Every factor in the rubric must appear exactly once in score_breakdown.
confidence should be LOW (below 0.4) if evidence was thin — thin evidence
means uncertainty, not automatically low risk."""

        raw_response = await llm_service.generate(prompt)

        try:
            parsed = _extract_json(raw_response)
            factors = [ScoreFactor(**f) for f in parsed["score_breakdown"]]
            total_score = sum(f.points for f in factors)

            return AgentScoreResult(
                agent=self.name,
                score=round(total_score, 1),
                score_breakdown=factors,
                summary=parsed["summary"],
                confidence=float(parsed["confidence"]),
                sources=parsed.get("sources", []),
                status="ok",
            )
        except Exception as exc:
            app_logger.error(f"[Risk Agent] failed to parse LLM output: {exc}")
            raise
