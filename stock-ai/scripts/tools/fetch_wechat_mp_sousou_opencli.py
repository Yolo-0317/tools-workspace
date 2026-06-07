#!/usr/bin/env python3
"""微信搜一搜数据看板 — 绑定已有 Chrome tab（不新开 OpenCLI 自动化窗）。

前提：OpenCLI ≥1.8、Chrome 扩展 ≥1.0.18；目标页须在 Chrome 且为前台 tab。

用法：
  1. Chrome 打开：广告与服务 → 微信搜一搜 → 数据看板
     （URL 形如 pluginloginpage?pluginuin=10071&token=…）
  2. 点一下该 tab，使其成为当前窗口的前台标签
  3. cd stock-ai && uv run python -m scripts.tools.fetch_wechat_mp_sousou_opencli

  # 可选：校验 URL 片段
  uv run python -m scripts.tools.fetch_wechat_mp_sousou_opencli \\
    --expect-url-substr 'pluginuin=10071' -o output/wechat_mp_sousou_latest.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

ROOT = Path(__file__).resolve().parents[2]
TZ = ZoneInfo("Asia/Shanghai")

from scripts.tools.fetch_eastmoney_quotes import _run_opencli  # noqa: E402

DEFAULT_SESSION = "mp"
PLUGIN_SUBSTR = "pluginloginpage"
DEFAULT_PLUGINUIN = "10071"

CHECK_BIND_JS = r"""
JSON.stringify((() => {
  const text = document.body.innerText || "";
  return {
    url: location.href,
    title: document.title,
    has_problem: text.includes("遇到问题"),
    has_dashboard: /搜索后阅读|搜索后关注|关键数据|数据中心/.test(text),
    pluginuin: "",
  };
})())
"""

EXTRACT_SOUSOU_JS = r"""
JSON.stringify((() => {
  const text = document.body.innerText || "";
  const numAfter = (label) => {
    const i = text.indexOf(label);
    if (i < 0) return null;
    const block = text.slice(i, i + 120);
    const m = block.match(/(\d[\d,]*)/);
    return m ? parseInt(m[1].replace(/,/g, ""), 10) : null;
  };
  const momo = (text.match(/环比[^\\n%]+%?/) || [])[0] || null;
  const dataDate = (text.match(/数据更新时间:\s*([0-9.]+)/) || [])[1] || null;
  const hotWords = [];
  const followIdx = text.indexOf("用户通过以下搜索词找到你的账号");
  const readIdx = text.indexOf("搜索后阅读");
  if (followIdx >= 0 && readIdx > followIdx) {
    const block = text.slice(followIdx, readIdx);
    const lines = block.split("\n").map(s => s.trim()).filter(Boolean);
    for (const line of lines) {
      if (/^\d+$/.test(line)) continue;
      if (line.includes("用户通过") || line.includes("搜索词")) continue;
      if (line.length < 2 || line.length > 40) continue;
      hotWords.push(line.replace(/^\d+\s*/, ""));
    }
  }
  const hotArticles = [];
  const artIdx = text.indexOf("用户点击最多的文章");
  const faqIdx = text.indexOf("常见问题", artIdx + 1);
  if (artIdx >= 0) {
    const end = faqIdx > artIdx ? faqIdx : artIdx + 500;
    const block = text.slice(artIdx, end);
    const re = /^(\d+)\s+(.+)$/gm;
    let m;
    while ((m = re.exec(block)) !== null && hotArticles.length < 5) {
      hotArticles.push({ rank: parseInt(m[1], 10), title: m[2].trim() });
    }
  }
  return {
    url: location.href,
    hash: location.hash,
    data_date: dataDate,
    has_problem: text.includes("遇到问题"),
    has_dashboard: /搜索后阅读|搜索后关注|关键数据/.test(text),
    search_read: numAfter("搜索后阅读"),
    search_read_mom: momo,
    search_follow: numAfter("搜索后关注"),
    account_search_terms: hotWords,
    top_clicked_articles: hotArticles,
    body_preview: text.slice(0, 4000),
  };
})())
"""


def _eval_session(
    session: str,
    js: str,
    *,
    frame: str | None = None,
    timeout: float = 60,
) -> str:
    cmd = ["browser", session, "eval"]
    if frame is not None:
        cmd.extend(["--frame", frame])
    cmd.append(js)
    stdout, stderr, rc = _run_opencli(cmd, timeout=timeout)
    if rc != 0:
        raise RuntimeError(f"OpenCLI eval 失败: {stderr or stdout}")
    return stdout.strip()


def _list_frames(session: str) -> list[dict]:
    stdout, stderr, rc = _run_opencli(["browser", session, "frames"], timeout=30)
    if rc != 0:
        raise RuntimeError(f"frames 失败: {stderr or stdout}")
    try:
        data = json.loads(stdout.strip())
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _sousou_frame_index(frames: list[dict]) -> str | None:
    for fr in frames:
        url = str(fr.get("url") or "")
        if "mmuxsearch" in url or "wsad.weixin.qq.com" in url:
            return str(fr.get("index", 0))
    return "0" if frames else None


def _load_json(raw: str, *, label: str) -> dict:
    if not raw:
        raise RuntimeError(f"{label}: OpenCLI eval 无输出")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"{label}: JSON 解析失败: {raw[:200]}") from e


def _parse_bind_stdout(stdout: str) -> dict[str, str]:
    s = (stdout or "").strip()
    if s.startswith("{"):
        try:
            data = json.loads(s)
            return {k: str(data.get(k) or "") for k in ("session", "url", "title")}
        except json.JSONDecodeError:
            pass
    return {"raw": s}


def bind_browser_session(session: str) -> dict[str, str]:
    stdout, stderr, rc = _run_opencli(["browser", session, "bind"], timeout=45)
    if rc != 0:
        raise RuntimeError(
            f"bind 失败（请确认 Chrome 前台 tab 为搜一搜看板、扩展已连接）: {stderr or stdout}"
        )
    return _parse_bind_stdout(stdout)


def unbind_browser_session(session: str) -> None:
    _run_opencli(["browser", session, "unbind"], timeout=20)


def fetch_sousou_dashboard_via_bind(
    *,
    session: str | None = None,
    expect_url_substr: str = "",
    expect_pluginuin: str = DEFAULT_PLUGINUIN,
) -> dict:
    sess = session or os.getenv("OPENCLI_BROWSER_SESSION", DEFAULT_SESSION)
    bind_meta = bind_browser_session(sess)
    try:
        shell_url = str(bind_meta.get("url") or "")
        if PLUGIN_SUBSTR not in shell_url:
            hint = (
                "当前前台 tab 不是搜一搜看板（常见为 about:blank 或其它页）。"
                if "about:blank" in shell_url or not shell_url
                else "当前绑定的 URL 不对。"
            )
            raise RuntimeError(
                f"{hint}\n实际: {shell_url or '(空)'}\n"
                "请用鼠标点一下 Chrome 里的看板 tab（pluginloginpage?pluginuin=10071），"
                "再立即重跑本命令。"
            )
        if expect_pluginuin and expect_pluginuin not in shell_url:
            raise RuntimeError(f"URL 未含 pluginuin={expect_pluginuin}，实际: {shell_url}")
        if expect_url_substr and expect_url_substr not in shell_url:
            raise RuntimeError(f"URL 未含期望片段 {expect_url_substr!r}，实际: {shell_url}")

        frames = _list_frames(sess)
        frame_idx = _sousou_frame_index(frames)
        if frame_idx is None:
            raise RuntimeError("未找到搜一搜看板 iframe；请确认数据看板已加载完成。")

        # iframe 常落在 #/recommendNoticeStaff（运营者管理），切回关键数据页
        _eval_session(
            sess,
            r"""
