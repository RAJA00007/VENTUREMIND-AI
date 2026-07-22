from typing import Generator
from sqlalchemy.orm import Session
from database.session import SessionLocal

def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()