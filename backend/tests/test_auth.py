import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models.user
import models.company
import models.analysis
from database.base import Base
from database.dependencies import get_db
from main import app
from core.security import create_access_token, get_password_hash
from models.user import User
from models.analysis import Analysis

# Set up isolated in-memory SQLite database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine
)

Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def setup_db():
    app.dependency_overrides[get_db] = override_get_db
    try:
        from database.session import get_db as get_session_db
        app.dependency_overrides[get_session_db] = override_get_db
    except ImportError:
        pass
    yield
    app.dependency_overrides.clear()

client = TestClient(app)


def test_register_and_login_flow():
    # 1. Register new user
    reg_payload = {
        "email": "sarah.connor@cyberdyne.io",
        "password": "ResistancePassword2026!",
        "name": "Sarah Connor",
        "account_type": "personal"
    }
    reg_res = client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 200, reg_res.text
    reg_data = reg_res.json()
    assert "access_token" in reg_data
    assert reg_data["email"] == "sarah.connor@cyberdyne.io"

    # 2. Duplicate registration fails with 400
    dup_res = client.post("/api/v1/auth/register", json=reg_payload)
    assert dup_res.status_code == 400
    assert "already exists" in dup_res.json()["detail"].lower()

    # 3. Login with correct password
    login_payload = {
        "email": "sarah.connor@cyberdyne.io",
        "password": "ResistancePassword2026!"
    }
    login_res = client.post("/api/v1/auth/login", json=login_payload)
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    assert token

    # 4. Login with invalid password
    bad_login = {
        "email": "sarah.connor@cyberdyne.io",
        "password": "WrongPassword!"
    }
    bad_res = client.post("/api/v1/auth/login", json=bad_login)
    assert bad_res.status_code == 401

    # 5. Access /auth/me with valid Bearer token
    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "sarah.connor@cyberdyne.io"
    assert me_res.json()["full_name"] == "Sarah Connor"

    # 6. Access /auth/me without token returns 401
    unauth_me = client.get("/api/v1/auth/me")
    assert unauth_me.status_code == 401


def test_protected_endpoints_reject_unauthenticated():
    endpoints = [
        ("GET", "/api/v1/analysis/history", None),
        ("GET", "/api/v1/analysis/1", None),
        ("POST", "/api/v1/analysis/startup", {"company": "TestCo"}),
        ("POST", "/api/v1/companies", {"company_name": "TestCo"}),
        ("POST", "/api/v1/chat", {"message": "hello"}),
        ("POST", "/api/v1/chat/stream", {"message": "hello"}),
        ("GET", "/api/v1/chat/history/test_thread", None),
    ]

    for method, path, payload in endpoints:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path, json=payload)
        assert res.status_code == 401, f"Expected 401 for {method} {path}, got {res.status_code}"

    # Verify document upload unauthenticated returns 401
    fake_pdf = io.BytesIO(b"%PDF-1.4 test")
    doc_res = client.post(
        "/api/v1/documents/upload",
        files={"file": ("deck.pdf", fake_pdf, "application/pdf")}
    )
    assert doc_res.status_code == 401


def test_analysis_resource_ownership_and_isolation():
    db = TestingSessionLocal()
    # Create User Alpha and User Beta
    user_alpha = User(
        email="alpha@test.com",
        hashed_password=get_password_hash("AlphaPass123!"),
        full_name="User Alpha"
    )
    user_beta = User(
        email="beta@test.com",
        hashed_password=get_password_hash("BetaPass123!"),
        full_name="User Beta"
    )
    db.add_all([user_alpha, user_beta])
    db.commit()
    db.refresh(user_alpha)
    db.refresh(user_beta)

    # Directly create an analysis owned by User Alpha
    analysis_alpha = Analysis(
        company_name="AlphaTech",
        user_id=user_alpha.id,
        final_decision={"verdict": "INVEST", "final_score": 85.0}
    )
    # And an analysis owned by User Beta
    analysis_beta = Analysis(
        company_name="BetaBiotech",
        user_id=user_beta.id,
        final_decision={"verdict": "WATCH", "final_score": 62.0}
    )
    db.add_all([analysis_alpha, analysis_beta])
    db.commit()
    db.refresh(analysis_alpha)
    db.refresh(analysis_beta)
    db.close()

    token_alpha = create_access_token(data={"sub": "alpha@test.com"})
    token_beta = create_access_token(data={"sub": "beta@test.com"})

    headers_alpha = {"Authorization": f"Bearer {token_alpha}"}
    headers_beta = {"Authorization": f"Bearer {token_beta}"}

    # 1. User Alpha checks history: sees ONLY AlphaTech
    res_alpha_hist = client.get("/api/v1/analysis/history", headers=headers_alpha)
    assert res_alpha_hist.status_code == 200, f"Error: {res_alpha_hist.status_code} {res_alpha_hist.text}"
    hist_alpha = res_alpha_hist.json()
    assert len(hist_alpha) == 1
    assert hist_alpha[0]["company_name"] == "AlphaTech"

    # 2. User Beta checks history: sees ONLY BetaBiotech
    res_beta_hist = client.get("/api/v1/analysis/history", headers=headers_beta)
    assert res_beta_hist.status_code == 200
    hist_beta = res_beta_hist.json()
    assert len(hist_beta) == 1
    assert hist_beta[0]["company_name"] == "BetaBiotech"

    # 3. User Alpha can access their own analysis by ID
    res_alpha_get = client.get(f"/api/v1/analysis/{analysis_alpha.id}", headers=headers_alpha)
    assert res_alpha_get.status_code == 200
    assert res_alpha_get.json()["company_name"] == "AlphaTech"

    # 4. User Beta CANNOT access User Alpha's analysis by ID (returns 404)
    res_beta_unauth_get = client.get(f"/api/v1/analysis/{analysis_alpha.id}", headers=headers_beta)
    assert res_beta_unauth_get.status_code == 404


def test_chat_thread_user_isolation():
    db = TestingSessionLocal()
    user_1 = User(email="chat_user1@test.com", hashed_password=get_password_hash("Pass123!"), full_name="User 1")
    user_2 = User(email="chat_user2@test.com", hashed_password=get_password_hash("Pass123!"), full_name="User 2")
    db.add_all([user_1, user_2])
    db.commit()
    db.refresh(user_1)
    db.refresh(user_2)
    db.close()

    token_1 = create_access_token(data={"sub": "chat_user1@test.com"})
    token_2 = create_access_token(data={"sub": "chat_user2@test.com"})

    headers_1 = {"Authorization": f"Bearer {token_1}"}
    headers_2 = {"Authorization": f"Bearer {token_2}"}

    # Verify both can query history for the same nominal thread name without collision
    res_1 = client.get("/api/v1/chat/history/due_diligence_memo", headers=headers_1)
    assert res_1.status_code == 200
    assert "history" in res_1.json()

    res_2 = client.get("/api/v1/chat/history/due_diligence_memo", headers=headers_2)
    assert res_2.status_code == 200
    assert "history" in res_2.json()
