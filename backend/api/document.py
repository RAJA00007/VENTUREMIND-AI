from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form,
    HTTPException,
    Depends,
)

import shutil
import uuid
from pathlib import Path
from typing import Optional

from rag.document_loader import document_loader
from rag.vector_store import vector_store
from core.security import get_current_user
from models.user import User


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

    file: UploadFile = File(...),
    company_id: Optional[str] = Form(None),
    analysis_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),

):
    filename = Path(file.filename or "").name
    if not filename or Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    doc_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{doc_id}_{filename}"


    with open(
        file_path,
        "wb"
    ) as buffer:


        shutil.copyfileobj(

            file.file,

            buffer

        )



    # extract PDF text per page (page-aware)

    pages = document_loader.load_pdf_pages(
        file_path
    )



    # store in vector DB with metadata

    result = vector_store.add_document(
        text=pages,
        doc_id=doc_id,
        document_name=filename,
        company_id=company_id,
        analysis_id=analysis_id,
        source_type="uploaded_document",
        file_path=str(file_path),
        user_id=str(current_user.id)
    )

    chunks_created = result.get("chunks_created", 0) if isinstance(result, dict) else int(result)
    pages_processed = result.get("pages_processed", len(pages)) if isinstance(result, dict) else len(pages)

    return {

        "filename": filename,
        "document_name": filename,
        "document_id": doc_id,
        "company_id": company_id or "",
        "analysis_id": analysis_id or "",
        "status": "stored in AI memory",
        "chunks_created": chunks_created,
        "pages_processed": pages_processed,
        "uploaded_by": current_user.email,
        "user_id": current_user.id,
        "vector_result": result

    }
