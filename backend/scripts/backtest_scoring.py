import os
import csv
import sys
import math
import argparse
import datetime
from typing import Dict, Any, List

# Add backend directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.scoring_formula import combine_scores, WEIGHT_PROFILES
from schemas.scoring import AgentScoreResult, ScoreFactor, BusinessProfile
from ml.predictor import startup_predictor
from core.logging import app_logger

def classify_company_profile(industry: str) -> str:
    industry_lower = industry.lower().strip()
    if industry_lower in ["ai", "productivity", "social", "design"]:
        return "TECH"
    elif industry_lower in ["hardware", "aerospace", "services"]:
        return "NON_TECH"
    else:
        return "HYBRID"

def pearson_correlation(x: List[float], y: List[float]) -> float:
    n = len(x)
    if n == 0: return 0.0
    avg_x = sum(x) / n
    avg_y = sum(y) / n
    diffprod = 0.0
    xdiff2 = 0.0
    ydiff2 = 0.0
    for idx in range(n):
        xdiff = x[idx] - avg_x
        ydiff = y[idx] - avg_y
        diffprod += xdiff * ydiff
        xdiff2 += xdiff * xdiff
        ydiff2 += ydiff * ydiff
    if xdiff2 == 0 or ydiff2 == 0:
        return 0.0
    return diffprod / math.sqrt(xdiff2 * ydiff2)

def spearman_correlation(x: List[float], y: List[float]) -> float:
    def get_ranks(val_list):
        sorted_vals = sorted(enumerate(val_list), key=lambda x: x[1])
        ranks = [0] * len(val_list)
        for rank, (orig_idx, _) in enumerate(sorted_vals):
            ranks[orig_idx] = rank + 1
        return ranks
    
    n = len(x)
    if n == 0: return 0.0
    ranks_x = get_ranks(x)
    ranks_y = get_ranks(y)
    
    d_squared_sum = sum((ranks_x[i] - ranks_y[i]) ** 2 for i in range(n))
    return 1.0 - (6.0 * d_squared_sum) / (n * (n**2 - 1)) if n > 1 else 0.0

