"""
Market Agent

Evaluates the market opportunity for a company: size (TAM/SAM), growth
rate, customer demand signals, and timing (tailwinds vs. headwinds).
Scores against an explicit rubric on a 0-100 scale — matching every
other scoring agent, so the Committee Agent can combine scores with a
single weighted formula without unit conversion.

NOTE: the previous version of this agent scored 1-10, while the rest of
the system (Committee Agent, frontend radar chart) uses 0-100. That
mismatch would have silently corrupted any combined score or chart. All
agents must stay on 0-100.
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
    {"factor": "Market size (TAM/SAM)", "max_points": 30,
     "guidance": "Credible market size figures found in evidence. Award 0 if no "
                 "reliable figure is found — do not estimate or invent a number."},
    {"factor": "Growth rate", "max_points": 25,
     "guidance": "Industry CAGR or growth rate found in evidence. Award 0 if unknown."},
    {"factor": "Customer demand signals", "max_points": 20,
     "guidance": "Evidence of real demand: adoption trends, search interest, "
                 "analyst commentary, customer complaints about status quo."},
    {"factor": "Market timing (tailwinds vs. headwinds)", "max_points": 25,
     "guidance": "Regulatory, technological, or macro trends helping or hurting "
                 "this market right now, based on evidence found."},
]

MAX_TOTAL_POINTS = sum(f["max_points"] for f in RUBRIC)  # = 100


def _build_queries(company_name: str, industry_hint: str | None) -> List[str]:
    base = industry_hint or company_name
    return [
        f"{base} market size TAM SAM",
        f"{base} industry growth rate CAGR",
        f"{company_name} target customer demand",
        f"{base} industry trends tailwinds headwinds",
    ]


def _extract_json(raw_text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    brace = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if brace:
        return json.loads(brace.group(0))
    raise ValueError("No JSON object found in LLM response")


class MarketAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="Market Agent",
            role="Market opportunity analyst",
        )

    async def run(self, input_data: Any) -> AgentScoreResult:
        company = input_data["company"]
        industry_hint = input_data.get("industry")

        queries = _build_queries(company, industry_hint)

        async def _safe_search(query: str):
            try:
                return await search_tool.search(query)
            except Exception as exc:
                app_logger.warning(f"[Market Agent] search failed for '{query}': {exc}")
                return None

        search_results = await asyncio.gather(*[_safe_search(q) for q in queries])

        all_results = []
        for hits in search_results:
            if hits:
                all_results.extend(hits if isinstance(hits, list) else [hits])

        if not all_results:
            return make_no_data_result(
                self.name,
                f"No market data found for '{company}'. Cannot assess market "
                f"opportunity without evidence.",
            )

        evidence_block = "\n\n".join(f"- {item}" for item in all_results)
        rubric_text = "\n".join(
            f"- {f['factor']} (max {f['max_points']} points): {f['guidance']}"
            for f in RUBRIC
        )

        prompt = f"""You are a VC market analyst. Score the market opportunity for
'{company}' against the exact rubric below, using ONLY the evidence provided.
Never invent a market size, growth rate, or trend that isn't supported by
the evidence — award 0 points and say "not found in available evidence"
instead of estimating.

RUBRIC:
{rubric_text}

MARKET EVIDENCE:
{evidence_block}

Return ONLY a single valid JSON object, no markdown fences, no preamble, in
exactly this shape:

{{
  "summary": "2-4 sentence plain-language summary of the market opportunity",
  "confidence": 0.0-1.0,
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
confidence should be LOW (below 0.4) if market data was thin or unclear."""

        try:
            parsed = await llm_service.generate_structured(prompt, bypass_cache=getattr(settings, "EVALUATION_MODE", False))
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
        except AllLLMProvidersFailedError:
            return make_no_data_result(
                self.name,
                "All LLM providers unavailable — evaluation could not be completed for this factor."
            )
        except Exception as exc:
            app_logger.error(f"[Market Agent] failed to parse LLM output: {exc}")
            raise
