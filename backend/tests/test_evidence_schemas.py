import os
import sys
import unittest
from pathlib import Path
from pydantic import ValidationError

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from schemas.evidence import FactType, SourceCredibility, EvidenceRecord, StatementRecord
from schemas.scoring import ScoreFactor


class TestEvidenceSchemas(unittest.TestCase):

    def test_1_verified_fact_github_api(self):
        """TEST 1: Create a VERIFIED_FACT with GitHub API evidence and verify serialization."""
        evidence = EvidenceRecord(
            evidence_id="ev_gh_001",
            source_type="github_api",
            source_name="GitHub REST API",
            url="https://api.github.com/repos/example/repo",
            credibility=SourceCredibility.HIGH,
            raw_snippet="{'commits': 247, 'contributors': 12}"
        )
        statement = StatementRecord(
            statement_id="stmt_001",
            statement_text="Repository has 247 commits",
            fact_type=FactType.VERIFIED_FACT,
            primary_evidence=evidence,
            confidence=0.95
        )

        dump = statement.model_dump()
        self.assertEqual(dump["fact_type"], "VERIFIED_FACT")
        self.assertEqual(dump["primary_evidence"]["source_type"], "github_api")
        self.assertEqual(dump["primary_evidence"]["credibility"], "HIGH")
        self.assertEqual(dump["confidence"], 0.95)

        json_str = statement.model_dump_json()
        self.assertIn("VERIFIED_FACT", json_str)
        self.assertIn("github_api", json_str)

    def test_2_company_claim_pitch_deck(self):
        """TEST 2: Create a COMPANY_CLAIM from a pitch deck and verify page metadata survives serialization."""
        evidence = EvidenceRecord(
            evidence_id="ev_deck_012",
            source_type="pitch_deck",
            source_name="Company Pitch Deck",
            document_id="doc_uuid_12345",
            document_name="company_pitch.pdf",
            page_number=12,
            chunk_id="doc_uuid_12345_p12_c0",
            credibility=SourceCredibility.LOW,
            raw_snippet="Achieved $10M ARR in FY2025"
        )
        statement = StatementRecord(
            statement_id="stmt_002",
            statement_text="$10M ARR",
            fact_type=FactType.COMPANY_CLAIM,
            primary_evidence=evidence,
            confidence=0.60
        )

        dump = statement.model_dump()
        self.assertEqual(dump["fact_type"], "COMPANY_CLAIM")
        self.assertEqual(dump["primary_evidence"]["document_name"], "company_pitch.pdf")
        self.assertEqual(dump["primary_evidence"]["page_number"], 12)
        self.assertEqual(dump["primary_evidence"]["credibility"], "LOW")

        # Verify round-trip deserialization from JSON
        json_str = statement.model_dump_json()
        reconstructed = StatementRecord.model_validate_json(json_str)
        self.assertEqual(reconstructed.primary_evidence.page_number, 12)
        self.assertEqual(reconstructed.primary_evidence.document_name, "company_pitch.pdf")

    def test_3_syndicated_independence_group(self):
        """TEST 3: Create multiple syndicated sources sharing the same independence_group."""
        ev1 = EvidenceRecord(
            evidence_id="ev_blog_1",
            source_type="web_search",
            source_name="TechBlog 1",
            url="https://techblog1.com/funding-announcement",
            credibility=SourceCredibility.MEDIUM,
            independence_group="company_pr_funding_2026"
        )
        ev2 = EvidenceRecord(
            evidence_id="ev_blog_2",
            source_type="web_search",
            source_name="TechNews 2",
            url="https://technews2.com/startup-raises-5m",
            credibility=SourceCredibility.MEDIUM,
            independence_group="company_pr_funding_2026"
        )
        statement = StatementRecord(
            statement_id="stmt_003",
            statement_text="Company raised $5M in Series A",
            fact_type=FactType.THIRD_PARTY_CLAIM,
            primary_evidence=ev1,
            corroborating_evidence=[ev2],
            confidence=0.70
        )

        self.assertEqual(statement.primary_evidence.independence_group, "company_pr_funding_2026")
        self.assertEqual(statement.corroborating_evidence[0].independence_group, "company_pr_funding_2026")

        dump = statement.model_dump()
        self.assertEqual(dump["primary_evidence"]["independence_group"], "company_pr_funding_2026")
        self.assertEqual(dump["corroborating_evidence"][0]["independence_group"], "company_pr_funding_2026")

    def test_4_statement_confidence_validation(self):
        """TEST 4: Verify StatementRecord rejects invalid confidence (> 1.0 or < 0.0)."""
        with self.assertRaises(ValidationError):
            StatementRecord(
                statement_id="stmt_err_1",
                statement_text="Invalid confidence high",
                confidence=1.5
            )

        with self.assertRaises(ValidationError):
            StatementRecord(
                statement_id="stmt_err_2",
                statement_text="Invalid confidence low",
                confidence=-0.1
            )

    def test_5_scorefactor_backward_compatibility(self):
        """TEST 5: Verify existing ScoreFactor backward compatibility without evidence fields."""
        factor = ScoreFactor(
            factor="TAM size",
            points=25.0,
            max_points=30.0,
            reason="Market size estimated at $5B TAM.",
            source="https://marketresearch.com/report"
        )

        self.assertEqual(factor.factor, "TAM size")
        self.assertEqual(factor.points, 25.0)
        self.assertIsNone(factor.fact_type)
        self.assertIsNone(factor.primary_evidence)
        self.assertEqual(factor.corroborating_evidence, [])
        self.assertIsNone(factor.evidence_confidence)

        dump = factor.model_dump()
        self.assertEqual(dump["factor"], "TAM size")
        self.assertEqual(dump["points"], 25.0)
        self.assertIsNone(dump["fact_type"])

    def test_6_scorefactor_with_evidence(self):
        """TEST 6: Create ScoreFactor with evidence attached and verify serialization."""
        evidence = EvidenceRecord(
            evidence_id="ev_sf_001",
            source_type="github_api",
            source_name="GitHub API",
            url="https://github.com/test/repo",
            credibility=SourceCredibility.HIGH
        )
        factor = ScoreFactor(
            factor="Code Quality",
            points=18.0,
            max_points=20.0,
            reason="Active commits and high test coverage",
            source="https://github.com/test/repo",
            fact_type=FactType.VERIFIED_FACT,
            primary_evidence=evidence,
            corroborating_evidence=[],
            evidence_confidence=0.95
        )

        self.assertEqual(factor.fact_type, FactType.VERIFIED_FACT)
        self.assertEqual(factor.primary_evidence.evidence_id, "ev_sf_001")
        self.assertEqual(factor.evidence_confidence, 0.95)

        json_str = factor.model_dump_json()
        self.assertIn("VERIFIED_FACT", json_str)
        self.assertIn("ev_sf_001", json_str)


if __name__ == "__main__":
    unittest.main()
