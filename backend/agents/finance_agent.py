"""
Finance Agent

Evaluates unit economics, revenue/traction, funding history & trend,
investor quality, burn rate, capital efficiency, and financial red
flags — scored on a 0-100 rubric.

CRITICAL GUARDRAIL: financial figures are the single easiest thing for
an LLM to hallucinate convincingly (a specific-sounding number like
"$1.2M ARR" or "18-month runway" reads as authoritative whether or not
it's real). This agent enforces:
1. Every specific figure cited MUST have a source URL. No source, no
   figure — award 0 for that factor and say "not found in evidence"
   instead of estimating or inferring a plausible-sounding number.
2. Company-reported figures (from the company's own site/press release)
   must be explicitly labeled as self-reported, since they are less
   reliable than third-party/independent reporting (e.g. a funding
   database, journalist coverage, or regulatory filing).
3. Investor quality is scored ONLY on publicly documented credibility
   (recognized VC/accelerator/angel names) — this agent must NEVER
   estimate an investor's ROI, fund performance, or other private
   metrics, since those are not public information and inventing them
   would fabricate a specific-sounding but entirely made-up figure.
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
    {"factor": "Unit economics evidence", "max_points": 15,
     "guidance": "Documented CAC, LTV, gross margin, or other unit economics "
                 "figures with a source. Award 0 if no sourced figures are found "
                 "— do not estimate plausible-sounding numbers."},
    {"factor": "Revenue/financial traction", "max_points": 15,
     "guidance": "Documented revenue, ARR/MRR, or growth figures with a source. "
                 "Label self-reported (company press release/site) figures as such "
                 "and weight them lower than independently reported figures. "
                 "Award 0 if no sourced figures are found."},
    {"factor": "Funding history & trend", "max_points": 20,
     "guidance": "Documented total capital raised, individual funding rounds "
                 "(seed/Series A/B/...), the latest funding stage, and how funding "
                 "has trended over time (e.g. consistent step-ups vs. a stalled/down "
                 "round). Award 0 if no sourced funding history is found — do not "
                 "estimate or infer amounts not stated in evidence."},
    {"factor": "Investor quality", "max_points": 15,
     "guidance": "Identify notable institutional investors, VC firms, accelerators, "
                 "or angel investors backing the company, from evidence only. Score "
                 "credibility based on whether these are recognized, reputable "
                 "names (e.g. well-known VC firms, YC/Techstars-caliber "
                 "accelerators) — NOT by estimating their ROI, fund performance, or "
                 "any private financial metrics, which are not publicly knowable "
                 "and must never be guessed. Award 0 if no investor information is "
                 "found."},
    {"factor": "Burn rate & runway", "max_points": 15,
     "guidance": "Documented burn rate or runway estimate with a source. Award 0 "
                 "if not found — absence of this info is not itself negative for "
                 "early-stage companies where it's rarely public."},
    {"factor": "Capital efficiency", "max_points": 10,
     "guidance": "Relationship between total funding raised and demonstrated "
                 "traction/output, if both are documented. Award 0 if insufficient "
                 "data to assess either side of this ratio."},
    {"factor": "Financial red flags", "max_points": 10,
     "guidance": "Deduct ONLY for documented financial distress signals (down "
                 "round, restructuring, missed payroll, insolvency reports). "
                 "Award full points if no negative financial evidence is found."},
]

MAX_TOTAL_POINTS = sum(f["max_points"] for f in RUBRIC)  # = 100


def _build_queries(company_name: str) -> List[str]:
    return [
        f"{company_name} revenue ARR funding raised",
        f"{company_name} unit economics margins",
        f"{company_name} funding rounds history total raised",
        f"{company_name} investors venture capital backers",
        f"{company_name} burn rate runway",
        f"{company_name} valuation down round financial trouble",
    ]


def _extract_json(raw_text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    brace = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if brace:
        return json.loads(brace.group(0))
    raise ValueError("No JSON object found in LLM response")


class FinanceAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="Finance Agent",
            role="Financial due-diligence analyst",
        )

    async def run(self, input_data: Any) -> AgentScoreResult:
        company = input_data["company"]

        queries = _build_queries(company)

        async def _safe_search(query: str):
            try:
                return await search_tool.search(query)
            except Exception as exc:
                app_logger.warning(f"[Finance Agent] search failed for '{query}': {exc}")
                return None

        search_results = await asyncio.gather(*[_safe_search(q) for q in queries])

        all_results = []
        for hits in search_results:
            if hits:
                all_results.extend(hits if isinstance(hits, list) else [hits])

        if not all_results:
            return make_no_data_result(
                self.name,
                f"No financial data found for '{company}'. This is common for "
                f"early-stage/private companies — cannot assess financials "
                f"without evidence.",
            )

        evidence_block = "\n\n".join(f"- {item}" for item in all_results)
        rubric_text = "\n".join(
            f"- {f['factor']} (max {f['max_points']} points): {f['guidance']}"
            for f in RUBRIC
        )

        prompt = f"""You are a financial due-diligence analyst evaluating '{company}'.
Score against the exact rubric below, using ONLY sourced figures from the
evidence provided.

CRITICAL RULES:
- Never state a specific financial figure (revenue, valuation, burn rate,
  funding amount) unless it appears in the evidence with a source. If no
  sourced figure exists for a factor, award 0 and say "not found in
  evidence" — do not estimate or infer a plausible number.
- Explicitly label any figure that comes from the company's own site/press
  release as "self-reported" and treat it as less reliable than figures
  from independent sources (news outlets, funding databases, filings).
- For investor quality: only assess whether backers are recognized,
  reputable names based on public evidence. NEVER estimate or state a
  specific investor's ROI, fund returns, or other private performance
  metrics — these are not public information and inventing them is a
  serious violation of this agent's rules, not a minor stylistic issue.
- Absence of financial data is normal for private/early-stage companies —
  it is not itself a red flag. Only deduct points for DOCUMENTED negative
  signals, never for missing information.

RUBRIC:
{rubric_text}

FINANCIAL EVIDENCE:
{evidence_block}

Return ONLY a single valid JSON object, no markdown fences, no preamble, in
exactly this shape:

{{
  "summary": "2-4 sentence plain-language summary of the financial picture",
  "confidence": 0.0-1.0,
  "score_breakdown": [
    {{
      "factor": "<exact factor name from rubric>",
      "points": <number, 0 to max_points for that factor>,
      "max_points": <number>,
      "reason": "1-2 sentences citing the specific sourced figure (mark "
                "self-reported ones), or why it's 0",
      "source": "<url if applicable, else null>"
    }}
  ],
  "sources": ["<all urls actually used>"]
}}

Every factor in the rubric must appear exactly once in score_breakdown.
confidence should be LOW (below 0.4) if financial evidence was thin,
entirely self-reported/unverified, or if funding history and investor
information could not be found at all."""

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
            app_logger.error(f"[Finance Agent] failed to parse LLM output: {exc}")
            raise
