import asyncio
import psycopg
from langchain_core.messages import HumanMessage
from core.config import settings
from workflows.chat_workflow import chatbot, _init_checkpointer

def run_persistence_tests():
    print("==================================================")
    print("  LANGGRAPH POSTGRESQL CHECKPOINT PERSISTENCE TEST")
    print("==================================================")

    # ----------------------------------------------------
    # TEST 1: Thread State Accumulation
    # ----------------------------------------------------
    thread_id = "test-persistence-001"
    config = {"configurable": {"thread_id": thread_id}}

    print(f"\n[Test 1] Sending initial message to thread '{thread_id}'...")
    res1 = chatbot.invoke({"messages": [HumanMessage(content="My startup is called TestAI.")]}, config=config)
    print(f" -> Initial response received. Message count in state: {len(res1['messages'])}")

    print(f"\n[Test 1.1] Sending second message in same thread '{thread_id}'...")
    res2 = chatbot.invoke({"messages": [HumanMessage(content="What metrics do you track for it?")]}, config=config)
    total_messages = len(res2["messages"])
    print(f" -> Follow-up response received. Total accumulated messages: {total_messages}")
    assert total_messages >= 4, f"Expected at least 4 messages in thread, got {total_messages}"
    print(" [PASSED] Thread state accumulation verified.")

    # ----------------------------------------------------
    # TEST 2: Thread Isolation
    # ----------------------------------------------------
    print("\n[Test 2] Testing state isolation between thread-A and thread-B...")
    config_a = {"configurable": {"thread_id": "thread-A-isolated"}}
    config_b = {"configurable": {"thread_id": "thread-B-isolated"}}

    chatbot.invoke({"messages": [HumanMessage(content="Apple is a technology company.")]}, config=config_a)
    chatbot.invoke({"messages": [HumanMessage(content="Nike is a sportswear brand.")]}, config=config_b)

    cp = _init_checkpointer()
    state_a = cp.get(config_a).get("channel_values", {}).get("messages", [])
    state_b = cp.get(config_b).get("channel_values", {}).get("messages", [])

    text_a = " ".join(getattr(m, "content", "") for m in state_a)
    text_b = " ".join(getattr(m, "content", "") for m in state_b)

    assert "Apple" in text_a and "Nike" not in text_a, "Thread-A leaked data into Thread-B!"
    assert "Nike" in text_b and "Apple" not in text_b, "Thread-B leaked data into Thread-A!"
    print(" [PASSED] Thread state isolation verified.")

    # ----------------------------------------------------
    # TEST 3: Process Restart Resilience
    # ----------------------------------------------------
    print(f"\n[Test 3] Simulating backend restart for thread '{thread_id}'...")
    fresh_cp = _init_checkpointer()
    restored_state = fresh_cp.get(config)
    assert restored_state is not None, "Failed to restore checkpoint state from PostgreSQL!"
    restored_messages = restored_state.get("channel_values", {}).get("messages", [])
    print(f" -> Restored {len(restored_messages)} messages from PostgreSQL after process restart.")
    assert len(restored_messages) >= 4
    assert any("TestAI" in getattr(m, "content", "") for m in restored_messages)
    print(" [PASSED] State survives process restart and re-initialization!")

    # ----------------------------------------------------
    # TEST 4: Physical PostgreSQL Table Inspection
    # ----------------------------------------------------
    print("\n[Test 4] Verifying physical PostgreSQL checkpoint tables...")
    db_url = getattr(settings, "LANGGRAPH_DATABASE_URL", None) or getattr(settings, "DATABASE_URL", "")
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    elif db_url.startswith("postgresql+psycopg://"):
        db_url = db_url.replace("postgresql+psycopg://", "postgresql://")

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM checkpoints;")
            checkpoints_cnt = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM checkpoint_blobs;")
            blobs_cnt = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM checkpoint_writes;")
            writes_cnt = cur.fetchone()[0]

            print(f" -> PostgreSQL Checkpoint Stats: {checkpoints_cnt} checkpoints, {blobs_cnt} blobs, {writes_cnt} writes.")
            assert checkpoints_cnt > 0, "No records found in PostgreSQL 'checkpoints' table!"
            assert blobs_cnt > 0, "No records found in PostgreSQL 'checkpoint_blobs' table!"

    print(" [PASSED] PostgreSQL tables contain physical checkpoint records.")

    print("\n==================================================")
    print("  ALL POSTGRESQL CHECKPOINT PERSISTENCE TESTS PASSED! ")
    print("==================================================")

if __name__ == "__main__":
    run_persistence_tests()
