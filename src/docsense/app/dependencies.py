from fastapi import status, HTTPException
from uuid import UUID
from .database.database import files_db
from .schemas.document import FileResponse

# NOTE: A dependency, not a route — called via Depends() from route functions.
# NOTE: Param must be named `id` to match the route's "/{id}" path.
def get_id_or_404(id: UUID) -> FileResponse:

    # NOTE: .get() returns None on a miss instead of raising KeyError.
    file = files_db.get(id)

    if not file:
        # NOTE: Stops execution here — the calling route's body never runs.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # NOTE: This value is what gets injected wherever Depends(get_id_or_404) is used.
    return file