(() => {
  if (!/搜索后阅读|关键数据/.test(document.body.innerText || '')) {
    location.hash = '#/wxSearch';
  }
  return true;
})()
""",
            frame=frame_idx,
            timeout=30,
        )
        time.sleep(2)

        check = _load_json(
            _eval_session(sess, CHECK_BIND_JS, frame=frame_idx, timeout=60),
            label="bind_check",
        )
        if check.get("has_problem") and not check.get("has_dashboard"):
            raise RuntimeError(
                "看板 iframe 未加载完成或显示异常。请在 Chrome 刷新数据看板后再 bind。"
            )
        if not check.get("has_dashboard"):
            raise RuntimeError(
                "未识别到看板内容（搜索后阅读/数据看板）。请确认 tab 已进入数据看板。"
            )

        data = _load_json(
            _eval_session(sess, EXTRACT_SOUSOU_JS, frame=frame_idx, timeout=90),
            label="sousou",
        )
        data["shell_url"] = shell_url
        data["iframe_index"] = frame_idx
        data["frames"] = frames
        data["bind_check"] = check
        data["bind_meta"] = bind_meta
        return data
    finally:
        unbind_browser_session(sess)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="绑定 Chrome 已有 tab 抓取微信搜一搜数据看板（不 browser open）"
    )
    parser.add_argument(
        "--session",
        default="",
        help=f"OpenCLI 会话名（默认 env OPENCLI_BROWSER_SESSION 或 {DEFAULT_SESSION}）",
    )
    parser.add_argument(
        "--expect-url-substr",
        default=os.getenv("WECHAT_MP_SOUSOU_EXPECT_URL", f"pluginuin={DEFAULT_PLUGINUIN}"),
        help="绑定后 URL 必须包含的片段（默认 pluginuin=10071）",
    )
    parser.add_argument(
        "--expect-pluginuin",
        default=DEFAULT_PLUGINUIN,
        help="pluginuin 校验（空字符串则跳过）",
    )
    parser.add_argument("-o", "--output", default="", help="输出 JSON 路径")
    args = parser.parse_args()

    session = (args.session or os.getenv("OPENCLI_BROWSER_SESSION") or DEFAULT_SESSION).strip()
    expect_substr = (args.expect_url_substr or "").strip()
    pluginuin = (args.expect_pluginuin or "").strip()

    print(
        "请确认：Chrome 前台 tab 为「微信搜一搜 → 数据看板」"
        f"（pluginloginpage?pluginuin={pluginuin or DEFAULT_PLUGINUIN}）…",
        file=sys.stderr,
    )

    try:
        dashboard = fetch_sousou_dashboard_via_bind(
            session=session,
            expect_url_substr=expect_substr,
            expect_pluginuin=pluginuin,
        )
        payload = {
            "fetched_at": datetime.now(TZ).isoformat(),
            "source": "mp.weixin.qq.com-sousou-bind",
            "session": session,
            "dashboard": dashboard,
        }
        out = (
            Path(args.output)
            if args.output
            else ROOT / "output" / "wechat_mp_sousou_latest.json"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print(f"\n已写入 {out}", file=sys.stderr)
        return 0
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
