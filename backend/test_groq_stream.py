import asyncio
from openai import AsyncOpenAI
from core.config import settings

async def main():
    print("Testing Groq AsyncOpenAI streaming...")
    client = AsyncOpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=settings.GROQ_API_KEY
    )
    try:
        stream = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Count from 1 to 5"}],
            stream=True
        )
        print("Connected to Groq! Streaming chunks:")
        tokens = []
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                t = chunk.choices[0].delta.content
                tokens.append(t)
                print(t, end="", flush=True)
        print(f"\n[SUCCESS] Groq streamed {len(tokens)} chunks.")
    except Exception as e:
        print(f"[FAIL] Groq stream: {e}")

if __name__ == "__main__":
    asyncio.run(main())
