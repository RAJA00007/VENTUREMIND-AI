"""
Metrics Calculation Engine for VentureMind AI Evaluation.
"""

from typing import List, Dict, Any, Tuple
import math
from evaluation.schemas import CaseRunResult, AggregateMetrics, RegressionReport


def calculate_mae(expected_list: List[float], actual_list: List[float]) -> float:
    if not expected_list or len(expected_list) != len(actual_list):
        return 0.0
    return sum(abs(e - a) for e, a in zip(expected_list, actual_list)) / len(expected_list)


def calculate_median(values: List[float]) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    n = len(sorted_v)
    mid = n // 2
    if n % 2 == 0:
        return (sorted_v[mid - 1] + sorted_v[mid]) / 2.0
    return sorted_v[mid]


def calculate_verdict_metrics(
    runs: List[CaseRunResult]
) -> Tuple[float, Dict[str, Dict[str, int]]]:
    verdicts = ["INVEST", "WATCH", "PASS"]
    matrix = {e: {a: 0 for a in verdicts} for e in verdicts}
    
    correct = 0
    total = 0
    
    for r in runs:
        if r.status != "completed" or not r.valid or not r.actual_verdict:
            continue
        exp = r.expected.verdict.upper()
        act = r.actual_verdict.upper()
        if exp in matrix and act in matrix[exp]:
            matrix[exp][act] += 1
        if exp == act:
            correct += 1
        total += 1
        
    acc = (correct / total * 100.0) if total > 0 else 0.0
    return acc, matrix


def calculate_risk_classification_metrics(
    runs: List[CaseRunResult]
) -> Tuple[float, float, float, float]:
    valid_runs = [r for r in runs if r.status == "completed" and r.valid and r.actual_risk_level]
    if not valid_runs:
        return 0.0, 0.0, 0.0, 0.0
        
    correct = 0
    for r in valid_runs:
        exp = r.expected.risk_level.upper()
        act = r.actual_risk_level.upper()
        if exp == act:
            correct += 1
            
    accuracy = (correct / len(valid_runs)) * 100.0
    
    # Calculate macro precision, recall, F1 across risk levels
    levels = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    precisions = []
    recalls = []
    
    for lvl in levels:
        tp = sum(1 for r in valid_runs if r.expected.risk_level.upper() == lvl and r.actual_risk_level.upper() == lvl)
        fp = sum(1 for r in valid_runs if r.expected.risk_level.upper() != lvl and r.actual_risk_level.upper() == lvl)
        fn = sum(1 for r in valid_runs if r.expected.risk_level.upper() == lvl and r.actual_risk_level.upper() != lvl)
        
        prec = (tp / (tp + fp)) if (tp + fp) > 0 else 1.0 if (tp == 0 and fp == 0) else 0.0
        rec = (tp / (tp + fn)) if (tp + fn) > 0 else 1.0 if (tp == 0 and fn == 0) else 0.0
        
        precisions.append(prec)
        recalls.append(rec)
        
    avg_prec = (sum(precisions) / len(levels)) * 100.0
    avg_rec = (sum(recalls) / len(levels)) * 100.0
    
    if (avg_prec + avg_rec) > 0:
        f1 = (2 * avg_prec * avg_rec) / (avg_prec + avg_rec)
    else:
        f1 = 0.0
        
    return accuracy, avg_prec, avg_rec, f1


