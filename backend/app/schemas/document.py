"""Document metadata API schema."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from backend.app.schemas.common import ORMResponse


class DocumentResponse(ORMResponse):
    id: UUID
    knowledge_base_id: UUID
    name: str
    source_type: str
    mime_type: Optional[str]
    size_bytes: Optional[int]
    content_hash: Optional[str]
    status: str
    error_message: Optional[str]
    metadata_: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
