from typing import List, Dict, Any
from pypdf import PdfReader


class DocumentLoader:

    def load_pdf_pages(
        self,
        file_path: str
    ) -> List[Dict[str, Any]]:
        """Extracts text page by page from a PDF file, preserving page numbers."""
        reader = PdfReader(file_path)
        pages = []

        for idx, page in enumerate(reader.pages):
            extracted = page.extract_text()
            if extracted and extracted.strip():
                pages.append({
                    "page_number": idx + 1,
                    "text": extracted
                })

        return pages

    def load_pdf(
        self,
        file_path: str
    ) -> str:
        """Backward-compatible method returning full concatenated PDF text."""
        pages = self.load_pdf_pages(file_path)
        return "\n".join(p["text"] for p in pages)


document_loader = DocumentLoader()