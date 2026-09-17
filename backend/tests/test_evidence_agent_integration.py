import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from agents.research_agent import ResearchAgent
from schemas.evidence import EvidenceRecord, FactType, SourceCredibility
from schemas.scoring import AgentScoreResult, ScoreFactor
from services.evidence_service import (
    build_evidence_lookup,
    calculate_evidence_confidence,
    resolve_evidence_ids,
    validate_fact_type,
)
from tools.search_tool import SearchResultsWithEvidence


class TestEvidenceAgentIntegration(unittest.TestCase):

    def setUp(self):
        self.ev_valid = EvidenceRecord(
            evidence_id="ev_web_valid",
            source_type="web_search",
            source_name="Reuters Article",
            url="https://reuters.com/news/1",
            raw_snippet="Company raised $10M",
            credibility=SourceCredibility.HIGH,
            independence_group="reuters.com"
        )
        self.ev_corr1 = EvidenceRecord(
            evidence_id="ev_web_corr1",
            source_type="web_search",
            source_name="SEC Filing",
            url="https://sec.gov/filing/1",
            raw_snippet="Form D filed for $10M",
            credibility=SourceCredibility.HIGH,
            independence_group="sec.gov"
        )
        self.ev_corr2 = EvidenceRecord(
            evidence_id="ev_web_corr2",
            source_type="web_search",
            source_name="GitHub Repo",
            url="https://github.com/company/repo",
            raw_snippet="Code commits active",
            credibility=SourceCredibility.HIGH,
            independence_group="github.com"
        )
        self.ev_pr1 = EvidenceRecord(
            evidence_id="ev_pr_1",
            source_type="web_search",
            source_name="PRNewswire",
            url="https://prnewswire.com/news/1",
            raw_snippet="PR Announcement",
            credibility=SourceCredibility.LOW,
            independence_group="company_pr_wire"
        )
        self.ev_pr2 = EvidenceRecord(
            evidence_id="ev_pr_2",
            source_type="web_search",
            source_name="BusinessWire Syndicated",
            url="https://businesswire.com/news/2",
            raw_snippet="PR Announcement copy",
            credibility=SourceCredibility.LOW,
            independence_group="company_pr_wire"
        )

    def test_1_valid_primary_evidence(self):
        """TEST 1: Valid primary evidence ID attaches actual EvidenceRecord."""
        lookup = build_evidence_lookup([self.ev_valid])
        prim, corr = resolve_evidence_ids("ev_web_valid", [], lookup)
        self.assertIsNotNone(prim)
        self.assertEqual(prim.evidence_id, "ev_web_valid")
        self.assertEqual(prim.source_name, "Reuters Article")
        self.assertEqual(corr, [])

    def test_2_invalid_evidence_id(self):
        """TEST 2: Invalid evidence ID sets primary_evidence to None without crashing."""
        lookup = build_evidence_lookup([self.ev_valid])
        prim, corr = resolve_evidence_ids("ev_web_fake", ["ev_web_fake2"], lookup)
        self.assertIsNone(prim)
        self.assertEqual(corr, [])

    def test_3_valid_corroborating_evidence(self):
        """TEST 3: Valid corroborating evidence IDs attach matching EvidenceRecords."""
        lookup = build_evidence_lookup([self.ev_valid, self.ev_corr1, self.ev_corr2])
        prim, corr = resolve_evidence_ids("ev_web_valid", ["ev_web_corr1", "ev_web_corr2"], lookup)
        self.assertIsNotNone(prim)
        self.assertEqual(prim.evidence_id, "ev_web_valid")
        self.assertEqual(len(corr), 2)
        self.assertEqual(corr[0].evidence_id, "ev_web_corr1")
        self.assertEqual(corr[1].evidence_id, "ev_web_corr2")

    def test_4_duplicate_evidence_ids(self):
        """TEST 4: Duplicate evidence IDs are deduplicated safely."""
        lookup = build_evidence_lookup([self.ev_valid, self.ev_corr1])
        prim, corr = resolve_evidence_ids("ev_web_valid", ["ev_web_valid", "ev_web_corr1", "ev_web_corr1"], lookup)
        self.assertIsNotNone(prim)
        self.assertEqual(prim.evidence_id, "ev_web_valid")
        self.assertEqual(len(corr), 1)
        self.assertEqual(corr[0].evidence_id, "ev_web_corr1")

    def test_5_same_independence_group_confidence(self):
        """TEST 5: Sources sharing same independence_group do not inflate confidence multiple times."""
        conf_single = calculate_evidence_confidence(self.ev_pr1, [])
        conf_syndicated = calculate_evidence_confidence(self.ev_pr1, [self.ev_pr2])
        self.assertEqual(conf_single, conf_syndicated)

    def test_6_independent_evidence_confidence(self):
        """TEST 6: Genuinely independent sources increase evidence confidence."""
        conf_single = calculate_evidence_confidence(self.ev_valid, [])
        conf_corroborated = calculate_evidence_confidence(self.ev_valid, [self.ev_corr1, self.ev_corr2])
        self.assertGreater(conf_corroborated, conf_single)
        self.assertEqual(conf_corroborated, 1.0)  # 0.85 + 0.10 + 0.05 = 1.0

    def test_7_invalid_fact_type(self):
        """TEST 7: Invalid fact_type string falls back to FactType.UNKNOWN safely."""
        ft = validate_fact_type("SUPER_CONFIRMED")
        self.assertEqual(ft, FactType.UNKNOWN)

    def test_8_no_evidence_fallback(self):
        """TEST 8: Empty evidence records list resolves cleanly without crash."""
        lookup = build_evidence_lookup([])
        prim, corr = resolve_evidence_ids(None, [], lookup)
        self.assertIsNone(prim)
        self.assertEqual(corr, [])
        conf = calculate_evidence_confidence(prim, corr)
        self.assertEqual(conf, 0.30)

    def test_9_fake_url_injection_prevention(self):
        """TEST 9: LLM attempting fake URL injection cannot inject unverified EvidenceRecords."""
        lookup = build_evidence_lookup([self.ev_valid])
        # Simulate LLM returning fake ID and fake URL in string
        fake_id = "ev_fake_999"
        prim, corr = resolve_evidence_ids(fake_id, ["ev_fake_888"], lookup)
        self.assertIsNone(prim)
        self.assertEqual(corr, [])

    @patch("agents.research_agent.search_tool.search_with_evidence")
    @patch("agents.research_agent.llm_service.generate_structured")
    def test_research_agent_end_to_end_mock(self, mock_llm, mock_search):
        """End-to-end test of ResearchAgent with mocked LLM and search tool."""
        mock_search.return_value = SearchResultsWithEvidence(
            results=[{"title": "Test Title", "url": "https://reuters.com/t", "content": "Test text"}],
            evidence_records=[self.ev_valid]
        )
        mock_llm.return_value = {
            "summary": "Solid startup fundamentals",
            "confidence": 0.9,
            "score_breakdown": [
                {
                    "factor": "Company overview clarity",
                    "points": 15,
                    "max_points": 15,
                    "reason": "Clear SaaS overview",
                    "source": "https://reuters.com/news/1",
                    "fact_type": "VERIFIED_FACT",
                    "primary_evidence_id": "ev_web_valid",
                    "corroborating_evidence_ids": []
                },
                {
                    "factor": "Founder credibility",
                    "points": 20,
                    "max_points": 20,
                    "reason": "Experienced team",
                    "source": None,
                    "fact_type": "THIRD_PARTY_CLAIM",
                    "primary_evidence_id": "ev_web_valid",
                    "corroborating_evidence_ids": []
                },
                {
                    "factor": "Product maturity",
                    "points": 20,
                    "max_points": 20,
                    "reason": "Shipped product",
                    "source": None,
                    "fact_type": "LLM_INFERENCE",
                    "primary_evidence_id": None,
                    "corroborating_evidence_ids": []
                },
                {
                    "factor": "Traction evidence",
                    "points": 25,
                    "max_points": 25,
                    "reason": "Strong user growth",
                    "source": None,
                    "fact_type": "THIRD_PARTY_CLAIM",
                    "primary_evidence_id": "ev_web_valid",
                    "corroborating_evidence_ids": []
                },
                {
                    "factor": "Funding history",
                    "points": 20,
                    "max_points": 20,
                    "reason": "Raised Series A",
                    "source": None,
                    "fact_type": "VERIFIED_FACT",
                    "primary_evidence_id": "ev_web_valid",
                    "corroborating_evidence_ids": []
                }
            ],
            "sources": ["https://reuters.com/news/1"],
            "business_profile": {
                "is_core_product_software": True,
                "is_revenue_physical_goods": False,
                "reasoning": "SaaS software product"
            }
        }

        agent = ResearchAgent()
        result = asyncio.run(agent.run({"company": "TestCorp", "company_id": "testcorp_123"}))

        self.assertIsInstance(result, AgentScoreResult)
        self.assertEqual(result.agent, "Research Agent")
        self.assertEqual(result.score, 100.0)
        self.assertEqual(result.business_profile.category, "TECH")
        self.assertEqual(len(result.score_breakdown), 5)

        factor_1 = result.score_breakdown[0]
        self.assertEqual(factor_1.fact_type, FactType.VERIFIED_FACT)
        self.assertIsNotNone(factor_1.primary_evidence)
        self.assertEqual(factor_1.primary_evidence.evidence_id, "ev_web_valid")
        self.assertEqual(factor_1.evidence_confidence, 0.85)


if __name__ == "__main__":
    unittest.main()
