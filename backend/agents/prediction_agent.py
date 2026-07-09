"""
Prediction Agent

Runs a trained ML model (non-LLM) to estimate startup success probability,
using REAL features extracted from other agents' findings — not the
hardcoded defaults the previous version silently fell back to.

CRITICAL FIX FROM PREVIOUS VERSION: the old agent called
`input_data.get("funding", 100)` etc. for six features, but nothing in
the system ever populated `input_data` with those keys — every company
silently got the exact same defaults (industry="AI", funding=100,
employees=100, age=3, revenue=10, growth=20) fed to the model. Since a
deterministic model given identical input produces identical output,
this agent was effectively returning the SAME prediction for every
company evaluated, regardless of who they were.

Fix: this agent expects `other_findings` — the AgentScoreResult objects
already produced by Research/Market/Finance/Founder agents (reusing
evidence they already gathered, avoiding duplicate search calls) — and
runs a small LLM extraction pass to pull real numeric values out of
their summaries/sources. Only fields that cannot be found anywhere are
defaulted, and — critically — `confidence` is set based on how many of
the 6 features were REAL vs. defaulted, so a low-data prediction is
visibly flagged as unreliable instead of silently looking authoritative.

ORCHESTRATION NOTE: because this agent depends on other agents' output,
it should run AFTER Research/Market/Finance/Founder complete, not in
the same parallel batch as them. This is a real sequencing constraint
for whoever builds the orchestrator/workflow graph.
"""

import asyncio
import json
import re
from typing import Any, Optional

from agents.base_agent import BaseAgent
from core.logging import app_logger
from ml.predictor import startup_predictor
from schemas.scoring import AgentScoreResult, ScoreFactor, make_no_data_result
from services.llm_service import llm_service
from tools.search_tool import search_tool


# Each feature's weight is used only to build a transparency breakdown
# (which features were real vs. defaulted) — it does NOT determine the
# agent's `score`, which comes directly from the model's predicted
# probability. See docstring below on why this agent's breakdown works
# differently from other agents.
FEATURE_WEIGHTS = {
    "industry": 10,
    "funding": 20,
    "employees": 15,
    "age": 15,
    "revenue": 20,
    "growth": 20,
}  # sums to 100

DEFAULTS = {
    "industry": "AI",
    "funding": 100,
    "employees": 100,
    "age": 3,
    "revenue": 10,
    "growth": 20,
}


