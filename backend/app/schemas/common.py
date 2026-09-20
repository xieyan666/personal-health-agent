"""Shared API schema configuration."""

from pydantic import BaseModel, ConfigDict


class ORMResponse(BaseModel):
    """Base response schema that accepts SQLAlchemy model attributes."""

    model_config = ConfigDict(from_attributes=True)
