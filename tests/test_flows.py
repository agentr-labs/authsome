"""Tests for authentication flows."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from authsome.crypto.keyring_crypto import KeyringCryptoBackend
from authsome.flows.api_key import ApiKeyEnvFlow, ApiKeyPromptFlow
from authsome.models.enums import AuthType, ConnectionStatus, FlowType
from authsome.models.provider import ApiKeyConfig, ProviderDefinition
from authsome.errors import AuthenticationFailedError, CredentialMissingError


def _make_api_key_provider() -> ProviderDefinition:
    return ProviderDefinition(
        name="testapi",
        display_name="Test API",
        auth_type=AuthType.API_KEY,
        flow=FlowType.API_KEY_PROMPT,
        api_key=ApiKeyConfig(
            header_name="Authorization",
            header_prefix="Bearer",
            env_var="TEST_API_KEY",
        ),
    )


class TestApiKeyPromptFlow:
    """API key prompt flow tests."""

    @pytest.fixture
    def crypto(self, tmp_path: Path) -> KeyringCryptoBackend:
        return KeyringCryptoBackend(tmp_path)

    def test_successful_login(self, crypto: KeyringCryptoBackend) -> None:
        flow = ApiKeyPromptFlow()
        provider = _make_api_key_provider()

        with patch("authsome.flows.api_key.getpass.getpass", return_value="sk-test-key-123"):
            record = flow.authenticate(
                provider=provider,
                crypto=crypto,
                profile="default",
                connection_name="default",
            )

        assert record.provider == "testapi"
        assert record.profile == "default"
        assert record.connection_name == "default"
        assert record.auth_type == AuthType.API_KEY
        assert record.status == ConnectionStatus.CONNECTED
        assert record.api_key is not None
        # Verify the encrypted key can be decrypted
        decrypted = crypto.decrypt(record.api_key)
        assert decrypted == "sk-test-key-123"

    def test_empty_key_rejected(self, crypto: KeyringCryptoBackend) -> None:
        flow = ApiKeyPromptFlow()
        provider = _make_api_key_provider()

        with patch("authsome.flows.api_key.getpass.getpass", return_value=""):
            with pytest.raises(AuthenticationFailedError, match="cannot be empty"):
                flow.authenticate(
                    provider=provider,
                    crypto=crypto,
                    profile="default",
                    connection_name="default",
                )

    def test_whitespace_only_rejected(self, crypto: KeyringCryptoBackend) -> None:
        flow = ApiKeyPromptFlow()
        provider = _make_api_key_provider()

        with patch("authsome.flows.api_key.getpass.getpass", return_value="   "):
            with pytest.raises(AuthenticationFailedError, match="cannot be empty"):
                flow.authenticate(
                    provider=provider,
                    crypto=crypto,
                    profile="default",
                    connection_name="default",
                )

    def test_missing_api_key_config(self, crypto: KeyringCryptoBackend) -> None:
        flow = ApiKeyPromptFlow()
        provider = ProviderDefinition(
            name="noconfig",
            display_name="No Config",
            auth_type=AuthType.API_KEY,
            flow=FlowType.API_KEY_PROMPT,
        )
        with pytest.raises(AuthenticationFailedError, match="missing 'api_key'"):
            flow.authenticate(
                provider=provider,
                crypto=crypto,
                profile="default",
                connection_name="default",
            )


class TestApiKeyEnvFlow:
    """API key env import flow tests."""

    @pytest.fixture
    def crypto(self, tmp_path: Path) -> KeyringCryptoBackend:
        return KeyringCryptoBackend(tmp_path)

    def test_successful_env_import(
        self, crypto: KeyringCryptoBackend, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TEST_API_KEY", "env-key-value")
        flow = ApiKeyEnvFlow()
        provider = _make_api_key_provider()

        record = flow.authenticate(
            provider=provider,
            crypto=crypto,
            profile="default",
            connection_name="default",
        )

        assert record.status == ConnectionStatus.CONNECTED
        assert record.api_key is not None
        assert crypto.decrypt(record.api_key) == "env-key-value"

    def test_missing_env_var(
        self, crypto: KeyringCryptoBackend, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("TEST_API_KEY", raising=False)
        flow = ApiKeyEnvFlow()
        provider = _make_api_key_provider()

        with pytest.raises(CredentialMissingError, match="not set or empty"):
            flow.authenticate(
                provider=provider,
                crypto=crypto,
                profile="default",
                connection_name="default",
            )

    def test_no_env_var_defined(self, crypto: KeyringCryptoBackend) -> None:
        flow = ApiKeyEnvFlow()
        provider = ProviderDefinition(
            name="noenv",
            display_name="No Env",
            auth_type=AuthType.API_KEY,
            flow=FlowType.API_KEY_ENV,
            api_key=ApiKeyConfig(env_var=None),
        )
        with pytest.raises(AuthenticationFailedError, match="does not define an env_var"):
            flow.authenticate(
                provider=provider,
                crypto=crypto,
                profile="default",
                connection_name="default",
            )
