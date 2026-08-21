"""
Report Formatting Engine for VentureMind AI Evaluation.
"""

from typing import List, Optional
from evaluation.schemas import CaseRunResult, AggregateMetrics, RegressionReport


def generate_cli_report(metrics: AggregateMetrics, runs: List[CaseRunResult], reg_report: Optional[RegressionReport] = None) -> str:
    lines = []
    lines.append("==================================================")
    lines.append("        VENTUREMIND AI EVALUATION REPORT          ")
    lines.append("==================================================")
    lines.append(f"Total Test Cases:            {metrics.total_cases}")
    lines.append(f"Completed Cases:             {metrics.completed_cases}")
    lines.append(f"Valid Benchmark Cases:       {metrics.valid_cases_count}")
    lines.append(f"Invalid / Incomplete Cases:  {metrics.invalid_cases_count}")
    lines.append(f"Provider Failure Events:     {metrics.provider_failures_count}")
    lines.append(f"Failed Cases:                {metrics.failed_cases}")
    lines.append(f"Workflow Success Rate:       {metrics.workflow_success_rate:.1f}%")
    lines.append(f"Agent Failure Rate:          {metrics.agent_failure_rate:.1f}%")
    lines.append("--------------------------------------------------")
    lines.append(f"Overall Score MAE:           {metrics.overall_score_mae:.2f} points")
    lines.append(f"Overall Score Median AE:     {metrics.overall_score_median_ae:.2f} points")
    lines.append(f"Overall Score Max Error:     {metrics.overall_score_max_error:.2f} points")
    lines.append(f"Verdict Accuracy:            {metrics.verdict_accuracy:.1f}%")
    lines.append(f"Risk Classification F1:      {metrics.risk_classification_f1:.2f}")
    lines.append(f"High Confidence Error Rate:  {metrics.high_confidence_error_rate:.1f}%")
    lines.append(f"Overconfident Cases:         {len(metrics.overconfident_case_ids)} {metrics.overconfident_case_ids}")
    lines.append("--------------------------------------------------")
    lines.append(f"Average Case Latency:        {metrics.avg_runtime_seconds:.2f} seconds")
    lines.append(f"P50 Case Latency:            {metrics.p50_runtime_seconds:.2f} seconds")
    lines.append(f"P95 Case Latency:            {metrics.p95_runtime_seconds:.2f} seconds")
    lines.append(f"Total Evaluation Runtime:    {metrics.total_runtime_seconds:.2f} seconds")
    lines.append(f"Slowest Agent (Avg):         {metrics.slowest_agent}")
    lines.append(f"Average Agent Latency:       {metrics.avg_agent_latency_ms:.0f} ms")
    lines.append(f"Provider Breakdown:          {metrics.provider_usage_breakdown}")
    lines.append(f"Remote Provider Calls:       {metrics.remote_provider_percentage:.1f}%")
    lines.append(f"Ollama Calls:                {metrics.ollama_percentage:.1f}%")
    lines.append(f"Fallback Percentage:         {metrics.fallback_percentage:.1f}%")
    lines.append(f"Average Sources Per Case:    {metrics.avg_sources_per_case:.1f}")
    lines.append(f"LLM Token Usage:             {metrics.llm_token_usage}")
    lines.append(f"LLM Estimated Cost:          {metrics.llm_estimated_cost}")
    lines.append(f"Hallucination Accuracy:      {metrics.hallucination_accuracy}")
    lines.append("==================================================")
    lines.append("             DIMENSION PERFORMANCE MAE            ")
    lines.append("==================================================")
    for dim, mae in metrics.dimension_maes.items():
        clean_dim = dim.replace("_score", "").capitalize()
        lines.append(f"{clean_dim:<25}: {mae:.2f} MAE")

    lines.append("==================================================")
    lines.append("             VERDICT CONFUSION MATRIX             ")
    lines.append("==================================================")
    lines.append("Expected \\ Actual | INVEST | WATCH | PASS |")
    lines.append("------------------------------------------")
    for exp_k, row in metrics.verdict_confusion_matrix.items():
        lines.append(f"{exp_k:<16} | {row.get('INVEST', 0):<6} | {row.get('WATCH', 0):<5} | {row.get('PASS', 0):<4} |")

    # Worst & Best Performing Cases
    completed_runs = [r for r in runs if r.status == "completed" and r.actual_overall_score is not None]
    if completed_runs:
        sorted_by_err = sorted(completed_runs, key=lambda r: abs(r.expected.overall_score - r.actual_overall_score), reverse=True)
        lines.append("==================================================")
        lines.append("             WORST PERFORMING CASES               ")
        lines.append("==================================================")
        for r in sorted_by_err[:3]:
            err = abs(r.expected.overall_score - r.actual_overall_score)
            lines.append(f"Case: {r.case_id} ({r.company_name})")
            lines.append(f"  Expected Score: {r.expected.overall_score:.1f} | Actual: {r.actual_overall_score:.1f} (Error: {err:.1f})")
            lines.append(f"  Expected Verdict: {r.expected.verdict} | Actual: {r.actual_verdict}")
            lines.append(f"  Overconfident Flag: {r.overconfident_flag}")

        lines.append("==================================================")
        lines.append("              BEST PERFORMING CASES               ")
        lines.append("==================================================")
        for r in sorted_by_err[-3:]:
            err = abs(r.expected.overall_score - r.actual_overall_score)
            lines.append(f"Case: {r.case_id} ({r.company_name})")
            lines.append(f"  Expected Score: {r.expected.overall_score:.1f} | Actual: {r.actual_overall_score:.1f} (Error: {err:.1f})")
            lines.append(f"  Expected Verdict: {r.expected.verdict} | Actual: {r.actual_verdict}")

    if reg_report:
        lines.append("==================================================")
        lines.append("               REGRESSION COMPARISON              ")
        lines.append("==================================================")
        lines.append(f"Regression Status:           {reg_report.status}")
        lines.append(f"MAE Delta:                   {reg_report.overall_score_mae_change:+.2f}")
        lines.append(f"Verdict Accuracy Delta:      {reg_report.verdict_accuracy_change:+.1f}%")
        lines.append(f"Avg Latency Delta:           {reg_report.avg_latency_change:+.2f}s")
        for detail in reg_report.details:
            lines.append(f" - {detail}")

    lines.append("==================================================")
    lines.append("                 RECOMMENDATIONS                  ")
    lines.append("==================================================")
    rec_count = 1
    if metrics.overall_score_mae > 10.0:
        lines.append(f"{rec_count}. High MAE ({metrics.overall_score_mae:.2f} pts). Calibrate scoring weights in agents/scoring_formula.py.")
        rec_count += 1
    if metrics.high_confidence_error_rate > 15.0:
        lines.append(f"{rec_count}. High Overconfidence Error Rate ({metrics.high_confidence_error_rate:.1f}%). Adjust trust service confidence weighting.")
        rec_count += 1
    if metrics.dimension_maes.get("risk_score", 0) > 12.0:
        lines.append(f"{rec_count}. High Risk Dimension Error. Refine Risk Agent prompt and penalty factors.")
        rec_count += 1
    if rec_count == 1:
        lines.append("1. Performance is within acceptable benchmark thresholds. Continue expanding golden dataset cases.")

    lines.append("==================================================")
    return "\n".join(lines)
