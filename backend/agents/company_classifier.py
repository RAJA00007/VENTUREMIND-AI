"""
Company Type Classifier

Determines whether a company is TECH, NON_TECH, or HYBRID so the
Committee Agent can select the right weight profile — code quality
should matter enormously for a pure software company (OpenAI, Cursor)
and barely at all for a physical-goods company (Nike, Mamaearth).

DESIGN: same "LLM extracts facts, code decides" split used elsewhere
(github_agent's scoring, the WEIGHTS formula). The LLM only answers two
factual questions from evidence; the classification RULE itself is a
fixed decision tree in code, always applied the same way — never left
to the LLM's own judgment of "which category feels right."

Decision rule (as specified):
    TECH      = core product IS software AND revenue IS software/API/SaaS
    NON_TECH  = core product is NOT software AND revenue IS physical
                goods/retail/FMCG
    HYBRID    = everything else (mixed signals, tech-enabled physical
                services, marketplaces, fintech, unclear evidence)

HYBRID is the deliberate safe default for ambiguous cases — better to
use a balanced weight profile than to wrongly apply an extreme one.
"""

import json
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

from core.logging import app_logger
from services.llm_service import llm_service

CompanyCategory = Literal["TECH", "NON_TECH", "HYBRID"]


class CompanyClassification(BaseModel):
    category: CompanyCategory
    is_core_product_software: Optional[bool] = Field(
        description="Whether the company's core product/offering IS software "
        "(not just 'uses software internally'). None if evidence is unclear."
    )
    is_revenue_physical_goods: Optional[bool] = Field(
        description="Whether revenue primarily comes from physical goods/"
        "retail/FMCG. None if evidence is unclear."
    )
    confidence: float
    reasoning: str


def _extract_json(raw_text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    brace = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if brace:
        return json.loads(brace.group(0))
    raise ValueError("No JSON object found in LLM response")


def _apply_decision_rule(
    is_software: Optional[bool], is_physical_revenue: Optional[bool]
) -> CompanyCategory:
    """This is the ONLY place the category is decided. Fixed, deterministic,
    always applied the same way — matches the exact rule specified."""
    if is_software is True and is_physical_revenue is False:
        return "TECH"
    if is_software is False and is_physical_revenue is True:
        return "NON_TECH"
    return "HYBRID"  # ambiguous, mixed, or unknown -> safe balanced default


async def classify_company(company: str, evidence_text: str) -> CompanyClassification:
    """
    `evidence_text` should be evidence already gathered by other agents
    (e.g. Research Agent's summary) — reused, not re-searched, same
    pattern as prediction_agent.
    """
    if not evidence_text:
        app_logger.warning(
            f"[Classifier] no evidence provided for '{company}' — defaulting to HYBRID"
        )
        return CompanyClassification(
            category="HYBRID",
            is_core_product_software=None,
            is_revenue_physical_goods=None,
            confidence=0.0,
            reasoning="No evidence available to classify — defaulted to HYBRID as the safe middle ground.",
        )

    prompt = f"""Based ONLY on the evidence below about '{company}', answer two factual
questions. Do not guess — if evidence is genuinely unclear, say so.

1. is_core_product_software: Is the company's core product/offering itself
   software (e.g. a SaaS platform, API, developer tool, AI model)? This is
   NOT about whether they use software internally — a retail company using
   an inventory app is still NOT a software company. true / false / null if unclear.

2. is_revenue_physical_goods: Does the company's revenue come primarily
   from selling physical goods, retail products, or FMCG (as opposed to
   software subscriptions, API usage, transaction fees on a digital
   platform, etc.)? true / false / null if unclear.

EVIDENCE:
{evidence_text}

Return ONLY a JSON object, no markdown fences, no preamble:
{{
  "is_core_product_software": true/false/null,
  "is_revenue_physical_goods": true/false/null,
  "confidence": 0.0-1.0,
  "reasoning": "1-2 sentences explaining your answers based on the evidence"
}}"""

    try:
        raw_response = await llm_service.generate(prompt)
        parsed = _extract_json(raw_response)
    except Exception as exc:
        app_logger.error(f"[Classifier] extraction failed for '{company}': {exc}")
        return CompanyClassification(
            category="HYBRID",
            is_core_product_software=None,
            is_revenue_physical_goods=None,
            confidence=0.0,
            reasoning=f"Classification extraction failed ({exc}) — defaulted to HYBRID.",
        )

    is_software = parsed.get("is_core_product_software")
    is_physical = parsed.get("is_revenue_physical_goods")
    category = _apply_decision_rule(is_software, is_physical)

    return CompanyClassification(
        category=category,
        is_core_product_software=is_software,
        is_revenue_physical_goods=is_physical,
        confidence=float(parsed.get("confidence", 0.5)),
        reasoning=parsed.get("reasoning", ""),
    )
