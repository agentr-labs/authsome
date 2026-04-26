"""Tests for the DCR PKCE OAuth flow."""

import json
import urllib.parse
import urllib.request
from unittest.mock import MagicMock, patch

import pytest
import requests

from authsome.auth.flows.bridge import _find_free_port
from authsome.auth.flows.dcr_pkce import (
    DcrPkceFlow,
    _CallbackHandler,
    _generate_pkce,
)
from authsome.auth.models.connection import ConnectionStatus
from authsome.auth.models.enums import AuthType, FlowType
from authsome.auth.models.provider import OAuthConfig, ProviderDefinition
from authsome.errors import AuthenticationFailedError, DiscoveryError


def _make_provider() -> ProviderDefinition:
    return ProviderDefinition(
        name="testdcr",
        display_name="Test DCR",
        auth_type=AuthType.OAUTH2,
        flow=FlowType.DCR_PKCE,
        oauth=OAuthConfig(
            authorization_url="https://auth.example.com/auth",
            token_url="https://auth.example.com/token",
        ),
    )


def test_find_free_port():
    port = _find_free_port()
    assert isinstance(port, int)
    assert port > 0


def test_generate_pkce():
    verifier, challenge = _generate_pkce()
    assert len(verifier) >= 43
    assert len(challenge) >= 43


def test_callback_handler_log():
    handler = _CallbackHandler.__new__(_CallbackHandler)
    handler.log_message("test %s", "msg")


def test_missing_oauth():
    provider = _make_provider()
    provider.oauth = None
    flow = DcrPkceFlow()

    with pytest.raises(AuthenticationFailedError, match="missing 'oauth' configuration"):
        flow.authenticate(provider, "default", "default")


def test_discover_registration_endpoint_missing_oauth():
    flow = DcrPkceFlow()
    provider = _make_provider()
    provider.oauth = None
    with pytest.raises(DiscoveryError, match="No OAuth config"):
        flow._discover_registration_endpoint(provider)


def test_discover_registration_endpoint_success():
    flow = DcrPkceFlow()
    provider = _make_provider()

    mock_resp1 = MagicMock()
    mock_resp1.status_code = 200
    mock_resp1.json.return_value = {}

    mock_resp2 = MagicMock()
    mock_resp2.status_code = 200
    mock_resp2.json.return_value = {"registration_endpoint": "https://auth.example.com/register"}

    with patch("authsome.auth.flows.dcr_pkce.http_client.get", side_effect=[mock_resp1, mock_resp2]):
        endpoint = flow._discover_registration_endpoint(provider)
        assert endpoint == "https://auth.example.com/register"


def test_discover_registration_endpoint_failure():
    flow = DcrPkceFlow()
    provider = _make_provider()

    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch(
        "authsome.auth.flows.dcr_pkce.http_client.get",
        side_effect=[requests.RequestException("boom"), mock_resp],
    ):
        with pytest.raises(DiscoveryError, match="Could not discover registration_endpoint"):
            flow._discover_registration_endpoint(provider)


def test_register_client_missing_oauth():
    flow = DcrPkceFlow()
    provider = _make_provider()
    provider.oauth = None
    with pytest.raises(AuthenticationFailedError, match="No OAuth config"):
        flow._register_client(provider, [])


def test_register_client_success():
    flow = DcrPkceFlow()
    provider = _make_provider()
    provider.oauth.registration_endpoint = "https://auth.example.com/register"

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"client_id": "new_cid", "client_secret": "new_sec"}

    with patch("authsome.auth.flows.dcr_pkce.http_client.post", return_value=mock_resp):
        cid, sec = flow._register_client(provider, ["scope1"])
        assert cid == "new_cid"
        assert sec == "new_sec"


def test_register_client_http_error():
    flow = DcrPkceFlow()
    provider = _make_provider()
    provider.oauth.registration_endpoint = "https://auth.example.com/register"

    with patch(
        "authsome.auth.flows.dcr_pkce.http_client.post",
        side_effect=requests.RequestException("boom"),
    ):
        with pytest.raises(AuthenticationFailedError, match="Registration failed"):
            flow._register_client(provider, [])


