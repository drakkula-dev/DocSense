from typing import Annotated
from datetime import datetime, UTC
import uuid
from uuid import UUID

# NOTE: FastAPI-specific imports. APIRouter groups related routes under one
# object; status gives named HTTP status codes (readable instead of magic
# numbers like 201, 404); UploadFile + File are what make FastAPI accept
# multipart file uploads instead of JSON; Depends is the dependency-injection
# mechanism used below in get_file_by_id.
from fastapi import APIRouter, status, UploadFile, File, Depends

# NOTE: Business logic that turns raw file bytes into extracted text/type —
# kept in its own "service" module, separate from routing, so this file only
# has to worry about HTTP concerns (requests/responses), not file parsing.
from ..services.document_service import process_file

# NOTE: The Pydantic model defining the *shape* of a document. Used as the
# return type hint of these functions AND as FastAPI's response_model, which
# controls what actually gets serialized back to the client.
from ..schemas.document import FileResponse

# NOTE: The in-memory "database" — a plain dict standing in for real
# persistence until Postgres is added later. Imported by reference, so every
# route/function that imports this is reading and writing the exact same
# dict in memory, not separate copies.
from ..database.database import files_db

# NOTE: A dependency function — runs automatically BEFORE a route's own body,
# looks up a document by id, and raises a 404 if it isn't found. Reused
# across every route below that needs "find this id or fail" — one source
# of truth for that check.
from ..dependencies import get_id_or_404


# NOTE: Groups related endpoints under one router, e.g. all "/documents"
# routes, so main.py can include them all with a single line elsewhere.
router = APIRouter()


# NOTE: response_model=FileResponse tells FastAPI to validate/shape the
# return value against that schema before sending it — this also drives what
# shows up in the auto-generated /docs page for this endpoint.
# NOTE: status_code=201 (Created) is the correct HTTP status for a
# successful POST that creates a new resource — not the default 200.
@router.post("/", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
def upload_file(
    # NOTE: Annotated + File() tells FastAPI to expect a file upload, not JSON.
    file: Annotated[UploadFile, File(description="PDF, DOCX, TXT ONLY")]) -> FileResponse:

    # NOTE: Reads the uploaded file into raw bytes for processing.
    file_bytes = file.file.read()
    result = process_file(file_bytes)

    # NOTE: Generated once, as its own variable — this matters because the
    # exact same id needs to be reused twice below: inside the FileResponse,
    # and as the files_db dict key. Generating it twice separately would
    # create two different, mismatched ids.
    created_id = uuid.uuid4()

    # NOTE: Built and saved to a variable (not returned immediately) so the
    # exact same object can also be stored in files_db below — not a second,
    # separately-constructed copy that could drift out of sync.
    response = FileResponse(
        file_id=created_id,
        file_name=file.filename,
        file_type=result["type"],
        file_content=result["content"],
        created_at=datetime.now(UTC)
    )

    # NOTE: The actual persistence step. Without this line, nothing survives
    # past this request — local variables vanish once a function returns.
    # This mutates the module-level dict in place, so no `global` keyword is
    # needed (that would only be required to *reassign* files_db entirely).
    files_db[created_id] = response

    return response

# NOTE: {id} in the path makes this a dynamic route — FastAPI extracts
# whatever's in that URL segment and looks for a parameter named exactly
# "id" (here, and inside get_id_or_404) to hand that value to.
@router.get("/{id}", response_model=FileResponse, status_code=status.HTTP_200_OK)
def get_file_by_id(
    # NOTE: Depends() means get_id_or_404 runs BEFORE this function's body
    # even starts. If it raises a 404, this function never executes at all.
    # If it succeeds, `file` already holds the fully resolved FileResponse —
    # no lookup, no None-check needed here.
    file: FileResponse = Depends(get_id_or_404)
) -> FileResponse:
    return file

# TODO: GET / — list all uploaded documents, likely with pagination.

# TODO: PUT/PATCH /{document_id} — update a document. Decide which: PUT
# would mean re-uploading/replacing the whole document; PATCH would mean
# updating a subset of fields (e.g. renaming, re-running extraction).

# TODO: DELETE /{document_id} — remove a document and its stored file/results.