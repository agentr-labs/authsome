"""Global configuration models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EncryptionConfig(BaseModel):
    """
    Encryption configuration block.

    Modes:
    - "local_key": master key stored at ~/.authsome/master.key
    - "keyring":   master key stored in the OS keyring
    """

    mode: str = "local_key"


class GlobalConfig(BaseModel):
    """Global configuration stored in ~/.authsome/config.json."""

    spec_version: int = 1
    default_profile: str = "default"
    encryption: EncryptionConfig | None = Field(default_factory=EncryptionConfig)

    extra_fields: dict[str, Any] = Field(default_factory=dict, exclude=True)

    model_config = {"extra": "allow"}
