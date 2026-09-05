from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class FileResponse(BaseModel):
    file_id: UUID
    file_name: str
    file_type: str
    file_text_content: str
    file_img_content: list[str]
    created_at: datetime
