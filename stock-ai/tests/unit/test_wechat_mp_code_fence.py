"""公众号正文 ``` 代码围栏渲染。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_format import prepare_static_mp_body, split_body_code_fences
from scripts.tools.wechat_mp_client import text_to_html
from scripts.tools.wechat_mp_content import build_temp_article
from scripts.tools.wechat_mp_rich_html import code_block_html


def test_split_body_code_fences() -> None:
    raw = "前文\n\n```bash\nlark-cli --version\n```\n\n后文"
    parts = split_body_code_fences(raw)
    assert ("code", "bash", "lark-cli --version") in [
        (k, lang, c.strip()) for k, lang, c in parts if k == "code"
    ]


def test_code_block_html_escapes() -> None:
    html = code_block_html('echo "<secret>"', lang="bash")
    assert "<pre" in html
    assert "&lt;secret&gt;" in html
    assert "monospace" in html


def test_text_to_html_renders_fence() -> None:
    body = "> 安装\n\n```bash\nlark-cli config init\n```\n\n配好后检查。"
    html = text_to_html(body, upload_figures=False)
    assert "lark-cli config init" in html
    assert "<pre" in html
    assert "安装" in html
    assert "text-align:center" in html


def test_prepare_static_mp_body_keeps_fence() -> None:
    raw = "**粗体**\n\n```\ncmd\n```"
    out = prepare_static_mp_body(raw)
    assert "```" in out
    assert "cmd" in out
    assert "**" not in out


def test_build_temp_lark_cli_has_code_blocks() -> None:
    art = build_temp_article(variant="lark_cli")
    assert "```bash" in art["body_text"]
    assert "<pre" in art["content"]
