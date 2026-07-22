from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.base import Base
from database.dependencies import get_db
from main import app

# Set up SQLite in-memory engine and sessionmaker for testing (no greenlet required)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
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

# Override dependency in app
app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def test_create_company_endpoint():
    company_data = {
        "name": "Stripe",
        "website": "https://stripe.com",
        "industry": "Fintech",
        "country": "US"
    }
    response = client.post("/api/v1/companies", json=company_data)
    assert response.status_code == 200
    
    resp_data = response.json()
    assert resp_data["name"] == "Stripe"
    assert resp_data["website"] == "https://stripe.com"
    assert resp_data["industry"] == "Fintech"
    assert resp_data["country"] == "US"
    assert "id" in resp_data
