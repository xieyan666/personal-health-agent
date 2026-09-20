from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MentalAssessmentSourceContext(BaseModel):
    """Opaque assessment reference supplied after an explicit result-page jump.

    The browser never sends questionnaire answers.  The Mental Health Agent
    resolves this ID against the authenticated user's own assessment record.
    """

    source: Literal["mental_assessment"]
    assessment_id: UUID
    assessment_type: str = Field(min_length=1, max_length=20)


class HealthChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[UUID] = None
    source_context: Optional[MentalAssessmentSourceContext] = None


class HealthChatResponse(BaseModel):
    answer: str
    conversation_id: Optional[UUID] = None
