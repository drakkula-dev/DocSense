from typing import Annotated
from datetime import datetime, UTC
import uuid

from fastapi import APIRouter, status, UploadFile, File

from ..services.document_service import process_file

from ..schemas.document import FileResponse

# NOTE: Groups related endpoints under one router, e.g. all "/documents" routes.
router = APIRouter()


@router.post("/", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
def upload_file(
    # NOTE: Annotated + File() tells FastAPI to expect a file upload, not JSON.
    file: Annotated[UploadFile, File(description="PDF, DOCX, TXT ONLY")]) -> FileResponse:

    # NOTE: Reads the uploaded file into raw bytes for processing.
    file_bytes = file.file.read()
    result = process_file(file_bytes)

    return FileResponse(
        file_id=uuid.uuid4(),
        file_name=file.filename,
        file_type=result["type"],
        file_content=result["content"],
        created_at=datetime.now(UTC)
    )



# TODO: GET /{document_id} — retrieve one document's metadata + extracted
# content. Requires persisting results somewhere first (DB/storage) —
# nothing is saved yet, so there's nothing to fetch back.

# TODO: GET / — list all uploaded documents, likely with pagination.

# TODO: PUT/PATCH /{document_id} — update a document. Decide which: PUT
# would mean re-uploading/replacing the whole document; PATCH would mean
# updating a subset of fields (e.g. renaming, re-running extraction).

# TODO: DELETE /{document_id} — remove a document and its stored file/results.