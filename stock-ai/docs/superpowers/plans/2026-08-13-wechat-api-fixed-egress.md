# WeChat API Fixed Egress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pin every `stock-ai` WeChat Official Account API request to one tested `api.weixin.qq.com` IPv4 target whose SASE egress is `140.206.121.26`, while preserving TLS hostname verification and failing closed when the route differs.

**Architecture:** Add an opt-in `requests` transport adapter that connects to a configured IPv4 address but retains `api.weixin.qq.com` for HTTP Host, TLS SNI, and certificate hostname validation. Add a diagnostic CLI that probes each DNS answer with the same transport, plus a required-egress preflight used before draft mutations. Existing behavior remains unchanged unless the new environment variables are set.

**Tech Stack:** Python 3.13, requests 2.32.5, urllib3 2.6.3, pytest, WeChat Official Account API.

## Global Constraints

- Only `stock-ai` WeChat API traffic may change; do not modify macOS proxy settings, `/etc/hosts`, Clash, or SASE.
- Never print AppSecret or a complete access token.
- `WECHAT_MP_API_RESOLVE_IP` must contain one IPv4 address.
- `WECHAT_MP_REQUIRED_EGRESS_IP` must equal `140.206.121.26` for this rollout.
- If the observed WeChat egress differs from the required value, stop before uploading material or updating a draft.
- Preserve current behavior when both new variables are unset.

---

## File Structure

- Modify `stock-ai/scripts/tools/wechat_mp_client.py`: fixed-address HTTPS adapter, session mounting, invalid-IP parsing, and required-egress preflight.
- Create `stock-ai/scripts/tools/wechat_mp_probe_api_routes.py`: resolve and probe WeChat API targets without writing drafts.
- Modify `stock-ai/scripts/tools/wechat_mp_newspic_draft.py`: run the preflight immediately before a real draft mutation.
- Create `stock-ai/tests/unit/test_wechat_mp_client_transport.py`: transport, parsing, preflight, and probe tests.
- Modify `stock-ai/.env.example`: document the two opt-in settings.
- Modify `.cursor/skills/wechat-mp-drafts/reference.md`: record operation and rollback commands.

### Task 1: Fixed-address HTTPS transport

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_client.py:60-125`
- Create: `stock-ai/tests/unit/test_wechat_mp_client_transport.py`

**Interfaces:**
- Produces: `FixedWeChatAPIAdapter(HTTPAdapter)`, `_configured_api_resolve_ip() -> str`, and `_mp_session() -> requests.Session`.
- Consumes: environment variable `WECHAT_MP_API_RESOLVE_IP`.

- [ ] **Step 1: Write failing tests for opt-in mounting and validation**

```python
import pytest

from scripts.tools import wechat_mp_client as client


def test_mp_session_keeps_default_transport_without_fixed_ip(monkeypatch):
    monkeypatch.delenv("WECHAT_MP_API_RESOLVE_IP", raising=False)
    session = client._mp_session()
    assert type(session.get_adapter("https://api.weixin.qq.com/token")) is client.HTTPAdapter


def test_mp_session_mounts_fixed_adapter_for_wechat_only(monkeypatch):
    monkeypatch.setenv("WECHAT_MP_API_RESOLVE_IP", "116.128.170.42")
    session = client._mp_session()
    assert isinstance(
        session.get_adapter("https://api.weixin.qq.com/token"),
        client.FixedWeChatAPIAdapter,
    )
    assert type(session.get_adapter("https://example.com")) is client.HTTPAdapter


def test_configured_api_resolve_ip_rejects_non_ipv4(monkeypatch):
    monkeypatch.setenv("WECHAT_MP_API_RESOLVE_IP", "api.weixin.qq.com")
    with pytest.raises(ValueError, match="IPv4"):
        client._configured_api_resolve_ip()
```

- [ ] **Step 2: Run the focused tests and confirm RED**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_wechat_mp_client_transport.py -q`

Expected: failures because `FixedWeChatAPIAdapter` and `_configured_api_resolve_ip` do not exist.

- [ ] **Step 3: Implement the adapter with original Host and TLS hostname**

