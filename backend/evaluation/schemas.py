"""
Schemas for the VentureMind AI Evaluation Framework.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ExpectedScores(BaseModel):
    company_type: str = Field(description="'TECH' | 'NON_TECH' | 'HYBRID'")
    market_score: float = Field(ge=0, le=100)
    competition_score: float = Field(ge=0, le=100)
    founder_score: float = Field(ge=0, le=100)
    finance_score: float = Field(ge=0, le=100)
    technology_score: float = Field(ge=0, le=100)
    risk_score: float = Field(ge=0, le=100)
    overall_score: float = Field(ge=0, le=100)
    risk_level: str = Field(description="'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'")
    verdict: str = Field(description="'INVEST' | 'WATCH' | 'PASS'")


class StartupTestCase(BaseModel):
    case_id: str
    case_type: str = Field(description="'SYNTHETIC' | 'PUBLIC_VERIFIABLE' | 'HUMAN_BENCHMARK'")
    company_name: str
    industry: str
    description: str
    funding: float = Field(description="Funding amount in USD")
    revenue: float = Field(description="Annual revenue in USD")
    growth: float = Field(description="Year-over-year growth rate (e.g. 0.15 for 15%)")
    employees: int = 10
    age: int = 2
    founder_information: Optional[str] = None
    github_url: Optional[str] = None
    expected: ExpectedScores
    rationale: str
    known_missing_information: List[str] = Field(default_factory=list)


class CaseRunResult(BaseModel):
    case_id: str
    company_name: str
    case_type: str
    expected: ExpectedScores
    actual_overall_score: Optional[float] = None
    actual_verdict: Optional[str] = None
    actual_overall_confidence: Optional[float] = None
    actual_company_type: Optional[str] = None
    actual_risk_level: Optional[str] = None
    actual_dimension_scores: Dict[str, float] = Field(default_factory=dict)
    runtime_seconds: float = 0.0
    total_runtime_ms: float = 0.0
    status: str = Field(default="completed", description="'completed' | 'failed' | 'partial'")
    error: Optional[str] = None
    agent_failures: int = 0
    no_data_agents: int = 0
    total_sources_cited: int = 0
    schema_valid: bool = True
    valid: bool = True
    invalidation_reason: Optional[str] = None
    provider_telemetry: List[Dict[str, Any]] = Field(default_factory=list)
    agent_runtimes_ms: Dict[str, float] = Field(default_factory=dict)
    provider_runtimes_ms: Dict[str, float] = Field(default_factory=dict)
    fallback_count: int = 0
    ollama_call_count: int = 0
    remote_provider_call_count: int = 0
    total_llm_calls: int = 0
    slowest_agent: Optional[str] = None
    fastest_agent: Optional[str] = None
    overconfident_flag: bool = False
    raw_committee_result: Optional[Dict[str, Any]] = None
    raw_agent_results: Optional[Dict[str, Any]] = None


class AggregateMetrics(BaseModel):
    total_cases: int
    completed_cases: int
    valid_cases_count: int = 0
    invalid_cases_count: int = 0
    provider_failures_count: int = 0
    failed_cases: int
    workflow_success_rate: float
    agent_failure_rate: float
    overall_score_mae: float
    overall_score_median_ae: float
    overall_score_max_error: float
    verdict_accuracy: float
    verdict_confusion_matrix: Dict[str, Dict[str, int]]
    risk_classification_accuracy: float
    risk_classification_precision: float
    risk_classification_recall: float
    risk_classification_f1: float
    dimension_maes: Dict[str, float]
    high_confidence_error_rate: float
    overconfident_case_ids: List[str]
    total_runtime_seconds: float
    avg_runtime_seconds: float
    p50_runtime_seconds: float = 0.0
    p95_runtime_seconds: float = 0.0
    min_runtime_seconds: float
    max_runtime_seconds: float
    avg_sources_per_case: float
    slowest_agent: str = "N/A"
    avg_agent_latency_ms: float = 0.0
    ollama_percentage: float = 0.0
    remote_provider_percentage: float = 0.0
    fallback_percentage: float = 0.0
    provider_usage_breakdown: Dict[str, int] = Field(default_factory=dict)
    total_llm_calls: int = 0
    total_fallbacks: int = 0
    llm_token_usage: str = "NOT AVAILABLE"
    llm_estimated_cost: str = "NOT AVAILABLE"
    hallucination_accuracy: str = "NOT MEASURED"


class RegressionReport(BaseModel):
    baseline_timestamp: str
    candidate_timestamp: str
    overall_score_mae_change: float
    verdict_accuracy_change: float
    workflow_success_rate_change: float
    avg_latency_change: float
    status: str = Field(description="'IMPROVED' | 'REGRESSED' | 'UNCHANGED'")
    details: List[str] = Field(default_factory=list)
