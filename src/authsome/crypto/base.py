"""Abstract base class for encryption backends."""

from __future__ import annotations

from abc import ABC, abstractmethod

from authsome.models.connection import EncryptedField


class CryptoBackend(ABC):
    """
    Abstract encryption backend for field-level credential encryption.

    Implementations must provide AES-256-GCM compatible encrypt/decrypt
    producing the portable envelope format defined in spec §10.4.
    """

    @abstractmethod
    def encrypt(self, plaintext: str) -> EncryptedField:
        """
        Encrypt a plaintext string and return a portable encrypted envelope.

        Args:
            plaintext: The sensitive value to encrypt (e.g., access token, API key).

        Returns:
            An EncryptedField containing the encrypted data in portable envelope format.
        """
        ...

    @abstractmethod
    def decrypt(self, field: EncryptedField) -> str:
        """
        Decrypt an encrypted field envelope and return the plaintext.

        Args:
            field: The encrypted field envelope to decrypt.

        Returns:
            The decrypted plaintext string.

        Raises:
            EncryptionUnavailableError: If decryption fails.
        """
        ...