```python
from ipaddress import IPv4Address, AddressValueError
from urllib.parse import urlsplit

from requests.adapters import HTTPAdapter


class FixedWeChatAPIAdapter(HTTPAdapter):
    def __init__(self, *, resolve_ip: str) -> None:
        self.resolve_ip = str(IPv4Address(resolve_ip))
        super().__init__()

    def get_connection_with_tls_context(self, request, verify, proxies=None, cert=None):
        parsed = urlsplit(request.url)
        if parsed.hostname != "api.weixin.qq.com":
            return super().get_connection_with_tls_context(
                request, verify, proxies=proxies, cert=cert
            )
        request.headers.setdefault("Host", "api.weixin.qq.com")
        return self.poolmanager.connection_from_host(
            host=self.resolve_ip,
            port=parsed.port or 443,
            scheme="https",
            pool_kwargs={
                "assert_hostname": "api.weixin.qq.com",
                "server_hostname": "api.weixin.qq.com",
            },
        )


def _configured_api_resolve_ip() -> str:
    value = _env("WECHAT_MP_API_RESOLVE_IP")
    if not value:
        return ""
    try:
        return str(IPv4Address(value))
    except AddressValueError as exc:
        raise ValueError("WECHAT_MP_API_RESOLVE_IP 须为 IPv4 地址") from exc


def _mp_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    resolve_ip = _configured_api_resolve_ip()
    if resolve_ip:
        session.mount(
            "https://api.weixin.qq.com/",
            FixedWeChatAPIAdapter(resolve_ip=resolve_ip),
        )
    return session
```

- [ ] **Step 4: Add a mocked TLS-pool test and run GREEN**

The test must call `get_connection_with_tls_context` with a prepared request and assert `host == resolve_ip`, `assert_hostname == "api.weixin.qq.com"`, `server_hostname == "api.weixin.qq.com"`, and `Host == "api.weixin.qq.com"`.

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_wechat_mp_client_transport.py -q`

Expected: all Task 1 tests pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add stock-ai/scripts/tools/wechat_mp_client.py stock-ai/tests/unit/test_wechat_mp_client_transport.py
git commit -m "feat: pin WeChat API transport to configured address"
```

### Task 2: Egress parsing and fail-closed preflight

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_client.py:175-260`
- Modify: `stock-ai/tests/unit/test_wechat_mp_client_transport.py`

**Interfaces:**
- Produces: `invalid_ip_from_error(error: Mapping[str, Any] | None) -> str`, `verify_required_wechat_egress() -> dict[str, Any]`.
- Consumes: `get_access_token(force_refresh=True)` and `WECHAT_MP_REQUIRED_EGRESS_IP`.

- [ ] **Step 1: Write failing parser and preflight tests**

```python
def test_invalid_ip_from_error_extracts_ipv4():
    error = {
        "errcode": 40164,
        "errmsg": "invalid ip 140.206.121.26 ipv6 ::ffff:140.206.121.26, not in whitelist",
    }
    assert client.invalid_ip_from_error(error) == "140.206.121.26"


def test_required_egress_rejects_different_observed_ip(monkeypatch):
    monkeypatch.setenv("WECHAT_MP_REQUIRED_EGRESS_IP", "140.206.121.26")
    monkeypatch.setattr(
        client,
        "get_access_token",
        lambda force_refresh=False: (
            None,
            {"errcode": 40164, "errmsg": "invalid ip 223.167.74.160, not in whitelist"},
        ),
    )
    with pytest.raises(RuntimeError, match="223.167.74.160"):
        client.verify_required_wechat_egress()


def test_required_egress_accepts_successful_forced_token(monkeypatch):
    monkeypatch.setenv("WECHAT_MP_REQUIRED_EGRESS_IP", "140.206.121.26")
    calls = []
    monkeypatch.setattr(
        client,
        "get_access_token",
        lambda force_refresh=False: (calls.append(force_refresh) or "token", None),
    )
    result = client.verify_required_wechat_egress()
    assert calls == [True]
    assert result["ok"] is True
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_wechat_mp_client_transport.py -q`

Expected: failures because parser and preflight functions do not exist.

- [ ] **Step 3: Implement strict parsing and preflight**

```python
INVALID_IP_RE = re.compile(r"invalid ip\s+(\d{1,3}(?:\.\d{1,3}){3})", re.I)


def invalid_ip_from_error(error):
    if not is_ip_whitelist_error(error):
        return ""
    match = INVALID_IP_RE.search(str((error or {}).get("errmsg") or ""))
    if not match:
        return ""
    try:
        return str(IPv4Address(match.group(1)))
    except AddressValueError:
        return ""


def verify_required_wechat_egress() -> dict[str, Any]:
    required = _env("WECHAT_MP_REQUIRED_EGRESS_IP")
    if not required:
        return {"ok": True, "required_ip": None, "observed_ip": None}
    required = str(IPv4Address(required))
    token, error = get_access_token(force_refresh=True)
    if token and not error:
        return {"ok": True, "required_ip": required, "observed_ip": None}
    observed = invalid_ip_from_error(error)
    if observed and observed != required:
        raise RuntimeError(f"微信 API 出口 {observed} 与要求 {required} 不一致")
    if observed == required:
        raise RuntimeError(f"微信 API 已走目标出口 {required}，但该 IP 尚未被白名单放行")
    raise RuntimeError(f"微信 API 出口预检失败: {(error or {}).get('errcode')}")
