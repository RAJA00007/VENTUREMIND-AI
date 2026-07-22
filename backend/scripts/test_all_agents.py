"""
VentureMind AI — Full Agent & Provider Diagnostic Test
Tests: All 7 LLM providers, all agents (Research, Market, Competitor, Risk, Founder, Finance, Prediction, Committee), Ollama status
"""
import asyncio
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from core.config import settings

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"
DIVIDER = "=" * 60


def section(title):
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)


async def test_ollama_status():
    """Check Ollama service availability and downloaded models."""
    section("OLLAMA STATUS")
    from openai import OpenAI

    url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434/v1")
    configured_model = getattr(settings, "OLLAMA_MODEL", "llama3.2")
    print(f"  Ollama URL     : {url}")
    print(f"  Configured Model: {configured_model}")

    try:
        client = OpenAI(base_url=url, api_key="ollama")
        models_resp = client.models.list()
        model_ids = []
        if models_resp and hasattr(models_resp, "data") and models_resp.data:
            model_ids = [m.id for m in models_resp.data]

        if model_ids:
            print(f"  {PASS} Ollama is RUNNING. Downloaded models: {model_ids}")
        else:
            print(f"  {WARN} Ollama is RUNNING but NO models downloaded.")
            print(f"        Run: ollama pull llama3  (or any model)")
        
        # Try a generation if any model exists
        if model_ids:
            target = configured_model if configured_model in model_ids else model_ids[0]
            resp = await asyncio.to_thread(
                client.chat.completions.create,
                model=target,
                messages=[{"role": "user", "content": "Say OK"}],
            )
            content = resp.choices[0].message.content.strip()
            print(f"  {PASS} Ollama generation works! Model '{target}' replied: '{content[:80]}'")
        else:
            print(f"  {WARN} Skipping generation test — no models available.")
        return True
    except Exception as e:
        err = str(e)
        if "connection" in err.lower() or "refused" in err.lower():
            print(f"  {FAIL} Ollama service NOT RUNNING. Start it with: ollama serve")
        else:
            print(f"  {FAIL} Ollama error: {err[:120]}")
        return False


