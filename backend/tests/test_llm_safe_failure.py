import time
import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pydantic import BaseModel, Field

from services.llm_service import llm_service, AllLLMProvidersFailedError, StructuredOutputParsingError
from services.trust_service import apply_verdict_safety
from agents.committee_agent import CommitteeAgent
from agents.research_agent import ResearchAgent
from agents.market_agent import MarketAgent
from agents.competitor_agent import CompetitorAgent
from agents.founder_agent import FounderAgent
from agents.finance_agent import FinanceAgent
from agents.github_agent import GitHubAgent
from agents.risk_agent import RiskAgent
from agents.prediction_agent import PredictionAgent
from schemas.scoring import CommitteeResult, AgentScoreResult, make_no_data_result
from core.config import settings


def test_zero_mock_data_fabrication_contract():
    """Assert that _generate_mock_fallback is completely deleted and ALLOW_MOCK_FALLBACK is False."""
    assert not hasattr(llm_service, "_generate_mock_fallback"), (
        "CRITICAL: _generate_mock_fallback must not exist on llm_service."
    )
    assert settings.ALLOW_MOCK_FALLBACK is False, (
        "ALLOW_MOCK_FALLBACK must be False by default in settings."
    )


def test_response_validation_rules():
    """Test that _validate_response rejects None, whitespace, and model refusals."""
    # Valid text passes through cleanly
    assert llm_service._validate_response("Valid response text", "test_provider") == "Valid response text"

    # None raises ValueError
    with pytest.raises(ValueError, match="returned None"):
        llm_service._validate_response(None, "test_provider")

    # Empty string raises ValueError
    with pytest.raises(ValueError, match="empty or whitespace"):
        llm_service._validate_response("", "test_provider")

    # Whitespace-only string raises ValueError
    with pytest.raises(ValueError, match="empty or whitespace"):
        llm_service._validate_response("   \n\t  ", "test_provider")

    # Refusals raise ValueError
    with pytest.raises(ValueError, match="refusal response"):
        llm_service._validate_response("I cannot fulfill this request as it violates policy.", "test_provider")

    with pytest.raises(ValueError, match="refusal response"):
        llm_service._validate_response("As an AI language model, I cannot provide this due diligence.", "test_provider")


@pytest.mark.anyio
async def test_structured_repair_succeeds_on_second_attempt():
    """Test that if the first output is malformed, exactly one repair retry is attempted and succeeds."""
    class SampleSchema(BaseModel):
        rating: int = Field(ge=1, le=10)
        reason: str

    call_count = 0

    async def fake_generate(prompt: str, bypass_cache: bool = False) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "This is not JSON: {invalid"
        return '{"rating": 8, "reason": "Repair succeeded"}'

    with patch.object(llm_service, "generate", side_effect=fake_generate):
        result = await llm_service.generate_structured("Score the startup", schema_cls=SampleSchema, bypass_cache=True)
        assert result["rating"] == 8
        assert result["reason"] == "Repair succeeded"
        assert call_count == 2, "Expected exactly 1 initial call and 1 repair retry"


@pytest.mark.anyio
async def test_structured_repair_exhausted_raises_error():
    """Test that when both initial and repair generation fail, StructuredOutputParsingError is raised."""
    class SampleSchema(BaseModel):
        rating: int

    call_count = 0

    async def fake_generate(prompt: str, bypass_cache: bool = False) -> str:
        nonlocal call_count
        call_count += 1
        return "Still broken JSON {{{"

    with patch.object(llm_service, "generate", side_effect=fake_generate):
        with pytest.raises(StructuredOutputParsingError) as exc_info:
            await llm_service.generate_structured("Score the startup", schema_cls=SampleSchema, bypass_cache=True)
        
        assert "after 1 retry" in str(exc_info.value)
        assert call_count == 2


def test_circuit_breaker_cooldown_behavior():
    """Test that setting a provider cooldown causes it to be skipped immediately."""
    provider = "test_cooldown_provider"
    future_time = time.monotonic() + 100.0
    llm_service._provider_cooldown[provider] = future_time

    # Cooldown should be in the future
    assert time.monotonic() < llm_service._provider_cooldown[provider]

    # Clear after test
    del llm_service._provider_cooldown[provider]


def test_trust_service_safety_verdict_guards():
    """Test that zero confidence results in UNABLE_TO_ASSESS verdict, and low confidence never allows INVEST or PASS."""
    # Zero confidence -> UNABLE_TO_ASSESS
    zero_conf = apply_verdict_safety(score=0.0, confidence=0.0)
    assert zero_conf.verdict == "UNABLE_TO_ASSESS"
    assert zero_conf.was_overridden is True
    assert "critical evidence unavailable" in zero_conf.override_reason.lower()

    zero_conf_high_score = apply_verdict_safety(score=88.0, confidence=0.0)
    assert zero_conf_high_score.verdict == "UNABLE_TO_ASSESS"
    assert zero_conf_high_score.was_overridden is True

    # High score with low confidence (below 0.60 cap) cannot be INVEST
    low_conf_high_score = apply_verdict_safety(score=85.0, confidence=0.35)
    assert low_conf_high_score.verdict != "INVEST"
    assert low_conf_high_score.verdict == "WATCH"

    # Low score with very low confidence (below 0.40) cannot be PASS
    low_conf_low_score = apply_verdict_safety(score=25.0, confidence=0.20)
    assert low_conf_low_score.verdict != "PASS"
    assert low_conf_low_score.verdict == "WATCH"