```

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_wechat_mp_client_transport.py -q`

Expected: all Task 1 and Task 2 tests pass without secrets in output.

- [ ] **Step 5: Commit Task 2**

```bash
git add stock-ai/scripts/tools/wechat_mp_client.py stock-ai/tests/unit/test_wechat_mp_client_transport.py
git commit -m "feat: fail closed on unexpected WeChat API egress"
```

### Task 3: Route-probe CLI

**Files:**
- Create: `stock-ai/scripts/tools/wechat_mp_probe_api_routes.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_client_transport.py`

**Interfaces:**
- Produces: `resolve_api_ipv4() -> list[str]`, `probe_target(ip: str) -> dict[str, Any]`, CLI JSON with `target_ip`, `ok`, `errcode`, and `observed_egress_ip` only.
- Consumes: `FixedWeChatAPIAdapter`, `invalid_ip_from_error`, and configured AppID/AppSecret.

- [ ] **Step 1: Write failing tests for sorted unique DNS results and redacted output**

```python
def test_resolve_api_ipv4_returns_sorted_unique(monkeypatch):
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


def test_probe_result_does_not_include_secret_or_token(monkeypatch):
    result = probe._public_probe_result(
        target_ip="112.65.193.153",
        token="secret-token",
        error={"errcode": 40164, "errmsg": "invalid ip 140.206.121.26"},
    )
    assert "secret-token" not in str(result)
    assert result["observed_egress_ip"] == "140.206.121.26"
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_wechat_mp_client_transport.py -q`

Expected: failures because the probe module does not exist.

- [ ] **Step 3: Implement the synchronous probe**

```python
def resolve_api_ipv4() -> list[str]:
    answers = socket.getaddrinfo(
        "api.weixin.qq.com", 443, family=socket.AF_INET, type=socket.SOCK_STREAM
    )
    return sorted({str(IPv4Address(item[4][0])) for item in answers})


def _public_probe_result(*, target_ip: str, token: str, error: dict | None) -> dict:
    return {
        "target_ip": target_ip,
        "ok": bool(token) and not error,
        "errcode": (error or {}).get("errcode"),
        "observed_egress_ip": invalid_ip_from_error(error),
    }


def probe_target(ip: str) -> dict:
    appid, secret = mp_credentials()
    session = requests.Session()
    session.trust_env = False
    session.mount(
        "https://api.weixin.qq.com/",
        FixedWeChatAPIAdapter(resolve_ip=ip),
    )
    response = session.get(
        f"{API_BASE}/token",
        params={"grant_type": "client_credential", "appid": appid, "secret": secret},
        timeout=20,
    )
    data = _mp_parse_json(response)
    return _public_probe_result(
        target_ip=ip,
        token=str(data.get("access_token") or ""),
        error=data if data.get("errcode") else None,
    )
```

`main()` prints `json.dumps([probe_target(ip) for ip in resolve_api_ipv4()], ensure_ascii=False, indent=2)` and exits nonzero if credentials are absent. It never includes the token or secret in its result.

- [ ] **Step 4: Run unit tests and a help smoke test**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_wechat_mp_client_transport.py -q`

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python scripts/tools/wechat_mp_probe_api_routes.py --help`

Expected: tests pass; help exits 0 without network access.

- [ ] **Step 5: Commit Task 3**

```bash
git add stock-ai/scripts/tools/wechat_mp_probe_api_routes.py stock-ai/tests/unit/test_wechat_mp_client_transport.py
git commit -m "feat: probe WeChat API route egress"
```

### Task 4: Draft mutation preflight and documentation

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_newspic_draft.py:210-230`
- Modify: `stock-ai/tests/unit/test_wechat_mp_newspic.py`
- Modify: `stock-ai/.env.example`
- Modify: `.cursor/skills/wechat-mp-drafts/reference.md`

**Interfaces:**
- Consumes: `verify_required_wechat_egress() -> dict[str, Any]`.
- Produces: `_preflight_before_mutation(*, dry_run: bool) -> None`; all non-dry-run newspic mutations gain the preflight.

- [ ] **Step 1: Write a failing CLI-flow test**

```python
from scripts.tools import wechat_mp_newspic_draft as command


def test_preflight_runs_for_real_mutation(monkeypatch):
    calls = []
    monkeypatch.setattr(
        command,
        "verify_required_wechat_egress",
        lambda: calls.append("preflight"),
    )
    command._preflight_before_mutation(dry_run=False)
    assert calls == ["preflight"]


def test_preflight_skips_dry_run(monkeypatch):
    calls = []
    monkeypatch.setattr(
        command,
        "verify_required_wechat_egress",
        lambda: calls.append("preflight"),
    )
    command._preflight_before_mutation(dry_run=True)
    assert calls == []
