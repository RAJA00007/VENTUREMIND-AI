import asyncio
import time
from workflows.chat_workflow import stream_chat_workflow

async def main():
    print("--- FIRST QUERY (Model initialization) ---")
    start1 = time.monotonic()
    async for event in stream_chat_workflow([{"role": "user", "content": "Hi"}]):
        now = time.monotonic() - start1
        print(f"[{now:.3f}s] {event}")

    print("\n--- SECOND QUERY (Warm start) ---")
    start2 = time.monotonic()
    async for event in stream_chat_workflow([{"role": "user", "content": "What is IRR?"}]):
        now = time.monotonic() - start2
        print(f"[{now:.3f}s] {event}")

if __name__ == "__main__":
    asyncio.run(main())