def compute_aggregate_metrics(runs: List[CaseRunResult]) -> AggregateMetrics:
    total_cases = len(runs)
    completed_runs = [r for r in runs if r.status == "completed"]
    valid_completed_runs = [r for r in completed_runs if r.valid]
    completed_cases = len(completed_runs)
    valid_cases_count = len(valid_completed_runs)
    invalid_cases_count = total_cases - valid_cases_count
    failed_cases = total_cases - completed_cases
    provider_failures_count = sum(1 for r in runs if r.agent_failures > 0 or not r.valid)
    
    workflow_success_rate = (completed_cases / total_cases * 100.0) if total_cases > 0 else 0.0
    
    # Agent failure metrics
    total_agent_failures = sum(r.agent_failures for r in runs)
    total_agent_invocations = max(1, total_cases * 8)
    agent_failure_rate = (total_agent_failures / total_agent_invocations * 100.0)
    
    # Score errors calculated ONLY on valid completed runs
    exp_scores = [r.expected.overall_score for r in valid_completed_runs if r.actual_overall_score is not None]
    act_scores = [r.actual_overall_score for r in valid_completed_runs if r.actual_overall_score is not None]
    
    errors = [abs(e - a) for e, a in zip(exp_scores, act_scores)] if exp_scores else [0.0]
    
    overall_score_mae = sum(errors) / len(errors) if exp_scores else 0.0
    overall_score_median_ae = calculate_median(errors) if exp_scores else 0.0
    overall_score_max_error = max(errors) if exp_scores else 0.0
    
    # Verdict metrics (calculated only on valid completed runs inside helper)
    verdict_acc, confusion_matrix = calculate_verdict_metrics(runs)
    
    # Risk classification metrics (calculated only on valid completed runs inside helper)
    risk_acc, risk_prec, risk_rec, risk_f1 = calculate_risk_classification_metrics(runs)
    
    # Dimension MAEs (calculated only on valid completed runs)
    dimensions = ["market_score", "competition_score", "founder_score", "finance_score", "technology_score", "risk_score"]
    dim_maes = {}
    for d in dimensions:
        d_exp = []
        d_act = []
        for r in valid_completed_runs:
            exp_val = getattr(r.expected, d, None)
            act_val = r.actual_dimension_scores.get(d)
            if exp_val is not None and act_val is not None:
                d_exp.append(exp_val)
                d_act.append(act_val)
        dim_maes[d] = calculate_mae(d_exp, d_act) if d_exp else 0.0
        
    # High confidence error rate & overconfidence flags
    high_conf_runs = [r for r in valid_completed_runs if (r.actual_overall_confidence or 0.0) >= 0.80]
    overconfident_cases = []
    
    for r in valid_completed_runs:
        conf = r.actual_overall_confidence or 0.0
        act_s = r.actual_overall_score or 0.0
        exp_s = r.expected.overall_score
        score_err = abs(exp_s - act_s)
        
        if conf >= 0.80 and score_err > 15.0:
            r.overconfident_flag = True
            overconfident_cases.append(r.case_id)
            
    high_confidence_error_rate = (
        (len(overconfident_cases) / len(high_conf_runs) * 100.0) if high_conf_runs else 0.0
    )
    
    # Performance metrics
    runtimes = [r.runtime_seconds for r in runs if r.runtime_seconds > 0]
    sorted_runtimes = sorted(runtimes) if runtimes else []
    total_runtime = sum(runtimes)
    avg_runtime = total_runtime / len(runtimes) if runtimes else 0.0
    min_runtime = min(runtimes) if runtimes else 0.0
    max_runtime = max(runtimes) if runtimes else 0.0
    
    p50_runtime = calculate_median(runtimes) if runtimes else 0.0
    p95_index = min(len(sorted_runtimes) - 1, int(len(sorted_runtimes) * 0.95)) if sorted_runtimes else 0
    p95_runtime = sorted_runtimes[p95_index] if sorted_runtimes else 0.0

    # Provider telemetry analysis across cases
    provider_counts: Dict[str, int] = {}
    total_calls = 0
    ollama_calls = 0
    remote_calls = 0
    total_fallbacks = 0
    all_agent_runtimes: Dict[str, List[float]] = {}

    for r in runs:
        total_calls += r.total_llm_calls
        ollama_calls += r.ollama_call_count
        remote_calls += r.remote_provider_call_count
        total_fallbacks += r.fallback_count

        for p_record in r.provider_telemetry:
            if p_record.get("status") == "success":
                prov = p_record.get("provider", "unknown").lower()
                provider_counts[prov] = provider_counts.get(prov, 0) + 1

        for ag_name, ag_time in r.agent_runtimes_ms.items():
            if ag_name not in all_agent_runtimes:
                all_agent_runtimes[ag_name] = []
            all_agent_runtimes[ag_name].append(ag_time)

    avg_agent_lat = 0.0
    slowest_ag = "N/A"
    slowest_ag_time = -1.0
    if all_agent_runtimes:
        flat_latencies = [t for times in all_agent_runtimes.values() for t in times]
        avg_agent_lat = (sum(flat_latencies) / len(flat_latencies)) if flat_latencies else 0.0
        
        for ag_name, times in all_agent_runtimes.items():
            ag_avg = sum(times) / len(times)
            if ag_avg > slowest_ag_time:
                slowest_ag_time = ag_avg
                slowest_ag = ag_name

    ollama_pct = (ollama_calls / total_calls * 100.0) if total_calls > 0 else 0.0
    remote_pct = (remote_calls / total_calls * 100.0) if total_calls > 0 else 0.0
    fallback_pct = (total_fallbacks / max(1, total_calls) * 100.0) if total_calls > 0 else 0.0

    # Source citations
    sources_cited = [r.total_sources_cited for r in completed_runs]
    avg_sources = sum(sources_cited) / len(sources_cited) if sources_cited else 0.0
    
    return AggregateMetrics(
        total_cases=total_cases,
        completed_cases=completed_cases,
        valid_cases_count=valid_cases_count,
        invalid_cases_count=invalid_cases_count,
        provider_failures_count=provider_failures_count,
        failed_cases=failed_cases,
        workflow_success_rate=workflow_success_rate,
        agent_failure_rate=agent_failure_rate,
        overall_score_mae=overall_score_mae,
        overall_score_median_ae=overall_score_median_ae,
        overall_score_max_error=overall_score_max_error,
        verdict_accuracy=verdict_acc,
        verdict_confusion_matrix=confusion_matrix,
        risk_classification_accuracy=risk_acc,
        risk_classification_precision=risk_prec,
        risk_classification_recall=risk_rec,
        risk_classification_f1=risk_f1,
        dimension_maes=dim_maes,
        high_confidence_error_rate=high_confidence_error_rate,
        overconfident_case_ids=overconfident_cases,
        total_runtime_seconds=total_runtime,
        avg_runtime_seconds=avg_runtime,
        p50_runtime_seconds=round(p50_runtime, 2),
        p95_runtime_seconds=round(p95_runtime, 2),
        min_runtime_seconds=min_runtime,
        max_runtime_seconds=max_runtime,
        avg_sources_per_case=avg_sources,
        slowest_agent=slowest_ag,
        avg_agent_latency_ms=round(avg_agent_lat, 1),
        ollama_percentage=round(ollama_pct, 1),
        remote_provider_percentage=round(remote_pct, 1),
        fallback_percentage=round(fallback_pct, 1),
        provider_usage_breakdown=provider_counts,
        total_llm_calls=total_calls,
        total_fallbacks=total_fallbacks,
        llm_token_usage="NOT AVAILABLE",
        llm_estimated_cost="NOT AVAILABLE",
        hallucination_accuracy="NOT MEASURED"
    )



