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

    def _validate_response(self, content: Any, provider_name: str) -> str:
        """Enforces that an LLM response is non-empty, non-whitespace, and not a refusal."""
        if content is None:
            raise ValueError(f"Provider '{provider_name}' returned None content.")
        text = str(content).strip()
        if not text:
            raise ValueError(f"Provider '{provider_name}' returned empty or whitespace-only response.")
        lower = text.lower()
        if any(refusal in lower for refusal in [
            "i cannot fulfill this request",
            "i am unable to fulfill this request",
            "i cannot assist with this request",
            "as an ai language model, i cannot",
        ]):
            raise ValueError(f"Provider '{provider_name}' returned a refusal response.")
        return text

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
        cloud_timeout = getattr(settings, "LLM_CLOUD_TIMEOUT_SECONDS", 8.0)
        local_timeout = getattr(settings, "LLM_LOCAL_TIMEOUT_SECONDS", 30.0)
        rate_limit_cooldown = getattr(settings, "PROVIDER_COOLDOWN_SECONDS", 60.0)
        transient_cooldown = getattr(settings, "PROVIDER_TRANSIENT_COOLDOWN_SECONDS", 15.0)

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
                            timeout=cloud_timeout
                        )
                        duration = time.monotonic() - start_time
                        content = self._validate_response(response.choices[0].message.content, "groq")
                        self._record_telemetry("groq", "llama-3.3-70b-versatile", "success", duration * 1000)
                        app_logger.info(f"[LLM] served by groq in {duration:.2f}s (attempt {attempt+1})")
                        await cache.set(cache_key, content, settings.LLM_CACHE_TTL_SECONDS)
                        return content
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
                            self._provider_cooldown["groq"] = time.monotonic() + rate_limit_cooldown
                            app_logger.warning(f"[LLM] Groq rate limited after retries. Cooldown set for {rate_limit_cooldown}s.")
                        else:
                            self._provider_cooldown["groq"] = time.monotonic() + transient_cooldown
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
                        timeout=cloud_timeout
                    )
                    duration = time.monotonic() - start_time
                    content = self._validate_response(response.text, "gemini")
                    self._record_telemetry("gemini", "gemini-2.5-flash", "success", duration * 1000)
                    app_logger.info(f"[LLM] served by gemini in {duration:.2f}s")
                    await cache.set(cache_key, content, settings.LLM_CACHE_TTL_SECONDS)
                    return content
                except Exception as e:
                    duration = time.monotonic() - start_time
                    is_rl = any(term in str(e).lower() for term in ["429", "quota", "rate_limit", "rate limit", "limit exceeded"])
                    self._record_telemetry("gemini", "gemini-2.5-flash", "rate_limited" if is_rl else "failed", duration * 1000, str(e))
                    if is_rl:
                        self._provider_cooldown["gemini"] = time.monotonic() + rate_limit_cooldown
                        app_logger.warning(f"[LLM] Gemini rate limited. Cooldown set for {rate_limit_cooldown}s.")
                    else:
                        self._provider_cooldown["gemini"] = time.monotonic() + transient_cooldown
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
                            timeout=cloud_timeout
                        )
                        duration = time.monotonic() - start_time
                        content = self._validate_response(response.choices[0].message.content, "openrouter")
                        self._record_telemetry("openrouter", "openrouter/free", "success", duration * 1000)
                        app_logger.info(f"[LLM] served by openrouter in {duration:.2f}s")
                        await cache.set(cache_key, content, settings.LLM_CACHE_TTL_SECONDS)
                        return content
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
                            self._provider_cooldown["openrouter"] = time.monotonic() + rate_limit_cooldown
                        else:
                            self._provider_cooldown["openrouter"] = time.monotonic() + transient_cooldown
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
                    timeout=cloud_timeout
                )
                duration = time.monotonic() - start_time
                content = self._validate_response(response.choices[0].message.content, "cerebras")
                self._record_telemetry("cerebras", "llama3.1-70b", "success", duration * 1000)
                app_logger.info(f"[LLM] served by cerebras in {duration:.2f}s")
                await cache.set(cache_key, content, settings.LLM_CACHE_TTL_SECONDS)
                return content
            except Exception as e4:
                duration = time.monotonic() - start_time
                is_rl = any(term in str(e4).lower() for term in ["429", "quota", "rate_limit", "rate limit", "limit exceeded"])
                self._record_telemetry("cerebras", "llama3.1-70b", "rate_limited" if is_rl else "failed", duration * 1000, str(e4))
                if is_rl:
                    self._provider_cooldown["cerebras"] = time.monotonic() + rate_limit_cooldown
                else:
                    self._provider_cooldown["cerebras"] = time.monotonic() + transient_cooldown
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
                    timeout=cloud_timeout
                )
                duration = time.monotonic() - start_time
                content = self._validate_response(response.choices[0].message.content, "together")
                self._record_telemetry("together", "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo", "success", duration * 1000)
                app_logger.info(f"[LLM] served by together in {duration:.2f}s")
                await cache.set(cache_key, content, settings.LLM_CACHE_TTL_SECONDS)
                return content
            except Exception as e5:
                duration = time.monotonic() - start_time
                is_rl = any(term in str(e5).lower() for term in ["429", "quota", "rate_limit", "rate limit", "limit exceeded"])
                self._record_telemetry("together", "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo", "rate_limited" if is_rl else "failed", duration * 1000, str(e5))
                if is_rl:
                    self._provider_cooldown["together"] = time.monotonic() + rate_limit_cooldown
                else:
                    self._provider_cooldown["together"] = time.monotonic() + transient_cooldown
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
                    timeout=cloud_timeout
                )
                duration = time.monotonic() - start_time
                content = self._validate_response(response.choices[0].message.content, "deepseek")
                self._record_telemetry("deepseek", "deepseek-chat", "success", duration * 1000)
                app_logger.info(f"[LLM] served by deepseek in {duration:.2f}s")
                await cache.set(cache_key, content, settings.LLM_CACHE_TTL_SECONDS)
                return content
            except Exception as e6:
                duration = time.monotonic() - start_time
                is_rl = any(term in str(e6).lower() for term in ["429", "quota", "rate_limit", "rate limit", "limit exceeded"])
                self._record_telemetry("deepseek", "deepseek-chat", "rate_limited" if is_rl else "failed", duration * 1000, str(e6))
                if is_rl:
                    self._provider_cooldown["deepseek"] = time.monotonic() + rate_limit_cooldown
                else:
                    self._provider_cooldown["deepseek"] = time.monotonic() + transient_cooldown
                app_logger.warning(f"DeepSeek AI fallback failed: {e6}, trying local Ollama...")
        else:
            app_logger.info("[LLM] Skipping DeepSeek AI (in cooldown).")

        # Provider 7: Local Ollama (with controlled single-model evaluation fallback)
        if time.monotonic() >= self._provider_cooldown.get("ollama", 0.0):
            ollama_sem = self._get_semaphore("ollama")
            async with ollama_sem:
                try:
                    content = await self._try_ollama_fallback(prompt)
                    validated = self._validate_response(content, "ollama")
                    await cache.set(cache_key, validated, settings.LLM_CACHE_TTL_SECONDS)
                    return validated
                except Exception as e7:
                    self._provider_cooldown["ollama"] = time.monotonic() + transient_cooldown
                    app_logger.warning(f"Local Ollama provider failed: {e7}")
        else:
            app_logger.info("[LLM] Skipping local Ollama (in cooldown).")

        # Terminal Fail Condition: All live providers failed or are in cooldown.
        # NEVER generate fabricated or mock due diligence analysis.
        raise AllLLMProvidersFailedError("All LLM providers (Gemini, Groq, OpenRouter, Cerebras, Together, DeepSeek, Ollama) failed or are in cooldown.")

    async def _try_ollama_fallback(self, prompt: str) -> str:
        ollama_client = self.ollama
        configured_model = getattr(settings, "OLLAMA_MODEL", "llama3:latest")
        if configured_model == "llama3.2":
            configured_model = "llama3:latest"
        
        local_timeout = getattr(settings, "LLM_LOCAL_TIMEOUT_SECONDS", 30.0)
        
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
                return self._validate_response(response.choices[0].message.content, "ollama")
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
                    timeout=local_timeout
                )
                duration = time.monotonic() - start_time
                content = self._validate_response(response.choices[0].message.content, f"ollama/{model_name}")
                self._record_telemetry("ollama", model_name, "success", duration * 1000)
                app_logger.info(f"[LLM] served by local ollama model '{model_name}' in {duration:.2f}s")
                return content
            except Exception as e:
                last_error = e
                duration = time.monotonic() - start_time
                self._record_telemetry("ollama", model_name, "failed", duration * 1000, str(e))

        raise Exception(f"All local Ollama models failed. Last error: {last_error}")

llm_service = LLMService()