from rag.document_loader import document_loader


if __name__ == '__main__':
    text = document_loader.load_pdf(
        "sample.pdf"
    )
    
    
    print(
        text[:1000]
    )