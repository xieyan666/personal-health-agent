from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    char_count: int
    created_at: datetime
    updated_at: datetime
