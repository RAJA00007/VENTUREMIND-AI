import asyncio
import sys
from pathlib import Path

# Fix Windows console encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from core.config import settings
try:
    from google import genai
except ImportError:
    import google.generativeai as genai
from groq import Groq
from openai import OpenAI


async def test_all_providers():
    print("==================================================")
    print(" LLM PROVIDER DIAGNOSTIC CHECKS")
    print("==================================================")

    # 1. Gemini
    print("\n1. Testing Gemini (gemini-2.0-flash)...")
    key = (settings.GEMINI_API_KEY or "").strip()
    if not key or key == "dummy":
        print("   [FAILED] Gemini: No key configured.")
    else:
        try:
            if hasattr(genai, "Client"):
                client = genai.Client(api_key=key)
                resp = await asyncio.to_thread(
                    client.models.generate_content,
                    model="gemini-2.0-flash",
                    contents="Say 'OK'",
                )
            else:
                genai.configure(api_key=key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                resp = await asyncio.to_thread(model.generate_content, "Say 'OK'")
            print(f"   [SUCCESS] Gemini: '{resp.text.strip()}'")
        except Exception as e:
            print(f"   [FAILED] Gemini: {e}")

    # 2. Groq
    print("\n2. Testing Groq (llama-3.3-70b-versatile)...")
    key = (settings.GROQ_API_KEY or "").strip()
    if not key:
        print("   [FAILED] Groq: No key configured.")
    else:
        try:
            client = Groq(api_key=key)
            resp = await asyncio.to_thread(
                client.chat.completions.create,
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": "Say 'OK'"}],
            )
            print(f"   [SUCCESS] Groq: '{resp.choices[0].message.content.strip()}'")
        except Exception as e:
            print(f"   [FAILED] Groq: {e}")

    # 3. OpenRouter
    print("\n3. Testing OpenRouter (openrouter/free)...")
    key = (settings.OPENROUTER_API_KEY or "").strip()
    if not key:
        print("   [FAILED] OpenRouter: No key configured.")
    else:
        try:
            client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
            resp = await asyncio.to_thread(
                client.chat.completions.create,
                model="openrouter/free",
                messages=[{"role": "user", "content": "Say 'OK'"}],
            )
            print(f"   [SUCCESS] OpenRouter: '{resp.choices[0].message.content.strip()}'")
        except Exception as e:
            print(f"   [FAILED] OpenRouter: {e}")

    # 4. Cerebras
    print("\n4. Testing Cerebras AI...")
    key = (settings.CEREBRAS_API_KEY or "").strip()
    if not key or "demo" in key:
        print("   [FAILED] Cerebras: No key configured.")
    else:
        try:
            client = OpenAI(base_url="https://api.cerebras.ai/v1", api_key=key)
            models = client.models.list()
            model_ids = [m.id for m in models.data]
            print(f"   Available Cerebras models: {model_ids}")
            chosen_model = model_ids[0] if model_ids else "llama3.1-8b"
            resp = await asyncio.to_thread(
                client.chat.completions.create,
                model=chosen_model,
                messages=[{"role": "user", "content": "Say 'OK'"}],
            )
            print(f"   [SUCCESS] Cerebras ({chosen_model}): '{resp.choices[0].message.content.strip()}'")
        except Exception as e:
            print(f"   [FAILED] Cerebras: {e}")

    # 5. Together AI
    print("\n5. Testing Together AI (meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo)...")
    key = (settings.TOGETHER_API_KEY or "").strip()
    if not key or "demo" in key:
        print("   [FAILED] Together: No key configured.")
    else:
        try:
            client = OpenAI(base_url="https://api.together.xyz/v1", api_key=key)
            resp = await asyncio.to_thread(
                client.chat.completions.create,
                model="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
                messages=[{"role": "user", "content": "Say 'OK'"}],
            )
            print(f"   [SUCCESS] Together: '{resp.choices[0].message.content.strip()}'")
        except Exception as e:
            print(f"   [FAILED] Together: {e}")

    # 6. DeepSeek AI
    print("\n6. Testing DeepSeek AI (deepseek-chat)...")
    key = (settings.DEEPSEEK_API_KEY or "").strip()
    if not key or "demo" in key:
        print("   [FAILED] DeepSeek: No key configured.")
    else:
        try:
            client = OpenAI(base_url="https://api.deepseek.com/v1", api_key=key)
            resp = await asyncio.to_thread(
                client.chat.completions.create,
                model="deepseek-chat",
                messages=[{"role": "user", "content": "Say 'OK'"}],
            )
            print(f"   [SUCCESS] DeepSeek: '{resp.choices[0].message.content.strip()}'")
        except Exception as e:
            print(f"   [FAILED] DeepSeek: {e}")

    # 7. Local Ollama
    print(f"\n7. Testing Local Ollama (@ {settings.OLLAMA_BASE_URL})...")
    try:
        client = OpenAI(base_url=settings.OLLAMA_BASE_URL, api_key="ollama")
        models_resp = client.models.list()
        model_ids = []
        if models_resp and hasattr(models_resp, "data") and models_resp.data:
            model_ids = [m.id for m in models_resp.data]
        print(f"   Available local Ollama models: {model_ids}")
        target_model = settings.OLLAMA_MODEL if settings.OLLAMA_MODEL in model_ids else (model_ids[0] if model_ids else settings.OLLAMA_MODEL)
        resp = await asyncio.to_thread(
            client.chat.completions.create,
            model=target_model,
            messages=[{"role": "user", "content": "Say 'OK'"}],
        )
        print(f"   [SUCCESS] Local Ollama ({target_model}): '{resp.choices[0].message.content.strip()}'")
    except Exception as e:
        print(f"   [FAILED] Local Ollama: {e}")

    print("\n==================================================")


if __name__ == "__main__":
    asyncio.run(test_all_providers())