def _extract_json(raw_text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    brace = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if brace:
        return json.loads(brace.group(0))
    raise ValueError("No JSON object found in LLM response")


def _collect_evidence_text(other_findings: Optional[dict]) -> str:
    """Pull summaries out of already-completed agent results instead of
    searching again. This is the reuse step that avoids duplicate API
    calls for the same information."""
    if not other_findings:
        return ""
    sections = []
    for agent_name, result in other_findings.items():
        summary = getattr(result, "summary", None) or (
            result.get("summary") if isinstance(result, dict) else None
        )
        if summary:
            sections.append(f"--- {agent_name} findings ---\n{summary}")
    return "\n\n".join(sections)


class PredictionAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="Prediction Agent",
            role="Startup success ML predictor",
        )

    async def run(self, input_data: Any) -> AgentScoreResult:
        company = input_data["company"]
        other_findings = input_data.get("other_findings")

        evidence_text = _collect_evidence_text(other_findings)

        # Fallback: if no other agents' findings were passed in (e.g. this
        # agent is being run standalone/tested in isolation), do a minimal
        # search of our own rather than jumping straight to defaults.
        if not evidence_text:
            try:
                hits = await search_tool.search(
                    f"{company} funding revenue employees growth industry"
                )
                if hits:
                    evidence_text = "\n".join(str(h) for h in hits)
            except Exception as exc:
                app_logger.warning(f"[Prediction Agent] fallback search failed: {exc}")

        if not evidence_text:
            return make_no_data_result(
                self.name,
                f"No evidence available (no other agent findings and no search "
                f"results) to extract features for '{company}'. Refusing to "
                f"predict on fabricated defaults.",
            )

        # --- Extract real numeric features via LLM, from real evidence ------
        extraction_prompt = f"""Extract these 6 fields about the company '{company}'
from the evidence below. Use ONLY values explicitly stated in the evidence.
If a field is not mentioned, return null for it — do NOT guess or estimate.

Fields:
- industry: string, e.g. "fintech", "healthtech"
- funding: total funding raised in USD thousands (number), e.g. 500 for $500K
- employees: employee count (number)
- age: company age in years (number)
- revenue: annual revenue in USD thousands (number)
- growth: year-over-year growth rate as a percentage (number)

EVIDENCE:
{evidence_text}

Return ONLY a JSON object, no markdown fences, no preamble:
{{"industry": <string or null>, "funding": <number or null>, "employees": <number or null>,
  "age": <number or null>, "revenue": <number or null>, "growth": <number or null>}}"""

        try:
            raw_response = await llm_service.generate(extraction_prompt)
            extracted = _extract_json(raw_response)
        except Exception as exc:
            app_logger.error(f"[Prediction Agent] feature extraction failed: {exc}")
            raise

        # --- Merge extracted values with defaults, tracking what's real -----
        features = {}
        field_is_real = {}
        for field, default_value in DEFAULTS.items():
            value = extracted.get(field)
            if value is not None:
                features[field] = value
                field_is_real[field] = True
            else:
                features[field] = default_value
                field_is_real[field] = False

        real_count = sum(field_is_real.values())
        confidence = round(real_count / len(DEFAULTS), 2)

        if real_count == 0:
            # Same situation as the old bug (all defaults) — but now we
            # KNOW it and can be honest about it instead of silently
            # returning a fake-confident constant prediction.
            app_logger.warning(
                f"[Prediction Agent] no real features extracted for '{company}' "
                f"— prediction will use only default values, confidence=0."
            )

        # --- Run the ML model (sync call — offload to a thread so it -------
        # --- doesn't block the event loop while other agents run async) ----
        try:
            raw_prediction = await asyncio.to_thread(
                startup_predictor.predict,
                industry=features["industry"],
                funding=features["funding"],
                employees=features["employees"],
                age=features["age"],
                revenue=features["revenue"],
                growth=features["growth"],
            )
        except Exception as exc:
            app_logger.error(f"[Prediction Agent] model inference failed: {exc}")
            raise

        # Defensively handle whatever shape the model returns.
        if isinstance(raw_prediction, dict):
            probability = raw_prediction.get("success_probability") or raw_prediction.get("probability")
        else:
            probability = getattr(raw_prediction, "success_probability", None)

        if probability is None:
            raise ValueError(
                f"Could not extract a success probability from model output: {raw_prediction!r}"
            )

        score = round(float(probability), 1)

        # --- Build transparency breakdown (does NOT sum to `score` — -------
        # --- see module docstring for why this agent's breakdown is a ------
        # --- feature-input audit trail, not a rubric that sums to score) ---
        factors = [
            ScoreFactor(
                factor=f"Input: {field}",
                points=FEATURE_WEIGHTS[field] if field_is_real[field] else 0,
                max_points=FEATURE_WEIGHTS[field],
                reason=(
                    f"Used real extracted value ({features[field]})"
                    if field_is_real[field]
                    else f"No value found in evidence — used default ({features[field]}), "
                         f"this reduces overall prediction confidence"
                ),
            )
            for field in DEFAULTS
        ]

        summary = (
            f"ML model estimates a {score:.0f}% success probability for '{company}', "
            f"based on {real_count}/6 features extracted from real evidence "
            f"(remaining {6 - real_count} used defaults)."
        )

        return AgentScoreResult(
            agent=self.name,
            score=score,
            score_breakdown=factors,
            summary=summary,
            confidence=confidence,
            sources=[],
            status="ok",
        )
