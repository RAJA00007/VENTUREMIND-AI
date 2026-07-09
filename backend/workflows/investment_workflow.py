from typing import TypedDict, List, Any

from langgraph.graph import StateGraph, END


from agents.research_agent import ResearchAgent
from agents.market_agent import MarketAgent
from agents.competitor_agent import CompetitorAgent
from agents.risk_agent import RiskAgent
from agents.prediction_agent import PredictionAgent
from agents.committee_agent import CommitteeAgent



# ==================================================
# Shared LangGraph State
# ==================================================

class AgentState(TypedDict):

    company: str

    results: List[Any]



# ==================================================
# Initialize Agents
# ==================================================

research_agent = ResearchAgent()

market_agent = MarketAgent()

competitor_agent = CompetitorAgent()

risk_agent = RiskAgent()

prediction_agent = PredictionAgent()

committee_agent = CommitteeAgent()



# ==================================================
# Nodes
# ==================================================

async def research_node(
    state: AgentState
):

    result = await research_agent.execute(
        {
            "company": state["company"]
        }
    )


    state["results"].append(
        result
    )


    return state




async def market_node(
    state: AgentState
):

    result = await market_agent.execute(
        {
            "company": state["company"]
        }
    )


    state["results"].append(
        result
    )


    return state





async def competitor_node(
    state: AgentState
):

    result = await competitor_agent.execute(
        {
            "company": state["company"]
        }
    )


    state["results"].append(
        result
    )


    return state





async def risk_node(
    state: AgentState
):

    result = await risk_agent.execute(
        state["results"]
    )


    state["results"].append(
        result
    )


    return state





async def prediction_node(
    state: AgentState
):

    result = await prediction_agent.execute(
        state
    )


    state["results"].append(
        result
    )


    return state





async def committee_node(
    state: AgentState
):

    result = await committee_agent.execute(
        state["results"]
    )


    state["results"].append(
        result
    )


    return state





# ==================================================
# Create Workflow
# ==================================================

workflow = StateGraph(
    AgentState
)



workflow.add_node(
    "research",
    research_node
)


workflow.add_node(
    "market",
    market_node
)


workflow.add_node(
    "competitor",
    competitor_node
)


workflow.add_node(
    "risk",
    risk_node
)


workflow.add_node(
    "prediction",
    prediction_node
)


workflow.add_node(
    "committee",
    committee_node
)




# ==================================================
# Graph Flow
# ==================================================

workflow.set_entry_point(
    "research"
)



workflow.add_edge(
    "research",
    "market"
)



workflow.add_edge(
    "market",
    "competitor"
)



workflow.add_edge(
    "competitor",
    "risk"
)



workflow.add_edge(
    "risk",
    "prediction"
)



workflow.add_edge(
    "prediction",
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