"""
Evaluation Runner for VentureMind AI Backend.

Executes startup evaluation benchmark cases against the production
investment_graph workflow and computes quantitative performance metrics.
"""

import os
import sys
import json
import time
import asyncio
import datetime
import argparse
from typing import List, Dict, Any, Optional

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflows.investment_workflow import investment_graph
from evaluation.schemas import StartupTestCase, ExpectedScores, CaseRunResult, AggregateMetrics
from evaluation.metrics import compute_aggregate_metrics, compare_runs
from evaluation.report import generate_cli_report
from core.logging import app_logger


from core.config import settings
from services.llm_service import llm_service


def load_dataset(dataset_path: str) -> List[StartupTestCase]:
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"Evaluation dataset file not found at: {dataset_path}")
        
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    cases = []
    for item in data:
        cases.append(StartupTestCase(**item))
    return cases


async def run_single_case(case: StartupTestCase) -> CaseRunResult:
    app_logger.info(f"[Evaluation Runner] Running case {case.case_id} ({case.company_name})...")
    
    # Enforce evaluation mode for non-mock honest analysis
    settings.EVALUATION_MODE = True
    llm_service.get_and_clear_telemetry()
    
    payload = {
        "company": case.company_name,
        "industry": case.industry,
        "funding": case.funding,
        "employees": case.employees,
        "age": case.age,
        "revenue": case.revenue,
        "growth": case.growth,
        "github_repo": case.github_url,
        "founder_names": case.founder_information,
        "agent_results": {},
        "committee_result": None
    }
    
    start_t = time.time()
    status = "completed"
    err_msg = None
    res = {}
    
    try:
        res = await investment_graph.ainvoke(payload)
    except Exception as e:
        status = "failed"
        err_msg = str(e)
        app_logger.error(f"[Evaluation Runner] Case {case.case_id} failed: {e}")
        
    end_t = time.time()
    runtime = end_t - start_t
    telemetry_records = llm_service.get_and_clear_telemetry()
    
    if status == "failed":
        return CaseRunResult(
            case_id=case.case_id,
            company_name=case.company_name,
            case_type=case.case_type,
            expected=case.expected,
            runtime_seconds=runtime,
            status="failed",
            error=err_msg,
            valid=False,
            invalidation_reason=f"Pipeline exception: {err_msg}",
            provider_telemetry=telemetry_records
        )
        
    # Extract actual outputs
    agent_results = res.get("agent_results", {})
    committee_res = res.get("committee_result")
    
    committee_dict = (
        committee_res.model_dump() if hasattr(committee_res, "model_dump")
        else dict(committee_res) if committee_res else {}
    )
    
    actual_overall_score = committee_dict.get("final_score")
    actual_verdict = committee_dict.get("verdict")
    actual_overall_confidence = committee_dict.get("overall_confidence")
    actual_company_type = committee_dict.get("category")
    
    # Map dimension scores
    agent_failures = 0
    no_data_agents = 0
    total_sources = 0
    actual_dim_scores = {}
    
    agent_name_mapping = {
        "Market Agent": "market_score",
        "Competitor Agent": "competition_score",
        "Founder Agent": "founder_score",
        "Finance Agent": "finance_score",
        "Code / GitHub Agent": "technology_score",
        "Risk Agent": "risk_score"
    }
    
    for agent_name, agent_obj in agent_results.items():
        a_dict = agent_obj.model_dump() if hasattr(agent_obj, "model_dump") else dict(agent_obj)
        a_status = a_dict.get("status", "ok")
        
        if a_status == "failed":
            agent_failures += 1
        elif a_status == "no_data":
            no_data_agents += 1
            
        sources = a_dict.get("sources", [])
        total_sources += len(sources)
        
        if agent_name in agent_name_mapping:
            dim_key = agent_name_mapping[agent_name]
            score_val = a_dict.get("score")
            if score_val is not None:
                actual_dim_scores[dim_key] = float(score_val)
                
    # Risk level estimation based on risk agent score
    risk_score = actual_dim_scores.get("risk_score", 50.0)
    if risk_score >= 80.0:
        actual_risk_level = "LOW"
    elif risk_score >= 60.0:
        actual_risk_level = "MEDIUM"
    elif risk_score >= 35.0:
        actual_risk_level = "HIGH"
    else:
        actual_risk_level = "CRITICAL"
        
    # Extract telemetry metrics
    total_calls = len(telemetry_records)
    ollama_calls = sum(1 for t in telemetry_records if t.get("provider") == "ollama" and t.get("status") == "success")
    remote_calls = sum(1 for t in telemetry_records if t.get("provider") != "ollama" and t.get("status") == "success")
    fallbacks = sum(1 for t in telemetry_records if t.get("status") in ["failed", "rate_limited"])
    
    agent_runtimes = {}
    slowest_ag = None
    slowest_time = -1.0
    fastest_ag = None
    fastest_time = float("inf")
    
    for ag_name, ag_obj in agent_results.items():
        a_dict = ag_obj.model_dump() if hasattr(ag_obj, "model_dump") else dict(ag_obj)
        # Check if agent has timing or estimate
        dur = a_dict.get("duration", 0.0)
        if dur > 0:
            ms = dur * 1000
            agent_runtimes[ag_name] = ms
            if ms > slowest_time:
                slowest_time = ms
                slowest_ag = ag_name
            if ms < fastest_time:
                fastest_time = ms
                fastest_ag = ag_name

    valid = (agent_failures == 0 and actual_overall_score is not None)
    invalidation_reason = None if valid else f"{agent_failures} agent failures encountered"

    return CaseRunResult(
        case_id=case.case_id,
        company_name=case.company_name,
        case_type=case.case_type,
        expected=case.expected,
        actual_overall_score=actual_overall_score,
        actual_verdict=actual_verdict,
        actual_overall_confidence=actual_overall_confidence,
        actual_company_type=actual_company_type,
        actual_risk_level=actual_risk_level,
        actual_dimension_scores=actual_dim_scores,
        runtime_seconds=runtime,
        total_runtime_ms=round(runtime * 1000, 2),
        status="completed",
        agent_failures=agent_failures,
        no_data_agents=no_data_agents,
        total_sources_cited=total_sources,
        valid=valid,
        invalidation_reason=invalidation_reason,
        provider_telemetry=telemetry_records,
        agent_runtimes_ms=agent_runtimes,
        fallback_count=fallbacks,
        ollama_call_count=ollama_calls,
        remote_provider_call_count=remote_calls,
        total_llm_calls=total_calls,
        slowest_agent=slowest_ag,
        fastest_agent=fastest_ag,
        raw_committee_result=committee_dict,
        raw_agent_results={
            k: (v.model_dump() if hasattr(v, "model_dump") else dict(v))
            for k, v in agent_results.items()
        }
    )


