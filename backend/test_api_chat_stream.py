import urllib.request
import json
import time

def main():
    print("Testing /api/v1/chat HTTP streaming endpoint...")
    url = "http://localhost:8000/api/v1/chat"
    payload = json.dumps({"message": "Count from 1 to 5", "thread_id": "test_script_thread"}).encode("utf-8")
    
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    
    start_time = time.monotonic()
    try:
        with urllib.request.urlopen(req) as resp:
            print("Connected! Response headers:", resp.headers.get("Content-Type"))
            print("Streaming tokens live:")
            chunks = 0
            while True:
                chunk = resp.read(10) # Read small byte chunks
                if not chunk:
                    break
                chunks += 1
                now = time.monotonic() - start_time
                print(chunk.decode("utf-8", errors="ignore"), end="", flush=True)
            print(f"\n\n[SUCCESS] Received {chunks} streaming chunks in {time.monotonic() - start_time:.2f}s!")
    except Exception as e:
        print(f"[FAIL] HTTP stream error: {e}")

if __name__ == "__main__":
    main()
