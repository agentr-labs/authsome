"""Enumerations for auth types, flow types, connection statuses, and export formats."""

from enum import Enum


class AuthType(str, Enum):
    """Authentication mechanism used by a provider."""

    OAUTH2 = "oauth2"
    API_KEY = "api_key"


class FlowType(str, Enum):
    """Specific authentication flow for a provider."""

    PKCE = "pkce"
    DEVICE_CODE = "device_code"
    DCR_PKCE = "dcr_pkce"
    API_KEY_PROMPT = "api_key_prompt"
    API_KEY_ENV = "api_key_env"


class ConnectionStatus(str, Enum):
    """Status of a credential connection."""

    NOT_CONNECTED = "not_connected"
    CONNECTED = "connected"
    EXPIRED = "expired"
    REVOKED = "revoked"
    INVALID = "invalid"


class ExportFormat(str, Enum):
    """Supported credential export formats."""

    ENV = "env"
    SHELL = "shell"
    JSON = "json"
