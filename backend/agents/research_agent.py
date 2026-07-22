"""
Research Agent

Gathers general, wide-net information about a target company from the
web (news, funding, founders, product, traction) plus internal RAG
memory (past evaluations / uploaded documents), then scores the
company's overall "research fundamentals" against an explicit rubric.

This agent does NOT decide invest/pass — it only gathers and scores
what's publicly findable. The Committee Agent combines this with other
agents' scores using a fixed formula (see committee_agent.py).

IMPORTANT: every point awarded MUST be justified with a `reason`, and
tied to a `source` URL wherever the claim comes from search results
rather than a general inference. If no reliable evidence is found for
a factor, award 0 and say so — never invent a number to fill a gap.
"""

import asyncio
import json
import re
from typing import Any, List

from agents.base_agent import BaseAgent
from core.logging import app_logger
from rag.vector_store import vector_store
from schemas.scoring import AgentScoreResult, BusinessProfile, ScoreFactor, make_no_data_result
from services.llm_service import llm_service, AllLLMProvidersFailedError
from tools.search_tool import search_tool


# ---------------------------------------------------------------------------
# Rubric definition — kept explicit and visible so it can be reviewed/tuned
# without hunting through prompt text.
# ---------------------------------------------------------------------------

RUBRIC = [
    {"factor": "Company overview clarity", "max_points": 15,
     "guidance": "Is it clear what the company does, for whom, and how it makes money?"},
    {"factor": "Founder credibility", "max_points": 20,
     "guidance": "Documented relevant experience, prior companies, domain expertise. "
                 "0 if no founder info is found — do not guess."},
    {"factor": "Product maturity", "max_points": 20,
     "guidance": "Evidence of a shipped, working product vs. concept/pre-launch."},
    {"factor": "Traction evidence", "max_points": 25,
     "guidance": "Concrete traction signals: users, revenue, growth, notable customers/press. "
                 "0 if no traction evidence is found."},
    {"factor": "Funding history", "max_points": 20,
     "guidance": "Prior funding raised, investor quality, if publicly known. "
                 "0 if unknown/not found — absence of funding info is not itself negative."},
]

MAX_TOTAL_POINTS = sum(f["max_points"] for f in RUBRIC)  # should sum to 100


def _classify_business_profile(
    is_software: bool | None, is_physical_revenue: bool | None
) -> str:
    """The ONLY place the TECH/NON_TECH/HYBRID category is decided. Fixed,
    deterministic rule — never left to the LLM's own free-form judgment.
    HYBRID is the safe default for ambiguous, mixed, or unknown evidence.

        TECH      = core product IS software AND revenue is NOT physical goods
        NON_TECH  = core product is NOT software AND revenue IS physical goods
        HYBRID    = everything else
    """
    if is_software is True and is_physical_revenue is False:
        return "TECH"
    if is_software is False and is_physical_revenue is True:
        return "NON_TECH"
    return "HYBRID"


def _build_queries(company_name: str) -> List[str]:
    """Discrete, targeted queries — NOT one blob string. A single query like
    '{company} funding, founders, product, traction, latest news' returns
    weak, generic results because it asks a search engine for five
    different things at once."""
    return [
        f"{company_name} company overview what they do",
        f"{company_name} founders background",
        f"{company_name} funding round investors",
        f"{company_name} traction users revenue growth",
        f"{company_name} latest news",
    ]


