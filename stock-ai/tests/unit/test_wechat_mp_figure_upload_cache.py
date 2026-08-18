"""正文插图上传缓存（换图须失效旧 URL）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_figures import figure_upload_cache_key, upload_inline_figure


def test_figure_upload_cache_key_changes_when_file_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    img = tmp_path / "inline-example.jpg"
    img.write_bytes(b"version-a")
    k1 = figure_upload_cache_key(img)
    img.write_bytes(b"version-b")
    k2 = figure_upload_cache_key(img)
    assert k1.startswith("inline-example.jpg#")
    assert k1 != k2


def test_upload_inline_figure_reuploads_after_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    inline = tmp_path / "inline"
    inline.mkdir(parents=True)
    img = inline / "inline-example.jpg"
    img.write_bytes(b"old-bytes")

    cache_path = tmp_path / "figure_upload_cache.json"
    legacy_key = "inline-example.jpg"
    cache_path.write_text(
        json.dumps({"urls": {legacy_key: "http://old.example/a.jpg"}}, ensure_ascii=False),
        encoding="utf-8",
    )

    calls: list[bytes] = []

    def fake_upload(path: Path) -> tuple[str | None, dict | None]:
        calls.append(path.read_bytes())
        return f"http://new.example/{len(calls)}.jpg", None

    monkeypatch.setattr(
        "scripts.tools.wechat_mp_figures.UPLOAD_CACHE_PATH",
        cache_path,
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_figures.resolve_inline_path",
        lambda _name: img,
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_client.upload_article_image",
        fake_upload,
    )

    url1, _ = upload_inline_figure("inline-example.jpg")
    assert url1 == "http://new.example/1.jpg"
    assert calls == [b"old-bytes"]

    img.write_bytes(b"new-bytes")
    url2, _ = upload_inline_figure("inline-example.jpg")
    assert url2 == "http://new.example/2.jpg"
    assert calls == [b"old-bytes", b"new-bytes"]

    data = json.loads(cache_path.read_text(encoding="utf-8"))
    urls = data.get("urls") or {}
    assert any(k.startswith("inline-example.jpg#") for k in urls)
    assert urls.get(legacy_key) == "http://old.example/a.jpg"  # 旧键保留无害
