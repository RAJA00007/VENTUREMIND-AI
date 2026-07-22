import json
import re
import random
import time
import asyncio
from google import genai
from groq import Groq
from core.config import settings
from core.logging import app_logger
from core.cache import cache, make_cache_key

class AllLLMProvidersFailedError(Exception):
    """Raised when all LLM providers (Gemini, Groq, OpenRouter) fail."""
    pass

class LLMService:

    def __init__(self):
        self._gemini = None
        self._groq = None
        self._provider_cooldown: dict[str, float] = {}

    @property
    def gemini(self):
        if self._gemini is None:
            key = (settings.GEMINI_API_KEY or "").strip()
            if not key:
                raise ValueError("No valid GEMINI_API_KEY configured.")
            self._gemini = genai.Client(api_key=key)
        return self._gemini

    @property
    def groq(self):
        if self._groq is None:
            key = (settings.GROQ_API_KEY or "").strip()
            if not key:
                raise ValueError("No valid GROQ_API_KEY configured.")
            self._groq = Groq(api_key=key)
        return self._groq

    async def generate_chat(self, prompt: str) -> str:
        """Dedicated chat completion using OpenRouter directly as the primary provider."""
        if settings.OPENROUTER_API_KEY:
            try:
                if time.monotonic() < self._provider_cooldown.get("openrouter", 0.0):
                    app_logger.info("[LLM] Skipping OpenRouter for chat (in cooldown).")
                    raise Exception("OpenRouter is in cooldown")

                app_logger.info("[Chat] Calling OpenRouter (openrouter/free)...")
                from openai import OpenAI
                openrouter_client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=settings.OPENROUTER_API_KEY
                )
                start_time = time.monotonic()
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        openrouter_client.chat.completions.create,
                        model="openrouter/free",
                        messages=[
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    ),
                    timeout=settings.LLM_PROVIDER_TIMEOUT_SECONDS
                )
                duration = time.monotonic() - start_time
                app_logger.info(f"[LLM] Chat served by openrouter in {duration:.2f}s")
                return response.choices[0].message.content
            except Exception as e:
                if any(term in str(e).lower() for term in ["429", "quota", "rate_limit", "rate limit", "limit exceeded"]):
                    self._provider_cooldown["openrouter"] = time.monotonic() + settings.PROVIDER_COOLDOWN_SECONDS
                    app_logger.warning(f"[LLM] OpenRouter rate limited. Cooldown set for {settings.PROVIDER_COOLDOWN_SECONDS}s.")
                app_logger.error(f"[Chat] OpenRouter auto-free failed: {e}.")
                if settings.ALLOW_MOCK_FALLBACK:
                    app_logger.warning("Gated mock fallback triggered for chat generation.")
                    return self._generate_mock_fallback(prompt)
                raise AllLLMProvidersFailedError(f"All providers failed for chat completion. Primary OpenRouter error: {e}")
        else:
            app_logger.warning("[Chat] No OpenRouter API key configured.")
            if settings.ALLOW_MOCK_FALLBACK:
                app_logger.warning("Gated mock fallback triggered for chat generation.")
                return self._generate_mock_fallback(prompt)
            raise AllLLMProvidersFailedError("No OpenRouter API key configured for chat completion.")

    async def generate(self, prompt: str, bypass_cache: bool = False) -> str:
        # Cache check
        cache_key = make_cache_key("llm_generate", prompt)
        if not bypass_cache:
            cached_val = await cache.get(cache_key)
            if cached_val is not None:
                app_logger.info("[Cache Hit] LLM generate cache hit.")
                return cached_val
            app_logger.info("[Cache Miss] LLM generate cache miss.")
        else:
            app_logger.info("[Cache Bypass] Bypassing LLM cache.")

        # Falls through to provider chain
        # Provider 1: Gemini
        if time.monotonic() >= self._provider_cooldown.get("gemini", 0.0):
            try:
                start_time = time.monotonic()
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.gemini.models.generate_content,
                        model="gemini-2.0-flash",
                        contents=prompt
                    ),
                    timeout=settings.LLM_PROVIDER_TIMEOUT_SECONDS
                )
                duration = time.monotonic() - start_time
                app_logger.info(f"[LLM] served by gemini in {duration:.2f}s")
                await cache.set(cache_key, response.text, settings.LLM_CACHE_TTL_SECONDS)
                return response.text
            except Exception as e:
                if any(term in str(e).lower() for term in ["429", "quota", "rate_limit", "rate limit", "limit exceeded"]):
                    self._provider_cooldown["gemini"] = time.monotonic() + settings.PROVIDER_COOLDOWN_SECONDS
                    app_logger.warning(f"[LLM] Gemini rate limited. Cooldown set for {settings.PROVIDER_COOLDOWN_SECONDS}s.")
                app_logger.warning(f"Gemini failed, trying Groq fallback: {e}")
        else:
            app_logger.info("[LLM] Skipping Gemini (in cooldown).")

        # Provider 2: Groq
        if time.monotonic() >= self._provider_cooldown.get("groq", 0.0):
            try:
                kwargs = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                }
                if "json" in prompt.lower():
                    kwargs["response_format"] = {"type": "json_object"}
                
                start_time = time.monotonic()
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.groq.chat.completions.create,
                        **kwargs
                    ),
                    timeout=settings.LLM_PROVIDER_TIMEOUT_SECONDS
                )
                duration = time.monotonic() - start_time
                app_logger.info(f"[LLM] served by groq in {duration:.2f}s")
                await cache.set(cache_key, response.choices[0].message.content, settings.LLM_CACHE_TTL_SECONDS)
                return response.choices[0].message.content
            except Exception as e2:
                if any(term in str(e2).lower() for term in ["429", "quota", "rate_limit", "rate limit", "limit exceeded"]):
                    self._provider_cooldown["groq"] = time.monotonic() + settings.PROVIDER_COOLDOWN_SECONDS
                    app_logger.warning(f"[LLM] Groq rate limited. Cooldown set for {settings.PROVIDER_COOLDOWN_SECONDS}s.")
                app_logger.warning(f"Groq failed, trying OpenRouter fallback: {e2}")
        else:
            app_logger.info("[LLM] Skipping Groq (in cooldown).")

        # Provider 3: OpenRouter
        if settings.OPENROUTER_API_KEY:
            if time.monotonic() >= self._provider_cooldown.get("openrouter", 0.0):
                try:
                    app_logger.info("Trying OpenRouter client fallback (openrouter/free)...")
                    from openai import OpenAI
                    openrouter_client = OpenAI(
                        base_url="https://openrouter.ai/api/v1",
                        api_key=settings.OPENROUTER_API_KEY
                    )
                    start_time = time.monotonic()
                    response = await asyncio.wait_for(
                        asyncio.to_thread(
                            openrouter_client.chat.completions.create,
                            model="openrouter/free",
                            messages=[
                                {
                                    "role": "user",
                                    "content": prompt
                                }
                            ]
                        ),
                        timeout=settings.LLM_PROVIDER_TIMEOUT_SECONDS
                    )
                    duration = time.monotonic() - start_time
                    app_logger.info(f"[LLM] served by openrouter in {duration:.2f}s")
                    await cache.set(cache_key, response.choices[0].message.content, settings.LLM_CACHE_TTL_SECONDS)
                    return response.choices[0].message.content
                except Exception as e3:
                    if any(term in str(e3).lower() for term in ["429", "quota", "rate_limit", "rate limit", "limit exceeded"]):
                        self._provider_cooldown["openrouter"] = time.monotonic() + settings.PROVIDER_COOLDOWN_SECONDS
                        app_logger.warning(f"[LLM] OpenRouter rate limited. Cooldown set for {settings.PROVIDER_COOLDOWN_SECONDS}s.")
                    app_logger.error(f"OpenRouter auto-free fallback failed: {e3}.")
                    if settings.ALLOW_MOCK_FALLBACK:
                        app_logger.warning("Gated mock fallback triggered for general generation.")
                        return self._generate_mock_fallback(prompt)
                    raise AllLLMProvidersFailedError(
                        f"All providers (Gemini, Groq, OpenRouter) failed. OpenRouter error: {e3}"
                    )
            else:
                app_logger.info("[LLM] Skipping OpenRouter (in cooldown).")
                if settings.ALLOW_MOCK_FALLBACK:
                    app_logger.warning("Gated mock fallback triggered for general generation.")
                    return self._generate_mock_fallback(prompt)
                raise AllLLMProvidersFailedError("All providers (Gemini, Groq, OpenRouter) failed or in cooldown.")
        else:
            app_logger.error("No OpenRouter API key configured.")
            if settings.ALLOW_MOCK_FALLBACK:
                app_logger.warning("Gated mock fallback triggered for general generation.")
                return self._generate_mock_fallback(prompt)
            raise AllLLMProvidersFailedError("All providers (Gemini, Groq) failed and no OpenRouter key set.")

    def _generate_mock_fallback(self, prompt: str) -> str:
        # Check if this is the chatbot assistant prompt
        if "VentureMind AI Chatbot" in prompt:
            user_query = "hi"
            user_matches = re.findall(r"USER:\s*(.*)", prompt)
            if user_matches:
                user_query = user_matches[-1].strip()
            
            user_query_lower = user_query.lower()
            
            if any(greet in user_query_lower for greet in ["hi", "hello", "hey", "greetings"]):
                return "Hello! I am your VentureMind AI Co-Pilot. I can help you analyze startups, explain due diligence scoring rubric factors, query vector memory for uploaded documents, or summarize historical evaluations. How can I assist you today?"
            
            elif "google" in user_query_lower:
                return "Google was evaluated with a Deal Score of 72.2/100 (Verdict: WATCH). Here is a quick breakdown:\n- Research: 90.0/100 (Strong market clarity and founder credibility)\n- Market: 75.0/100 (Massive TAM but facing some regulatory headwinds)\n- Competitor: 68.0/100 (Clear search moat, but high advertising rivalry)\n- Risk: 88.0/100 (Favorable low operational and execution risk)\nLet me know if you would like me to drill into any specific agent findings!"
            
            elif "stripe" in user_query_lower:
                return "Stripe is rated as a strong contender in online payment processing. Key risk factors identified in evaluations include:\n1. Regulatory Compliance: Ongoing scrutiny over cross-border payment structures.\n2. Competitive Pressure: High rivalry from Adyen and PayPal/Braintree.\n3. Macro Trends: Exposure to e-commerce transaction volumes fluctuations.\nWould you like me to run a full execution analysis for Stripe?"
            
            elif any(x in user_query_lower for x in ["risk agent", "risk rubric", "risk scorecard", "risk score"]):
                return "Under the VentureMind due diligence framework, the Risk Agent reviews five key categories:\n1. Business/Operational risks (customer concentration)\n2. Market/Macro timing risks\n3. Financial runway risks\n4. Execution/Team key-person dependency\n5. Legal & compliance issues."
            
            elif any(x in user_query_lower for x in ["market agent", "market rubric", "market scorecard", "market score", "tam criteria", "cagr factors"]):
                return "The Market Agent scores TAM, SAM, and CAGR growth. We look for large addressable spaces ($1B+ TAM) and secular tailwinds (CAGR > 15%)."
            
            elif any(x in user_query_lower for x in ["valuation framework", "valuation multiple", "funding multiples", "valuation criteria"]):
                return "Valuations are assessed by cross-referencing industry averages, ARR multiple standards (typically 8x-15x ARR for SaaS), growth forecasts, and historical round structures."
                
            else:
                return f"I understand your query: '{user_query}'. I can access the internal RAG database and list evaluations. For example, Google scored 72.2/100 with a WATCH verdict, showing high Research credentials (90.0) but moderate competitor density. If you've uploaded a spec document, I can query its contents semantically using our vector index. How would you like to proceed?"

        # Find company name in prompt
        match = re.search(r"company\s+['\"]([^'\"]+)['\"]", prompt, re.IGNORECASE) or re.search(r"company\s+([^'\s\n,]+)", prompt, re.IGNORECASE)
        company = match.group(1) if match else "Venture"
        
        # Determine which agent is calling by searching prompt content
        if "research analyst" in prompt.lower():
            # Research Agent
            score_breakdown = [
                {"factor": "Value Proposition", "points": random.choice([20, 22, 23]), "max_points": 25, "reason": f"Sourced reports confirm {company} offers an innovative developer scaling and micro-service management platform.", "source": "https://techcrunch.com"},
                {"factor": "Initial Traction", "points": random.choice([15, 17, 18]), "max_points": 20, "reason": f"{company} has reported onboarding over 10,000 developers with positive sentiment and organic community growth.", "source": "https://github.com"},
                {"factor": "Founding Team", "points": random.choice([22, 25, 27]), "max_points": 30, "reason": f"Founders previously held engineering leadership roles at Stripe and Vercel.", "source": "https://linkedin.com"},
                {"factor": "Tech Moat", "points": random.choice([18, 20, 21]), "max_points": 25, "reason": f"Proprietary resource orchestration and custom zero-config build engine provides defensibility.", "source": "https://news.ycombinator.com"}
            ]
            return json.dumps({
                "summary": f"{company} exhibits high potential in the developer tooling space with an experienced core engineering team, positive early adoption metrics, and a distinct tech-led value proposition.",
                "confidence": 0.85,
                "score_breakdown": score_breakdown,
                "sources": ["https://techcrunch.com", "https://github.com", "https://linkedin.com", "https://news.ycombinator.com"],
                "business_profile": {
                    "is_core_product_software": True,
                    "is_revenue_physical_goods": False,
                    "reasoning": f"{company} sells developer software licenses and cloud hosting plans."
                }
            })
            
        elif "market analyst" in prompt.lower():
            # Market Agent
            score_breakdown = [
                {"factor": "Market size (TAM/SAM)", "points": random.choice([22, 25, 26]), "max_points": 30, "reason": "Developer tools and cloud orchestration is a $45B global addressable market.", "source": "https://gartner.com"},
                {"factor": "Growth rate", "points": random.choice([18, 20, 21]), "max_points": 25, "reason": "Market exhibits a robust 22% CAGR driven by enterprise cloud adoption.", "source": "https://idc.com"},
                {"factor": "Customer demand signals", "points": random.choice([15, 17, 18]), "max_points": 20, "reason": "Strong developer survey trends indicating demand for low-latency build architectures.", "source": "https://stackoverflow.com"},
                {"factor": "Market timing (tailwinds vs. headwinds)", "points": random.choice([20, 22, 23]), "max_points": 25, "reason": "Favorable regulatory push for multi-cloud deployments offers significant tailwinds.", "source": "https://forbes.com"}
            ]
            return json.dumps({
                "summary": f"The developer tooling sector represents a massive and rapidly expanding market. {company} is well-positioned to leverage strong tailwinds in cloud-native developer stacks.",
                "confidence": 0.90,
                "score_breakdown": score_breakdown,
                "sources": ["https://gartner.com", "https://idc.com", "https://stackoverflow.com", "https://forbes.com"]
            })
            
        elif "competitive intelligence analyst" in prompt.lower():
            # Competitor Agent
            score_breakdown = [
                {"factor": "Competitive landscape mapping", "points": random.choice([15, 17, 18]), "max_points": 20, "reason": "Landscape contains direct competitors like Vercel and Netlify alongside cloud incumbents.", "source": "https://techcrunch.com"},
                {"factor": "Differentiation clarity", "points": random.choice([16, 18, 19]), "max_points": 20, "reason": f"Differentiates through custom resource optimization that halves infrastructure overhead.", "source": "https://news.ycombinator.com"},
                {"factor": "Moat strength (evidence-gated)", "points": random.choice([22, 25, 28]), "max_points": 35, "reason": "Proprietary container virtualization and network caching models yield strong IP defenses.", "source": "https://patents.google.com"},
                {"factor": "Competitive risk exposure", "points": random.choice([18, 20, 21]), "max_points": 25, "reason": "Insulated from direct copycats due to high switching costs for integrated enterprises.", "source": "https://gartner.com"}
            ]
            return json.dumps({
                "summary": f"While competition is intense from funded scale-ups, {company} offers clear architectural differentiation and a defensible IP moat that creates substantial switching friction.",
                "confidence": 0.88,
                "score_breakdown": score_breakdown,
                "sources": ["https://techcrunch.com", "https://news.ycombinator.com", "https://patents.google.com", "https://gartner.com"]
            })
            
        elif "founding team" in prompt.lower():
            # Founder Agent
            score_breakdown = [
                {"factor": "Relevant domain experience", "points": random.choice([24, 27, 28]), "max_points": 30, "reason": "Founding CTO was former lead virtualization engineer at AWS.", "source": "https://linkedin.com"},
                {"factor": "Prior track record", "points": random.choice([20, 22, 23]), "max_points": 25, "reason": "CEO co-founded a previous SaaS tool that was successfully acquired by Okta.", "source": "https://techcrunch.com"},
                {"factor": "Team completeness", "points": random.choice([22, 23, 24]), "max_points": 25, "reason": "Fully balanced executive team across technical product leadership and enterprise GTM sales.", "source": "https://crunchbase.com"},
                {"factor": "Execution signals", "points": random.choice([16, 18, 19]), "max_points": 20, "reason": "Demonstrated rapid shipment speed, hitting key product roadmap milestones ahead of schedule.", "source": "https://github.com"}
            ]
            return json.dumps({
                "summary": f"The founders of {company} possess stellar pedigree with AWS virtualization expertise and a successful prior SaaS exit, showing exceptional domain-market fit.",
                "confidence": 0.95,
                "score_breakdown": score_breakdown,
                "sources": ["https://linkedin.com", "https://techcrunch.com", "https://crunchbase.com", "https://github.com"]
            })
            
        elif "financial due-diligence analyst" in prompt.lower():
            # Finance Agent
            score_breakdown = [
                {"factor": "Unit economics evidence", "points": random.choice([10, 12, 13]), "max_points": 15, "reason": "Reported high 82% gross margins with LTV/CAC ratio estimated at 4.2x.", "source": "https://saastr.com"},
                {"factor": "Revenue/financial traction", "points": random.choice([11, 13, 14]), "max_points": 15, "reason": "Sourced revenue figures indicate ARR of $1.8M growing at 120% YoY.", "source": "https://techcrunch.com"},
                {"factor": "Funding history & trend", "points": random.choice([16, 18, 19]), "max_points": 20, "reason": "Successfully closed a $3.5M Seed round led by top-tier dev-tool VCs.", "source": "https://crunchbase.com"},
                {"factor": "Capital efficiency & runway", "points": random.choice([12, 14, 15]), "max_points": 15, "reason": "Strong capital efficiency with 22 months of current runway based on active burn rate.", "source": "https://medium.com"},
                {"factor": "Investor quality", "points": random.choice([13, 14, 15]), "max_points": 15, "reason": "Backed by leading early-stage tech funds including Y Combinator and Founders Fund.", "source": "https://crunchbase.com"},
                {"factor": "Financial red flags", "points": random.choice([18, 19, 20]), "max_points": 20, "reason": "Clean financial audit trails with no reported liabilities or legal concerns.", "source": "https://sec.gov"}
            ]
            return json.dumps({
                "summary": f"{company} demonstrates highly attractive SaaS financials with strong ARR growth, excellent gross margins, and backing from blue-chip developer-tooling investors.",
                "confidence": 0.92,
                "score_breakdown": score_breakdown,
                "sources": ["https://saastr.com", "https://techcrunch.com", "https://crunchbase.com", "https://medium.com", "https://sec.gov"]
            })
            
        elif "risk analyst" in prompt.lower():
            # Risk Agent
            score_breakdown = [
                {"factor": "Business/operational risk", "points": random.choice([16, 18, 19]), "max_points": 20, "reason": "Minimal operational friction; low customer concentration risk.", "source": "inferred"},
                {"factor": "Market timing & macro risk", "points": random.choice([15, 17, 18]), "max_points": 20, "reason": "Exposed to generic cloud spending slowdowns, though cloud migration trends offset this.", "source": "inferred"},
                {"factor": "Financial risk", "points": random.choice([16, 18, 19]), "max_points": 20, "reason": "Stable runway provides protection, though future rounds will require sustained GTM acceleration.", "source": "inferred"},
                {"factor": "Execution/team risk", "points": random.choice([18, 19, 20]), "max_points": 20, "reason": "Low key-person dependency due to complete engineering management layers.", "source": "inferred"},
                {"factor": "Legal/compliance risk", "points": random.choice([18, 19, 20]), "max_points": 20, "reason": "Standard software compliance with SOC2 in progress; no legal flags.", "source": "inferred"}
            ]
            return json.dumps({
                "summary": f"{company} exhibits a favorable low-risk profile. Primary risk vectors are typical enterprise sales cycle friction and cloud macro spending timing.",
                "confidence": 0.90,
                "score_breakdown": score_breakdown,
                "sources": []
            })
            
        elif "extract these 6 fields" in prompt.lower() or "prediction" in prompt.lower():
            # Prediction Agent (feature extraction)
            return json.dumps({
                "industry": "AI/Software",
                "funding": 3.5,
                "employees": 25,
                "age": 2,
                "revenue": 1.8,
                "growth": 120.0
            })
            
        elif "committee" in prompt.lower():
            # Committee Agent narrative synthesis
            return json.dumps({
                "narrative": f"The Investment Committee has completed the synthesis for {company}. Given the strong technical foundation, stellar founder profiles, and attractive market tailwinds in developer tooling, the platform recommends an INVEST decision. The primary strengths lie in AWS domain-expert founders, SOC2 progress, and a healthy $1.8M ARR with 120% YoY growth. Recommended next steps include detailed technical review of cloud orchestration IP.",
                "key_opportunities": ["Stellar founder profiles with AWS experience", "Healthy $1.8M ARR with 120% growth", "High gross margins of 82%"],
                "key_risks": ["Cloud macro spending slowdown", "Enterprise sales cycle friction"]
            })
            
        else:
            # Fallback general text
            return f"Mock analysis content generated for {company} due to LLM quota constraints."

llm_service = LLMService()