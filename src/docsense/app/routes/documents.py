from typing import Annotated, Any

from fastapi import APIRouter, status, UploadFile, File

from ..services.document_service import process_document

# NOTE: Groups related endpoints under one router, e.g. all "/documents" routes.
router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED)
def upload_file(
    # NOTE: Annotated + File() tells FastAPI to expect a file upload, not JSON.
    file: Annotated[UploadFile, File(description="PDF, DOCX, TXT ONLY")]
) -> dict[Any, Any]:

    # NOTE: Reads the uploaded file into raw bytes for processing.
    file_content = file.file.read()

    # NOTE: Delegates file-type checking and processing to the service layer.
    file_type = process_document(file_content)

    # TODO: Have process_document also extract and return the file's text content.
    return {
        "File Name": file.filename,
        "File Type": file_type,
        # TODO: Add extracted text here once process_document returns it.
    }