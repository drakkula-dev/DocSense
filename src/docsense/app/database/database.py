from uuid import UUID
from ..schemas.document import FileResponse

files_db: dict[UUID, FileResponse] = {}