from fastapi import status, HTTPException
from uuid import UUID
from .database.database import files_db

def get_id_or_404(id: UUID):
    file = files_db.get(id)
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return file