def _extract_json(raw_text: str) -> dict:
    """LLMs frequently wrap JSON in markdown fences or add preamble text
    despite instructions. Extract the first {...} block defensively."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))

    brace = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if brace:
        return json.loads(brace.group(0))

    raise ValueError("No JSON object found in LLM response")


class ResearchAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="Research Agent",
            role="Startup research analyst",
        )

    async def run(self, input_data: Any) -> AgentScoreResult:
        company = input_data["company"]

        # --- Gather evidence (parallel, not sequential) -----------------------
        # 5 independent queries with no dependency on each other — running
        # them one-by-one with `await` in a loop would serialize their
        # latency (5 queries x ~1-2s each = 5-10s wasted). asyncio.gather
        # fires them all at once; total time ~= the slowest single query.
        queries = _build_queries(company)

        async def _safe_search(query: str):
            try:
                return await search_tool.search(query)
            except Exception as exc:
                app_logger.warning(f"[Research Agent] search failed for '{query}': {exc}")
                return None

        search_results = await asyncio.gather(*[_safe_search(q) for q in queries])

        all_results = []
        for hits in search_results:
            if hits:
                all_results.extend(hits if isinstance(hits, list) else [hits])

        try:
            memory_hits = vector_store.search(
                f"{company} founders traction business model market"
            )
        except Exception as exc:
            app_logger.warning(f"[Research Agent] vector store search failed: {exc}")
            memory_hits = None

        if not all_results and not memory_hits:
            return make_no_data_result(
                self.name,
                f"No web results or internal memory found for '{company}'. "
                f"Cannot assess research fundamentals without evidence.",
            )

        evidence_block = "\n\n".join(
            f"- {item}" for item in all_results
        ) or "(no web results found)"
        memory_block = str(memory_hits) if memory_hits else "(no internal memory found)"

        # --- Build rubric text for the prompt --------------------------------
        rubric_text = "\n".join(
            f"- {f['factor']} (max {f['max_points']} points): {f['guidance']}"
            for f in RUBRIC
        )

        prompt = f"""You are a VC research analyst. Score the company '{company}' against
the exact rubric below, using ONLY the evidence provided. Do not use outside
knowledge not present in the evidence — if the evidence doesn't support a
factor, award 0 points for it and say so in the reason.

RUBRIC:
{rubric_text}

WEB EVIDENCE:
{evidence_block}

INTERNAL MEMORY:
{memory_block}

Return ONLY a single valid JSON object, no markdown fences, no preamble, in
exactly this shape:

{{
  "summary": "2-4 sentence plain-language summary of what you found",
  "confidence": 0.0-1.0,
  "score_breakdown": [
    {{
      "factor": "<exact factor name from rubric>",
      "points": <number, 0 to max_points for that factor>,
      "max_points": <number>,
      "reason": "1-2 sentences citing what evidence justifies these points, or why it's 0",
      "source": "<url if applicable, else null>"
    }}
  ],
  "sources": ["<all urls actually used>"],
  "business_profile": {{
    "is_core_product_software": true/false/null,
    "is_revenue_physical_goods": true/false/null,
    "reasoning": "1-2 sentences explaining these two answers based on the evidence"
  }}
}}

For business_profile: is_core_product_software asks whether the company's
core product/offering IS software itself (a SaaS platform, API, developer
tool, AI model) — NOT whether they merely use software internally (e.g. a
retail company running an inventory app is still false here).
is_revenue_physical_goods asks whether revenue comes primarily from physical
goods/retail/FMCG rather than software subscriptions, API usage, or digital
transaction fees. Use null for either if the evidence genuinely doesn't say —
do not guess.

Every factor in the rubric must appear exactly once in score_breakdown.
confidence should be LOW (below 0.4) if evidence was thin, contradictory,
or mostly absent — do not report high confidence just because you produced
an answer."""

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

            profile_facts = parsed.get("business_profile", {}) or {}
            is_software = profile_facts.get("is_core_product_software")
            is_physical = profile_facts.get("is_revenue_physical_goods")
            category = _classify_business_profile(is_software, is_physical)

            business_profile = BusinessProfile(
                category=category,
                is_core_product_software=is_software,
                is_revenue_physical_goods=is_physical,
                reasoning=profile_facts.get("reasoning", ""),
            )

            return AgentScoreResult(
                agent=self.name,
                score=round(total_score, 1),
                score_breakdown=factors,
                summary=parsed["summary"],
                confidence=float(parsed["confidence"]),
                sources=parsed.get("sources", []),
                status="ok",
                business_profile=business_profile,
            )
        except Exception as exc:
            # The LLM didn't follow the contract. This is a failure of this
            # run, not a "the company scored 0" situation — surface it as
            # failed so the Committee Agent and frontend can tell the
            # difference and possibly retry, rather than silently treating
            # a parse error as a real score of 0.
            app_logger.error(f"[Research Agent] failed to parse LLM output: {exc}")
            raise
