import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import models.company
import models.user
from database.base import Base
from database.dependencies import get_db
from main import app
from core.security import create_access_token, get_password_hash
from models.user import User

from sqlalchemy.pool import StaticPool

# Set up SQLite in-memory engine and sessionmaker for testing (no greenlet required)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine
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
def setup_db():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()

client = TestClient(app)

def test_create_company_unauthenticated_rejected():
    company_data = {
        "company_name": "Stripe",
        "website": "https://stripe.com",
        "industry": "Fintech",
        "registered_state": "CA"
    }
    response = client.post("/api/v1/companies", json=company_data)
    assert response.status_code == 401


def test_create_company_authenticated_success():
    # Seed a test user
    db = TestingSessionLocal()
    user = User(
        email="test_company_owner@venturemind.ai",
        hashed_password=get_password_hash("securepass123"),
        full_name="Company Tester"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()

    token = create_access_token(data={"sub": "test_company_owner@venturemind.ai"})
    headers = {"Authorization": f"Bearer {token}"}

    company_data = {
        "company_name": "Stripe",
        "website": "https://stripe.com",
        "industry": "Fintech",
        "registered_state": "CA"
    }
    response = client.post("/api/v1/companies", json=company_data, headers=headers)
    assert response.status_code == 200
    
    resp_data = response.json()
    assert resp_data["company_name"] == "Stripe"
    assert resp_data["website"] == "https://stripe.com"
    assert resp_data["industry"] == "Fintech"
    assert "id" in resp_data
