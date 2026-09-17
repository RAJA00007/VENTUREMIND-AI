import os
import tempfile
import uuid
import pytest
from datetime import datetime
from sqlalchemy import create_engine, inspect, select, text, event
from sqlalchemy.orm import sessionmaker

from database.base import Base
from models.user import User
from models.company import Company, Founder, FundingRound, CompanyFinancial
from models.analysis import Analysis
from models.analysis_job import AnalysisJob


@pytest.fixture
def clean_db():
    """Creates a clean isolated in-memory SQLite database engine with foreign keys enabled."""
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Enable foreign keys on SQLite connection
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()

    yield session, engine

    session.close()
    engine.dispose()



def test_all_expected_tables_exist(clean_db):
    session, engine = clean_db
    insp = inspect(engine)
    tables = insp.get_table_names()
    expected = [
        "users",
        "companies",
        "founders",
        "funding_rounds",
        "company_financials",
        "analyses",
        "analysis_jobs",
    ]
    for table in expected:
        assert table in tables, f"Expected table '{table}' missing from database"


def test_canonical_columns_exist(clean_db):
    session, engine = clean_db
    insp = inspect(engine)

    # 1. users
    user_cols = {c["name"]: c for c in insp.get_columns("users")}
    for col in ["id", "email", "hashed_password", "full_name", "account_type", "company_name", "is_active", "created_at"]:
        assert col in user_cols

    # 2. companies
    comp_cols = {c["name"]: c for c in insp.get_columns("companies")}
    for col in ["id", "cin", "company_name", "legal_name", "company_status", "industry", "created_by_user_id"]:
        assert col in comp_cols

    # 3. analyses
    analysis_cols = {c["name"]: c for c in insp.get_columns("analyses")}
    for col in ["id", "user_id", "company_id", "company_name", "research_result", "final_decision", "created_at"]:
        assert col in analysis_cols

    # 4. analysis_jobs
    job_cols = {c["name"]: c for c in insp.get_columns("analysis_jobs")}
    for col in ["id", "job_id", "user_id", "company_name", "company_id", "status", "progress", "analysis_id"]:
        assert col in job_cols


def test_user_ownership_and_cascade_delete(clean_db):
    session, engine = clean_db

    # Create user
    user = User(
        email="founder@venturemind.ai",
        hashed_password="hashed_secret_123",
        full_name="Founder Alpha"
    )
    session.add(user)
    session.commit()

    # Create analysis owned by user
    analysis = Analysis(
        user_id=user.id,
        company_name="Alpha Tech",
        final_decision={"verdict": "INVEST", "score": 88}
    )
    session.add(analysis)

    # Create job owned by user
    job = AnalysisJob(
        job_id=f"job_{uuid.uuid4().hex}",
        user_id=user.id,
        company_name="Alpha Tech",
        input_payload={"company": "Alpha Tech"}
    )
    session.add(job)

    # Create company created by user
    company = Company(
        company_name="Alpha Corp",
        legal_name="Alpha Technologies Pvt Ltd",
        created_by_user_id=user.id
    )
    session.add(company)
    session.commit()

    assert session.query(Analysis).filter(Analysis.user_id == user.id).count() == 1
    assert session.query(AnalysisJob).filter(AnalysisJob.user_id == user.id).count() == 1
    assert company.created_by_user_id == user.id

    # Deleting user must CASCADE delete analyses and analysis_jobs, and SET NULL on company.created_by_user_id
    session.delete(user)
    session.commit()

    assert session.query(Analysis).count() == 0
    assert session.query(AnalysisJob).count() == 0
    session.refresh(company)
    assert company.created_by_user_id is None


def test_company_child_cascade_delete(clean_db):
    session, engine = clean_db

    company = Company(
        company_name="Nexus AI",
        legal_name="Nexus Intelligence Inc"
    )
    session.add(company)
    session.commit()

    founder = Founder(
        company_id=company.id,
        name="Alice Walker",
        title="CEO"
    )
    funding = FundingRound(
        company_id=company.id,
        round_type="Seed",
        amount_usd=2000000.00
    )
    financial = CompanyFinancial(
        company_id=company.id,
        fiscal_year="FY24",
        revenue_inr=15000000.00
    )
    session.add_all([founder, funding, financial])
    session.commit()

    assert session.query(Founder).filter(Founder.company_id == company.id).count() == 1
    assert session.query(FundingRound).filter(FundingRound.company_id == company.id).count() == 1
    assert session.query(CompanyFinancial).filter(CompanyFinancial.company_id == company.id).count() == 1

    # Deleting company must cascade delete all 3 child entities
    session.delete(company)
    session.commit()

    assert session.query(Founder).count() == 0
    assert session.query(FundingRound).count() == 0
    assert session.query(CompanyFinancial).count() == 0


