import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Fix Windows console encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from agents.research_agent import ResearchAgent
from agents.market_agent import MarketAgent
from agents.competitor_agent import CompetitorAgent
from agents.founder_agent import FounderAgent
from agents.finance_agent import FinanceAgent
from agents.github_agent import GitHubAgent
from agents.risk_agent import RiskAgent
from agents.prediction_agent import PredictionAgent
from agents.committee_agent import CommitteeAgent


def print_agent_header(agent_num: int, agent_name: str, role: str):
    print("\n" + "=" * 80)
    print(f" AGENT {agent_num}/9: [{agent_name.upper()}] - {role}")
    print("=" * 80)


def print_result_details(result):
    print(f"\n STATUS: {result.status.upper()}")
    print(f" SCORE:  {result.score}/100")
    print(f" CONFIDENCE: {result.confidence * 100:.0f}%")
    if result.summary:
        print(f"\n SUMMARY:\n {result.summary.strip()}")

    if result.score_breakdown:
        print("\n RUBRIC SCORE BREAKDOWN:")
        for factor in result.score_breakdown:
            print(f"  - [{factor.factor}] -> {factor.points}/{factor.max_points} pts")
            if factor.reason:
                print(f"    Reason: {factor.reason}")
            if factor.source:
                print(f"    Source: {factor.source}")

    if result.sources:
        print("\n EVIDENCE SOURCES CITED:")
        for src in result.sources:
            print(f"  * {src}")


async def main():
    target_company = "OpenAI"
    github_repo = "openai/openai-python"
    founder_names = ["Sam Altman", "Greg Brockman"]

    print(f"==> STARTING SEQUENTIAL AGENT EXECUTION DEMO FOR: '{target_company}'")
    print(f"Target Repo: {github_repo} | Founders: {', '.join(founder_names)}")

    results = {}

    # 1. Research Agent
    print_agent_header(1, "Research Agent", "Gathering baseline company profile & vision")
    print(" [Background] Searching Tavily for overview, founders, traction, and news...")
    t0 = time.time()
    research_agent = ResearchAgent()
    res1 = await research_agent.execute({"company": target_company})
    results["Research Agent"] = res1
    print(f" [Background] Completed in {time.time() - t0:.2f}s")
    print_result_details(res1)

    # 2. Market Agent
    print_agent_header(2, "Market Agent", "Evaluating TAM, SAM, CAGR growth, and industry timing")
    print(" [Background] Searching Tavily for market size, growth rate, and customer demand...")
    t0 = time.time()
    market_agent = MarketAgent()
    res2 = await market_agent.execute({"company": target_company, "industry": "AI"})
    results["Market Agent"] = res2
    print(f" [Background] Completed in {time.time() - t0:.2f}s")
    print_result_details(res2)

    # 3. Competitor Agent
    print_agent_header(3, "Competitor Agent", "Mapping competitive landscape, moat defensibility")
    print(" [Background] Searching Tavily for competitors, market rivalry, and tech differentiation...")
    t0 = time.time()
    competitor_agent = CompetitorAgent()
    res3 = await competitor_agent.execute({"company": target_company})
    results["Competitor Agent"] = res3
    print(f" [Background] Completed in {time.time() - t0:.2f}s")
    print_result_details(res3)

    # 4. Founder Agent
    print_agent_header(4, "Founder Agent", "Analyzing founder track record and domain experience")
    print(" [Background] Searching Tavily for founder pedigree, exits, and execution signals...")
    t0 = time.time()
    founder_agent = FounderAgent()
    res4 = await founder_agent.execute({"company": target_company, "founder_names": founder_names})
    results["Founder Agent"] = res4
    print(f" [Background] Completed in {time.time() - t0:.2f}s")
    print_result_details(res4)

    # 5. Finance Agent
    print_agent_header(5, "Finance Agent", "Evaluating ARR, unit economics, runway, and funding history")
    print(" [Background] Searching Tavily for financial traction, ARR, gross margins, and investors...")
    t0 = time.time()
    finance_agent = FinanceAgent()
    res5 = await finance_agent.execute({"company": target_company})
    results["Finance Agent"] = res5
    print(f" [Background] Completed in {time.time() - t0:.2f}s")
    print_result_details(res5)

    # 6. Code / GitHub Agent
    print_agent_header(6, "Code / GitHub Agent", "Deterministic code quality & repository health scoring")
    print(f" [Background] Querying GitHub REST API for {github_repo} (commits, contributors, CI/CD, tests)...")
    t0 = time.time()
    github_agent = GitHubAgent()
    res6 = await github_agent.execute({"company": target_company, "github_repo": github_repo})
    results["Code / GitHub Agent"] = res6
    print(f" [Background] Completed in {time.time() - t0:.2f}s")
    print_result_details(res6)

    # 7. Risk Agent
    print_agent_header(7, "Risk Agent", "Independent red-flag analysis (lawsuits, operational, legal)")
    print(" [Background] Searching Tavily for controversies, lawsuits, regulatory issues + cross-referencing sibling agent findings...")
    t0 = time.time()
    risk_agent = RiskAgent()
    res7 = await risk_agent.execute({"company": target_company, "other_findings": results})
    results["Risk Agent"] = res7
    print(f" [Background] Completed in {time.time() - t0:.2f}s")
    print_result_details(res7)

    # 8. Prediction Agent
    print_agent_header(8, "Prediction Agent", "Feature extraction & XGBoost/ML success probability model")
    print(" [Background] Extracting 6 core financial/firmographic metrics from gathered agent evidence...")
    t0 = time.time()
    prediction_agent = PredictionAgent()
    res8 = await prediction_agent.execute({"company": target_company, "other_findings": results})
    results["Prediction Agent"] = res8
    print(f" [Background] Completed in {time.time() - t0:.2f}s")
    print_result_details(res8)

    # 9. Investment Committee Agent
    print_agent_header(9, "Investment Committee Agent", "Synthesizing final score, verdict, & narrative")
    print(" [Background] Combining agent scores with deterministic weighting formula and trust safety rules...")
    t0 = time.time()
    committee_agent = CommitteeAgent()
    comm_res = await committee_agent.execute({"company": target_company, "agent_results": results})
    print(f" [Background] Completed in {time.time() - t0:.2f}s")

    print("\n" + "*" * 80)
    print(f" FINAL INVESTMENT DECISION FOR '{comm_res.company}'")
    print("*" * 80)
    print(f" COMPANY CATEGORY: {comm_res.category}")
    print(f" FINAL SCORE:     {comm_res.final_score}/100")
    print(f" VERDICT:         {comm_res.verdict}")
    print(f" CONFIDENCE:      {comm_res.overall_confidence * 100:.1f}%")
    print(f" DISAGREEMENT:    {comm_res.significant_disagreement}")
    if comm_res.disagreement_note:
        print(f" DISAGREEMENT NOTE: {comm_res.disagreement_note}")
    print(f"\n NARRATIVE:\n {comm_res.narrative}")
    print("=" * 80)


if __name__ == '__main__':
    asyncio.run(main())
