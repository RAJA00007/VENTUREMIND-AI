from rag.document_loader import document_loader

from rag.vector_store import vector_store



if __name__ == '__main__':
    text = document_loader.load_pdf(
        "sample.pdf"
    )
    
    
    result = vector_store.add_document(
    
        text,
    
        "startup_pitch"
    
    )
    
    
    print(result)
    
    
    
    search = vector_store.search(
    
        "Tell me about founders"
    
    )
    
    
    print(search)