def test_adhoc_startup_analysis_without_company(clean_db):
    session, engine = clean_db

    user = User(
        email="analyst@venturemind.ai",
        hashed_password="pw",
        full_name="Analyst"
    )
    session.add(user)
    session.commit()

    # Evaluating ad-hoc company with no corresponding Company record in registry
    analysis = Analysis(
        user_id=user.id,
        company_name="Random Pre-Seed Stealth Co",
        company_id=None,
        final_decision={"verdict": "WATCH"}
    )
    session.add(analysis)
    session.commit()

    assert analysis.id is not None
    assert analysis.company_id is None
    assert analysis.company_name == "Random Pre-Seed Stealth Co"


def test_analysis_linked_to_company_set_null_on_company_delete(clean_db):
    session, engine = clean_db

    user = User(email="vc@fund.com", hashed_password="pw")
    company = Company(company_name="Known Unicorn", legal_name="Known Unicorn Ltd")
    session.add_all([user, company])
    session.commit()

    analysis = Analysis(
        user_id=user.id,
        company_id=company.id,
        company_name="Known Unicorn",
        final_decision={"verdict": "INVEST"}
    )
    session.add(analysis)
    session.commit()

    assert analysis.company_id == company.id

    # Deleting the company should SET NULL on analysis.company_id, preserving the analysis
    session.delete(company)
    session.commit()

    session.refresh(analysis)
    assert analysis.company_id is None
    assert analysis.company_name == "Known Unicorn"


def test_analysis_job_linked_to_analysis_set_null_on_analysis_delete(clean_db):
    session, engine = clean_db

    user = User(email="investor@venturemind.ai", hashed_password="pw")
    session.add(user)
    session.commit()

    analysis = Analysis(
        user_id=user.id,
        company_name="Quantum Robotics",
        final_decision={"verdict": "INVEST"}
    )
    session.add(analysis)
    session.commit()

    job = AnalysisJob(
        job_id=f"job_{uuid.uuid4().hex}",
        user_id=user.id,
        company_name="Quantum Robotics",
        analysis_id=analysis.id,
        status="completed",
        progress=100,
        input_payload={"company": "Quantum Robotics"}
    )
    session.add(job)
    session.commit()

    assert job.analysis_id == analysis.id

    # Deleting the analysis should SET NULL on job.analysis_id, preserving the audit log
    session.delete(analysis)
    session.commit()

    session.refresh(job)
    assert job.analysis_id is None
    assert job.status == "completed"


def test_unique_constraints(clean_db):
    session, engine = clean_db

    user1 = User(email="unique@test.com", hashed_password="pw")
    session.add(user1)
    session.commit()

    # Duplicate user email must raise IntegrityError
    user2 = User(email="unique@test.com", hashed_password="pw2")
    session.add(user2)
    with pytest.raises(Exception):
        session.commit()
    session.rollback()

    # Duplicate company CIN must raise IntegrityError
    comp1 = Company(cin="U12345DL2024PTC123456", company_name="Co 1", legal_name="Co 1 Ltd")
    session.add(comp1)
    session.commit()

    comp2 = Company(cin="U12345DL2024PTC123456", company_name="Co 2", legal_name="Co 2 Ltd")
    session.add(comp2)
    with pytest.raises(Exception):
        session.commit()
    session.rollback()

    # Duplicate job_id must raise IntegrityError
    jid = f"job_{uuid.uuid4().hex}"
    job1 = AnalysisJob(job_id=jid, user_id=user1.id, company_name="Co 1", input_payload={})
    session.add(job1)
    session.commit()

    job2 = AnalysisJob(job_id=jid, user_id=user1.id, company_name="Co 2", input_payload={})
    session.add(job2)
    with pytest.raises(Exception):
        session.commit()
    session.rollback()


def test_alembic_upgrade_from_scratch():
    """Verifies that running Alembic upgrade head on a brand new empty SQLite database succeeds."""
    import subprocess
    t = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    t.close()
    db_path = t.name.replace("\\", "/")

    try:
        cmd = [
            ".venv/Scripts/python.exe",
            "-m",
            "alembic",
            "-c",
            "backend/alembic.ini",
            "-x",
            f"db_url=sqlite:///{db_path}",
            "upgrade",
            "head"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"Alembic upgrade failed: {res.stderr}"

        # Verify tables created
        import sqlite3
        conn = sqlite3.connect(t.name)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        conn.close()

        expected = [
            "alembic_version",
            "analyses",
            "analysis_jobs",
            "companies",
            "company_financials",
            "founders",
            "funding_rounds",
            "users",
        ]
        for tbl in expected:
            assert tbl in tables, f"Table {tbl} not created by Alembic"

    finally:
        if os.path.exists(t.name):
            try:
                os.unlink(t.name)
            except Exception:
                pass


def test_alembic_head_single_revision():
    """Verifies that Alembic has exactly one linear head revision (b2b07e15d89f)."""
    import subprocess
    cmd = [
        ".venv/Scripts/python.exe",
        "-m",
        "alembic",
        "-c",
        "backend/alembic.ini",
        "heads"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "b2b07e15d89f (head)" in res.stdout

