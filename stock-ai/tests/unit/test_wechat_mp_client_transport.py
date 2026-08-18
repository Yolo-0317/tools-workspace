from __future__ import annotations

import importlib
from unittest.mock import Mock

import pytest
from requests import Request
from requests.exceptions import ConnectionError

from scripts.tools import wechat_mp_client as client


def test_mp_session_keeps_default_transport_without_fixed_ip(monkeypatch):
    """Catches accidentally changing every existing WeChat client session."""
    monkeypatch.delenv("WECHAT_MP_API_RESOLVE_IP", raising=False)

    session = client._mp_session()

    assert type(session.get_adapter("https://api.weixin.qq.com/token")) is client.HTTPAdapter


def test_mp_session_mounts_fixed_adapter_for_wechat_only(monkeypatch):
    """Catches mounting the fixed route globally instead of only for WeChat API."""
    monkeypatch.setenv("WECHAT_MP_API_RESOLVE_IP", "116.128.170.42")

    session = client._mp_session()

    assert isinstance(
        session.get_adapter("https://api.weixin.qq.com/token"),
        client.FixedWeChatAPIAdapter,
    )
    assert type(session.get_adapter("https://example.com")) is client.HTTPAdapter


def test_configured_api_resolve_ip_rejects_non_ipv4(monkeypatch):
    """Catches accepting a hostname or malformed value as a fixed IPv4 target."""
    monkeypatch.setenv("WECHAT_MP_API_RESOLVE_IP", "api.weixin.qq.com")

    with pytest.raises(ValueError, match="IPv4"):
        client._configured_api_resolve_ip()


def test_fixed_adapter_keeps_wechat_host_for_http_and_tls():
    """Catches connecting by IP while validating TLS against that IP."""
    adapter = client.FixedWeChatAPIAdapter(resolve_ip="116.128.170.42")
    pool = Mock()
    pool.connection_from_host.return_value = object()
    adapter.poolmanager = pool
    prepared = Request("GET", "https://api.weixin.qq.com/cgi-bin/token").prepare()

    connection = adapter.get_connection_with_tls_context(
        prepared,
        verify=True,
        proxies=None,
        cert=None,
    )

    assert connection is pool.connection_from_host.return_value
    assert prepared.headers["Host"] == "api.weixin.qq.com"
    pool.connection_from_host.assert_called_once_with(
        host="116.128.170.42",
        port=443,
        scheme="https",
        pool_kwargs={
            "assert_hostname": "api.weixin.qq.com",
            "server_hostname": "api.weixin.qq.com",
        },
    )


def test_invalid_ip_from_error_extracts_ipv4():
    """Catches losing the only observable source-IP evidence from WeChat."""
    error = {
        "errcode": 40164,
        "errmsg": (
            "invalid ip 140.206.121.26 ipv6 ::ffff:140.206.121.26, "
            "not in whitelist"
        ),
    }

    assert client.invalid_ip_from_error(error) == "140.206.121.26"


def test_invalid_ip_from_error_ignores_unrelated_errors():
    """Catches treating arbitrary API failures as route evidence."""
    error = {"errcode": 40001, "errmsg": "invalid credential"}

    assert client.invalid_ip_from_error(error) == ""


def test_required_egress_rejects_different_observed_ip(monkeypatch):
    """Catches continuing a draft mutation through the wrong SASE egress."""
    monkeypatch.setenv("WECHAT_MP_REQUIRED_EGRESS_IP", "140.206.121.26")
    monkeypatch.setattr(
        client,
        "get_access_token",
        lambda force_refresh=False: (
            None,
            {
                "errcode": 40164,
                "errmsg": "invalid ip 223.167.74.160, not in whitelist",
            },
        ),
    )

    with pytest.raises(RuntimeError, match="223.167.74.160"):
        client.verify_required_wechat_egress()


def test_required_egress_reports_target_not_whitelisted(monkeypatch):
    """Catches hiding the distinction between correct routing and whitelist state."""
    monkeypatch.setenv("WECHAT_MP_REQUIRED_EGRESS_IP", "140.206.121.26")
    monkeypatch.setattr(
        client,
        "get_access_token",
        lambda force_refresh=False: (
            None,
            {
                "errcode": 40164,
                "errmsg": "invalid ip 140.206.121.26, not in whitelist",
            },
        ),
    )

    with pytest.raises(RuntimeError, match="尚未被白名单放行"):
        client.verify_required_wechat_egress()


def test_required_egress_accepts_successful_forced_token(monkeypatch):
    """Catches accidentally trusting a cached token during route preflight."""
    monkeypatch.setenv("WECHAT_MP_REQUIRED_EGRESS_IP", "140.206.121.26")
    calls: list[bool] = []

    def fake_token(*, force_refresh=False):
        calls.append(force_refresh)
        return "token", None

    monkeypatch.setattr(client, "get_access_token", fake_token)

    result = client.verify_required_wechat_egress()

    assert calls == [True]
    assert result == {
        "ok": True,
        "required_ip": "140.206.121.26",
        "observed_ip": None,
    }


def test_route_probe_resolves_sorted_unique_ipv4(monkeypatch):
    """Catches probing duplicate DNS answers or producing unstable ordering."""
    probe = importlib.import_module("scripts.tools.wechat_mp_probe_api_routes")
    monkeypatch.setattr(
        probe.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (2, 1, 6, "", ("116.128.170.42", 443)),
            (2, 1, 6, "", ("112.65.193.153", 443)),
            (2, 1, 6, "", ("116.128.170.42", 443)),
        ],
    )

    assert probe.resolve_api_ipv4() == ["112.65.193.153", "116.128.170.42"]


def test_route_probe_public_result_redacts_token():
    """Catches leaking a live access token from diagnostic output."""
    probe = importlib.import_module("scripts.tools.wechat_mp_probe_api_routes")

    result = probe._public_probe_result(
        target_ip="112.65.193.153",
        token="secret-token",
        error={"errcode": 40164, "errmsg": "invalid ip 140.206.121.26"},
    )

    assert "secret-token" not in str(result)
    assert result == {
        "target_ip": "112.65.193.153",
        "ok": False,
        "errcode": 40164,
        "observed_egress_ip": "140.206.121.26",
    }


def test_get_access_token_redacts_network_exception(monkeypatch):
    """Catches leaking AppSecret through a requests exception URL."""
    monkeypatch.setenv("WECHAT_MP_APPID", "wx-test-appid")
    monkeypatch.setenv("WECHAT_MP_SECRET", "do-not-leak-this-secret")

    class FailingSession:
        def get(self, *_args, **_kwargs):
            raise ConnectionError(
                "failed https://api.weixin.qq.com/token?secret=do-not-leak-this-secret"
            )

    monkeypatch.setattr(client, "_mp_session", lambda: FailingSession())

    token, error = client.get_access_token(force_refresh=True)

    assert token is None
    assert error == {"errcode": -2, "errmsg": "微信公众号 token 网络请求失败"}
    assert "do-not-leak-this-secret" not in str(error)