def compare_runs(baseline: AggregateMetrics, candidate: AggregateMetrics, base_time: str, cand_time: str) -> RegressionReport:
    mae_diff = candidate.overall_score_mae - baseline.overall_score_mae
    verdict_diff = candidate.verdict_accuracy - baseline.verdict_accuracy
    success_diff = candidate.workflow_success_rate - baseline.workflow_success_rate
    latency_diff = candidate.avg_runtime_seconds - baseline.avg_runtime_seconds
    
    details = []
    
    # Lower MAE is better
    if mae_diff < -1.0:
        details.append(f"Overall MAE improved by {abs(mae_diff):.2f} points.")
    elif mae_diff > 1.0:
        details.append(f"Overall MAE regressed by {mae_diff:.2f} points.")
        
    # Higher verdict accuracy is better
    if verdict_diff > 2.0:
        details.append(f"Verdict accuracy improved by +{verdict_diff:.1f}%.")
    elif verdict_diff < -2.0:
        details.append(f"Verdict accuracy regressed by {verdict_diff:.1f}%.")
        
    # Higher success rate is better
    if success_diff < 0:
        details.append(f"Workflow success rate dropped by {abs(success_diff):.1f}%.")
        
    # Status determination
    if mae_diff <= 0.5 and verdict_diff >= -1.0 and success_diff >= 0:
        if mae_diff < -0.5 or verdict_diff > 1.0:
            status = "IMPROVED"
        else:
            status = "UNCHANGED"
    else:
        status = "REGRESSED"
        
    return RegressionReport(
        baseline_timestamp=base_time,
        candidate_timestamp=cand_time,
        overall_score_mae_change=mae_diff,
        verdict_accuracy_change=verdict_diff,
        workflow_success_rate_change=success_diff,
        avg_latency_change=latency_diff,
        status=status,
        details=details
    )
