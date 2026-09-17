from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class FactType(str, Enum):
    VERIFIED_FACT = "VERIFIED_FACT"
    CORROBORATED_FACT = "CORROBORATED_FACT"
    COMPANY_CLAIM = "COMPANY_CLAIM"
    THIRD_PARTY_CLAIM = "THIRD_PARTY_CLAIM"
    USER_PROVIDED = "USER_PROVIDED"
    LLM_INFERENCE = "LLM_INFERENCE"
    MODEL_PREDICTION = "MODEL_PREDICTION"
    UNKNOWN = "UNKNOWN"


class SourceCredibility(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class EvidenceRecord(BaseModel):
    evidence_id: str = Field(description="Unique ID for this evidence record")
    source_type: str = Field(description="Type of source, e.g. 'github_api', 'pitch_deck', 'web_search'")
    source_name: str = Field(description="Name or title of the source")
    url: Optional[str] = Field(default=None, description="URL of the evidence, if available")
    document_id: Optional[str] = Field(default=None, description="Document ID, if from an uploaded file")
    document_name: Optional[str] = Field(default=None, description="Filename of the uploaded document")
    page_number: Optional[int] = Field(default=None, description="Page number in document, if applicable")
    chunk_id: Optional[str] = Field(default=None, description="Vector store chunk ID, if applicable")
    raw_snippet: Optional[str] = Field(default=None, description="Raw evidence text snippet")
    credibility: SourceCredibility = Field(default=SourceCredibility.UNKNOWN, description="Credibility level of this source")
    independence_group: Optional[str] = Field(default=None, description="Group ID linking syndicated/derived news to the original source")
    retrieved_at: Optional[datetime] = Field(default=None, description="Timestamp when evidence was retrieved")
    query: Optional[str] = Field(default=None, description="Originating search query term")
    relevance_score: Optional[float] = Field(default=None, description="Search engine relevance score")
    published_date: Optional[str] = Field(default=None, description="Publication date of the source")
    domain: Optional[str] = Field(default=None, description="Extracted source domain name")


class StatementRecord(BaseModel):
    statement_id: str = Field(description="Unique statement ID")
    statement_text: str = Field(description="Text of the claim or fact")
    fact_type: FactType = Field(default=FactType.UNKNOWN, description="Fact/claim classification")
    primary_evidence: Optional[EvidenceRecord] = Field(default=None, description="Primary supporting evidence")
    corroborating_evidence: List[EvidenceRecord] = Field(default_factory=list, description="Additional corroborating evidence")
    confidence: float = Field(default=0.5, description="Confidence score between 0.0 and 1.0")

    @field_validator("confidence")
    @classmethod
    def confidence_within_bounds(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {v}")
        return v
