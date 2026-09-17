import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
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
    from models.analysis import Analysis


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    job_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: f"job_{uuid.uuid4().hex}"
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )


    company_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True
    )

    company_id: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="queued",
        index=True,
        nullable=False
    )

    progress: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    current_stage: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True
    )

    current_agent: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True
    )

    input_payload: Mapped[dict] = mapped_column(
        JSON,
        nullable=False
    )

    analysis_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("analyses.id", ondelete="SET NULL"),
        nullable=True
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True
    )

    error_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="analysis_jobs")
    analysis: Mapped[Optional["Analysis"]] = relationship("Analysis", back_populates="jobs")

