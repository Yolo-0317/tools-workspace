#!/usr/bin/env python3
"""Render a reviewed market article as inline-style WeChat HTML and local preview."""

import argparse
from html import escape
from pathlib import Path
import re


STOCK_ROW = re.compile(r"(\d+)\. (.+?)（(\d{6})）：(涨|跌)(\d+(?:\.\d+)?)%")
ORDERED_ROW = re.compile(r"(\d+)\. (.+)")
PARAGRAPH_STYLE = (
    "margin:0 0 21px;font-size:17px;line-height:1.85;color:#333;"
    "text-align:left;word-break:break-word"
)


def inline(text: str) -> str:
    """Escape text while preserving simple Markdown emphasis and http(s) links."""
    result = []
    cursor = 0
    pattern = re.compile(r"\*\*([^*]+)\*\*|\[([^\]]+)\]\((https?://[^)]+)\)")
    for match in pattern.finditer(text):
        result.append(escape(text[cursor : match.start()]))
        if match.group(1) is not None:
            result.append(f'<strong style="color:#1a5276">{escape(match.group(1))}</strong>')
        else:
            result.append(
                f'<a href="{escape(match.group(3), quote=True)}" '
                f'style="color:#1a5276;text-decoration:underline">'
                f'{escape(match.group(2))}</a>'
            )
        cursor = match.end()
    result.append(escape(text[cursor:]))
    return "".join(result)


def list_block(lines: list[str]) -> str:
    stock_rows = [STOCK_ROW.fullmatch(line) for line in lines]
    if all(stock_rows):
        html_rows = []
        for expected, match in enumerate(stock_rows, 1):
            assert match is not None
            rank, name, code, direction, change = match.groups()
            if int(rank) != expected:
                raise ValueError("股吧人气榜名次必须从 1 开始连续排列")
            background = "#f7fafc" if expected % 2 else "#fff"
            html_rows.append(
                f'<tr style="background:{background}">'
                f'<td style="padding:10px 5px 10px 10px;border-bottom:1px solid #e8eef2;'
                f'font-size:15px;line-height:1.55;color:#7895a7;width:26px">{rank}</td>'
                f'<td style="padding:10px 5px;border-bottom:1px solid #e8eef2;'
                f'font-size:16px;line-height:1.55;color:#333">{escape(name)}'
                f'<span style="display:block;font-size:12px;color:#78858e">{code}</span></td>'
                f'<td style="padding:10px 10px 10px 5px;border-bottom:1px solid #e8eef2;'
                f'font-size:15px;line-height:1.55;color:#333;text-align:right;'
                f'width:90px;white-space:nowrap">{direction}{escape(change)}%</td></tr>'
            )
        return (
            '<table style="width:100%;border-collapse:collapse;margin:0 0 13px;'
            'table-layout:fixed">' + "".join(html_rows) + "</table>"
        )

    rows = []
    for expected, line in enumerate(lines, 1):
        match = ORDERED_ROW.fullmatch(line)
        if not match or int(match.group(1)) != expected:
            raise ValueError("有序列表名次必须从 1 开始连续排列")
        rows.append(f'<li style="margin:0 0 11px;padding-left:3px">{inline(match.group(2))}</li>')
    return (
        '<ol style="margin:0 0 23px;padding:0 0 0 27px;font-size:17px;'
        'line-height:1.85;color:#333">' + "".join(rows) + "</ol>"
    )


def render(markdown: str, label: str) -> tuple[str, str]:
    parts = [part.strip() for part in markdown.strip().split("\n\n") if part.strip()]
    if not parts or not parts[0].startswith("# "):
        raise ValueError("文章首段必须是单行 # 标题")
    title = parts[0][2:].strip()
    if not title or "\n" in title:
        raise ValueError("标题不能为空或跨行")
    blocks = [
        '<p style="margin:0 0 20px;font-size:13px;line-height:1.6;'
        f'letter-spacing:1px;color:#637b8b">{escape(label)}</p>'
    ]
    section_number = 0
    for part in parts[1:]:
        if part.startswith("## "):
            section_number += 1
            blocks.append(
                '<section style="margin:38px 0 19px;padding:0 0 11px;'
                'border-bottom:1px solid #c7d8e3">'
                f'<span style="font-size:13px;line-height:1.5;color:#7895a7">'
                f'{section_number:02d}</span>'
                f'<h2 style="margin:3px 0 0;font-size:21px;line-height:1.5;'
                f'font-weight:700;color:#1a5276">{escape(part[3:].strip())}</h2></section>'
            )
        elif part.startswith("> "):
            blocks.append(
                '<section style="margin:6px 0 28px;padding:16px 18px;'
                'background:#f1f6fa;border-left:3px solid #1a5276;'
                'border-radius:0 7px 7px 0">'
                '<p style="margin:0;font-size:17px;line-height:1.8;'
                f'font-weight:600;color:#1a5276">{inline(part[2:].strip())}</p></section>'
            )
        elif part.startswith("资料："):
            blocks.append(
                '<section style="margin:32px 0 0;padding:18px 0 2px;'
                'border-top:1px solid #dce6ec">'
                '<p style="margin:0 0 9px;font-size:14px;line-height:1.7;'
                'font-weight:700;color:#1a5276">资料与说明</p>'
                f'<p style="margin:0;font-size:13px;line-height:1.8;'
                f'color:#606b73">{inline(part.removeprefix("资料："))}</p></section>'
            )
        elif all(ORDERED_ROW.fullmatch(line) for line in part.splitlines()):
            blocks.append(list_block(part.splitlines()))
        else:
            blocks.append(f'<p style="{PARAGRAPH_STYLE}">{inline(part)}</p>')

    content = '<section style="padding:0 6px">' + "\n".join(blocks) + "</section>"
    preview = (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{escape(title)}</title></head>'
        '<body style="margin:0;background:#eef1f3;font-family:-apple-system,'
        'BlinkMacSystemFont,\'PingFang SC\',\'Microsoft YaHei\',sans-serif">'
        '<main style="max-width:640px;margin:0 auto;padding:28px 17px 40px;'
        'background:#fff;box-sizing:border-box">'
        '<header style="margin:0 6px 28px;padding-bottom:17px;'
        'border-bottom:1px solid #dce6ec">'
        f'<h1 style="margin:0;font-size:25px;line-height:1.5;color:#25313a">'
        f'{escape(title)}</h1></header>{content}</main></body></html>'
    )
    return content, preview


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("article", type=Path, help="审核后的 Markdown 文章")
    parser.add_argument("--output-dir", type=Path, help="输出目录；默认与文章同目录")
    parser.add_argument("--label", default="妙想 Skill · 盘后观察", help="正文顶部栏目标签")
    args = parser.parse_args()
    output_dir = args.output_dir or args.article.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    content, preview = render(args.article.read_text(), args.label)
    (output_dir / "rendered_content.html").write_text(content)
    (output_dir / "preview.html").write_text(preview)
    print(f"已生成 {output_dir / 'rendered_content.html'} 与 {output_dir / 'preview.html'}")


if __name__ == "__main__":
    main()
