"""Abstract base class and result type for authentication flows."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from authsome.auth.models.connection import ConnectionRecord, ProviderClientRecord
from authsome.auth.models.provider import ProviderDefinition


@dataclass
class FlowResult:
    """Returned by every flow's authenticate() method.

    client_record is only populated by DCR-based flows that register a new
    OAuth client as part of the authentication process.
    """

    connection: ConnectionRecord
    client_record: ProviderClientRecord | None = None


class AuthFlow(ABC):
    """Abstract authentication flow handler.

    Flows return FlowResult with plaintext credential fields.
    Encryption is handled by the Vault when the record is persisted.
    """

    @abstractmethod
    def authenticate(
        self,
        provider: ProviderDefinition,
        profile: str,
        connection_name: str,
        scopes: list[str] | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        api_key: str | None = None,
    ) -> FlowResult:
        """Execute the authentication flow and return a FlowResult.

        All credential fields in the returned record are plaintext strings.
        The caller (AuthLayer) is responsible for persisting via the Vault.
        """
        ...
