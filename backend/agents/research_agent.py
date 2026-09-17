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
from core.config import settings
from core.logging import app_logger
from rag.vector_store import vector_store
from schemas.evidence import EvidenceRecord, SourceCredibility
from schemas.scoring import AgentScoreResult, BusinessProfile, ScoreFactor, make_no_data_result
from services.evidence_service import (
    build_evidence_lookup,
    calculate_evidence_confidence,
    resolve_evidence_ids,
    validate_fact_type,
)
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
    """Discrete, targeted queries — NOT one blob string."""
    return [
        f"{company_name} company overview what they do",
        f"{company_name} founders background",
        f"{company_name} funding round investors",
        f"{company_name} traction users revenue growth",
        f"{company_name} latest news",
    ]


def _extract_json(raw_text: str) -> dict:
    """Extract first {...} block defensively from LLM text output."""
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

        # --- Gather evidence (parallel web search with evidence capture) ------
        queries = _build_queries(company)

        async def _safe_search(query: str):
            try:
                return await search_tool.search_with_evidence(query)
            except Exception as exc:
                app_logger.warning(f"[Research Agent] search failed for '{query}': {exc}")
                return None

        search_results = await asyncio.gather(*[_safe_search(q) for q in queries])

        all_results = []
        all_evidence_records: List[EvidenceRecord] = []

        for res in search_results:
            if res:
                if hasattr(res, "results") and hasattr(res, "evidence_records"):
                    all_results.extend(res.results)
                    all_evidence_records.extend(res.evidence_records)
                elif isinstance(res, list):
                    all_results.extend(res)

        # --- Vector Store RAG Retrieval ---------------------------------------
        memory_hits = None
        try:
            company_id = input_data.get("company_id") or company
            memory_hits = vector_store.search(
                f"{company} founders traction business model market",
                company_id=company_id
            )
            # Convert RAG memory hits into EvidenceRecords if available
            if memory_hits and isinstance(memory_hits, dict) and memory_hits.get("documents"):
                docs = memory_hits["documents"][0] if memory_hits["documents"] else []
                metas = memory_hits.get("metadatas", [[]])[0] if memory_hits.get("metadatas") else []
                for i, doc_text in enumerate(docs):
                    if not doc_text:
                        continue
                    meta = metas[i] if i < len(metas) else {}
                    rag_id = meta.get("chunk_id") or f"ev_rag_{meta.get('document_id', i)}_p{meta.get('page_number', 1)}"
                    all_evidence_records.append(
                        EvidenceRecord(
                            evidence_id=rag_id,
                            source_type=meta.get("source_type", "rag_document"),
                            source_name=meta.get("document_name", "Uploaded Document"),
                            document_id=meta.get("document_id"),
                            document_name=meta.get("document_name"),
                            page_number=meta.get("page_number"),
                            chunk_id=meta.get("chunk_id"),
                            raw_snippet=doc_text,
                            credibility=SourceCredibility.MEDIUM,
                            independence_group=meta.get("document_id") or "rag_docs"
                        )
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

        # --- Build Evidence Lookup Map ----------------------------------------
        evidence_lookup = build_evidence_lookup(all_evidence_records)

        # --- Build Compact Evidence Context for LLM ---------------------------
        evidence_blocks = []
        for rec in all_evidence_records:
            evidence_blocks.append(
                f"[EVIDENCE_ID: {rec.evidence_id}]\n"
                f"Source: {rec.source_name}\n"
                f"Domain: {rec.domain or 'N/A'}\n"
                f"Credibility: {rec.credibility.value}\n"
                f"Snippet:\n{rec.raw_snippet or '(no snippet available)'}"
            )
        available_evidence_text = "\n\n---\n\n".join(evidence_blocks) if evidence_blocks else "(no available evidence found)"
        memory_block = str(memory_hits) if memory_hits else "(no internal memory found)"

        # --- Build Rubric Text ------------------------------------------------
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

AVAILABLE EVIDENCE:
{available_evidence_text}

INTERNAL MEMORY:
{memory_block}

EVIDENCE RULES:
1. Only reference evidence IDs provided in AVAILABLE EVIDENCE.
2. Never invent:
   - evidence IDs
   - URLs
   - sources
   - publication dates
   - citations
3. Every factual claim should reference available evidence when possible.
4. If no evidence supports a statement, classify it as LLM_INFERENCE or UNKNOWN.
5. COMPANY_CLAIM must be used for claims originating from the company's own materials (pitch decks, company website, founder statements).
6. THIRD_PARTY_CLAIM must be used when information comes from an external source but is not independently verified.
7. VERIFIED_FACT should only be used when evidence comes from a strong authoritative source (government filing, official registry, platform API).
8. CORROBORATED_FACT should be used when multiple independent external sources confirm the statement.
9. Do not treat multiple sources from the same domain or PR distribution as independent corroboration.

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
      "source": "<url if applicable, else null>",
      "fact_type": "VERIFIED_FACT | CORROBORATED_FACT | COMPANY_CLAIM | THIRD_PARTY_CLAIM | USER_PROVIDED | LLM_INFERENCE | MODEL_PREDICTION | UNKNOWN",
      "primary_evidence_id": "<EVIDENCE_ID string from AVAILABLE EVIDENCE, else null>",
      "corroborating_evidence_ids": ["<EVIDENCE_ID string>", ...]
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
tool, AI model) — NOT whether they merely use software internally.
is_revenue_physical_goods asks whether revenue comes primarily from physical
goods/retail/FMCG. Use null for either if the evidence genuinely doesn't say.

Every factor in the rubric must appear exactly once in score_breakdown.
confidence should be LOW (below 0.4) if evidence was thin, contradictory,
or mostly absent."""

        try:
            parsed = await llm_service.generate_structured(prompt, bypass_cache=getattr(settings, "EVALUATION_MODE", False))
            
            factors: List[ScoreFactor] = []
            for f in parsed.get("score_breakdown", []):
                raw_fact_type = f.get("fact_type")
                fact_type = validate_fact_type(raw_fact_type)

                prim_id = f.get("primary_evidence_id")
                corr_ids = f.get("corroborating_evidence_ids")

                prim_rec, corr_recs = resolve_evidence_ids(prim_id, corr_ids, evidence_lookup)
                ev_conf = calculate_evidence_confidence(prim_rec, corr_recs)

                source_url = f.get("source") or (prim_rec.url if prim_rec else None)

                factor_obj = ScoreFactor(
                    factor=f["factor"],
                    points=float(f["points"]),
                    max_points=float(f["max_points"]),
                    reason=f["reason"],
                    source=source_url,
                    fact_type=fact_type,
                    primary_evidence=prim_rec,
                    corroborating_evidence=corr_recs,
                    evidence_confidence=ev_conf
                )
                factors.append(factor_obj)

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
        except AllLLMProvidersFailedError:
            return make_no_data_result(
                self.name,
                "All LLM providers unavailable — evaluation could not be completed for this factor."
            )
        except Exception as exc:
            app_logger.error(f"[Research Agent] failed to parse LLM output: {exc}")
            raise
