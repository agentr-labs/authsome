"""Connection, provider metadata, and provider state record models matching spec §11-13."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from authsome.models.enums import AuthType, ConnectionStatus


class EncryptedField(BaseModel):
    """
    Portable encryption envelope for sensitive fields.

    Spec §10.4: AES-256-GCM encrypted field with base64-encoded components.
    """

    enc: int = 1
    alg: str = "AES-256-GCM"
    kid: str = "local"
    nonce: str  # base64-encoded
    ciphertext: str  # base64-encoded
    tag: str  # base64-encoded


class AccountInfo(BaseModel):
    """Account identity information from the provider."""

    id: Optional[str] = None
    label: Optional[str] = None


class ConnectionRecord(BaseModel):
    """
    Credential record for a named connection.

    Spec §12: Stored at key profile:<profile>:<provider>:connection:<connection_name>.
    Required fields: schema_version, provider, profile, connection_name, auth_type, status, metadata.
    """

    schema_version: int = 1
    provider: str
    profile: str
    connection_name: str
    auth_type: AuthType
    status: ConnectionStatus

    # OAuth2 fields
    scopes: Optional[list[str]] = None
    access_token: Optional[EncryptedField] = None
    refresh_token: Optional[EncryptedField] = None
    token_type: Optional[str] = None
    expires_at: Optional[datetime] = None
    obtained_at: Optional[datetime] = None

    # API key field
    api_key: Optional[EncryptedField] = None

    # Account info
    account: Optional[AccountInfo] = Field(default_factory=AccountInfo)

    # DCR-obtained client credentials (stored encrypted)
    client_id: Optional[str] = None
    client_secret: Optional[EncryptedField] = None

    # Forward-compatible metadata
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class ProviderMetadataRecord(BaseModel):
    """
    Non-secret metadata about a provider within a profile.

    Spec §11: Stored at key profile:<profile>:<provider>:metadata.
    """

    schema_version: int = 1
    profile: str
    provider: str
    default_connection: str = "default"
    connection_names: list[str] = Field(default_factory=list)
    last_used_connection: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class ProviderStateRecord(BaseModel):
    """
    Transient, non-secret provider state within a profile.

    Spec §13: Stored at key profile:<profile>:<provider>:state.
    """

    schema_version: int = 1
    provider: str
    profile: str
    last_refresh_at: Optional[datetime] = None
    last_refresh_error: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}
