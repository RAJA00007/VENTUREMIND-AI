import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, DateTime, Boolean, Float, Date, Numeric, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )

    cin: Mapped[Optional[str]] = mapped_column(String(21), unique=True, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    incorporation_date: Mapped[Optional[datetime]] = mapped_column(Date)
    company_status: Mapped[str] = mapped_column(String(50), default="Active")
    company_type: Mapped[Optional[str]] = mapped_column(String(50))
    registered_state: Mapped[Optional[str]] = mapped_column(String(100))
    roc: Mapped[Optional[str]] = mapped_column(String(100))
    
    dpiit_recognized: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    dpiit_certificate_number: Mapped[Optional[str]] = mapped_column(String(100))
    
    industry: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    sub_industry: Mapped[Optional[str]] = mapped_column(String(100))
    website: Mapped[Optional[str]] = mapped_column(String(255))
    
    source: Mapped[str] = mapped_column(String(100), default="MCA Ingestion")
    source_url: Mapped[Optional[str]] = mapped_column(String(500))
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)
    
    last_verified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    founders: Mapped[List["Founder"]] = relationship("Founder", back_populates="company", cascade="all, delete-orphan")
    funding_rounds: Mapped[List["FundingRound"]] = relationship("FundingRound", back_populates="company", cascade="all, delete-orphan")
    financials: Mapped[List["CompanyFinancial"]] = relationship("CompanyFinancial", back_populates="company", cascade="all, delete-orphan")


class Founder(Base):
    __tablename__ = "founders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    din: Mapped[Optional[str]] = mapped_column(String(8))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(100), default="Co-Founder")
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(255))
    github_handle: Mapped[Optional[str]] = mapped_column(String(100))
    prior_exits: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company", back_populates="founders")


class FundingRound(Base):
    __tablename__ = "funding_rounds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    round_type: Mapped[str] = mapped_column(String(50), nullable=False)
    amount_usd: Mapped[Optional[float]] = mapped_column(Numeric(15, 2))
    valuation_usd: Mapped[Optional[float]] = mapped_column(Numeric(15, 2))
    announced_date: Mapped[Optional[datetime]] = mapped_column(Date)
    source: Mapped[Optional[str]] = mapped_column(String(100))
    source_url: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company", back_populates="funding_rounds")


class CompanyFinancial(Base):
    __tablename__ = "company_financials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    fiscal_year: Mapped[str] = mapped_column(String(10), nullable=False)
    revenue_inr: Mapped[Optional[float]] = mapped_column(Numeric(15, 2))
    ebitda_inr: Mapped[Optional[float]] = mapped_column(Numeric(15, 2))
    pat_inr: Mapped[Optional[float]] = mapped_column(Numeric(15, 2))
    burn_rate_monthly: Mapped[Optional[float]] = mapped_column(Numeric(15, 2))
    runway_months: Mapped[Optional[int]] = mapped_column(Integer)
    source: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company", back_populates="financials")