def run_backtest(profile_filter: str):
    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ml", "dataset", "startup_data.csv")
    
    if not os.path.exists(csv_path):
        print(f"Error: dataset file not found at {csv_path}")
        return
        
    rows = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
            
    filtered_rows = []
    for r in rows:
        company_profile = classify_company_profile(r["industry"])
        if profile_filter == "all" or company_profile == profile_filter:
            filtered_rows.append((r, company_profile))
            
    if not filtered_rows:
        print(f"No rows match weight profile filter: {profile_filter}")
        return
        
    scores = []
    actuals = []
    results_list = []
    
    # Rationale for Finance scoring mappings:
    # 40% based on Revenue (capped at 50M for max score)
    # 30% based on Funding (capped at 200M for max score)
    # 30% based on growth rate (capped at 100% for max score, min 0%)
    
    for row, profile in filtered_rows:
        # Finance metrics mapping
        rev = float(row["revenue_million"])
        funding = float(row["funding_million"])
        growth = float(row["growth_rate"])
        
        rev_points = min(40.0, (rev / 50.0) * 40.0) if rev > 0 else 0.0
        fund_points = min(30.0, (funding / 200.0) * 30.0) if funding > 0 else 0.0
        growth_points = min(30.0, max(0.0, (growth / 100.0) * 30.0))
        
        fin_score = round(rev_points + fund_points + growth_points, 1)
        
        finance_result = AgentScoreResult(
            agent="Finance Agent",
            score=fin_score,
            score_breakdown=[
                ScoreFactor(factor="Revenue Sizing", points=rev_points, max_points=40.0, reason=f"Revenue is {rev}M"),
                ScoreFactor(factor="Funding Traction", points=fund_points, max_points=30.0, reason=f"Total funding is {funding}M"),
                ScoreFactor(factor="Growth Sizing", points=growth_points, max_points=30.0, reason=f"Growth rate is {growth}%")
            ],
            summary=f"Synthetic finance score for {row['company']}.",
            confidence=1.0,
            sources=[],
            status="ok"
        )
        
        # Prediction metrics mapping
        pred_res = startup_predictor.predict(
            industry=row["industry"],
            funding=funding,
            employees=int(row["employees"]),
            age=int(row["age_years"]),
            revenue=rev,
            growth=growth
        )
        pred_score = pred_res["success_probability"]
        
        pred_result = AgentScoreResult(
            agent="Prediction Agent",
            score=pred_score,
            score_breakdown=[
                ScoreFactor(factor="Success Probability", points=pred_score, max_points=100.0, reason=f"ML Prediction result: {pred_res['prediction']}")
            ],
            summary=f"ML predictor success probability is {pred_score}%",
            confidence=1.0,
            sources=[],
            status="ok"
        )
        
        agent_results = {
            "Finance Agent": finance_result,
            "Prediction Agent": pred_result
        }
        
        # Combine scores using core formula
        combined = combine_scores(agent_results, category=profile)
        
        actual = 1 if row["status"].strip().lower() == "success" else 0
        scores.append(combined.final_score)
        actuals.append(actual)
        
        results_list.append({
            "company": row["company"],
            "profile": profile,
            "actual_status": row["status"],
            "finance_score": fin_score,
            "prediction_score": pred_score,
            "final_score": combined.final_score
        })
        
    print(f"\nEvaluating weight profile filter: {profile_filter.upper()} (Total rows: {len(filtered_rows)})")
    
    # 1. Pearson and Spearman Correlation
    p_corr = pearson_correlation(scores, actuals)
    s_corr = spearman_correlation(scores, actuals)
    
    print("\n" + "="*55)
    print(f"CORRELATION METRICS")
    print("="*55)
    print(f"Pearson Correlation:  {p_corr:.4f}")
    print(f"Spearman Correlation: {s_corr:.4f}")
    print("="*55)

    # 2. Confusion Matrix at Production Thresholds (INVEST >= 75, WATCH >= 50, else PASS)
    invest_success = 0
    invest_failed = 0
    watch_success = 0
    watch_failed = 0
    pass_success = 0
    pass_failed = 0
    
    for item in results_list:
        score = item["final_score"]
        actual_val = item["actual_status"].strip().lower()
        if score >= 75:
            if actual_val == "success": invest_success += 1
            else: invest_failed += 1
        elif score >= 50:
            if actual_val == "success": watch_success += 1
            else: watch_failed += 1
        else:
            if actual_val == "success": pass_success += 1
            else: pass_failed += 1
            
    print("\nCONFUSION MATRIX (Production Thresholds: INVEST>=75, WATCH>=50)")
    print("-" * 55)
    print(f"{'Actual':<10} | {'INVEST (>=75)':<15} | {'WATCH (50-74)':<15} | {'PASS (<50)':<10}")
    print("-" * 55)
    print(f"{'SUCCESS':<10} | {invest_success:<15} | {watch_success:<15} | {pass_success:<10}")
    print(f"{'FAILED':<10} | {invest_failed:<15} | {watch_failed:<15} | {pass_failed:<10}")
    print("-" * 55)

    # 3. Threshold Sweep Metrics
    sweep_results = []
    for threshold in range(0, 101, 5):
        tp = 0
        fp = 0
        fn = 0
        tn = 0
        for item in results_list:
            score = item["final_score"]
            actual_val = 1 if item["actual_status"].strip().lower() == "success" else 0
            pred_val = 1 if score >= threshold else 0
            if actual_val == 1 and pred_val == 1: tp += 1
            elif actual_val == 0 and pred_val == 1: fp += 1
            elif actual_val == 1 and pred_val == 0: fn += 1
            else: tn += 1
            
        precision = (tp / (tp + fp) * 100) if (tp + fp) > 0 else 0.0
        recall = (tp / (tp + fn) * 100) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        sweep_results.append((threshold, precision, recall, f1))
        
    print("\nTHRESHOLD SWEEP PERFORMANCE")
    print("-" * 55)
    print(f"{'Threshold':<10} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10}")
    print("-" * 55)
    for t, p, r, f1 in sweep_results:
        print(f"{t:<10} | {p:<9.1f}% | {r:<9.1f}% | {f1:<9.1f}%")
    print("-" * 55)

    # 4. Recommendation analysis
    # Find threshold that maximizes F1 score
    best_thresh, best_prec, best_rec, best_f1 = max(sweep_results, key=lambda x: x[3])
    print(f"\nRecommendation:")
    print(f"Optimal F1 threshold is {best_thresh} (Precision: {best_prec:.1f}%, Recall: {best_rec:.1f}%, F1: {best_f1:.1f}%).")
    if best_thresh != 75:
        print(f"Consider adjusting your INVEST_THRESHOLD from 75 to {best_thresh} based on this cohort.")
    else:
        print("INVEST_THRESHOLD of 75 matches the optimal F1 threshold for this cohort.")
        
    # Write report CSV
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(reports_dir, f"backtest_results_{timestamp}.csv")
    
    with open(report_file, mode="w", newline="", encoding="utf-8") as rf:
        writer = csv.writer(rf)
        writer.writerow(["Company", "Profile", "Actual Status", "Finance Score", "Prediction Score", "Final Score"])
        for item in results_list:
            writer.writerow([
                item["company"],
                item["profile"],
                item["actual_status"],
                item["finance_score"],
                item["prediction_score"],
                item["final_score"]
            ])
            
    print(f"\nReport successfully saved to: {report_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest scoring formula against historical CSV startup data")
    parser.add_argument("--profile", type=str, choices=["TECH", "NON_TECH", "HYBRID", "all"], default="all",
                        help="Filter backtest by company profile (TECH/NON_TECH/HYBRID/all)")
    args = parser.parse_args()
    
    run_backtest(args.profile)
