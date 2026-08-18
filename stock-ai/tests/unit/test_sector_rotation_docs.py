from pathlib import Path


def test_docs_publish_only_the_manual_sector_rotation_entrypoint() -> None:
    capabilities = Path("docs/CAPABILITIES.md").read_text(encoding="utf-8")
    playbook = Path(
        "investment-agent/docs/skills/stock-strategy-selector/references/strategy-playbook.md"
    ).read_text(encoding="utf-8")
    command = ".venv/bin/python -m scripts.analysis.detect_sector_rotation"

    assert command in capabilities
    assert command in playbook
    assert "每个方向最多10只观察股" in capabilities
    assert "自动下单" in capabilities and "不" in capabilities
