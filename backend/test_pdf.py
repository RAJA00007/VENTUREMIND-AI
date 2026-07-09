from rag.document_loader import document_loader


text = document_loader.load_pdf(
    "sample.pdf"
)


print(
    text[:1000]
)