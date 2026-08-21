import pytest
import asyncio
from langchain_core.messages import HumanMessage
from core.config import settings
from workflows.chat_workflow import chatbot, _init_checkpointer
from workflows.investment_workflow import investment_graph

def test_postgres_checkpoint_persistence_and_restart():
    """Test 1 & Test 2: Thread persistence & state restoration across checkpointer re-initialization."""
    thread_id = "test-persistence-001"
    config = {"configurable": {"thread_id": thread_id}}

    # 1. Send first message
    msg1 = "My startup is called TestAI."
    res1 = chatbot.invoke({"messages": [HumanMessage(content=msg1)]}, config=config)
    assert len(res1["messages"]) >= 2
    assert res1["messages"][0].content == msg1

    # 2. Send second message in same thread
    msg2 = "What metrics do you track for it?"
    res2 = chatbot.invoke({"messages": [HumanMessage(content=msg2)]}, config=config)
    # Total messages in thread should accumulate (at least 4: human, ai, human, ai)
    assert len(res2["messages"]) >= 4

    # 3. Simulate backend restart: re-initialize a new Postgres checkpointer instance from scratch
    fresh_checkpointer = _init_checkpointer()
    state = fresh_checkpointer.get(config)
    assert state is not None
    saved_messages = state.get("channel_values", {}).get("messages", [])
    assert len(saved_messages) >= 4
    assert any("TestAI" in getattr(m, "content", "") for m in saved_messages)


def test_thread_isolation():
    """Test 3: Verify different thread IDs maintain strictly isolated state."""
    config_a = {"configurable": {"thread_id": "thread-A-unique"}}
    config_b = {"configurable": {"thread_id": "thread-B-unique"}}

    chatbot.invoke({"messages": [HumanMessage(content="Apple is a tech company.")]}, config=config_a)
    chatbot.invoke({"messages": [HumanMessage(content="Nike is a footwear brand.")]}, config=config_b)

    checkpointer = _init_checkpointer()
    state_a = checkpointer.get(config_a).get("channel_values", {}).get("messages", [])
    state_b = checkpointer.get(config_b).get("channel_values", {}).get("messages", [])

    content_a = " ".join(getattr(m, "content", "") for m in state_a)
    content_b = " ".join(getattr(m, "content", "") for m in state_b)

    assert "Apple" in content_a
    assert "Nike" not in content_a

    assert "Nike" in content_b
    assert "Apple" not in content_b


def test_postgres_tables_contain_checkpoints():
    """Test 5: Verify checkpoint records are physically stored in PostgreSQL tables."""
    import psycopg
    db_url = getattr(settings, "LANGGRAPH_DATABASE_URL", None) or getattr(settings, "DATABASE_URL", "")
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    elif db_url.startswith("postgresql+psycopg://"):
        db_url = db_url.replace("postgresql+psycopg://", "postgresql://")

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM checkpoints;")
            count = cur.fetchone()[0]
            assert count > 0, "checkpoints table should contain persisted checkpoint records"


@pytest.mark.asyncio
async def test_investment_workflow_compatibility():
    """Test 4: Verify investment workflow completes successfully without regressions."""
    res = await investment_graph.ainvoke({
        "company": "PersistenceTech",
        "industry": "Enterprise Software",
        "funding": 2.0,
        "employees": 15,
        "age": 2,
        "revenue": 0.5,
        "growth": 1.5,
        "github_repo": None,
        "founder_names": "Alice Smith",
        "agent_results": {},
        "committee_result": None
    })
    assert res is not None
    assert "committee_result" in res or "agent_results" in res