async def main():
    parser = argparse.ArgumentParser(description="VentureMind AI Evaluation Runner")
    parser.add_argument(
        "--dataset",
        type=str,
        default=os.path.join(os.path.dirname(__file__), "datasets", "startup_cases.json"),
        help="Path to evaluation dataset JSON"
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default=os.path.join(os.path.dirname(__file__), "results"),
        help="Directory to save raw execution JSON results"
    )
    parser.add_argument(
        "--compare-with",
        type=str,
        default=None,
        help="Path to previous evaluation run JSON for regression comparison"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit execution to N cases for fast debugging"
    )
    parser.add_argument(
        "--case",
        type=str,
        default=None,
        help="Run exactly one benchmark case by case_id (e.g. --case SYN-001)"
    )
    args = parser.parse_args()
    
    settings.EVALUATION_MODE = True
    cases = load_dataset(args.dataset)
    
    if args.case:
        cases = [c for c in cases if c.case_id.upper() == args.case.upper()]
        if not cases:
            print(f"Error: Benchmark case '{args.case}' not found in dataset.")
            sys.exit(1)
    elif args.limit:
        cases = cases[:args.limit]
        
    print(f"\n==================================================")
    print(f"  STARTING VENTUREMIND AI EVALUATION ({len(cases)} cases)")
    print(f"  Mode: EVALUATION (Mock Fallbacks Disabled)")
    print(f"==================================================\n")
    
    run_results = []
    for idx, case in enumerate(cases, 1):
        print(f"[{idx}/{len(cases)}] Running evaluation for '{case.company_name}' ({case.case_id})...")
        run_res = await run_single_case(case)
        run_results.append(run_res)
        valid_tag = "VALID" if run_res.valid else f"INVALID ({run_res.invalidation_reason})"
        print(f"   -> Result: Verdict={run_res.actual_verdict}, Score={run_res.actual_overall_score}, Validity={valid_tag}, Runtime={run_res.runtime_seconds:.2f}s")
        
        # Single case debug mode detailed printout
        if args.case:
            print("\n--------------------------------------------------")
            print(f"  SINGLE-CASE DEBUG REPORT: {case.case_id} ({case.company_name})")
            print("--------------------------------------------------")
            print(f"Workflow Status  : {run_res.status}")
            print(f"Case Validity    : {'VALID' if run_res.valid else 'INVALID'}")
            if not run_res.valid:
                print(f"Invalid Reason   : {run_res.invalidation_reason}")
            print(f"Expected Score   : {case.expected.overall_score} (Verdict: {case.expected.verdict})")
            print(f"Actual Score     : {run_res.actual_overall_score} (Verdict: {run_res.actual_verdict})")
            print(f"Confidence       : {run_res.actual_overall_confidence}")
            print(f"Runtime          : {run_res.runtime_seconds:.2f}s ({run_res.total_runtime_ms:.0f}ms)")
            print(f"Agent Failures   : {run_res.agent_failures}")
            print(f"No-Data Agents   : {run_res.no_data_agents}")
            print(f"Sources Sourced  : {run_res.total_sources_cited}")
            print(f"Total LLM Calls  : {run_res.total_llm_calls} (Remote: {run_res.remote_provider_call_count}, Ollama: {run_res.ollama_call_count}, Fallbacks: {run_res.fallback_count})")
            print(f"Slowest Agent    : {run_res.slowest_agent or 'N/A'}")
            print(f"Fastest Agent    : {run_res.fastest_agent or 'N/A'}")
            
            print("\n--- AGENT RESULTS & TIMING ---")
            for ag_name, ag_data in (run_res.raw_agent_results or {}).items():
                st = ag_data.get("status")
                sc = ag_data.get("score")
                cnf = ag_data.get("confidence")
                ms = run_res.agent_runtimes_ms.get(ag_name, 0.0)
                print(f"  * {ag_name:25s}: score={sc}, confidence={cnf}, status={st}, runtime={ms:.0f}ms")
                
            print("\n--- LLM PROVIDER ATTEMPTS ---")
            if run_res.provider_telemetry:
                for p in run_res.provider_telemetry:
                    err_str = f" ({p.get('error')})" if p.get('error') else ""
                    print(f"  * {p.get('provider'):12s} | model={p.get('model'):35s} | status={p.get('status'):12s} | latency={p.get('latency_ms'):.0f}ms{err_str}")
            else:
                print("  No LLM telemetry recorded.")
            print("--------------------------------------------------\n")

    metrics = compute_aggregate_metrics(run_results)
    
    reg_report = None
    if args.compare_with and os.path.exists(args.compare_with):
        with open(args.compare_with, "r", encoding="utf-8") as f:
            base_data = json.load(f)
            base_metrics = AggregateMetrics(**base_data["metrics"])
            base_time = base_data.get("timestamp", "previous")
            cand_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            reg_report = compare_runs(base_metrics, metrics, base_time, cand_time)
            
    cli_report = generate_cli_report(metrics, run_results, reg_report)
    print("\n" + cli_report)
    
    # Save raw results
    os.makedirs(args.results_dir, exist_ok=True)
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_filename = f"evaluation_{timestamp_str}.json"
    out_path = os.path.join(args.results_dir, out_filename)
    
    raw_payload = {
        "timestamp": datetime.datetime.now().isoformat(),
        "dataset_path": args.dataset,
        "metrics": metrics.model_dump(),
        "cases": [r.model_dump() for r in run_results]
    }
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(raw_payload, f, indent=2)
        
    print(f"\n[Evaluation Runner] Saved raw evaluation results to: {out_path}\n")


if __name__ == "__main__":
    asyncio.run(main())
