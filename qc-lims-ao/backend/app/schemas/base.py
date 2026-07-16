"""
Base Pydantic schema for QC LIMS API response/request models.

Provides ORM-mode (from_attributes) so SQLAlchemy ORM objects can be
serialized directly. Pydantic v2.
"""

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base schema with ORM attribute reading enabled (pydantic v2)."""

    model_config = ConfigDict(from_attributes=True)
