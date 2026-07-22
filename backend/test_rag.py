from rag.document_loader import document_loader
from rag.vector_store import vector_store



if __name__ == '__main__':
    text = document_loader.load_pdf(
        "sample.pdf"
    )
    
    
    count = vector_store.add_document(
        text,
        "startup_pdf"
    )
    
    
    print(
        "Chunks stored:",
        count
    )
    
    
    result = vector_store.search(
        "What does it say about founders?"
    )
    
    
    print(
        result["documents"]
    )