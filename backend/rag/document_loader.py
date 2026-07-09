from pypdf import PdfReader


class DocumentLoader:


    def load_pdf(
        self,
        file_path: str
    ) -> str:


        reader = PdfReader(
            file_path
        )


        text = ""


        for page in reader.pages:

            extracted = page.extract_text()


            if extracted:

                text += extracted + "\n"



        return text



document_loader = DocumentLoader()