def test_register_client_invalid_json():
    flow = DcrPkceFlow()
    provider = _make_provider()
    provider.oauth.registration_endpoint = "https://auth.example.com/register"

    mock_resp = MagicMock()
    mock_resp.json.side_effect = json.JSONDecodeError("msg", "doc", 0)

    with patch("authsome.auth.flows.dcr_pkce.http_client.post", return_value=mock_resp):
        with pytest.raises(AuthenticationFailedError, match="not valid JSON"):
            flow._register_client(provider, [])


def test_register_client_missing_client_id():
    flow = DcrPkceFlow()
    provider = _make_provider()
    provider.oauth.registration_endpoint = "https://auth.example.com/register"

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"client_secret": "new_sec"}

    with patch("authsome.auth.flows.dcr_pkce.http_client.post", return_value=mock_resp):
        with pytest.raises(AuthenticationFailedError, match="missing client_id"):
            flow._register_client(provider, [])


def test_dcr_pkce_flow_success():
    provider = _make_provider()
    flow = DcrPkceFlow()
    flow.callback_port = _find_free_port()
    port = flow.callback_port

    def mock_open(url):
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        state = params["state"][0]

        callback_url = f"http://127.0.0.1:{port}/callback?code=mock_code&state={state}"
        req = urllib.request.Request(callback_url)
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200

    dcr_resp = MagicMock()
    dcr_resp.json.return_value = {"client_id": "cid", "client_secret": "sec"}

    token_resp = MagicMock()
    token_resp.json.return_value = {
        "access_token": "mock_access",
        "refresh_token": "mock_refresh",
        "expires_in": 3600,
    }

    with patch("authsome.auth.flows.dcr_pkce.http_client.post", side_effect=[dcr_resp, token_resp]):
        with patch("authsome.auth.flows.dcr_pkce.webbrowser.open", side_effect=mock_open):
            with patch(
                "authsome.auth.flows.dcr_pkce.DcrPkceFlow._discover_registration_endpoint",
                return_value="url",
            ):
                result = flow.authenticate(provider, "default", "default", scopes=["test"])

    assert result.connection.status == ConnectionStatus.CONNECTED
    assert result.connection.schema_version == 2
    assert result.connection.metadata == {}
    # DCR client credentials come back via FlowResult, not metadata
    assert result.client_record is not None
    assert result.client_record.client_id == "cid"
    assert result.client_record.client_secret == "sec"
    # Tokens are plaintext
    assert result.connection.access_token == "mock_access"


def test_dcr_pkce_flow_reuse_client():
    provider = _make_provider()
    flow = DcrPkceFlow()
    flow.callback_port = _find_free_port()
    port = flow.callback_port

    def mock_open(url):
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        assert "scope" not in params
        state = params["state"][0]
        callback_url = f"http://127.0.0.1:{port}/callback?code=mock_code&state={state}"
        urllib.request.urlopen(urllib.request.Request(callback_url))

    token_resp = MagicMock()
    token_resp.json.return_value = {"access_token": "mock_access"}

    with patch("authsome.auth.flows.dcr_pkce.http_client.post", return_value=token_resp):
        with patch("authsome.auth.flows.dcr_pkce.webbrowser.open", side_effect=mock_open):
            result = flow.authenticate(provider, "default", "default", client_id="existing_cid")

    assert result.connection.status == ConnectionStatus.CONNECTED
    # No new DCR registration — client_record is None, stored credentials are unchanged
    assert result.client_record is None
    assert result.connection.expires_at is None


def test_dcr_pkce_flow_callback_error():
    provider = _make_provider()
    flow = DcrPkceFlow()
    flow.callback_port = _find_free_port()
    port = flow.callback_port

    def mock_open(url):
        callback_url = f"http://127.0.0.1:{port}/callback?error=access_denied&error_description=User%20denied"
        try:
            urllib.request.urlopen(urllib.request.Request(callback_url))
        except urllib.error.HTTPError as e:
            assert e.code == 400

    with patch("authsome.auth.flows.dcr_pkce.webbrowser.open", side_effect=mock_open):
        with pytest.raises(AuthenticationFailedError, match="access_denied"):
            flow.authenticate(provider, "default", "default", client_id="cid")


