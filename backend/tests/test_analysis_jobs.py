import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models.analysis_job
import models.analysis
import models.user
from database.base import Base
from database.dependencies import get_db
import database.session as db_session
from main import app
from core.security import create_access_token, get_password_hash
from models.user import User
from models.analysis_job import AnalysisJob
from schemas.scoring import AgentScoreResult, CommitteeResult, AgentSummaryEntry, ScoreFactor
from services.job_service import job_service



# Set up SQLite in-memory engine and sessionmaker for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
)

# Create schema in the in-memory database
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    app.dependency_overrides[get_db] = override_get_db
    try:
        from database.session import get_db as get_session_db
        app.dependency_overrides[get_session_db] = override_get_db
    except ImportError:
        pass
    monkeypatch.setattr("services.job_service.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(db_session, "SessionLocal", TestingSessionLocal)
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def _get_or_create_user(email: str, name: str) -> tuple[User, str]:
    db = TestingSessionLocal()
    user = db.query(User).filter_by(email=email).first()
    if not user:
        user = User(
            email=email,
            hashed_password=get_password_hash("securepass123"),
            full_name=name
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    token = create_access_token({"sub": user.email})
    db.close()
    return user, token


def test_startup_endpoint_unauthenticated_rejected():
    response = client.post("/api/v1/analysis/startup", json={"company": "Acme AI"})
    assert response.status_code == 401


def test_startup_endpoint_enqueues_job_immediately(monkeypatch):
    # Prevent background task from automatically executing actual agents during unit test
    monkeypatch.setattr(job_service, "start_background_job", lambda job_id: None)

    _, token = _get_or_create_user("async_user1@test.com", "Async User 1")

    payload = {
        "company": "Nova Robotics",
        "industry": "Robotics",
        "funding": 250,
        "revenue": 15
    }

    response = client.post(
        "/api/v1/analysis/startup",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert data["company_name"] == "Nova Robotics"
    assert "queued successfully" in data["message"]


def test_startup_endpoint_deduplication(monkeypatch):
    monkeypatch.setattr(job_service, "start_background_job", lambda job_id: None)
    _, token = _get_or_create_user("async_user2@test.com", "Async User 2")

    payload = {"company": "QuantumPulse"}

    # First request
    res1 = client.post(
        "/api/v1/analysis/startup",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res1.status_code == 202
    job1_id = res1.json()["job_id"]

    # Immediate duplicate request
    res2 = client.post(
        "/api/v1/analysis/startup",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res2.status_code == 202
    job2_id = res2.json()["job_id"]

    # Must return the existing active job
    assert job1_id == job2_id
    assert "already in progress" in res2.json()["message"]


def test_get_job_unauthenticated_rejected():
    response = client.get("/api/v1/jobs/job_12345")
    assert response.status_code == 401


def test_get_job_owner_isolation(monkeypatch):
    user1, token1 = _get_or_create_user("owner_user@test.com", "Owner")
    user2, token2 = _get_or_create_user("intruder_user@test.com", "Intruder")

    # Create a job owned by user 1
    db = TestingSessionLocal()
    job = AnalysisJob(
        job_id="job_owner_private_123",
        user_id=user1.id,
        company_name="Confidential Bio",
        status="queued",
        progress=0,
        input_payload={"company": "Confidential Bio"}
    )
    db.add(job)
    db.commit()
    target_job_id = job.job_id
    db.close()

    # User 1 accesses their own job -> 200 OK
    res1 = client.get(
        f"/api/v1/jobs/{target_job_id}",
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert res1.status_code == 200
    assert res1.json()["company_name"] == "Confidential Bio"

    # User 2 tries to access user 1's job -> 404 Not Found (no metadata leak)
    res2 = client.get(
        f"/api/v1/jobs/{target_job_id}",
        headers={"Authorization": f"Bearer {token2}"}
    )
    assert res2.status_code == 404


@pytest.mark.anyio
async def test_worker_execution_lifecycle_and_persistence(monkeypatch):
    user, token = _get_or_create_user("lifecycle_user@test.com", "Lifecycle")

    # Create queued job
    db = TestingSessionLocal()
    job = AnalysisJob(
        job_id="job_lifecycle_test_456",
        user_id=user.id,
        company_name="AeroDrive",
        status="queued",
        progress=0,
        input_payload={"company": "AeroDrive", "industry": "Aerospace"}
    )
    db.add(job)
    db.commit()
    db.close()

    mock_agent_result = AgentScoreResult(
        agent="Test Agent",
        score=82.0,
        score_breakdown=[
            ScoreFactor(factor="Team Execution", points=82.0, max_points=100.0, reason="Experienced founders")
        ],
        summary="Strong aerospace engineering background with verified track record.",
        confidence=0.88,
        status="ok",
        sources=["https://aerodrive.example.com"]
    )

    mock_comm_result = CommitteeResult(

        company="AeroDrive",
        category="INVEST",
        final_score=85.0,
        verdict="INVEST",
        overall_confidence=0.89,
        was_overridden=False,
        data_integrity="verified",
        evaluation_status="complete",
        agent_summaries=[
            AgentSummaryEntry(
                agent="Test Agent",
                score=82.0,
                confidence=0.88,
                status="ok",
                summary="Strong background"
            )
        ],
        narrative="Solid aerospace startup with high potential."
    )


    # Mock investment_graph.astream yielding sequential node updates
    async def mock_astream(graph_input):
        yield {
            "parallel_independent": {
                "agent_results": {
                    "Research Agent": mock_agent_result,
                    "Market Agent": mock_agent_result,
                    "Competitor Agent": mock_agent_result,
                    "Founder Agent": mock_agent_result,
                    "Finance Agent": mock_agent_result,
                    "Code / GitHub Agent": mock_agent_result
                }
            }
        }
        yield {
            "risk_prediction": {
                "agent_results": {
                    "Risk Agent": mock_agent_result,
                    "Prediction Agent": mock_agent_result
                }
            }
        }
        yield {
            "committee": {
                "committee_result": mock_comm_result
            }
        }

    monkeypatch.setattr("services.job_service.investment_graph.astream", mock_astream)

    # Run the worker directly
    await job_service._execute_job("job_lifecycle_test_456")

    # Check job state in DB
    db = TestingSessionLocal()
    completed_job = db.query(AnalysisJob).filter_by(job_id="job_lifecycle_test_456").first()
    assert completed_job is not None
    assert completed_job.status == "completed"
    assert completed_job.progress == 100
    assert completed_job.analysis_id is not None
    assert completed_job.error_message is None

    # Check status endpoint returns completed analysis details
    res = client.get(
        f"/api/v1/jobs/{completed_job.job_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    job_data = res.json()
    assert job_data["status"] == "completed"
    assert job_data["progress"] == 100
    assert job_data["result"] is not None
    assert job_data["result"]["verdict"] == "INVEST"
    assert job_data["result"]["data_integrity"] == "verified"
    db.close()


@pytest.mark.anyio
async def test_worker_safe_failure_propagation(monkeypatch):
    user, token = _get_or_create_user("safefail_user@test.com", "SafeFail")

    db = TestingSessionLocal()
    job = AnalysisJob(
        job_id="job_safefail_test_789",
        user_id=user.id,
        company_name="OfflineTech",
        status="queued",
        progress=0,
        input_payload={"company": "OfflineTech"}
    )
    db.add(job)
    db.commit()
    db.close()

    # When all providers fail, agents return no_data and committee returns UNABLE_TO_ASSESS
    failed_agent_result = AgentScoreResult(
        agent="Failed Agent",
        score=0.0,
        score_breakdown=[],
        summary="All providers failed",
        confidence=0.0,
        status="no_data",
        sources=[],
        error="All providers failed"
    )
    unable_to_assess_comm = CommitteeResult(
        company="OfflineTech",
        category="HYBRID",
        final_score=0.0,
        verdict="UNABLE_TO_ASSESS",
        overall_confidence=0.0,
        was_overridden=True,
        override_reason="Overridden to UNABLE_TO_ASSESS due to complete evidence absence",
        data_integrity="incomplete",
        evaluation_status="failed",
        agent_summaries=[
            AgentSummaryEntry(
                agent="Failed Agent",
                score=0.0,
                confidence=0.0,
                status="no_data",
                summary="All providers failed"
            )
        ],
        narrative="Unable to assess company due to total absence of verifiable intelligence."
    )


    async def mock_astream_safefailure(graph_input):
        yield {
            "parallel_independent": {
                "agent_results": {"Research Agent": failed_agent_result}
            }
        }
        yield {
            "risk_prediction": {
                "agent_results": {"Risk Agent": failed_agent_result}
            }
        }
        yield {
            "committee": {
                "committee_result": unable_to_assess_comm
            }
        }

    monkeypatch.setattr("services.job_service.investment_graph.astream", mock_astream_safefailure)

    await job_service._execute_job("job_safefail_test_789")

    # Verify job safely completed without crashing or fabricating mock ARR/scores
    db = TestingSessionLocal()
    safefail_job = db.query(AnalysisJob).filter_by(job_id="job_safefail_test_789").first()
    assert safefail_job.status == "completed"
    assert safefail_job.analysis_id is not None

    res = client.get(
        f"/api/v1/jobs/{safefail_job.job_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    job_data = res.json()
    assert job_data["status"] == "completed"
    assert job_data["result"]["verdict"] == "UNABLE_TO_ASSESS"
    assert job_data["result"]["data_integrity"] == "incomplete"
    assert job_data["result"]["evaluation_status"] == "failed"
    assert job_data["result"]["final_score"] == 0.0
    db.close()


def test_reap_stale_jobs_on_startup():
    db = TestingSessionLocal()
    user = User(email="reap_stale_test@venturemind.ai", hashed_password="pw")
    db.add(user)
    db.commit()
    db.refresh(user)

    job1 = AnalysisJob(
        job_id="job_stale_queued",
        user_id=user.id,
        company_name="InterruptedCo1",
        status="queued",
        progress=0,
        input_payload={"company": "InterruptedCo1"}
    )
    job2 = AnalysisJob(
        job_id="job_stale_running",
        user_id=user.id,
        company_name="InterruptedCo2",
        status="running",
        progress=45,
        input_payload={"company": "InterruptedCo2"}
    )
    db.add_all([job1, job2])
    db.commit()

    db.close()

    reaped_count = job_service.reap_stale_jobs()
    assert reaped_count >= 2

    db = TestingSessionLocal()
    j1 = db.query(AnalysisJob).filter_by(job_id="job_stale_queued").first()
    j2 = db.query(AnalysisJob).filter_by(job_id="job_stale_running").first()
    assert j1.status == "failed"
    assert j1.error_type == "ServerRestartError"
    assert j2.status == "failed"
    assert j2.error_type == "ServerRestartError"
    db.close()
