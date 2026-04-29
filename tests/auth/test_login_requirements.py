"""Integration tests for per-flow input requirements in AuthLayer.login()."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from authsome.auth import AuthLayer
from authsome.auth.flows.base import FlowResult
from authsome.auth.input_provider import InputField
from authsome.auth.models.connection import ConnectionRecord
from authsome.auth.models.enums import AuthType, ConnectionStatus, FlowType
from authsome.auth.models.provider import FlowConfig, OAuthConfig, ProviderDefinition
from authsome.context import AuthsomeContext
from authsome.errors import AuthsomeError


@pytest.fixture
def auth(tmp_path: Path) -> AuthLayer:
    home = tmp_path / ".authsome"
    actx = AuthsomeContext.create(home=home)
    yield actx.auth
    actx.close()


class CapturingProvider:
    """Records the ``InputField``s requested + returns canned values."""

    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}
        self.captured: list[InputField] = []

    def collect(self, fields: list[InputField]) -> dict[str, str]:
        self.captured.extend(fields)
        return {k: v for k, v in self.values.items() if any(f.name == k for f in fields)}

    def names(self) -> list[str]:
        return [f.name for f in self.captured]

    def required_names(self) -> list[str]:
        # Mirrors BridgeInputProvider's convention: default is None ⇒ required.
        return [f.name for f in self.captured if f.default is None]


def _connection(provider: str) -> ConnectionRecord:
    return ConnectionRecord(
        schema_version=2,
        provider=provider,
        profile="default",
        connection_name="default",
        auth_type=AuthType.OAUTH2,
        status=ConnectionStatus.CONNECTED,
        access_token="tok",
    )


def _register(
    auth: AuthLayer,
    name: str,
    *,
    flow: FlowType = FlowType.PKCE,
    flows_block: dict | None = None,
) -> None:
    auth.register_provider(
        ProviderDefinition(
            name=name,
            display_name=name.title(),
            auth_type=AuthType.OAUTH2,
            flow=flow,
            oauth=OAuthConfig(
                authorization_url="http://auth",
                token_url="http://token",
                flows=flows_block or {},
            ),
        )
    )


def _patch_handler(record: ConnectionRecord):
    handlers = patch("authsome.auth._FLOW_HANDLERS")
    started = handlers.start()
    mock_handler = MagicMock()
    mock_handler.authenticate.return_value = FlowResult(connection=record)
    started.get.return_value = lambda: mock_handler
    return handlers


def test_hidden_field_not_prompted(auth: AuthLayer) -> None:
    _register(
        auth,
        "p1",
        flow=FlowType.DEVICE_CODE,
        flows_block={"device_code": FlowConfig(inputs={"client_id": "required", "client_secret": "hidden"})},
    )
    capt = CapturingProvider({"client_id": "cid"})
    p = _patch_handler(_connection("p1"))
    try:
        auth.login("p1", input_provider=capt, scopes=[])
    finally:
        p.stop()

    assert "client_id" in capt.names()
    assert "client_secret" not in capt.names()
    assert "client_id" in capt.required_names()


def test_both_hidden_skips_credentials(auth: AuthLayer) -> None:
    _register(
        auth,
        "p2",
        flow=FlowType.DEVICE_CODE,
        flows_block={"device_code": FlowConfig(inputs={"client_id": "hidden", "client_secret": "hidden"})},
    )
    capt = CapturingProvider()
    p = _patch_handler(_connection("p2"))
    try:
        auth.login("p2", input_provider=capt, scopes=[])
    finally:
        p.stop()

    assert "client_id" not in capt.names()
    assert "client_secret" not in capt.names()


def test_required_blank_raises(auth: AuthLayer) -> None:
    _register(
        auth,
        "p3",
        flows_block={"pkce": FlowConfig(inputs={"client_secret": "required"})},
    )
    capt = CapturingProvider({"client_id": "cid", "client_secret": ""})
    p = _patch_handler(_connection("p3"))
    try:
        with pytest.raises(AuthsomeError, match="client_secret"):
            auth.login("p3", input_provider=capt)
    finally:
        p.stop()


def test_required_supplied_succeeds(auth: AuthLayer) -> None:
    _register(
        auth,
        "p4",
        flows_block={"pkce": FlowConfig(inputs={"client_secret": "required"})},
    )
    capt = CapturingProvider({"client_id": "cid", "client_secret": "csec"})
    p = _patch_handler(_connection("p4"))
    try:
        auth.login("p4", input_provider=capt)
    finally:
        p.stop()

    creds = auth._get_provider_client_credentials("p4")
    assert creds.client_id == "cid"
    assert creds.client_secret == "csec"


def test_no_flows_block_keeps_legacy_behavior(auth: AuthLayer) -> None:
    """Provider without `flows` block ⇒ same prompts as before the feature."""
    _register(auth, "p5", flow=FlowType.PKCE)
    capt = CapturingProvider({"client_id": "cid", "client_secret": ""})
    p = _patch_handler(_connection("p5"))
    try:
        auth.login("p5", input_provider=capt, scopes=[])
    finally:
        p.stop()

    # Legacy: client_id required, client_secret optional.
    assert "client_id" in capt.required_names()
    assert "client_secret" in capt.names()
    assert "client_secret" not in capt.required_names()


def test_github_pkce_makes_client_secret_required(auth: AuthLayer) -> None:
    capt = CapturingProvider({"client_id": "cid", "client_secret": ""})
    p = _patch_handler(_connection("github"))
    try:
        with pytest.raises(AuthsomeError, match="client_secret"):
            auth.login("github", input_provider=capt, flow_override=FlowType.PKCE)
    finally:
        p.stop()


def test_github_device_code_hides_client_secret(auth: AuthLayer) -> None:
    capt = CapturingProvider({"client_id": "cid"})
    p = _patch_handler(_connection("github"))
    try:
        auth.login("github", input_provider=capt, flow_override=FlowType.DEVICE_CODE, scopes=[])
    finally:
        p.stop()

    assert "client_secret" not in capt.names()
    assert "client_id" in capt.required_names()


def test_postiz_device_code_asks_no_credentials(auth: AuthLayer) -> None:
    capt = CapturingProvider()
    p = _patch_handler(_connection("postiz"))
    try:
        auth.login("postiz", input_provider=capt, scopes=[])
    finally:
        p.stop()

    assert "client_id" not in capt.names()
    assert "client_secret" not in capt.names()


def test_no_scopes_prompt_when_provider_declares_no_scopes(auth: AuthLayer) -> None:
    """Providers with empty/missing oauth.scopes don't show a useless scopes field."""
    capt = CapturingProvider()
    p = _patch_handler(_connection("postiz"))
    try:
        auth.login("postiz", input_provider=capt)
    finally:
        p.stop()

    assert "scopes" not in capt.names()


def test_scopes_prompt_appears_when_provider_declares_scopes(auth: AuthLayer) -> None:
    """Providers with non-empty oauth.scopes still get the scopes prompt."""
    capt = CapturingProvider({"client_id": "cid"})
    p = _patch_handler(_connection("github"))
    try:
        auth.login("github", input_provider=capt, flow_override=FlowType.DEVICE_CODE)
    finally:
        p.stop()

    assert "scopes" in capt.names()
