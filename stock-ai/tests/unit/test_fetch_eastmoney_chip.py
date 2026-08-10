from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.tools import fetch_eastmoney_quotes as subject


def executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_explicit_opencli_path_has_priority(monkeypatch, tmp_path: Path) -> None:
    configured = executable(tmp_path / "configured" / "opencli")
    executable(tmp_path / "path" / "opencli")
    monkeypatch.setenv("OPENCLI_BIN", str(configured))
    monkeypatch.setenv("PATH", str(tmp_path / "path"))

    assert subject.resolve_opencli_bin(nvm_root=tmp_path / "nvm") == str(configured)


def test_path_opencli_is_used_without_explicit_configuration(monkeypatch, tmp_path: Path) -> None:
    discovered = executable(tmp_path / "bin" / "opencli")
    monkeypatch.delenv("OPENCLI_BIN", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))

    assert subject.resolve_opencli_bin(nvm_root=tmp_path / "nvm") == str(discovered)


def test_semantically_latest_nvm_opencli_is_selected(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENCLI_BIN", raising=False)
    monkeypatch.setenv("PATH", "")
    executable(tmp_path / "v9.9.0" / "bin" / "opencli")
    executable(tmp_path / "v22.15.0" / "bin" / "opencli")
    latest = executable(tmp_path / "v24.2.0" / "bin" / "opencli")

    assert subject.resolve_opencli_bin(nvm_root=tmp_path) == str(latest)


def test_missing_opencli_reports_the_scoped_install_command(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENCLI_BIN", raising=False)
    monkeypatch.setenv("PATH", "")

    with pytest.raises(FileNotFoundError, match="npm install -g @jackwener/opencli"):
        subject.resolve_opencli_bin(nvm_root=tmp_path)


def test_chip_fetch_preserves_the_turnover_column(monkeypatch) -> None:
    row = "2026-08-10,23.46,23.95,24.84,22.71,1124242,2654998952,9.39,5.60,1.27,22.70"
    monkeypatch.setattr(subject, "_reset_browser_if", lambda enabled: None)
    monkeypatch.setattr(subject, "_open_page", lambda *args, **kwargs: None)
    monkeypatch.setattr(subject, "_wait_page_ready", lambda **kwargs: None)
    monkeypatch.setattr(subject, "_eval_js", lambda *args, **kwargs: json.dumps([row]))
    monkeypatch.setattr(subject, "release_browser_session", lambda **kwargs: None)

    rows = subject.fetch_chip_kline_rows_opencli("603011")

    assert rows == [[
        "2026-08-10",
        "23.46",
        "23.95",
        "24.84",
        "22.71",
        "1124242",
        "2654998952",
        "9.39",
        "5.60",
        "1.27",
        "22.70",
    ]]
