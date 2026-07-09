from fastapi import (
    APIRouter,
    UploadFile,
    File
)

import shutil

from pathlib import Path


from rag.document_loader import document_loader
from rag.vector_store import vector_store



router = APIRouter(

    prefix="/documents",

    tags=["Documents"]

)



UPLOAD_DIR = Path(
    "uploads"
)



UPLOAD_DIR.mkdir(
    exist_ok=True
)




@router.post(
    "/upload"
)
async def upload_document(

    file: UploadFile = File(...)

):


    file_path = (
        UPLOAD_DIR /
        file.filename
    )


    with open(
        file_path,
        "wb"
    ) as buffer:


        shutil.copyfileobj(

            file.file,

            buffer

        )



    # extract PDF text

    text = document_loader.load_pdf(
        file_path
    )



    # store in vector DB

    result = vector_store.add_document(

        text=text,

        document_name=file.filename

    )



    return {

        "filename": file.filename,

        "status": "stored in AI memory",

        "vector_result": result

    }