async def test_llm_providers():
    """Test all 7 LLM provider connections."""
    section("LLM PROVIDER CHAIN TEST")

    from openai import OpenAI
    try:
        from google import genai
    except ImportError:
        import google.generativeai as genai
    from groq import Groq

    results = {}

    # 1. Gemini
    print("\n  1. Gemini...")
    key = (settings.GEMINI_API_KEY or "").strip()
    if not key or key == "dummy":
        print(f"     {FAIL} No API key configured")
        results["Gemini"] = False
    else:
        try:
            if hasattr(genai, "Client"):
                client = genai.Client(api_key=key)
                resp = await asyncio.to_thread(client.models.generate_content, model="gemini-2.0-flash", contents="Say OK")
            else:
                genai.configure(api_key=key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                resp = await asyncio.to_thread(model.generate_content, "Say OK")
            print(f"     {PASS} Gemini: '{resp.text.strip()[:60]}'")
            results["Gemini"] = True
        except Exception as e:
            print(f"     {FAIL} Gemini: {str(e)[:100]}")
            results["Gemini"] = False

    # 2. Groq
    print("  2. Groq...")
    key = (settings.GROQ_API_KEY or "").strip()
    if not key:
        print(f"     {FAIL} No API key configured")
        results["Groq"] = False
    else:
        try:
            client = Groq(api_key=key)
            resp = await asyncio.to_thread(
                client.chat.completions.create,
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": "Say OK"}],
            )
            print(f"     {PASS} Groq: '{resp.choices[0].message.content.strip()[:60]}'")
            results["Groq"] = True
        except Exception as e:
            print(f"     {FAIL} Groq: {str(e)[:100]}")
            results["Groq"] = False

    # 3. OpenRouter
    print("  3. OpenRouter...")
    key = (settings.OPENROUTER_API_KEY or "").strip()
    if not key:
        print(f"     {FAIL} No API key configured")
        results["OpenRouter"] = False
    else:
        try:
            client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
            resp = await asyncio.to_thread(
                client.chat.completions.create,
                model="openrouter/free",
                messages=[{"role": "user", "content": "Say OK"}],
            )
            print(f"     {PASS} OpenRouter: '{resp.choices[0].message.content.strip()[:60]}'")
            results["OpenRouter"] = True
        except Exception as e:
            err = str(e)
            if "429" in err or "rate" in err.lower():
                print(f"     {WARN} OpenRouter: Rate limited (quota exceeded)")
            else:
                print(f"     {FAIL} OpenRouter: {err[:100]}")
            results["OpenRouter"] = False

    # 4. Cerebras
    print("  4. Cerebras...")
    key = (settings.CEREBRAS_API_KEY or "").strip()
    if not key or "demo" in key.lower() or "your_" in key.lower():
        print(f"     {FAIL} No valid API key configured")
        results["Cerebras"] = False
    else:
        try:
            client = OpenAI(base_url="https://api.cerebras.ai/v1", api_key=key)
            resp = await asyncio.to_thread(
                client.chat.completions.create,
                model="llama3.1-70b",
                messages=[{"role": "user", "content": "Say OK"}],
            )
            print(f"     {PASS} Cerebras: '{resp.choices[0].message.content.strip()[:60]}'")
            results["Cerebras"] = True
        except Exception as e:
            print(f"     {FAIL} Cerebras: {str(e)[:100]}")
            results["Cerebras"] = False

    # 5. Together
    print("  5. Together AI...")
    key = (settings.TOGETHER_API_KEY or "").strip()
    if not key or "demo" in key.lower() or "your_" in key.lower():
        print(f"     {FAIL} No valid API key configured")
        results["Together"] = False
    else:
        try:
            client = OpenAI(base_url="https://api.together.xyz/v1", api_key=key)
            resp = await asyncio.to_thread(
                client.chat.completions.create,
                model="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
                messages=[{"role": "user", "content": "Say OK"}],
            )
            print(f"     {PASS} Together: '{resp.choices[0].message.content.strip()[:60]}'")
            results["Together"] = True
        except Exception as e:
            print(f"     {FAIL} Together: {str(e)[:100]}")
            results["Together"] = False

    # 6. DeepSeek
    print("  6. DeepSeek...")
    key = (settings.DEEPSEEK_API_KEY or "").strip()
    if not key or "demo" in key.lower() or "your_" in key.lower():
        print(f"     {FAIL} No valid API key configured")
        results["DeepSeek"] = False
    else:
        try:
            client = OpenAI(base_url="https://api.deepseek.com/v1", api_key=key)
            resp = await asyncio.to_thread(
                client.chat.completions.create,
                model="deepseek-chat",
                messages=[{"role": "user", "content": "Say OK"}],
            )
            print(f"     {PASS} DeepSeek: '{resp.choices[0].message.content.strip()[:60]}'")
            results["DeepSeek"] = True
        except Exception as e:
            print(f"     {FAIL} DeepSeek: {str(e)[:100]}")
            results["DeepSeek"] = False

    # 7. Ollama
    print("  7. Ollama (local)...")
    url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434/v1")
    try:
        client = OpenAI(base_url=url, api_key="ollama")
        models_resp = client.models.list()
        model_ids = [m.id for m in models_resp.data] if models_resp and hasattr(models_resp, "data") and models_resp.data else []
        if model_ids:
            target = model_ids[0]
            resp = await asyncio.to_thread(
                client.chat.completions.create,
                model=target,
                messages=[{"role": "user", "content": "Say OK"}],
            )
            print(f"     {PASS} Ollama ({target}): '{resp.choices[0].message.content.strip()[:60]}'")
            results["Ollama"] = True
        else:
            print(f"     {WARN} Ollama running but no models pulled. Run: ollama pull llama3")
            results["Ollama"] = False
    except Exception as e:
        print(f"     {FAIL} Ollama: {str(e)[:100]}")
        results["Ollama"] = False

    return results


async def test_agents():
    """Test each agent individually with a sample company."""
    section("AGENT EXECUTION TEST (Company: 'Stripe')")

    from services.llm_service import llm_service

    agent_tests = {}
    company = "Stripe"

    # Research Agent
    print("\n  1. Research Agent...")
    try:
        from agents.research_agent import ResearchAgent
        agent = ResearchAgent()
        start = time.monotonic()
        result = await agent.execute({"company": company})
        duration = time.monotonic() - start
        has_score = hasattr(result, "score") or (isinstance(result, dict) and "score" in result)
        print(f"     {PASS} Research Agent completed in {duration:.2f}s (has score: {has_score})")
        agent_tests["Research"] = True
    except Exception as e:
        print(f"     {FAIL} Research Agent: {str(e)[:120]}")
        agent_tests["Research"] = False

    # Market Agent
    print("  2. Market Agent...")
    try:
        from agents.market_agent import MarketAgent
        agent = MarketAgent()
        start = time.monotonic()
        result = await agent.execute({"company": company})
        duration = time.monotonic() - start
        print(f"     {PASS} Market Agent completed in {duration:.2f}s")
        agent_tests["Market"] = True
    except Exception as e:
        print(f"     {FAIL} Market Agent: {str(e)[:120]}")
        agent_tests["Market"] = False

    # Competitor Agent
    print("  3. Competitor Agent...")
    try:
        from agents.competitor_agent import CompetitorAgent
        agent = CompetitorAgent()
        start = time.monotonic()
        result = await agent.execute({"company": company})
        duration = time.monotonic() - start
        print(f"     {PASS} Competitor Agent completed in {duration:.2f}s")
        agent_tests["Competitor"] = True
    except Exception as e:
        print(f"     {FAIL} Competitor Agent: {str(e)[:120]}")
        agent_tests["Competitor"] = False

    # Founder Agent
    print("  4. Founder Agent...")
    try:
        from agents.founder_agent import FounderAgent
        agent = FounderAgent()
        start = time.monotonic()
        result = await agent.execute({"company": company})
        duration = time.monotonic() - start
        print(f"     {PASS} Founder Agent completed in {duration:.2f}s")
        agent_tests["Founder"] = True
    except Exception as e:
        print(f"     {FAIL} Founder Agent: {str(e)[:120]}")
        agent_tests["Founder"] = False

    # Finance Agent
    print("  5. Finance Agent...")
    try:
        from agents.finance_agent import FinanceAgent
        agent = FinanceAgent()
        start = time.monotonic()
        result = await agent.execute({"company": company})
        duration = time.monotonic() - start
        print(f"     {PASS} Finance Agent completed in {duration:.2f}s")
        agent_tests["Finance"] = True
    except Exception as e:
        print(f"     {FAIL} Finance Agent: {str(e)[:120]}")
        agent_tests["Finance"] = False

    # Risk Agent
    print("  6. Risk Agent...")
    try:
        from agents.risk_agent import RiskAgent
        agent = RiskAgent()
        start = time.monotonic()
        result = await agent.execute({"company": company})
        duration = time.monotonic() - start
        print(f"     {PASS} Risk Agent completed in {duration:.2f}s")
        agent_tests["Risk"] = True
    except Exception as e:
        print(f"     {FAIL} Risk Agent: {str(e)[:120]}")
        agent_tests["Risk"] = False

    # Prediction Agent
    print("  7. Prediction Agent...")
    try:
        from agents.prediction_agent import PredictionAgent
        agent = PredictionAgent()
        start = time.monotonic()
        result = await agent.execute({"company": company})
        duration = time.monotonic() - start
        print(f"     {PASS} Prediction Agent completed in {duration:.2f}s")
        agent_tests["Prediction"] = True
    except Exception as e:
        print(f"     {FAIL} Prediction Agent: {str(e)[:120]}")
        agent_tests["Prediction"] = False

    # Committee Agent
    print("  8. Committee Agent...")
    try:
        from agents.committee_agent import CommitteeAgent
        agent = CommitteeAgent()
        start = time.monotonic()
        result = await agent.execute({"company": company})
        duration = time.monotonic() - start
        print(f"     {PASS} Committee Agent completed in {duration:.2f}s")
        agent_tests["Committee"] = True
    except Exception as e:
        print(f"     {FAIL} Committee Agent: {str(e)[:120]}")
        agent_tests["Committee"] = False

    return agent_tests


async def main():
    print(f"\n{'#' * 60}")
    print(f"  VENTUREMIND AI — FULL DIAGNOSTIC TEST")
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#' * 60}")

    # 1. Ollama status
    ollama_ok = await test_ollama_status()

    # 2. LLM providers
    provider_results = await test_llm_providers()

    # 3. Agent tests
    agent_results = await test_agents()

    # Summary
    section("FINAL SUMMARY")
    
    print("\n  LLM Providers:")
    for name, ok in provider_results.items():
        status = PASS if ok else FAIL
        print(f"    {status} {name}")
    
    working_providers = sum(1 for v in provider_results.values() if v)
    print(f"\n    => {working_providers}/{len(provider_results)} providers operational")

    print("\n  Agents:")
    for name, ok in agent_results.items():
        status = PASS if ok else FAIL
        print(f"    {status} {name} Agent")
    
    working_agents = sum(1 for v in agent_results.values() if v)
    print(f"\n    => {working_agents}/{len(agent_results)} agents operational")

    print(f"\n  Ollama: {'RUNNING (but needs models)' if ollama_ok else 'NOT AVAILABLE'}")
    if not ollama_ok or not any(v for k, v in provider_results.items() if k == "Ollama"):
        print(f"    To enable: ollama pull llama3")

    print(f"\n{DIVIDER}")
    print("  DIAGNOSTIC COMPLETE")
    print(DIVIDER)


if __name__ == "__main__":
    asyncio.run(main())
