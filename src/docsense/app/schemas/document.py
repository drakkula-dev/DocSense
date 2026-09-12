from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from typing import Optional
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

class FileUpdate(BaseModel):
    file_name: Optional[str] = Field(default=None, min_length=1, json_schema_extra={"example": ""})

    model_config = ConfigDict(extra='forbid')
