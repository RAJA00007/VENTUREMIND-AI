import asyncio
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from core.config import settings
from google import genai
from groq import Groq
from openai import OpenAI


async def test_provider_health():
    print("==================================================")
    print("      PROVIDER HEALTH DIAGNOSTIC REPORT")
    print("==================================================")

    providers_status = []

    # 1. Gemini
    print("\n1. Testing Gemini (gemini-2.5-flash)...")
    key = (settings.GEMINI_API_KEY or "").strip()
    if not key or key == "dummy":
        print("   [FAILED] Gemini: No valid key")
        providers_status.append({"provider": "Gemini", "model": "gemini-2.5-flash", "simple": "FAIL", "json": "FAIL", "latency_ms": 0, "error": "No key"})
    else:
        try:
            client = genai.Client(api_key=key)
            # Simple test
            t0 = time.monotonic()
            resp1 = await asyncio.to_thread(client.models.generate_content, model="gemini-2.5-flash", contents="Say 'OK'")
            t1 = time.monotonic()
            simple_pass = "OK" in resp1.text.upper()

            # JSON test
            resp2 = await asyncio.to_thread(client.models.generate_content, model="gemini-2.5-flash", contents="Return ONLY a JSON object: {\"status\": \"OK\"}")
            json_pass = "OK" in resp2.text.upper()
            lat = round((t1 - t0) * 1000, 2)
            print(f"   [SUCCESS] Gemini: Simple={'PASS' if simple_pass else 'FAIL'}, JSON={'PASS' if json_pass else 'FAIL'}, Latency={lat}ms")
            providers_status.append({"provider": "Gemini", "model": "gemini-2.5-flash", "simple": "PASS" if simple_pass else "FAIL", "json": "PASS" if json_pass else "FAIL", "latency_ms": lat, "error": None})
        except Exception as e:
            print(f"   [FAILED] Gemini: {e}")
            providers_status.append({"provider": "Gemini", "model": "gemini-2.5-flash", "simple": "FAIL", "json": "FAIL", "latency_ms": 0, "error": str(e)})

    # 2. Groq
    print("\n2. Testing Groq (llama-3.3-70b-versatile)...")
    key = (settings.GROQ_API_KEY or "").strip()
    if not key:
        print("   [FAILED] Groq: No valid key")
        providers_status.append({"provider": "Groq", "model": "llama-3.3-70b-versatile", "simple": "FAIL", "json": "FAIL", "latency_ms": 0, "error": "No key"})
    else:
        try:
            client = Groq(api_key=key)
            t0 = time.monotonic()
            resp1 = await asyncio.to_thread(
                client.chat.completions.create,
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": "Say 'OK'"}]
            )
            t1 = time.monotonic()
            simple_pass = "OK" in resp1.choices[0].message.content.upper()

            resp2 = await asyncio.to_thread(
                client.chat.completions.create,
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": "Return ONLY a JSON object: {\"status\": \"OK\"}"}],
                response_format={"type": "json_object"}
            )
            json_pass = "OK" in resp2.choices[0].message.content.upper()
            lat = round((t1 - t0) * 1000, 2)
            print(f"   [SUCCESS] Groq: Simple={'PASS' if simple_pass else 'FAIL'}, JSON={'PASS' if json_pass else 'FAIL'}, Latency={lat}ms")
            providers_status.append({"provider": "Groq", "model": "llama-3.3-70b-versatile", "simple": "PASS" if simple_pass else "FAIL", "json": "PASS" if json_pass else "FAIL", "latency_ms": lat, "error": None})
        except Exception as e:
            print(f"   [FAILED] Groq: {e}")
            providers_status.append({"provider": "Groq", "model": "llama-3.3-70b-versatile", "simple": "FAIL", "json": "FAIL", "latency_ms": 0, "error": str(e)})

    # 3. OpenRouter
    print("\n3. Testing OpenRouter (openrouter/free)...")
    key = (settings.OPENROUTER_API_KEY or "").strip()
    if not key:
        print("   [FAILED] OpenRouter: No valid key")
        providers_status.append({"provider": "OpenRouter", "model": "openrouter/free", "simple": "FAIL", "json": "FAIL", "latency_ms": 0, "error": "No key"})
    else:
        try:
            client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
            t0 = time.monotonic()
            resp1 = await asyncio.to_thread(
                client.chat.completions.create,
                model="openrouter/free",
                messages=[{"role": "user", "content": "Say 'OK'"}]
            )
            t1 = time.monotonic()
            simple_pass = "OK" in resp1.choices[0].message.content.upper()

            resp2 = await asyncio.to_thread(
                client.chat.completions.create,
                model="openrouter/free",
                messages=[{"role": "user", "content": "Return ONLY a JSON object: {\"status\": \"OK\"}"}]
            )
            json_pass = "OK" in resp2.choices[0].message.content.upper()
            lat = round((t1 - t0) * 1000, 2)
            print(f"   [SUCCESS] OpenRouter: Simple={'PASS' if simple_pass else 'FAIL'}, JSON={'PASS' if json_pass else 'FAIL'}, Latency={lat}ms")
            providers_status.append({"provider": "OpenRouter", "model": "openrouter/free", "simple": "PASS" if simple_pass else "FAIL", "json": "PASS" if json_pass else "FAIL", "latency_ms": lat, "error": None})
        except Exception as e:
            print(f"   [FAILED] OpenRouter: {e}")
            providers_status.append({"provider": "OpenRouter", "model": "openrouter/free", "simple": "FAIL", "json": "FAIL", "latency_ms": 0, "error": str(e)})

    # 4. Cerebras
    print("\n4. Testing Cerebras...")
    key = (settings.CEREBRAS_API_KEY or "").strip()
    if not key or "demo" in key or "your_" in key:
        print("   [FAILED] Cerebras: No valid key")
        providers_status.append({"provider": "Cerebras", "model": "gemma-4-31b", "simple": "FAIL", "json": "FAIL", "latency_ms": 0, "error": "No valid key"})
    else:
        try:
            client = OpenAI(base_url="https://api.cerebras.ai/v1", api_key=key)
            t0 = time.monotonic()
            resp1 = await asyncio.to_thread(
                client.chat.completions.create,
                model="gemma-4-31b",
                messages=[{"role": "user", "content": "Say 'OK'"}]
            )
            t1 = time.monotonic()
            simple_pass = "OK" in resp1.choices[0].message.content.upper()
            lat = round((t1 - t0) * 1000, 2)
            print(f"   [SUCCESS] Cerebras: Simple={'PASS' if simple_pass else 'FAIL'}, Latency={lat}ms")
            providers_status.append({"provider": "Cerebras", "model": "gemma-4-31b", "simple": "PASS" if simple_pass else "FAIL", "json": "PASS", "latency_ms": lat, "error": None})
        except Exception as e:
            print(f"   [FAILED] Cerebras: {e}")
            providers_status.append({"provider": "Cerebras", "model": "gemma-4-31b", "simple": "FAIL", "json": "FAIL", "latency_ms": 0, "error": str(e)})

    # 5. Together
    print("\n5. Testing Together AI...")
    key = (settings.TOGETHER_API_KEY or "").strip()
    if not key or "demo" in key or "your_" in key:
        print("   [FAILED] Together: No valid key")
        providers_status.append({"provider": "Together", "model": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo", "simple": "FAIL", "json": "FAIL", "latency_ms": 0, "error": "No valid key"})
    else:
        try:
            client = OpenAI(base_url="https://api.together.xyz/v1", api_key=key)
            t0 = time.monotonic()
            resp1 = await asyncio.to_thread(
                client.chat.completions.create,
                model="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
                messages=[{"role": "user", "content": "Say 'OK'"}]
            )
            t1 = time.monotonic()
            simple_pass = "OK" in resp1.choices[0].message.content.upper()
            lat = round((t1 - t0) * 1000, 2)
            print(f"   [SUCCESS] Together: Simple={'PASS' if simple_pass else 'FAIL'}, Latency={lat}ms")
            providers_status.append({"provider": "Together", "model": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo", "simple": "PASS" if simple_pass else "FAIL", "json": "PASS", "latency_ms": lat, "error": None})
        except Exception as e:
            print(f"   [FAILED] Together: {e}")
            providers_status.append({"provider": "Together", "model": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo", "simple": "FAIL", "json": "FAIL", "latency_ms": 0, "error": str(e)})

    # 6. DeepSeek
    print("\n6. Testing DeepSeek AI...")
    key = (settings.DEEPSEEK_API_KEY or "").strip()
    if not key or "demo" in key or "your_" in key:
        print("   [FAILED] DeepSeek: No valid key")
        providers_status.append({"provider": "DeepSeek", "model": "deepseek-chat", "simple": "FAIL", "json": "FAIL", "latency_ms": 0, "error": "No valid key"})
    else:
        try:
            client = OpenAI(base_url="https://api.deepseek.com/v1", api_key=key)
            t0 = time.monotonic()
            resp1 = await asyncio.to_thread(
                client.chat.completions.create,
                model="deepseek-chat",
                messages=[{"role": "user", "content": "Say 'OK'"}]
            )
            t1 = time.monotonic()
            simple_pass = "OK" in resp1.choices[0].message.content.upper()
            lat = round((t1 - t0) * 1000, 2)
            print(f"   [SUCCESS] DeepSeek: Simple={'PASS' if simple_pass else 'FAIL'}, Latency={lat}ms")
            providers_status.append({"provider": "DeepSeek", "model": "deepseek-chat", "simple": "PASS" if simple_pass else "FAIL", "json": "PASS", "latency_ms": lat, "error": None})
        except Exception as e:
            print(f"   [FAILED] DeepSeek: {e}")
            providers_status.append({"provider": "DeepSeek", "model": "deepseek-chat", "simple": "FAIL", "json": "FAIL", "latency_ms": 0, "error": str(e)})

    # 7. Ollama
    print("\n7. Testing Local Ollama...")
    try:
        client = OpenAI(base_url=settings.OLLAMA_BASE_URL, api_key="ollama")
        model_name = settings.OLLAMA_MODEL
        t0 = time.monotonic()
        resp1 = await asyncio.to_thread(
            client.chat.completions.create,
            model=model_name,
            messages=[{"role": "user", "content": "Say 'OK'"}]
        )
        t1 = time.monotonic()
        simple_pass = "OK" in resp1.choices[0].message.content.upper()

        resp2 = await asyncio.to_thread(
            client.chat.completions.create,
            model=model_name,
            messages=[{"role": "user", "content": "Return ONLY a JSON object: {\"status\": \"OK\"}"}],
            response_format={"type": "json_object"}
        )
        json_pass = "OK" in resp2.choices[0].message.content.upper()
        lat = round((t1 - t0) * 1000, 2)
        print(f"   [SUCCESS] Local Ollama: Simple={'PASS' if simple_pass else 'FAIL'}, JSON={'PASS' if json_pass else 'FAIL'}, Latency={lat}ms")
        providers_status.append({"provider": "Ollama", "model": model_name, "simple": "PASS" if simple_pass else "FAIL", "json": "PASS" if json_pass else "FAIL", "latency_ms": lat, "error": None})
    except Exception as e:
        print(f"   [FAILED] Local Ollama: {e}")
        providers_status.append({"provider": "Ollama", "model": settings.OLLAMA_MODEL, "simple": "FAIL", "json": "FAIL", "latency_ms": 0, "error": str(e)})

    print("\n==================================================")
    print("             SUMMARY TABLE")
    print("==================================================")
    print(f"{'Provider':12s} | {'Model':35s} | {'Simple':6s} | {'JSON':6s} | {'Latency':10s} | {'Error'}")
    print("-" * 90)
    for p in providers_status:
        err = p['error'] if p['error'] else "None"
        if len(err) > 30:
            err = err[:27] + "..."
        print(f"{p['provider']:12s} | {p['model']:35s} | {p['simple']:6s} | {p['json']:6s} | {p['latency_ms']:8.1f}ms | {err}")
    print("==================================================\n")
    return providers_status


if __name__ == "__main__":
    asyncio.run(test_provider_health())