@pytest.mark.anyio
async def test_all_agents_produce_no_data_on_all_providers_failed():
    """Test that every scoring agent returns status='no_data' with score=0.0 and confidence=0.0 on LLM failure."""
    agents = [
        ResearchAgent(),
        MarketAgent(),
        CompetitorAgent(),
        FounderAgent(),
        FinanceAgent(),
        GitHubAgent(),
        RiskAgent(),
        PredictionAgent(),
    ]

    mock_search_results = {"results": [{"title": "Acme", "url": "https://example.com", "content": "Company data"}]}
    mock_github_metrics = {
        "days_since_last_push": 10,
        "commit_count_90d": 15,
        "commit_sample_size": 15,
        "contributor_count": 3,
        "top_contributor_share": 0.4,
        "has_test_dir": True,
        "has_ci": True,
        "has_readme": True,
        "readme_length": 1200,
        "stars": 120,
        "forks": 15,
        "url": "https://github.com/acme/repo"
    }

    from tools.search_tool import SearchResultsWithEvidence
    mock_evidence_results = SearchResultsWithEvidence(
        results=[{"title": "Acme", "url": "https://example.com", "content": "Company data"}],
        evidence_records=[]
    )

    with patch.object(llm_service, "generate_structured", side_effect=AllLLMProvidersFailedError("All providers offline")), \
         patch.object(llm_service, "generate", side_effect=AllLLMProvidersFailedError("All providers offline")), \
         patch("tools.search_tool.search_tool.search", new_callable=AsyncMock, return_value=mock_search_results), \
         patch("tools.search_tool.search_tool.search_with_evidence", new_callable=AsyncMock, return_value=mock_evidence_results), \
         patch("tools.github_tool.github_tool.get_repo_metrics", new_callable=AsyncMock, return_value=mock_github_metrics):
        for agent in agents:
            input_data = {
                "company": "Acme Ventures",
                "company_id": "test_id",
                "industry": "Software",
                "founder_names": ["Jane Doe"],
                "github_repo": "acme/repo",
                "other_findings": {}
            }
            res = await agent.run(input_data)
            assert isinstance(res, AgentScoreResult)
            assert res.status == "no_data", f"Agent {agent.name} did not return no_data status"
            assert res.score == 0.0, f"Agent {agent.name} produced non-zero score"
            assert res.confidence == 0.0, f"Agent {agent.name} produced non-zero confidence"
            assert res.sources == []
            assert "AWS" not in res.summary
            assert "$1.8M ARR" not in res.summary


@pytest.mark.anyio
async def test_committee_agent_all_providers_failed_contract():
    """Test that CommitteeAgent returns UNABLE_TO_ASSESS verdict with incomplete data integrity when all LLM providers fail."""
    committee = CommitteeAgent()
    
    with patch.object(llm_service, "generate_structured", side_effect=AllLLMProvidersFailedError("All providers down")):
        agent_results = {
            "Research Agent": make_no_data_result("Research Agent", "All LLM providers unavailable"),
            "Market Agent": make_no_data_result("Market Agent", "All LLM providers unavailable"),
            "Competitor Agent": make_no_data_result("Competitor Agent", "All LLM providers unavailable"),
        }
        
        result = await committee.execute({
            "company": "Acme Ventures",
            "agent_results": agent_results
        })
        
        assert isinstance(result, CommitteeResult)
        assert result.verdict == "UNABLE_TO_ASSESS"
        assert result.final_score == 0.0
        assert result.overall_confidence == 0.0
        assert result.data_integrity == "incomplete"
        assert result.evaluation_status == "failed"
        assert "AWS" not in result.narrative
        assert "$1.8M ARR" not in result.narrative
        assert result.key_opportunities == []
        assert result.key_risks == []


@pytest.mark.anyio
async def test_existing_successful_provider_behavior():
    """Verify that when a provider succeeds with valid content, generation works normally and records telemetry."""
    llm_service.telemetry_history.clear()
    
    # Mock Groq succeeding
    mock_choice = MagicMock()
    mock_choice.message.content = '{"status": "ok", "message": "Live inference working"}'
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    
    mock_groq = MagicMock()
    mock_groq.chat.completions.create.return_value = mock_response

    with patch.object(llm_service, "_groq", mock_groq), \
         patch.dict(llm_service._provider_cooldown, {}, clear=True):
        content = await llm_service.generate("Ping live test", bypass_cache=True)
        assert "Live inference working" in content
        
        # Verify telemetry recorded success
        records = [r for r in llm_service.telemetry_history if r["provider"] == "groq" and r["status"] == "success"]
        assert len(records) >= 1
