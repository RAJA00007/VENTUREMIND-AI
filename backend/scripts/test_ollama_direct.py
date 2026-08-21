"""
Direct Ollama Structured Output Test Script for VentureMind AI
"""
import sys
import os
import time
import json
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.llm_service import llm_service, _parse_and_clean_json
from schemas.scoring import ScoreFactor, AgentScoreResult
from core.config import settings

async def main():
    print("==================================================")
    print("  DIRECT OLLAMA STRUCTURED OUTPUT DIAGNOSTIC TEST")
    print("==================================================")
    
    settings.EVALUATION_MODE = True
    print(f"Ollama Base URL : {settings.OLLAMA_BASE_URL}")
    print(f"Ollama Model    : {settings.OLLAMA_MODEL}")
    
    # 1. Test raw list of models
    try:
        models = llm_service.ollama.models.list()
        model_ids = [m.id for m in models.data]
        print(f"Installed Models: {model_ids}")
    except Exception as e:
        print(f"Failed to list Ollama models: {e}")
        return

    # Prompt testing Market Agent structured response format
    prompt = """You are a VC market analyst. Score the market opportunity for 'CloudScale AI' against the rubric using the evidence provided.

RUBRIC:
- Market size (TAM/SAM) (max 30 points): Credible market size figures found in evidence.
- Growth rate (max 25 points): Industry CAGR or growth rate.
- Customer demand signals (max 20 points): Evidence of real demand.
- Market timing (tailwinds vs. headwinds) (max 25 points): Macro trends helping or hurting.

MARKET EVIDENCE:
- CloudScale AI provides automated cloud infrastructure optimization for enterprises. Sourced reports estimate TAM at $45B with a 22% CAGR. Customer adoption shows 150 enterprise clients signed in 2025.

Return ONLY a single valid JSON object, no markdown fences, no preamble, in exactly this shape:
{
  "summary": "Plain language summary",
  "confidence": 0.85,
  "score_breakdown": [
    {
      "factor": "Market size (TAM/SAM)",
      "points": 25,
      "max_points": 30,
      "reason": "TAM estimated at $45B",
      "source": "https://gartner.com"
    },
    {
      "factor": "Growth rate",
      "points": 20,
      "max_points": 25,
      "reason": "CAGR is 22%",
      "source": "https://idc.com"
    },
    {
      "factor": "Customer demand signals",
      "points": 16,
      "max_points": 20,
      "reason": "150 enterprise clients",
      "source": "https://techcrunch.com"
    },
    {
      "factor": "Market timing (tailwinds vs. headwinds)",
      "points": 22,
      "max_points": 25,
      "reason": "Strong multi-cloud tailwinds",
      "source": "https://forbes.com"
    }
  ],
  "sources": ["https://gartner.com", "https://idc.com", "https://techcrunch.com", "https://forbes.com"]
}"""

    start_t = time.monotonic()
    print("\nSending prompt directly to OpenAI client pointing to Ollama (timeout=35s)...")
    
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                llm_service.ollama.chat.completions.create,
                model="llama3:latest",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            ),
            timeout=35
        )
        duration = time.monotonic() - start_t
        raw_resp = response.choices[0].message.content
        print(f"\n[Ollama Completed in {duration:.2f}s]")
        print(f"Raw Response Length: {len(raw_resp)} chars")
        print("--- RAW RESPONSE CONTENT ---")
        print(raw_resp)
        print("----------------------------")
        
        # Test JSON parsing
        try:
            parsed = _parse_and_clean_json(raw_resp)
            print("\n[SUCCESS] JSON Parsing: PASSED!")
            
            # Test Pydantic Schema Validation
            try:
                factors = [ScoreFactor(**f) for f in parsed["score_breakdown"]]
                total_score = sum(f.points for f in factors)
                result = AgentScoreResult(
                    agent="Market Agent",
                    score=round(total_score, 1),
                    score_breakdown=factors,
                    summary=parsed["summary"],
                    confidence=float(parsed["confidence"]),
                    sources=parsed.get("sources", []),
                    status="ok"
                )
                print(f"[SUCCESS] Pydantic Schema Validation: PASSED! Score = {result.score}, Status = {result.status}")
            except Exception as val_err:
                print(f"[FAILED] Pydantic Schema Validation FAILED: {val_err}")
                print(f"Parsed Dict Keys: {list(parsed.keys())}")
        except Exception as parse_err:
            print(f"\n[FAILED] JSON Parsing FAILED: {parse_err}")
            
    except Exception as exc:
        duration = time.monotonic() - start_t
        print(f"\n[FAILED] Direct Ollama Request Failed after {duration:.2f}s: {type(exc).__name__} - {exc}")

if __name__ == "__main__":
    asyncio.run(main())
