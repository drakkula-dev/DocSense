from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class Table(BaseModel):
    rows: list[list[str]]

class FileResponse(BaseModel):
    file_id: UUID
    file_name: str
    file_type: str
    file_text_content: str
    file_table_content: list[Table]
    file_img_content: list[str]
    created_at: datetime
