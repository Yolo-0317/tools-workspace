from pathlib import Path


WORKSPACE = Path(__file__).parents[3]
STOCK_AI = WORKSPACE / "stock-ai"
MARKERS = (
    "AI_STATUS: DEPRECATED",
    "AI_USAGE: FORBIDDEN",
    "HUMAN_USAGE: AUDIT_ONLY",
)


def test_legacy_sop_routes_stop_ai_and_preserve_human_audit_only() -> None:
    route = (STOCK_AI / "investment-agent/docs/skills/eastmoney-browser-sop/ROUTING.md").read_text(
        encoding="utf-8"
    )
    skill = (STOCK_AI / "investment-agent/docs/skills/eastmoney-browser-sop/SKILL.md").read_text(
        encoding="utf-8"
    )

    for marker in MARKERS:
        assert marker in route
        assert marker in skill
    for rule in ("立即停止", "不得调用", "不得推荐", "不得继续读取"):
        assert rule in route


def test_current_ai_routes_do_not_recommend_the_legacy_sop() -> None:
    opencli = (WORKSPACE / ".cursor/skills/stock-opencli/ROUTING.md").read_text(encoding="utf-8")
    opencli_skill = (WORKSPACE / ".cursor/skills/stock-opencli/SKILL.md").read_text(
        encoding="utf-8"
    )
    selector = (
        STOCK_AI / "investment-agent/docs/skills/stock-strategy-selector/SKILL.md"
    ).read_text(encoding="utf-8")
    capabilities = (STOCK_AI / "docs/CAPABILITIES.md").read_text(encoding="utf-8")

    assert "新版个股诊断" in opencli
    assert "stock-strategy-selector" in opencli
    assert "eastmoney-browser-sop" not in opencli
    assert "eastmoney-browser-sop" not in opencli_skill
    assert "SOP 多维快照" not in opencli_skill
    assert "eastmoney-browser-sop/SKILL.md" not in selector
    for marker in MARKERS:
        assert marker in capabilities
    assert "人工审计遗留能力" in capabilities


def test_deprecation_does_not_delete_legacy_human_audit_script() -> None:
    assert (STOCK_AI / "scripts/analysis/eastmoney_sop_extract.py").is_file()
