import os
import sys
import unittest
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from rag.document_loader import document_loader
from rag.vector_store import vector_store, get_chroma_path


class TestRAGIsolationAndProvenance(unittest.TestCase):

    def setUp(self):
        # Ensure clean initialized vector store
        vector_store._ensure_initialized()

    def test_1_metadata_preservation(self):
        """TEST 1 — Metadata Preservation: Insert page-aware chunks and verify metadata."""
        doc_pages = [
            {"page_number": 1, "text": "Page one overview for TestCorp."},
            {"page_number": 2, "text": "Page two financial metrics for TestCorp."}
        ]
        result = vector_store.add_document(
            text=doc_pages,
            doc_id="doc_test_101",
            document_name="testcorp_deck.pdf",
            company_id="comp_testcorp",
            analysis_id="analysis_999",
            source_type="uploaded_document"
        )
        self.assertEqual(result["chunks_created"], 2)
        self.assertEqual(result["pages_processed"], 2)

        # Query vector store with company_id filter
        res = vector_store.search("financial metrics", company_id="comp_testcorp")
        self.assertTrue(len(res["documents"][0]) > 0)
        
        meta = res["metadatas"][0][0]
        self.assertEqual(meta["company_id"], "comp_testcorp")
        self.assertEqual(meta["analysis_id"], "analysis_999")
        self.assertEqual(meta["document_id"], "doc_test_101")
        self.assertEqual(meta["document_name"], "testcorp_deck.pdf")
        self.assertEqual(meta["source_type"], "uploaded_document")
        self.assertIn("page_number", meta)

    def test_2_company_isolation(self):
        """TEST 2 — Company Isolation: Verify Company A docs never appear in Company B queries."""
        vector_store.add_document(
            text="Company Alpha confidential revenue is $10M in FY2025.",
            doc_id="doc_alpha_1",
            document_name="alpha_deck.pdf",
            company_id="company_alpha"
        )
        vector_store.add_document(
            text="Company Beta confidential revenue is $1M in FY2025.",
            doc_id="doc_beta_1",
            document_name="beta_deck.pdf",
            company_id="company_beta"
        )

        # Query for Company Alpha
        res_alpha = vector_store.search("revenue FY2025", company_id="company_alpha")
        docs_alpha = res_alpha["documents"][0]
        metas_alpha = res_alpha["metadatas"][0]

        self.assertTrue(len(docs_alpha) > 0)
        for meta in metas_alpha:
            self.assertEqual(meta["company_id"], "company_alpha")
            self.assertNotEqual(meta["company_id"], "company_beta")

        for doc in docs_alpha:
            self.assertIn("Company Alpha", doc)
            self.assertNotIn("Company Beta", doc)

        # Query for Company Beta
        res_beta = vector_store.search("revenue FY2025", company_id="company_beta")
        docs_beta = res_beta["documents"][0]
        metas_beta = res_beta["metadatas"][0]

        self.assertTrue(len(docs_beta) > 0)
        for meta in metas_beta:
            self.assertEqual(meta["company_id"], "company_beta")
            self.assertNotEqual(meta["company_id"], "company_alpha")

        for doc in docs_beta:
            self.assertIn("Company Beta", doc)
            self.assertNotIn("Company Alpha", doc)

    def test_3_working_directory_independence(self):
        """TEST 3 — Working Directory Independence: Verify Chroma path is absolute."""
        chroma_path = get_chroma_path()
        self.assertTrue(chroma_path.is_absolute())
        self.assertTrue(chroma_path.exists())

    def test_4_legacy_data_safety(self):
        """TEST 4 — Legacy Data Safety: Un-scoped legacy chunks are filtered out from company queries."""
        # Insert a legacy chunk without company_id metadata, passing pre-computed embeddings
        legacy_doc = ["Unscoped legacy public data snippet."]
        legacy_embeddings = vector_store.embedding_model.encode(legacy_doc).tolist()
        vector_store.collection.add(
            ids=["legacy_chunk_001"],
            documents=legacy_doc,
            embeddings=legacy_embeddings,
            metadatas=[{"source_type": "legacy_doc"}]
        )

        # Query scoped to company_alpha should NOT return legacy_chunk_001
        res = vector_store.search("legacy public data", company_id="company_alpha")
        ids = res["ids"][0]
        self.assertNotIn("legacy_chunk_001", ids)

        # Un-scoped query without company_id returns safe empty result by default
        unscoped_res = vector_store.search("legacy public data")
        self.assertEqual(len(unscoped_res["documents"][0]), 0)

    def test_5_application_smoke_test(self):
        """TEST 5 — Existing Application Smoke Test: Verify routes, imports, and services."""
        from main import app
        from api.document import upload_document
        from workflows.chat_workflow import chatbot
        
        self.assertIsNotNone(app)
        self.assertIsNotNone(upload_document)
        self.assertIsNotNone(chatbot)

    def test_6_allow_global_does_not_bypass_company_filter(self):
        """TEST 6 — Verify allow_global=True CANNOT bypass company_id metadata filtering when company_id is set."""
        vector_store.add_document(
            text="Confidential Strategy doc for Company Alpha.",
            doc_id="doc_alpha_strat",
            document_name="alpha_strat.pdf",
            company_id="company_alpha"
        )
        vector_store.add_document(
            text="Confidential Strategy doc for Company Beta.",
            doc_id="doc_beta_strat",
            document_name="beta_strat.pdf",
            company_id="company_beta"
        )

        # Call search with company_id="company_beta" AND allow_global=True
        res = vector_store.search("Confidential Strategy", company_id="company_beta", allow_global=True)
        docs = res["documents"][0]
        metas = res["metadatas"][0]

        self.assertTrue(len(docs) > 0)
        for meta in metas:
            self.assertEqual(meta["company_id"], "company_beta")
            self.assertNotEqual(meta["company_id"], "company_alpha")

        for doc in docs:
            self.assertIn("Company Beta", doc)
            self.assertNotIn("Company Alpha", doc)


if __name__ == "__main__":
    unittest.main()
