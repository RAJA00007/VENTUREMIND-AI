from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import (
    Integer,
    String,
    DateTime,
    JSON,
    ForeignKey
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship
)

from database.base import Base

if TYPE_CHECKING:
    from models.user import User
    from models.company import Company
    from models.analysis_job import AnalysisJob


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    company_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    company_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True
    )

    research_result: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True
    )

    market_result: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True
    )

    competitor_result: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True
    )

    risk_result: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True
    )

    final_decision: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="analyses")
    company: Mapped[Optional["Company"]] = relationship("Company", back_populates="analyses")
    jobs: Mapped[List["AnalysisJob"]] = relationship("AnalysisJob", back_populates="analysis")