def test_dcr_pkce_flow_callback_invalid():
    provider = _make_provider()
    flow = DcrPkceFlow()
    flow.callback_port = _find_free_port()
    port = flow.callback_port

    def mock_open(url):
        callback_url = f"http://127.0.0.1:{port}/callback?other=123"
        try:
            urllib.request.urlopen(urllib.request.Request(callback_url))
        except urllib.error.HTTPError as e:
            assert e.code == 400

    with patch("authsome.auth.flows.dcr_pkce.webbrowser.open", side_effect=mock_open):
        with pytest.raises(AuthenticationFailedError, match="no code received"):
            flow.authenticate(provider, "default", "default", client_id="cid")


def test_dcr_pkce_flow_state_mismatch():
    provider = _make_provider()
    flow = DcrPkceFlow()
    flow.callback_port = _find_free_port()
    port = flow.callback_port

    def mock_open(url):
        callback_url = f"http://127.0.0.1:{port}/callback?code=mock_code&state=wrong"
        urllib.request.urlopen(urllib.request.Request(callback_url))

    with patch("authsome.auth.flows.dcr_pkce.webbrowser.open", side_effect=mock_open):
        with pytest.raises(AuthenticationFailedError, match="state mismatch"):
            flow.authenticate(provider, "default", "default", client_id="cid")


def test_dcr_pkce_flow_timeout():
    provider = _make_provider()
    flow = DcrPkceFlow()

    def mock_open(url):
        pass

    with patch("authsome.auth.flows.dcr_pkce.webbrowser.open", side_effect=mock_open):
        with patch("authsome.auth.flows.dcr_pkce._CALLBACK_TIMEOUT_SECONDS", 0.01):
            with pytest.raises(AuthenticationFailedError, match="timed out"):
                flow.authenticate(provider, "default", "default", client_id="cid")


def test_exchange_code_http_error():
    provider = _make_provider()
    flow = DcrPkceFlow()
    flow.callback_port = _find_free_port()
    port = flow.callback_port

    def mock_open(url):
        parsed = urllib.parse.urlparse(url)
        state = urllib.parse.parse_qs(parsed.query)["state"][0]
        urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/callback?code=mock_code&state={state}"))

    with patch("authsome.auth.flows.dcr_pkce.webbrowser.open", side_effect=mock_open):
        with patch(
            "authsome.auth.flows.dcr_pkce.http_client.post",
            side_effect=requests.RequestException("boom"),
        ):
            with pytest.raises(AuthenticationFailedError, match="Token exchange failed"):
                flow.authenticate(provider, "default", "default", client_id="cid")


def test_exchange_code_invalid_json():
    provider = _make_provider()
    flow = DcrPkceFlow()
    flow.callback_port = _find_free_port()
    port = flow.callback_port

    def mock_open(url):
        parsed = urllib.parse.urlparse(url)
        state = urllib.parse.parse_qs(parsed.query)["state"][0]
        urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/callback?code=mock_code&state={state}"))

    mock_resp = MagicMock()
    mock_resp.json.side_effect = json.JSONDecodeError("msg", "doc", 0)

    with patch("authsome.auth.flows.dcr_pkce.webbrowser.open", side_effect=mock_open):
        with patch("authsome.auth.flows.dcr_pkce.http_client.post", return_value=mock_resp):
            with pytest.raises(AuthenticationFailedError, match="not valid JSON"):
                flow.authenticate(provider, "default", "default", client_id="cid")


def test_exchange_code_missing_access_token():
    provider = _make_provider()
    flow = DcrPkceFlow()
    flow.callback_port = _find_free_port()
    port = flow.callback_port

    def mock_open(url):
        parsed = urllib.parse.urlparse(url)
        state = urllib.parse.parse_qs(parsed.query)["state"][0]
        urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/callback?code=mock_code&state={state}"))

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "error": "invalid_grant",
        "error_description": "bad code",
    }

    with patch("authsome.auth.flows.dcr_pkce.webbrowser.open", side_effect=mock_open):
        with patch("authsome.auth.flows.dcr_pkce.http_client.post", return_value=mock_resp):
            with pytest.raises(AuthenticationFailedError, match="bad code"):
                flow.authenticate(provider, "default", "default", client_id="cid")
