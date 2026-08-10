"""分析报告腔扫描。"""

from __future__ import annotations

from scripts.tools.wechat_mp_report_voice import scan_report_voice


def test_scan_report_voice_catches_wind_direction() -> None:
    text = "风向是在松：四十集上限准备放开。"
    hits = scan_report_voice(text)
    assert hits
    assert any("风向" in label or "拟放开" in label for label, _, _ in hits)


def test_scan_report_voice_catches_industry_example() -> None:
    text = "有人举那种压了多年的仙侠，服化道一眼五年前。"
    hits = scan_report_voice(text)
    assert len(hits) >= 2


def test_scan_report_voice_ok_colloquial() -> None:
    text = "最近帖子也在传：四十集上限可能要放开。有人接话：积压剧能不能快点见光？"
    assert not scan_report_voice(text)
