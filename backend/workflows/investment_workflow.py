import asyncio
from typing import TypedDict, List, Any, Optional
from langgraph.graph import StateGraph, END

from agents.research_agent import ResearchAgent
from agents.market_agent import MarketAgent
from agents.competitor_agent import CompetitorAgent
from agents.founder_agent import FounderAgent
from agents.finance_agent import FinanceAgent
from agents.github_agent import GitHubAgent
from agents.risk_agent import RiskAgent
from agents.prediction_agent import PredictionAgent
from agents.committee_agent import CommitteeAgent
from schemas.scoring import AgentScoreResult, CommitteeResult

# ==================================================
# Shared LangGraph State
# ==================================================

class AgentState(TypedDict):
    company: str
    industry: str
    funding: float
    employees: int
    age: int
    revenue: float
    growth: float
    github_repo: Optional[str]
    founder_names: Optional[str]
    agent_results: dict[str, AgentScoreResult]
    committee_result: Optional[CommitteeResult]

# ==================================================
# Initialize Agents
# ==================================================

research_agent = ResearchAgent()
market_agent = MarketAgent()
competitor_agent = CompetitorAgent()
founder_agent = FounderAgent()
finance_agent = FinanceAgent()
github_agent = GitHubAgent()
risk_agent = RiskAgent()
prediction_agent = PredictionAgent()
committee_agent = CommitteeAgent()

# ==================================================
# Nodes
# ==================================================

async def parallel_independent_node(
    state: AgentState
) -> AgentState:
    """Runs all 6 independent scoring/data gathering agents in parallel."""
    
    # Parse founder names string to a list if provided
    founder_names_list = None
    if state.get("founder_names"):
        founder_names_list = [
            name.strip() for name in state["founder_names"].split(",") if name.strip()
        ]

    research_input = {"company": state["company"]}
    market_input = {"company": state["company"]}
    competitor_input = {"company": state["company"]}
    founder_input = {"company": state["company"], "founder_names": founder_names_list}
    finance_input = {"company": state["company"]}
    github_input = {"company": state["company"], "github_repo": state.get("github_repo")}

    results = await asyncio.gather(
        research_agent.execute(research_input),
        market_agent.execute(market_input),
        competitor_agent.execute(competitor_input),
        founder_agent.execute(founder_input),
        finance_agent.execute(finance_input),
        github_agent.execute(github_input)
    )

    state["agent_results"]["Research Agent"] = results[0]
    state["agent_results"]["Market Agent"] = results[1]
    state["agent_results"]["Competitor Agent"] = results[2]
    state["agent_results"]["Founder Agent"] = results[3]
    state["agent_results"]["Finance Agent"] = results[4]
    state["agent_results"]["Code / GitHub Agent"] = results[5]

    return state


async def risk_prediction_node(
    state: AgentState
) -> AgentState:
    """Runs Risk and Prediction agents in parallel, reusing earlier results."""
    
    risk_input = {
        "company": state["company"],
        "other_findings": state["agent_results"]
    }
    prediction_input = {
        "company": state["company"],
        "other_findings": state["agent_results"]
    }

    results = await asyncio.gather(
        risk_agent.execute(risk_input),
        prediction_agent.execute(prediction_input)
    )

    state["agent_results"]["Risk Agent"] = results[0]
    state["agent_results"]["Prediction Agent"] = results[1]

    return state


async def committee_node(
    state: AgentState
) -> AgentState:
    """Runs the Investment Committee Agent to synthesize the final decision."""
    
    result = await committee_agent.execute(
        {
            "company": state["company"],
            "agent_results": state["agent_results"]
        }
    )
    state["committee_result"] = result
    return state

# ==================================================
# Create Workflow
# ==================================================

workflow = StateGraph(
    AgentState
)

workflow.add_node(
    "parallel_independent",
    parallel_independent_node
)

workflow.add_node(
    "risk_prediction",
    risk_prediction_node
)

workflow.add_node(
    "committee",
    committee_node
)

# ==================================================
# Graph Flow
# ==================================================

workflow.set_entry_point(
    "parallel_independent"
)

workflow.add_edge(
    "parallel_independent",
    "risk_prediction"
)

workflow.add_edge(
    "risk_prediction",
    "committee"
)

workflow.add_edge(
    "committee",
    END
)

# ==================================================
# Compile
# ==================================================

investment_graph = workflow.compile()