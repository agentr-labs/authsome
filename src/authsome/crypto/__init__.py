"""Authsome crypto layer.

Two encryption backends are available, selected via config.json encryption.mode:

- "keyring": Master key stored in the OS keyring (macOS Keychain, GNOME Keyring, etc.)
- "local_key": Master key stored as a local file (~/.authsome/master.key)
"""

from authsome.crypto.base import CryptoBackend
from authsome.crypto.keyring_crypto import KeyringCryptoBackend
from authsome.crypto.local_file_crypto import LocalFileCryptoBackend

__all__ = ["CryptoBackend", "KeyringCryptoBackend", "LocalFileCryptoBackend"]
