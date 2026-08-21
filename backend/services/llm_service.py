import json
import re
import random
import time
import asyncio
from typing import Optional, List, Any
try:
    from google import genai
except ImportError:
    import google.generativeai as genai
from groq import Groq
from core.config import settings
from core.logging import app_logger
from core.cache import cache, make_cache_key

class AllLLMProvidersFailedError(Exception):
    """Raised when all LLM providers (Gemini, Groq, OpenRouter) fail."""
    pass

class StructuredOutputParsingError(Exception):
    """Raised when an LLM fails to output valid JSON matching schema after retry."""
    pass


def _parse_and_clean_json(text: str) -> dict:
    """Helper to strip markdown code fences and extract JSON object dict."""
    if not text:
        raise ValueError("Empty LLM response text")
    
    # 1. Strip markdown fences ```json ... ``` or ``` ... ```
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))

    # 2. Match raw JSON object {...}
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        return json.loads(brace.group(0))

    # 3. Direct json.loads fallback
    return json.loads(text.strip())


class LLMService:

    def __init__(self):
        self._gemini = None
        self._groq = None
        self._cerebras = None
        self._together = None
        self._deepseek = None
        self._ollama = None
        self._provider_cooldown: dict[str, float] = {}
        self._semaphores: dict = {}
        self.telemetry_history: list[dict] = []

    def _get_semaphore(self, provider: str) -> asyncio.Semaphore:
        limits = {
            "gemini": getattr(settings, "GEMINI_MAX_CONCURRENCY", 3),
            "groq": getattr(settings, "GROQ_MAX_CONCURRENCY", 2),
            "openrouter": getattr(settings, "OPENROUTER_MAX_CONCURRENCY", 2),
            "ollama": getattr(settings, "OLLAMA_MAX_CONCURRENCY", 1),
        }
        limit = limits.get(provider.lower(), 2)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        
        if not hasattr(self, "_semaphores") or self._semaphores is None:
            self._semaphores = {}
            
        if provider not in self._semaphores or self._semaphores[provider][0] != loop:
            self._semaphores[provider] = (loop, asyncio.Semaphore(limit))
        return self._semaphores[provider][1]

    def get_and_clear_telemetry(self) -> list[dict]:
        records = list(self.telemetry_history)
        self.telemetry_history.clear()
        return records

    def _record_telemetry(self, provider: str, model: str, status: str, latency_ms: float, error: Optional[str] = None):
        self.telemetry_history.append({
            "timestamp": time.time(),
            "provider": provider,
            "model": model,
            "status": status,
            "latency_ms": round(latency_ms, 2),
            "error": error
        })

    @property
    def gemini(self):
        if self._gemini is None:
            key = (settings.GEMINI_API_KEY or "").strip()
            if not key or key == "dummy":
                raise ValueError("No valid GEMINI_API_KEY configured.")
            if hasattr(genai, "Client"):
                self._gemini = genai.Client(api_key=key)
            else:
                genai.configure(api_key=key)
                self._gemini = genai.GenerativeModel("gemini-1.5-flash")
        return self._gemini

    @property
    def groq(self):
        if self._groq is None:
            key = (settings.GROQ_API_KEY or "").strip()
            if not key:
                raise ValueError("No valid GROQ_API_KEY configured.")
            self._groq = Groq(api_key=key)
        return self._groq

    @property
    def cerebras(self):
        if self._cerebras is None:
            key = (settings.CEREBRAS_API_KEY or "").strip()
            if not key or "demo" in key.lower() or "your_" in key.lower():
                raise ValueError("No valid CEREBRAS_API_KEY configured.")
            from openai import OpenAI
            self._cerebras = OpenAI(base_url="https://api.cerebras.ai/v1", api_key=key)
        return self._cerebras

    @property
    def together(self):
        if self._together is None:
            key = (settings.TOGETHER_API_KEY or "").strip()
            if not key or "demo" in key.lower() or "your_" in key.lower():
                raise ValueError("No valid TOGETHER_API_KEY configured.")
            from openai import OpenAI
            self._together = OpenAI(base_url="https://api.together.xyz/v1", api_key=key)
        return self._together

    @property
    def deepseek(self):
        if self._deepseek is None:
            key = (settings.DEEPSEEK_API_KEY or "").strip()
            if not key or "demo" in key.lower() or "your_" in key.lower():
                raise ValueError("No valid DEEPSEEK_API_KEY configured.")
            from openai import OpenAI
            self._deepseek = OpenAI(base_url="https://api.deepseek.com/v1", api_key=key)
        return self._deepseek

    @property
    def ollama(self):
        if self._ollama is None:
            url = (getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434/v1") or "").strip()
            from openai import OpenAI
            self._ollama = OpenAI(base_url=url, api_key="ollama")
        return self._ollama

    async def generate_chat(self, prompt: str) -> str:
        """Dedicated chat completion using OpenRouter directly as primary provider with full fallback pipeline."""
        if settings.OPENROUTER_API_KEY and time.monotonic() >= self._provider_cooldown.get("openrouter", 0.0):
            try:
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
                app_logger.error(f"[Chat] OpenRouter auto-free failed: {e}, attempting provider chain fallback...")
        
        # Fall back through full provider pipeline (Gemini, Groq, Cerebras, Together, DeepSeek, Local Ollama)
        return await self.generate(prompt, bypass_cache=True)

    async def generate_chat_stream(self, prompt: str):
        """Truly non-blocking async token streaming with multi-provider fallback (OpenRouter -> Groq -> Local)."""
        from openai import AsyncOpenAI

        # Provider 1: OpenRouter Stream
        if settings.OPENROUTER_API_KEY and time.monotonic() >= self._provider_cooldown.get("openrouter", 0.0):
            try:
                app_logger.info("[Chat Stream] Non-blocking streaming from OpenRouter (openrouter/free)...")
                openrouter_client = AsyncOpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=settings.OPENROUTER_API_KEY
                )
                stream_resp = await openrouter_client.chat.completions.create(
                    model="openrouter/free",
                    messages=[{"role": "user", "content": prompt}],
                    stream=True,
                    extra_headers={
                        "HTTP-Referer": "http://localhost:8000",
                        "X-Title": "VentureMind AI"
                    }
                )
                async for chunk in stream_resp:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if hasattr(delta, "content") and delta.content:
                            yield delta.content
                return
            except Exception as e:
                if any(term in str(e).lower() for term in ["429", "quota", "rate_limit", "rate limit", "limit exceeded"]):
                    self._provider_cooldown["openrouter"] = time.monotonic() + settings.PROVIDER_COOLDOWN_SECONDS
                app_logger.warning(f"[Chat Stream] OpenRouter failed: {e}, falling back to Groq stream...")

        # Provider 2: Groq Stream
        if settings.GROQ_API_KEY and time.monotonic() >= self._provider_cooldown.get("groq", 0.0):
            try:
                app_logger.info("[Chat Stream] Non-blocking streaming from Groq (llama-3.3-70b-versatile)...")
                groq_client = AsyncOpenAI(
                    base_url="https://api.groq.com/openai/v1",
                    api_key=settings.GROQ_API_KEY
                )
                stream_resp = await groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    stream=True
                )
                async for chunk in stream_resp:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if hasattr(delta, "content") and delta.content:
                            yield delta.content
                return
            except Exception as e2:
                if any(term in str(e2).lower() for term in ["429", "quota", "rate_limit", "rate limit", "limit exceeded"]):
                    self._provider_cooldown["groq"] = time.monotonic() + settings.PROVIDER_COOLDOWN_SECONDS
                app_logger.warning(f"[Chat Stream] Groq stream failed: {e2}")

        # Fallback async chunk generator if all live streams fail
        full_text = await self.generate_chat(prompt)
        words = full_text.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
            await asyncio.sleep(0.01)




    async def generate_structured(
        self,
        prompt: str,
        schema_cls: Optional[Any] = None,
        bypass_cache: bool = False
    ) -> dict:
        """
        Reusable structured JSON generation. Strips code fences, parses JSON,
        validates against optional Pydantic schema, and executes ONE controlled
        repair/retry on parsing failure before raising StructuredOutputParsingError.
        """
        json_prompt = prompt
        if "json" not in prompt.lower():
            json_prompt += "\n\nCRITICAL REQUIREMENT: Return ONLY a valid JSON object. Do not include extra commentary or markdown outside the JSON."

        first_text = await self.generate(json_prompt, bypass_cache=bypass_cache)
        try:
            parsed = _parse_and_clean_json(first_text)
            if schema_cls and hasattr(schema_cls, "model_validate"):
                schema_cls.model_validate(parsed)
            return parsed
        except Exception as first_error:
            app_logger.warning(
                f"[LLM Structured Output] Initial parsing failed: {first_error}. Initiating 1-retry repair..."
            )
            repair_prompt = (
                f"Your previous response failed JSON parsing/validation:\n"
                f"ERROR: {first_error}\n\n"
                f"Original Task:\n{prompt}\n\n"
                f"CRITICAL: Return ONLY a valid, correctly formatted JSON object with double quotes and no markdown fences."
            )
            retry_text = await self.generate(repair_prompt, bypass_cache=True)
            try:
                parsed_retry = _parse_and_clean_json(retry_text)
                if schema_cls and hasattr(schema_cls, "model_validate"):
                    schema_cls.model_validate(parsed_retry)
                app_logger.info("[LLM Structured Output] Controlled JSON repair retry succeeded!")
                return parsed_retry
            except Exception as retry_error:
                app_logger.error(f"[LLM Structured Output] Controlled JSON repair failed: {retry_error}")
                raise StructuredOutputParsingError(
                    f"Failed to generate valid structured JSON after 1 retry: {retry_error}"
                )

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
        # Provider 1: Groq (with controlled 429 retry + exponential backoff + jitter)
        if time.monotonic() >= self._provider_cooldown.get("groq", 0.0):
            groq_sem = self._get_semaphore("groq")
            async with groq_sem:
                max_retries = 2
                for attempt in range(max_retries + 1):
                    try:
                        kwargs = {
                            "model": "llama-3.3-70b-versatile",
                            "messages": [{"role": "user", "content": prompt}]
                        }
                        if "json" in prompt.lower():
                            kwargs["response_format"] = {"type": "json_object"}
                        
                        start_time = time.monotonic()
                        response = await asyncio.wait_for(
                            asyncio.to_thread(self.groq.chat.completions.create, **kwargs),
                            timeout=settings.LLM_PROVIDER_TIMEOUT_SECONDS
                        )
                        duration = time.monotonic() - start_time
                        self._record_telemetry("groq", "llama-3.3-70b-versatile", "success", duration * 1000)
                        app_logger.info(f"[LLM] served by groq in {duration:.2f}s (attempt {attempt+1})")
                        await cache.set(cache_key, response.choices[0].message.content, settings.LLM_CACHE_TTL_SECONDS)
                        return response.choices[0].message.content
                    except Exception as e2:
                        duration = time.monotonic() - start_time
                        is_rl = any(term in str(e2).lower() for term in ["429", "quota", "rate_limit", "rate limit", "limit exceeded"])
                        
                        if is_rl and attempt < max_retries:
                            jitter = random.uniform(0.1, 0.4)
                            backoff_sec = (1.5 ** attempt) + jitter
                            app_logger.warning(f"[LLM] Groq 429 rate limited. Retrying in {backoff_sec:.2f}s (attempt {attempt+1}/{max_retries})...")
                            self._record_telemetry("groq", "llama-3.3-70b-versatile", "rate_limit_retry", duration * 1000, str(e2))
                            await asyncio.sleep(backoff_sec)
                            continue
                        
                        self._record_telemetry("groq", "llama-3.3-70b-versatile", "rate_limited" if is_rl else "failed", duration * 1000, str(e2))
                        if is_rl:
                            self._provider_cooldown["groq"] = time.monotonic() + settings.PROVIDER_COOLDOWN_SECONDS
                            app_logger.warning(f"[LLM] Groq rate limited after retries. Cooldown set for {settings.PROVIDER_COOLDOWN_SECONDS}s.")
                        app_logger.warning(f"Groq failed, trying Gemini fallback: {e2}")
                        break
        else:
            app_logger.info("[LLM] Skipping Groq (in cooldown).")

        # Provider 2: Gemini
        if time.monotonic() >= self._provider_cooldown.get("gemini", 0.0):
            gemini_sem = self._get_semaphore("gemini")
            async with gemini_sem:
                try:
                    start_time = time.monotonic()
                    client_obj = self.gemini
                    if hasattr(client_obj, "models"):
                        fn = lambda: client_obj.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                    else:
                        fn = lambda: client_obj.generate_content(prompt)
                    response = await asyncio.wait_for(
                        asyncio.to_thread(fn),
                        timeout=settings.LLM_PROVIDER_TIMEOUT_SECONDS
                    )
                    duration = time.monotonic() - start_time
                    self._record_telemetry("gemini", "gemini-2.5-flash", "success", duration * 1000)
                    app_logger.info(f"[LLM] served by gemini in {duration:.2f}s")
                    await cache.set(cache_key, response.text, settings.LLM_CACHE_TTL_SECONDS)
                    return response.text
                except Exception as e:
                    duration = time.monotonic() - start_time
                    is_rl = any(term in str(e).lower() for term in ["429", "quota", "rate_limit", "rate limit", "limit exceeded"])
                    self._record_telemetry("gemini", "gemini-2.5-flash", "rate_limited" if is_rl else "failed", duration * 1000, str(e))
                    if is_rl:
                        self._provider_cooldown["gemini"] = time.monotonic() + settings.PROVIDER_COOLDOWN_SECONDS
                        app_logger.warning(f"[LLM] Gemini rate limited. Cooldown set for {settings.PROVIDER_COOLDOWN_SECONDS}s.")
                    app_logger.warning(f"Gemini failed, trying OpenRouter fallback: {e}")
        else:
            app_logger.info("[LLM] Skipping Gemini (in cooldown).")

        # Provider 3: OpenRouter (with semaphore & backoff retry)
        if settings.OPENROUTER_API_KEY and time.monotonic() >= self._provider_cooldown.get("openrouter", 0.0):
            openrouter_sem = self._get_semaphore("openrouter")
            async with openrouter_sem:
                max_retries = 1
                for attempt in range(max_retries + 1):
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
                                messages=[{"role": "user", "content": prompt}]
                            ),
                            timeout=settings.LLM_PROVIDER_TIMEOUT_SECONDS
                        )
                        duration = time.monotonic() - start_time
                        self._record_telemetry("openrouter", "openrouter/free", "success", duration * 1000)
                        app_logger.info(f"[LLM] served by openrouter in {duration:.2f}s")
                        await cache.set(cache_key, response.choices[0].message.content, settings.LLM_CACHE_TTL_SECONDS)
                        return response.choices[0].message.content
                    except Exception as e3:
                        duration = time.monotonic() - start_time
                        is_rl = any(term in str(e3).lower() for term in ["429", "quota", "rate_limit", "rate limit", "limit exceeded"])
                        if is_rl and attempt < max_retries:
                            backoff_sec = 1.0 + random.uniform(0.1, 0.3)
                            app_logger.warning(f"[LLM] OpenRouter 429 rate limited. Retrying in {backoff_sec:.2f}s...")
                            await asyncio.sleep(backoff_sec)
                            continue
                        self._record_telemetry("openrouter", "openrouter/free", "rate_limited" if is_rl else "failed", duration * 1000, str(e3))
                        if is_rl:
                            self._provider_cooldown["openrouter"] = time.monotonic() + settings.PROVIDER_COOLDOWN_SECONDS
                        app_logger.warning(f"OpenRouter fallback failed: {e3}, trying Cerebras AI...")
                        break
        else:
            app_logger.info("[LLM] Skipping OpenRouter (in cooldown).")

        # Provider 4: Cerebras AI
        if time.monotonic() >= self._provider_cooldown.get("cerebras", 0.0):
            try:
                cerebras_client = self.cerebras
                app_logger.info("Trying Cerebras AI client fallback (llama3.1-70b)...")
                start_time = time.monotonic()
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        cerebras_client.chat.completions.create,
                        model="llama3.1-70b",
                        messages=[{"role": "user", "content": prompt}]
                    ),
                    timeout=settings.LLM_PROVIDER_TIMEOUT_SECONDS
                )
                duration = time.monotonic() - start_time
                self._record_telemetry("cerebras", "llama3.1-70b", "success", duration * 1000)
                app_logger.info(f"[LLM] served by cerebras in {duration:.2f}s")
                await cache.set(cache_key, response.choices[0].message.content, settings.LLM_CACHE_TTL_SECONDS)
                return response.choices[0].message.content
            except Exception as e4:
                duration = time.monotonic() - start_time
                is_rl = any(term in str(e4).lower() for term in ["429", "quota", "rate_limit", "rate limit", "limit exceeded"])
                self._record_telemetry("cerebras", "llama3.1-70b", "rate_limited" if is_rl else "failed", duration * 1000, str(e4))
                if is_rl:
                    self._provider_cooldown["cerebras"] = time.monotonic() + settings.PROVIDER_COOLDOWN_SECONDS
                app_logger.warning(f"Cerebras AI fallback failed: {e4}, trying Together AI...")
        else:
            app_logger.info("[LLM] Skipping Cerebras AI (in cooldown).")

        # Provider 5: Together AI
        if time.monotonic() >= self._provider_cooldown.get("together", 0.0):
            try:
                together_client = self.together
                app_logger.info("Trying Together AI client fallback (meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo)...")
                start_time = time.monotonic()
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        together_client.chat.completions.create,
                        model="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
                        messages=[{"role": "user", "content": prompt}]
                    ),
                    timeout=settings.LLM_PROVIDER_TIMEOUT_SECONDS
                )
                duration = time.monotonic() - start_time
                self._record_telemetry("together", "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo", "success", duration * 1000)
                app_logger.info(f"[LLM] served by together in {duration:.2f}s")
                await cache.set(cache_key, response.choices[0].message.content, settings.LLM_CACHE_TTL_SECONDS)
                return response.choices[0].message.content
            except Exception as e5:
                duration = time.monotonic() - start_time
                is_rl = any(term in str(e5).lower() for term in ["429", "quota", "rate_limit", "rate limit", "limit exceeded"])
                self._record_telemetry("together", "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo", "rate_limited" if is_rl else "failed", duration * 1000, str(e5))
                if is_rl:
                    self._provider_cooldown["together"] = time.monotonic() + settings.PROVIDER_COOLDOWN_SECONDS
                app_logger.warning(f"Together AI fallback failed: {e5}, trying DeepSeek AI...")
        else:
            app_logger.info("[LLM] Skipping Together AI (in cooldown).")

        # Provider 6: DeepSeek AI
        if time.monotonic() >= self._provider_cooldown.get("deepseek", 0.0):
            try:
                deepseek_client = self.deepseek
                app_logger.info("Trying DeepSeek AI client fallback (deepseek-chat)...")
                start_time = time.monotonic()
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        deepseek_client.chat.completions.create,
                        model="deepseek-chat",
                        messages=[{"role": "user", "content": prompt}]
                    ),
                    timeout=settings.LLM_PROVIDER_TIMEOUT_SECONDS
                )
                duration = time.monotonic() - start_time
                self._record_telemetry("deepseek", "deepseek-chat", "success", duration * 1000)
                app_logger.info(f"[LLM] served by deepseek in {duration:.2f}s")
                await cache.set(cache_key, response.choices[0].message.content, settings.LLM_CACHE_TTL_SECONDS)
                return response.choices[0].message.content
            except Exception as e6:
                duration = time.monotonic() - start_time
                is_rl = any(term in str(e6).lower() for term in ["429", "quota", "rate_limit", "rate limit", "limit exceeded"])
                self._record_telemetry("deepseek", "deepseek-chat", "rate_limited" if is_rl else "failed", duration * 1000, str(e6))
                if is_rl:
                    self._provider_cooldown["deepseek"] = time.monotonic() + settings.PROVIDER_COOLDOWN_SECONDS
                app_logger.warning(f"DeepSeek AI fallback failed: {e6}, trying local Ollama...")
        else:
            app_logger.info("[LLM] Skipping DeepSeek AI (in cooldown).")

        # Provider 7: Local Ollama (with controlled single-model evaluation fallback)
        if time.monotonic() >= self._provider_cooldown.get("ollama", 0.0):
            ollama_sem = self._get_semaphore("ollama")
            async with ollama_sem:
                try:
                    content = await self._try_ollama_fallback(prompt)
                    await cache.set(cache_key, content, settings.LLM_CACHE_TTL_SECONDS)
                    return content
                except Exception as e7:
                    self._provider_cooldown["ollama"] = time.monotonic() + 15
                    app_logger.warning(f"Local Ollama provider failed: {e7}")
        else:
            app_logger.info("[LLM] Skipping local Ollama (in cooldown).")

        # Final Fallback: Gated Mock Response (DISABLED during EVALUATION_MODE)
        if settings.ALLOW_MOCK_FALLBACK and not getattr(settings, "EVALUATION_MODE", False):
            app_logger.warning("Gated mock fallback triggered for general generation after all live providers failed.")
            return self._generate_mock_fallback(prompt)

        raise AllLLMProvidersFailedError("All LLM providers (Gemini, Groq, OpenRouter, Cerebras, Together, DeepSeek, Ollama) failed or in cooldown.")

    async def _try_ollama_fallback(self, prompt: str) -> str:
        ollama_client = self.ollama
        configured_model = getattr(settings, "OLLAMA_MODEL", "llama3:latest")
        if configured_model == "llama3.2":
            configured_model = "llama3:latest"
        
        # When in EVALUATION_MODE, use single model with a 90s timeout to allow local CPU inference across all parallel agents
        if getattr(settings, "EVALUATION_MODE", False):
            start_time = time.monotonic()
            try:
                app_logger.info(f"[Ollama Evaluation Mode] Calling model '{configured_model}'...")
                kwargs = {
                    "model": configured_model,
                    "messages": [{"role": "user", "content": prompt}],
                }
                if "json" in prompt.lower():
                    kwargs["response_format"] = {"type": "json_object"}

                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        ollama_client.chat.completions.create,
                        **kwargs
                    ),
                    timeout=90
                )
                duration = time.monotonic() - start_time
                self._record_telemetry("ollama", configured_model, "success", duration * 1000)
                app_logger.info(f"[LLM] served by local ollama model '{configured_model}' in {duration:.2f}s")
                return response.choices[0].message.content
            except Exception as e:
                duration = time.monotonic() - start_time
                self._record_telemetry("ollama", configured_model, "failed", duration * 1000, str(e))
                raise Exception(f"Ollama model '{configured_model}' failed in evaluation mode: {e}")

        # Discover available local models dynamically (Dev mode)
        discovered_models = []
        try:
            models_resp = await asyncio.to_thread(ollama_client.models.list)
            if models_resp and hasattr(models_resp, "data") and models_resp.data:
                discovered_models = [m.id for m in models_resp.data if hasattr(m, "id") and m.id]
        except Exception as e:
            app_logger.debug(f"[Ollama] Dynamic model list check skipped: {e}")

        fallback_candidates = [configured_model, "llama3.2", "llama3:latest", "mistral", "qwen2.5:latest"]
        candidate_queue = []
        if configured_model:
            candidate_queue.append(configured_model)
        for m in discovered_models + fallback_candidates:
            if m and m not in candidate_queue:
                candidate_queue.append(m)

        last_error = None
        for model_name in candidate_queue:
            try:
                start_time = time.monotonic()
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        ollama_client.chat.completions.create,
                        model=model_name,
                        messages=[{"role": "user", "content": prompt}]
                    ),
                    timeout=30
                )
                duration = time.monotonic() - start_time
                self._record_telemetry("ollama", model_name, "success", duration * 1000)
                app_logger.info(f"[LLM] served by local ollama model '{model_name}' in {duration:.2f}s")
                return response.choices[0].message.content
            except Exception as e:
                last_error = e
                duration = time.monotonic() - start_time
                self._record_telemetry("ollama", model_name, "failed", duration * 1000, str(e))

        raise Exception(f"All local Ollama models failed. Last error: {last_error}")

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