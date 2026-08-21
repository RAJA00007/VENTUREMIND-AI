"""
Competitor Agent

Maps the competitive landscape for a company and scores its defensibility
on a 0-100 rubric. The previous version let the LLM freely assert a
"strong/medium/weak" moat with no evidence requirement, and returned a
categorical "threat level" (LOW/MEDIUM/HIGH) that didn't fit the 0-100
scale used everywhere else. Both are fixed here:

- Moat points are only awarded when a *concrete* mechanism is found in
  evidence (proprietary data, network effects, switching costs, brand,
  regulatory barriers) — not because the company *claims* differentiation
  in its own marketing.
- Everything is scored 0-100 so the Committee Agent can combine it with
  other agents using a single weighted formula.
"""

import asyncio
import json
import re
from typing import Any, List

from agents.base_agent import BaseAgent
from core.config import settings
from core.logging import app_logger
from schemas.scoring import AgentScoreResult, ScoreFactor, make_no_data_result
from services.llm_service import llm_service, AllLLMProvidersFailedError
from tools.search_tool import search_tool


RUBRIC = [
    {"factor": "Competitive landscape mapping", "max_points": 20,
     "guidance": "How clearly can direct and indirect competitors be identified "
                 "from evidence? Award 0 if no competitors could be identified at all "
                 "(this may mean thin evidence, not necessarily no competition)."},
    {"factor": "Differentiation clarity", "max_points": 20,
     "guidance": "Is there a specific, articulable way this company differs from "
                 "competitors, based on evidence — not just marketing claims?"},
    {"factor": "Moat strength (evidence-gated)", "max_points": 35,
     "guidance": "ONLY award points if a CONCRETE mechanism is found in evidence: "
                 "proprietary data/tech, network effects, switching costs, regulatory "
                 "barriers, exclusive partnerships, or brand with real retention proof. "
                 "A company simply claiming to be 'different' or 'better' earns 0 here. "
                 "Being skeptical is the job — most startups do not have a strong moat."},
    {"factor": "Competitive risk exposure", "max_points": 25,
     "guidance": "How exposed is this company to being copied, undercut, or displaced "
                 "by a well-funded incumbent or new entrant? Higher points = LOWER risk "
                 "(i.e. more insulated from competition)."},
]

MAX_TOTAL_POINTS = sum(f["max_points"] for f in RUBRIC)  # = 100


def _build_queries(company_name: str, industry_hint: str | None) -> List[str]:
    base = industry_hint or company_name
    return [
        f"{company_name} competitors alternatives",
        f"{base} top companies competitive landscape",
        f"{company_name} vs competitors comparison",
        f"{company_name} competitive advantage moat",
    ]


def _extract_json(raw_text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    brace = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if brace:
        return json.loads(brace.group(0))
    raise ValueError("No JSON object found in LLM response")


class CompetitorAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="Competitor Agent",
            role="Competitive intelligence analyst",
        )

    async def run(self, input_data: Any) -> AgentScoreResult:
        company = input_data["company"]
        industry_hint = input_data.get("industry")

        queries = _build_queries(company, industry_hint)

        async def _safe_search(query: str):
            try:
                return await search_tool.search(query)
            except Exception as exc:
                app_logger.warning(f"[Competitor Agent] search failed for '{query}': {exc}")
                return None

        search_results = await asyncio.gather(*[_safe_search(q) for q in queries])

        all_results = []
        for hits in search_results:
            if hits:
                all_results.extend(hits if isinstance(hits, list) else [hits])

        if not all_results:
            return make_no_data_result(
                self.name,
                f"No competitive landscape data found for '{company}'. Cannot "
                f"assess competition or moat without evidence.",
            )

        evidence_block = "\n\n".join(f"- {item}" for item in all_results)
        rubric_text = "\n".join(
            f"- {f['factor']} (max {f['max_points']} points): {f['guidance']}"
            for f in RUBRIC
        )

        prompt = f"""You are a skeptical competitive intelligence analyst evaluating
'{company}'. Score against the exact rubric below, using ONLY the evidence
provided. Be deliberately skeptical about moat claims: most startups do not
have a defensible moat, and a company describing itself as "unique" or
"innovative" in its own marketing is NOT evidence of a moat. Only award moat
points when a concrete mechanism is documented in the evidence.

RUBRIC:
{rubric_text}

COMPETITIVE EVIDENCE:
{evidence_block}

Return ONLY a single valid JSON object, no markdown fences, no preamble, in
exactly this shape:

{{
  "summary": "2-4 sentence plain-language summary of the competitive landscape",
  "confidence": 0.0-1.0,
  "competitors_identified": ["<competitor name>", ...],
  "score_breakdown": [
    {{
      "factor": "<exact factor name from rubric>",
      "points": <number, 0 to max_points for that factor>,
      "max_points": <number>,
      "reason": "1-2 sentences citing the specific evidence, or why it's 0",
      "source": "<url if applicable, else null>"
    }}
  ],
  "sources": ["<all urls actually used>"]
}}

Every factor in the rubric must appear exactly once in score_breakdown.
confidence should be LOW (below 0.4) if competitive evidence was thin."""

        try:
            parsed = await llm_service.generate_structured(prompt, bypass_cache=getattr(settings, "EVALUATION_MODE", False))
            factors = [ScoreFactor(**f) for f in parsed["score_breakdown"]]
            total_score = sum(f.points for f in factors)

            competitors = parsed.get("competitors_identified", [])
            summary = parsed["summary"]
            if competitors:
                summary += f" Identified competitors: {', '.join(competitors[:5])}."

            return AgentScoreResult(
                agent=self.name,
                score=round(total_score, 1),
                score_breakdown=factors,
                summary=summary,
                confidence=float(parsed["confidence"]),
                sources=parsed.get("sources", []),
                status="ok",
            )
        except AllLLMProvidersFailedError:
            return make_no_data_result(
                self.name,
                "All LLM providers unavailable — evaluation could not be completed for this factor."
            )
        except Exception as exc:
            app_logger.error(f"[Competitor Agent] failed to parse LLM output: {exc}")
            raise
