import shutil
from pathlib import Path
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
        text: str,
        doc_id: str
    ) -> int:
        chunks = self.chunk_text(text)
        if not chunks:
            return 0

        embeddings = self.embedding_model.encode(chunks).tolist()

        self.collection.add(
            ids=[f"{doc_id}_{i}" for i in range(len(chunks))],
            documents=chunks,
            embeddings=embeddings
        )

        return len(chunks)

    def search(
        self,
        query: str
    ):
        query_embedding = self.embedding_model.encode(query).tolist()
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=3
        )
        return results

    def chunk_text(
        self,
        text: str,
        size_in_words: int = 120,
        overlap: int = 20
    ):
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