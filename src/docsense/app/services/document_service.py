from typing import Annotated
from datetime import datetime, UTC
import uuid

from fastapi import APIRouter, status, UploadFile, File, Depends

from ..services.document_service import process_file
from ..schemas.document import FileResponse
from ..database.database import files_db
from ..dependencies import get_id_or_404

router = APIRouter()


# NOTE: response_model shapes/validates the return value against FileResponse.
@router.post("/", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
def upload_file(
    # NOTE: Annotated + File() = expect a multipart file upload, not JSON.
    file: Annotated[UploadFile, File(description="PDF, DOCX, TXT ONLY")]) -> FileResponse:

    file_bytes = file.file.read()
    result = process_file(file_bytes)

    # NOTE: Generated once so the same id can be reused below — avoids a
    # mismatch between the stored key and the object's own file_id field.
    created_id = uuid.uuid4()

    response = FileResponse(
        file_id=created_id,
        file_name=file.filename,
        file_type=result["type"],
        file_content=result["content"],
        created_at=datetime.now(UTC)
    )

    # NOTE: This is the actual persistence step — without it, nothing
    # survives past this request.
    files_db[created_id] = response

    return response


# NOTE: {id} must match the parameter name inside get_id_or_404 exactly.
@router.get("/{id}", response_model=FileResponse, status_code=status.HTTP_200_OK)
def get_file_by_id(
    # NOTE: Depends() runs get_id_or_404 first. 404 → this body never runs.
    # Success → `file` already holds the found FileResponse, no lookup needed.
    file: FileResponse = Depends(get_id_or_404)
) -> FileResponse:
    return file

# TODO: GET / — list all uploaded documents, likely with pagination.

# TODO: PUT/PATCH /{document_id} — update a document. Decide which: PUT
# would mean re-uploading/replacing the whole document; PATCH would mean
# updating a subset of fields (e.g. renaming, re-running extraction).

# TODO: DELETE /{document_id} — remove a document and its stored file/results.