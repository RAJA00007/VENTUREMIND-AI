import asyncio
from openai import AsyncOpenAI
from core.config import settings

async def main():
    print("Testing OpenRouter direct streaming with API key:", settings.OPENROUTER_API_KEY[:15] + "...")
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.OPENROUTER_API_KEY
    )
    
    models_to_try = [
        "meta-llama/llama-3.3-70b-instruct:free",
        "google/gemini-2.0-flash-exp:free",
        "deepseek/deepseek-r1:free",
        "openrouter/free",
        "openrouter/auto"
    ]
    
    for model in models_to_try:
        print(f"\n--- Trying OpenRouter model: {model} ---")
        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Count from 1 to 5"}],
                stream=True,
                extra_headers={
                    "HTTP-Referer": "http://localhost:8000",
                    "X-Title": "VentureMind AI"
                }
            )
            print("Connected! Streaming chunks:")
            tokens = []
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    t = chunk.choices[0].delta.content
                    tokens.append(t)
                    print(t, end="", flush=True)
            print(f"\n[SUCCESS] Model '{model}' streamed {len(tokens)} chunks.")
            break
        except Exception as e:
            print(f"[FAIL] Model '{model}': {e}")

if __name__ == "__main__":
    asyncio.run(main())
