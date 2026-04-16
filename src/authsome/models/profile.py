"""Profile metadata models matching spec §8."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class ProfileMetadata(BaseModel):
    """
    Profile metadata stored in ~/.authsome/profiles/<name>/metadata.json.

    Spec §8: Required fields are name, created_at, updated_at.
    """

    name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    description: Optional[str] = None

    model_config = {"extra": "allow"}
