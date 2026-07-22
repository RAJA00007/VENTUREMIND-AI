"""
Founder Agent

Analyzes the founding team's professional background, relevant domain
experience, prior track record, and team completeness — scored on a
0-100 rubric.

STRICT GUARDRAIL: this agent evaluates documented CAREER FACTS only. It
must never infer personality traits, character, or competence from
indirect signals (background, name, education pedigree, etc.) — only
from explicitly documented professional history. A red flag may only be
cited if it is a specific, sourced, publicly reported fact (e.g. a
reported prior venture shutdown) — never a speculative inference.
"""

import asyncio
import json
import re
from typing import Any, List

from agents.base_agent import BaseAgent
from core.logging import app_logger
from schemas.scoring import AgentScoreResult, ScoreFactor, make_no_data_result
from services.llm_service import llm_service, AllLLMProvidersFailedError
from tools.search_tool import search_tool


RUBRIC = [
    {"factor": "Relevant domain experience", "max_points": 30,
     "guidance": "Documented prior work directly relevant to this venture's domain "
                 "(e.g. built similar tech, worked in this industry). Award 0 if no "
                 "founder background could be found — do not guess competence."},
    {"factor": "Prior track record", "max_points": 25,
     "guidance": "Documented prior founder/exec experience: previous startups, exits, "
                 "senior roles at recognized companies. Award 0 if unknown."},
    {"factor": "Team completeness", "max_points": 25,
     "guidance": "Does the team have complementary skills (e.g. technical + business "
                 "co-founders)? Deduct if evidence suggests a clear gap (e.g. no "
                 "technical co-founder for a deep-tech product). Award 0 if team "
                 "composition can't be determined from evidence."},
    {"factor": "Execution signals", "max_points": 20,
     "guidance": "Concrete evidence of shipping/executing: launched products before, "
                 "raised funding before, public technical work (e.g. open source). "
                 "Award 0 if no execution evidence is found."},
]

MAX_TOTAL_POINTS = sum(f["max_points"] for f in RUBRIC)  # = 100


def _build_queries(company_name: str, founder_names_hint: List[str] | None) -> List[str]:
    queries = [
        f"{company_name} founders team",
        f"{company_name} CEO CTO background",
        f"{company_name} founding team experience",
    ]
    if founder_names_hint:
        queries.extend(f"{name} {company_name} career background" for name in founder_names_hint)
    return queries


def _extract_json(raw_text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    brace = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if brace:
        return json.loads(brace.group(0))
    raise ValueError("No JSON object found in LLM response")


class FounderAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="Founder Agent",
            role="Founder due-diligence analyst",
        )

    async def run(self, input_data: Any) -> AgentScoreResult:
        company = input_data["company"]
        founder_names_hint = input_data.get("founder_names")

        queries = _build_queries(company, founder_names_hint)

        async def _safe_search(query: str):
            try:
                return await search_tool.search(query)
            except Exception as exc:
                app_logger.warning(f"[Founder Agent] search failed for '{query}': {exc}")
                return None

        search_results = await asyncio.gather(*[_safe_search(q) for q in queries])

        all_results = []
        for hits in search_results:
            if hits:
                all_results.extend(hits if isinstance(hits, list) else [hits])

        if not all_results:
            return make_no_data_result(
                self.name,
                f"No founder/team information found for '{company}'. Cannot assess "
                f"founder background without evidence.",
            )

        evidence_block = "\n\n".join(f"- {item}" for item in all_results)
        rubric_text = "\n".join(
            f"- {f['factor']} (max {f['max_points']} points): {f['guidance']}"
            for f in RUBRIC
        )

        prompt = f"""You are a due-diligence analyst evaluating the founding team of
'{company}'. Score against the exact rubric below, using ONLY documented career
facts from the evidence provided.

STRICT RULES:
- Never infer personality, character, or competence from indirect signals
  (name, education pedigree, appearance, etc.) — only explicitly documented
  professional history counts.
- Only cite a red flag if it is a specific, sourced, publicly reported fact
  (e.g. a reported prior venture shutdown). Never speculate or infer a
  concern that isn't directly stated in the evidence.
- If founder identities or backgrounds cannot be determined from evidence,
  award 0 for the relevant factors and say so — do not fill the gap with
  assumptions.

RUBRIC:
{rubric_text}

FOUNDER/TEAM EVIDENCE:
{evidence_block}

Return ONLY a single valid JSON object, no markdown fences, no preamble, in
exactly this shape:

{{
  "summary": "2-4 sentence plain-language summary of the founding team",
  "confidence": 0.0-1.0,
  "founders_identified": ["<name (role)>", ...],
  "score_breakdown": [
    {{
      "factor": "<exact factor name from rubric>",
      "points": <number, 0 to max_points for that factor>,
      "max_points": <number>,
      "reason": "1-2 sentences citing the specific documented fact, or why it's 0",
      "source": "<url if applicable, else null>"
    }}
  ],
  "sources": ["<all urls actually used>"]
}}

Every factor in the rubric must appear exactly once in score_breakdown.
confidence should be LOW (below 0.4) if founder evidence was thin or unclear."""

        try:
            raw_response = await llm_service.generate(prompt)
        except AllLLMProvidersFailedError as exc:
            return make_no_data_result(
                self.name,
                "All LLM providers unavailable — evaluation could not be completed for this factor."
            )

        try:
            parsed = _extract_json(raw_response)
            factors = [ScoreFactor(**f) for f in parsed["score_breakdown"]]
            total_score = sum(f.points for f in factors)

            founders = parsed.get("founders_identified", [])
            summary = parsed["summary"]
            if founders:
                summary += f" Founders identified: {', '.join(founders)}."

            return AgentScoreResult(
                agent=self.name,
                score=round(total_score, 1),
                score_breakdown=factors,
                summary=summary,
                confidence=float(parsed["confidence"]),
                sources=parsed.get("sources", []),
                status="ok",
            )
        except Exception as exc:
            app_logger.error(f"[Founder Agent] failed to parse LLM output: {exc}")
            raise
