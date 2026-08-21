import asyncio
import os
import sys
import time
from typing import Dict, Any

# Ensure backend root is on sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from core.config import settings
from services.llm_service import llm_service
from evaluation.runner import load_dataset, run_single_case


async def force_ollama_generate(prompt: str, bypass_cache: bool = False) -> str:
    """Helper that forces all LLM requests to use Local Ollama directly."""
    return await llm_service._try_ollama_fallback(prompt)


async def run_ollama_concurrency_test(concurrency_limit: int) -> Dict[str, Any]:
    print(f"\n---> Running Ollama Concurrency Experiment: OLLAMA_MAX_CONCURRENCY = {concurrency_limit}")
    
    settings.EVALUATION_MODE = True
    settings.OLLAMA_MAX_CONCURRENCY = concurrency_limit
    
    # Store original generate method
    orig_generate = llm_service.generate
    
    # Monkey-patch generate to force Ollama usage specifically for this experiment
    llm_service.generate = force_ollama_generate
    
    dataset_path = os.path.join(backend_dir, "evaluation", "datasets", "startup_cases.json")
    cases = load_dataset(dataset_path)
    syn001 = [c for c in cases if c.case_id == "SYN-001"][0]
    
    start_t = time.time()
    try:
        res = await run_single_case(syn001)
        runtime = time.time() - start_t
        
        telemetry = res.provider_telemetry or []
        ollama_telemetry = [t for t in telemetry if t.get("provider") == "ollama" and t.get("status") == "success"]
        latencies = [t.get("latency_ms", 0) for t in ollama_telemetry]
        avg_lat = (sum(latencies) / len(latencies)) if latencies else 0.0
        max_lat = max(latencies) if latencies else 0.0
        
        return {
            "concurrency": concurrency_limit,
            "total_runtime_s": round(runtime, 2),
            "avg_request_ms": round(avg_lat, 1),
            "max_request_ms": round(max_lat, 1),
            "agent_failures": res.agent_failures,
            "valid": res.valid,
            "actual_score": res.actual_overall_score,
            "verdict": res.actual_verdict
        }
    finally:
        # Restore original generate method
        llm_service.generate = orig_generate


async def main():
    print("==================================================")
    print("      OLLAMA CONCURRENCY EXPERIMENT (SYN-001)")
    print("==================================================")
    
    results = []
    for c in [1, 2, 6]:
        r = await run_ollama_concurrency_test(c)
        results.append(r)
        
    print("\n==================================================")
    print("         OLLAMA CONCURRENCY EXPERIMENT RESULTS")
    print("==================================================")
    print(f"{'Concurrency':12s} | {'Total Runtime':13s} | {'Avg Req (ms)':13s} | {'Max Req (ms)':13s} | {'Failures':9s} | {'Valid'}")
    print("-" * 80)
    for r in results:
        print(f"{r['concurrency']:<12d} | {r['total_runtime_s']:11.2f}s | {r['avg_request_ms']:11.1f}ms | {r['max_request_ms']:11.1f}ms | {r['agent_failures']:<9d} | {'YES' if r['valid'] else 'NO'}")
    print("==================================================\n")


if __name__ == "__main__":
    asyncio.run(main())
