from datetime import datetime

from sqlalchemy import (
    Integer,
    String,
    DateTime,
    JSON
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column
)

from database.base import Base


class Analysis(Base):

    __tablename__ = "analyses"


    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )


    company_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )


    research_result: Mapped[dict] = mapped_column(
        JSON,
        nullable=True
    )


    market_result: Mapped[dict] = mapped_column(
        JSON,
        nullable=True
    )


    competitor_result: Mapped[dict] = mapped_column(
        JSON,
        nullable=True
    )


    risk_result: Mapped[dict] = mapped_column(
        JSON,
        nullable=True
    )


    final_decision: Mapped[dict] = mapped_column(
        JSON,
        nullable=True
    )


    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )