import chromadb

from sentence_transformers import SentenceTransformer



class VectorStore:


    def __init__(self):

        self.client = chromadb.PersistentClient(
            path="./chroma_db"
        )


        self.collection = (
            self.client.get_or_create_collection(
                name="startup_docs"
            )
        )


        self.embedding_model = SentenceTransformer(
            "all-MiniLM-L6-v2"
        )



    def add_document(
        self,
        text: str,
        doc_id: str
    ):


        chunks = self.chunk_text(
            text
        )


        embeddings = (
            self.embedding_model.encode(
                chunks
            )
            .tolist()
        )


        self.collection.add(

            ids=[
                f"{doc_id}_{i}"
                for i in range(len(chunks))
            ],


            documents=chunks,


            embeddings=embeddings
        )


        return len(chunks)



    def search(
        self,
        query: str
    ):


        query_embedding = (
            self.embedding_model
            .encode(
                query
            )
            .tolist()
        )


        results = self.collection.query(

            query_embeddings=[
                query_embedding
            ],

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