```

- [ ] **Step 2: Run the two tests and confirm RED**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_wechat_mp_newspic.py -q`

Expected: the new ordering assertion fails because no preflight exists.

- [ ] **Step 3: Add the preflight immediately before upsert**

```python
def _preflight_before_mutation(*, dry_run: bool) -> None:
    if dry_run:
        return
    try:
        verify_required_wechat_egress()
    except RuntimeError as exc:
        raise ValueError(str(exc)) from exc


# Call this inside main()'s existing validation try block, before its except clauses.
_preflight_before_mutation(dry_run=args.dry_run)
```

Import the function from `wechat_mp_client`. The helper converts `RuntimeError` to `ValueError`, so the existing `错误: ...` path exits nonzero without a traceback containing credentials. The existing `upsert_newspic_draft(...)` call remains unchanged after the dry-run return.

- [ ] **Step 4: Document configuration and rollback**

Add to `.env.example`:

```dotenv
# WECHAT_MP_API_RESOLVE_IP=112.65.193.153
# WECHAT_MP_REQUIRED_EGRESS_IP=140.206.121.26
```

Add to the reference guide:

```bash
PYTHONPATH=. .venv/bin/python scripts/tools/wechat_mp_probe_api_routes.py
```

State that removing both variables restores system DNS behavior.

- [ ] **Step 5: Run focused and regression tests**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_wechat_mp_client_transport.py tests/unit/test_wechat_mp_newspic.py tests/unit/test_wechat_mp_virtual_film.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit Task 4**

```bash
git add stock-ai/scripts/tools/wechat_mp_newspic_draft.py stock-ai/tests/unit/test_wechat_mp_newspic.py stock-ai/.env.example .cursor/skills/wechat-mp-drafts/reference.md
git commit -m "feat: guard WeChat draft writes by required egress"
```

### Task 5: Live mapping, rollout, and draft delivery

**Files:**
- Modify locally, never commit: `stock-ai/.env`
- Read: `stock-ai/output/zhixia-kung-fu-soccer-copy.txt`
- Read: `stock-ai/output/zhixia-kung-fu-soccer-topic-card.json`
- Read: `stock-ai/output/zhixia-kung-fu-soccer-image-sources.json`

**Interfaces:**
- Consumes: probe CLI and existing `wechat_mp_newspic_draft.py` command.
- Produces: one verified `virtual_lifestyle` draft, not a published article.

- [ ] **Step 1: Probe every current target**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python scripts/tools/wechat_mp_probe_api_routes.py`

Expected: at least one row has `observed_egress_ip` equal to `140.206.121.26`. If none does, stop; do not guess or edit SASE.

- [ ] **Step 2: Configure only the proven mapping**

Extract exactly one proven target and require it to exist:

```bash
probe_json="$(PYTHONPATH=. .venv/bin/python scripts/tools/wechat_mp_probe_api_routes.py)"
proven_ip="$(printf '%s' "$probe_json" | jq -r '[.[] | select(.observed_egress_ip == "140.206.121.26")][0].target_ip // empty')"
test -n "$proven_ip"
```

Use `apply_patch` to set the literal value printed in `proven_ip` as `WECHAT_MP_API_RESOLVE_IP` in the uncommitted `stock-ai/.env`, and set both `WECHAT_MP_REQUIRED_EGRESS_IP` and `WECHAT_MP_WHITELIST_IP` to `140.206.121.26`.

- [ ] **Step 3: Force-refresh token through the fixed route**

Run the preflight from Python and require either success or a `40164` naming exactly `140.206.121.26`. If it names another IP, remove the new variables and stop.

- [ ] **Step 4: Upload one image through the fixed route**

Run a one-off Python command that calls `upload_permanent_image(Path("assets/wechat_mp/virtual-lifestyle/2026-08-13-kung-fu-soccer/gallery-11.jpg"))` and prints only whether a media ID was returned plus the public error object.

Expected: media ID returned and no `40164`. If it fails, stop without changing the draft.

- [ ] **Step 5: Run the existing dry-run again**

Run the full six-image `wechat_mp_newspic_draft.py` command with `--dry-run`.

Expected: type A, lane `popular_film`, 6 images, title `《功夫女足》：赢了以后呢`.

- [ ] **Step 6: Push and remotely verify the draft**

Run the same command without `--dry-run` and with `--watermark ''`.

Expected: `OK [virtual_lifestyle] updated|created media_id=...`; built-in verification confirms title, body, and six images. No publish API is called.

- [ ] **Step 7: Final regression verification**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_wechat_mp_client_transport.py tests/unit/test_wechat_mp_newspic.py tests/unit/test_wechat_mp_virtual_film.py -q`

Expected: all tests pass after the live rollout.
