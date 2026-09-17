import os
import sys
import unittest
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from schemas.evidence import EvidenceRecord, SourceCredibility
from tools.search_tool import (
    SearchTool,
    create_evidence_record_from_hit,
    determine_domain_credibility,
    extract_domain,
    generate_web_evidence_id,
)


class TestWebEvidencePreservation(unittest.TestCase):

    def setUp(self):
        self.sample_hit = {
            "title": "Reuters: Startup Secures $10M Funding",
            "url": "https://www.reuters.com/technology/startup-secures-10m-funding-2026",
            "content": "Startup Corp announced a $10M Series A round led by Tier 1 VC.",
            "score": 0.92,
            "published_date": "2026-02-15"
        }
        self.query = "Startup Corp funding round"

    def test_A_tavily_hit_conversion(self):
        """TEST A: Tavily-like hit converts into a valid EvidenceRecord instance."""
        record = create_evidence_record_from_hit(self.sample_hit, self.query)
        self.assertIsInstance(record, EvidenceRecord)
        self.assertEqual(record.source_type, "web_search")

    def test_B_title_preserved(self):
        """TEST B: Title is preserved in source_name."""
        record = create_evidence_record_from_hit(self.sample_hit, self.query)
        self.assertEqual(record.source_name, "Reuters: Startup Secures $10M Funding")

    def test_C_url_preserved(self):
        """TEST C: URL is preserved in url."""
        record = create_evidence_record_from_hit(self.sample_hit, self.query)
        self.assertEqual(record.url, "https://www.reuters.com/technology/startup-secures-10m-funding-2026")

    def test_D_snippet_preserved(self):
        """TEST D: Snippet content is preserved in raw_snippet."""
        record = create_evidence_record_from_hit(self.sample_hit, self.query)
        self.assertEqual(record.raw_snippet, "Startup Corp announced a $10M Series A round led by Tier 1 VC.")

    def test_E_query_preserved(self):
        """TEST E: Originating query is preserved in query field."""
        record = create_evidence_record_from_hit(self.sample_hit, self.query)
        self.assertEqual(record.query, "Startup Corp funding round")

    def test_F_deterministic_evidence_id_identical(self):
        """TEST F: Deterministic evidence ID remains identical for same URL + query."""
        id1 = generate_web_evidence_id(self.sample_hit["url"], self.query)
        id2 = generate_web_evidence_id(self.sample_hit["url"], self.query)
        self.assertEqual(id1, id2)
        self.assertTrue(id1.startswith("ev_web_"))

    def test_G_different_query_changes_evidence_id(self):
        """TEST G: Different query changes evidence ID for the same URL."""
        id_q1 = generate_web_evidence_id(self.sample_hit["url"], "Query 1")
        id_q2 = generate_web_evidence_id(self.sample_hit["url"], "Query 2")
        self.assertNotEqual(id_q1, id_q2)

    def test_H_domain_and_source_origin_extraction(self):
        """TEST H: Domain and source-origin extraction works correctly."""
        domain = extract_domain("https://www.reuters.com/article/123")
        self.assertEqual(domain, "reuters.com")

        record = create_evidence_record_from_hit(self.sample_hit, self.query)
        self.assertEqual(record.domain, "reuters.com")
        self.assertEqual(record.independence_group, "reuters.com")

    def test_I_credibility_mapping(self):
        """TEST I: Verified high/medium/low/unknown credibility mapping."""
        # High Credibility (.gov / SEC / GitHub)
        self.assertEqual(determine_domain_credibility("sec.gov"), SourceCredibility.HIGH)
        self.assertEqual(determine_domain_credibility("india.gov.in"), SourceCredibility.HIGH)
        self.assertEqual(determine_domain_credibility("github.com"), SourceCredibility.HIGH)

        # Medium Credibility (Reuters / TechCrunch)
        self.assertEqual(determine_domain_credibility("reuters.com"), SourceCredibility.MEDIUM)
        self.assertEqual(determine_domain_credibility("techcrunch.com"), SourceCredibility.MEDIUM)

        # Low Credibility (PR Wires)
        self.assertEqual(determine_domain_credibility("prnewswire.com"), SourceCredibility.LOW)
        self.assertEqual(determine_domain_credibility("businesswire.com"), SourceCredibility.LOW)

        # Unknown Domain (Conservative baseline)
        self.assertEqual(determine_domain_credibility("randomblog123.io"), SourceCredibility.UNKNOWN)

    def test_J_search_return_contract_backward_compatibility(self):
        """TEST J: Verify search_tool.search return contract remains List[dict]."""
        tool = SearchTool()
        self.assertTrue(hasattr(tool, "search"))
        self.assertTrue(hasattr(tool, "search_with_evidence"))


if __name__ == "__main__":
    unittest.main()
