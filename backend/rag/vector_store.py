import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import chromadb
from core.config import settings
from core.logging import app_logger

# Base backend directory: c:\Users\Raja\venturemind-ai\backend
BASE_DIR = Path(__file__).resolve().parent.parent


def get_chroma_path() -> Path:
    """Returns the absolute, deterministic path to ChromaDB persistent storage."""
    if getattr(settings, "CHROMA_PERSIST_DIRECTORY", None):
        return Path(settings.CHROMA_PERSIST_DIRECTORY).resolve()
    return (BASE_DIR / "chroma_db").resolve()





class VectorStore:

    def __init__(self):
        self._client = None
        self._collection = None
        self._embedding_model = None

    def _ensure_initialized(self):
        if self._client is not None and self._collection is not None:
            return

        chroma_path = get_chroma_path()
        chroma_path.mkdir(parents=True, exist_ok=True)
        chroma_path_str = str(chroma_path)

        try:
            self._client = chromadb.PersistentClient(path=chroma_path_str)
            self._collection = self._client.get_or_create_collection(name="startup_docs")
        except Exception as exc:
            app_logger.warning(f"[VectorStore] Initializing ChromaDB at '{chroma_path_str}' warning: {exc}. Resetting store...")
            if chroma_path.exists():
                shutil.rmtree(chroma_path_str, ignore_errors=True)
                chroma_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=chroma_path_str)
            self._collection = self._client.get_or_create_collection(name="startup_docs")

    @property
    def client(self):
        self._ensure_initialized()
        return self._client

    @property
    def collection(self):
        self._ensure_initialized()
        return self._collection

    @property
    def embedding_model(self):
        if not hasattr(self, "_embedding_model") or self._embedding_model is None:
            from sentence_transformers import SentenceTransformer
            self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        return self._embedding_model

    def add_document(
        self,
        text: Union[str, List[Dict[str, Any]]] = None,
        doc_id: Optional[str] = None,
        document_name: Optional[str] = None,
        company_id: Optional[str] = None,
        analysis_id: Optional[str] = None,
        source_type: str = "uploaded_document",
        file_path: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Adds document chunks with complete provenance metadata to ChromaDB.
        Supports both raw text strings and page-aware structures.
        """
        self._ensure_initialized()

        effective_doc_id = doc_id or kwargs.get("document_id") or str(uuid.uuid4())
        effective_doc_name = document_name or kwargs.get("filename") or "document.pdf"
        effective_company_id = company_id or ""
        effective_analysis_id = str(analysis_id) if analysis_id is not None else ""
        uploaded_at = datetime.now(timezone.utc).isoformat()

        chunk_texts: List[str] = []
        chunk_ids: List[str] = []
        chunk_metadatas: List[Dict[str, Any]] = []
        pages_processed = 0

        if isinstance(text, list):
            # Page-aware structure: list of {"page_number": int, "text": str}
            pages_processed = len(text)
            for page in text:
                p_num = page.get("page_number", 1)
                p_text = page.get("text", "")
                p_chunks = self.chunk_text(p_text)
                for c_idx, c_text in enumerate(p_chunks):
                    c_id = f"{effective_doc_id}_p{p_num}_c{c_idx}"
                    chunk_texts.append(c_text)
                    chunk_ids.append(c_id)
                    chunk_metadatas.append({
                        "company_id": effective_company_id,
                        "analysis_id": effective_analysis_id,
                        "document_id": effective_doc_id,
                        "document_name": effective_doc_name,
                        "source_type": source_type,
                        "page_number": p_num,
                        "chunk_id": c_id,
                        "uploaded_at": uploaded_at,
                    })
        elif isinstance(text, str):
            pages_processed = 1
            p_chunks = self.chunk_text(text)
            for c_idx, c_text in enumerate(p_chunks):
                c_id = f"{effective_doc_id}_c{c_idx}"
                chunk_texts.append(c_text)
                chunk_ids.append(c_id)
                chunk_metadatas.append({
                    "company_id": effective_company_id,
                    "analysis_id": effective_analysis_id,
                    "document_id": effective_doc_id,
                    "document_name": effective_doc_name,
                    "source_type": source_type,
                    "page_number": 1,
                    "chunk_id": c_id,
                    "uploaded_at": uploaded_at,
                })
        else:
            return {
                "chunks_created": 0,
                "pages_processed": 0,
                "document_id": effective_doc_id,
                "company_id": effective_company_id,
                "analysis_id": effective_analysis_id,
                "document_name": effective_doc_name,
            }

        if not chunk_texts:
            return {
                "chunks_created": 0,
                "pages_processed": pages_processed,
                "document_id": effective_doc_id,
                "company_id": effective_company_id,
                "analysis_id": effective_analysis_id,
                "document_name": effective_doc_name,
            }

        embeddings = self.embedding_model.encode(chunk_texts).tolist()

        self.collection.add(
            ids=chunk_ids,
            documents=chunk_texts,
            embeddings=embeddings,
            metadatas=chunk_metadatas
        )

        return {
            "chunks_created": len(chunk_texts),
            "pages_processed": pages_processed,
            "document_id": effective_doc_id,
            "company_id": effective_company_id,
            "analysis_id": effective_analysis_id,
            "document_name": effective_doc_name,
        }

    def search(
        self,
        query: str,
        company_id: Optional[str] = None,
        analysis_id: Optional[str] = None,
        n_results: int = 3,
        where: Optional[dict] = None,
        allow_global: bool = False
    ) -> Dict[str, Any]:
        """
        Retrieves relevant context with strict company metadata isolation.
        
        If company_id is provided, search is strictly filtered by company_id.
        If company_id is omitted and allow_global is False, returns a safe
        empty result to prevent accidental cross-company data leakage.
        """
        self._ensure_initialized()

        where_filter = where

        if where_filter is None:
            filters = []
            if company_id:
                filters.append({"company_id": company_id})
            if analysis_id:
                filters.append({"analysis_id": str(analysis_id)})

            if len(filters) == 1:
                where_filter = filters[0]
            elif len(filters) > 1:
                where_filter = {"$and": filters}

        # Safe Isolation Check: if no filter and allow_global is False, refuse global search
        if not where_filter and not allow_global:
            app_logger.info(f"[VectorStore] Un-scoped search for query '{query}' denied (no company_id). Returning safe empty result.")
            return {
                "ids": [[]],
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]]
            }

        query_embedding = self.embedding_model.encode(query).tolist()
        query_kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": n_results
        }
        if where_filter:
            query_kwargs["where"] = where_filter

        results = self.collection.query(**query_kwargs)
        return results

    def chunk_text(
        self,
        text: str,
        size_in_words: int = 120,
        overlap: int = 20
    ) -> List[str]:
        words = text.split()
        if not words:
            return []

        chunks = []
        i = 0
        while i < len(words):
            chunk_words = words[i:i + size_in_words]
            chunks.append(" ".join(chunk_words))
            i += (size_in_words - overlap)
            if size_in_words <= overlap:
                break
        return chunks


vector_store = VectorStore()
