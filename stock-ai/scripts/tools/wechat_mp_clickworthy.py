"""把公众号标题与开头变得更具体，但不脱离可核验事实。"""

from __future__ import annotations


_DISCLOSURE = "以下为综合公开报道常见处境的合成情境，不对应具体当事人。"


def rewrite_clickworthy_title(
    title: str,
    *,
    topic_label: str,
    enabled: bool,
) -> str:
    """仅在已知主体时，把难以理解的抽象判断换成可感知的问题。"""
    clean = (title or "").strip()
    label = (topic_label or "").strip()
    if not enabled or "改命" not in clean:
        if enabled and clean.endswith("影响大吗？"):
            return clean.removesuffix("影响大吗？").rstrip("，、：: ") + "，会先影响谁的钱包和选择？"
        return clean
    if "董明珠" in clean and "格力" in clean and "董明珠" in label and "格力" in label:
        return "董明珠当校长，技校生毕业真能进格力吗？"
    return clean


def prepend_disclosed_composite_opening(
    body: str,
    *,
    topic_label: str,
    fact_lines: list[str],
    enabled: bool,
) -> str:
    """用披露过的合成情境引出已核验事实；不具备事实时保持原文。"""
    clean_body = (body or "").strip()
    if not enabled or not clean_body or not fact_lines or clean_body.startswith(_DISCLOSURE):
        return clean_body
    fact = next((line.strip() for line in fact_lines if line and line.strip()), "")
    if not fact:
        return clean_body
    label = (topic_label or "这件事").strip()
    scene = f"“这条路走下去，最后能换来什么？”围绕{label}，很多人的犹豫并不抽象。"
    return f"{scene}\n\n{_DISCLOSURE}\n\n{fact}\n\n{clean_body}"
