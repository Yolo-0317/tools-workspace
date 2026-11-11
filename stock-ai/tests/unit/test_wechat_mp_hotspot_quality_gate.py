from __future__ import annotations

import pytest

from scripts.tools.wechat_mp_hotspot_quality_gate import (
    evaluate_hotspot_editorial_quality,
    scan_hotspot_public_copy,
)


def test_rejects_editorial_instruction_leak() -> None:
    findings = scan_hotspot_public_copy(
        title="辽宁中考3科不再计分，减负会不会变成偏科？",
        digest="辽宁调整中考计分科目。",
        body="这是辽宁的地方政策，更不能写成全国统一取消历史、地理和生物三科计分。",
        research_urls=("https://jyt.ln.gov.cn/policy",),
    )

    assert [item.code for item in findings] == ["editorial_instruction_leak"]


@pytest.mark.parametrize(
    "sentence",
    (
        "不计入总分不等于取消课程。",
        "不能据此推断全国统一调整。",
        "不能把管理成本转嫁给家长。",
    ),
)
def test_allows_reader_facing_argument(sentence: str) -> None:
    assert not scan_hotspot_public_copy(
        title="辽宁中考调整会带来什么？",
        digest="辽宁调整部分科目计分方式。",
        body=f"辽宁省教育厅发布调整。\n\n{sentence}\n\n家长仍需等待细则。",
        research_urls=("https://jyt.ln.gov.cn/policy",),
    )


def test_rejects_banned_marketing_title_and_unsupported_scope() -> None:
    findings = scan_hotspot_public_copy(
        title="重磅！全国所有学生彻底取消中考3科",
        digest="辽宁发布地方调整。",
        body="辽宁省教育厅发布地方调整。\n\n其他地区方案不同。",
        research_urls=("https://example.com/report",),
    )

    assert {item.code for item in findings} >= {"title_hype", "unsupported_scope"}


def test_allows_scope_word_when_title_explicitly_denies_nationwide_change() -> None:
    assert not scan_hotspot_public_copy(
        title="辽宁调整不代表全国统一取消中考3科",
        digest="辽宁发布地方调整。",
        body="辽宁省教育厅发布地方调整，中考3科改为等级考查。",
        research_urls=("https://example.com/report",),
    )


@pytest.mark.parametrize(
    ("title", "body"),
    (
        ("买学区房必上这所小学", "北京某区今年公布义务教育入学细则。"),
        ("深圳小升初怎么选？", "我们有内部名额，可以保证录取。"),
        ("广州高中选校指南", "缴纳费用即可花钱保录取。"),
        ("上海民办初中怎么报？", "报名这项课程可以百分百录取。"),
    ),
)
def test_rejects_school_choice_admission_promises(title: str, body: str) -> None:
    findings = scan_hotspot_public_copy(
        title=title,
        digest="家长关注当年招生规则。",
        body=body,
        research_urls=("https://edu.example.gov.cn/policy",),
    )

    assert "school_choice_admission_promise" in {item.code for item in findings}


@pytest.mark.parametrize(
    "body",
    (
        "买学区房也不能保证入学，最终要看当年区级审核和派位结果。",
        "警方查处宣称百分百录取的入学骗局，家长不要相信内部名额。",
        "教育部门明确禁止学校收取所谓择校费，也不存在花钱保录取。",
    ),
)
def test_allows_school_choice_warning_context(body: str) -> None:
    assert not scan_hotspot_public_copy(
        title="北京义务教育入学规则怎么变？",
        digest="解读当年区级招生政策。",
        body=body,
        research_urls=("https://jw.beijing.gov.cn/policy",),
    )


def test_school_choice_promise_scan_does_not_affect_unrelated_hotspot() -> None:
    findings = scan_hotspot_public_copy(
        title="平台会员承诺引发退款争议",
        digest="消费者要求平台兑现服务。",
        body="商家宣称百分百退款，双方对合同理解不同。",
        research_urls=("https://example.com/report",),
    )

    assert "school_choice_admission_promise" not in {item.code for item in findings}


def test_warning_before_contrast_does_not_hide_later_admission_promise() -> None:
    findings = scan_hotspot_public_copy(
        title="深圳积分入学怎么准备？",
        digest="核对当年区级招生细则。",
        body="普通渠道不能保证录取，但我们有内部名额，可以保证孩子入学。",
        research_urls=("https://www.sz.gov.cn/policy",),
    )

    assert "school_choice_admission_promise" in {item.code for item in findings}


def test_rejects_unfulfilled_title_number_and_duplicate_paragraph() -> None:
    body = "辽宁调整中考科目。\n\n家长仍在等待实施细则。\n\n家长仍在等待实施细则。"

    findings = scan_hotspot_public_copy(
        title="辽宁中考5项变化",
        digest="辽宁调整中考科目。",
        body=body,
        research_urls=("https://jyt.ln.gov.cn/policy",),
    )

    assert {item.code for item in findings} >= {
        "title_number_unfulfilled",
        "duplicate_paragraph",
    }


def test_title_arabic_number_can_be_fulfilled_by_chinese_number() -> None:
    findings = scan_hotspot_public_copy(
        title="辽宁中考3科不再计分",
        digest="辽宁调整中考科目。",
        body="辽宁省教育厅明确，历史、地理和生物三科改为等级考查。",
        research_urls=("https://jyt.ln.gov.cn/policy",),
    )

    assert "title_number_unfulfilled" not in {item.code for item in findings}


def test_editorial_score_rewards_complete_commentary() -> None:
    report = evaluate_hotspot_editorial_quality(
        title="辽宁中考3科不再计分，减负会不会变成偏科？",
        topic="辽宁中考科目调整",
        original_thesis="减少计分科目能否减负，取决于课时、等级使用和录取配套是否公开。",
        research_urls=("https://a.gov.cn/1", "https://b.cn/2", "https://c.cn/3"),
        body=(
            "辽宁省教育厅发布中考科目调整，历史、地理和生物改为等级考查。\n\n"
            "家长关心的不是少考三科，而是课时、等级和录取规则会怎样变化。\n\n"
            "支持者认为减少计分项目能够减轻刷题压力，这个方向有现实依据。\n\n"
            "但如果压力全部转向语数外物理，学生总负担未必降低。\n\n"
            "这是辽宁的地方政策，各地中考方案不同，不能据此推断全国统一调整。\n\n"
            "如果历史、地理和生物不计总分，你更担心压力转移还是课程被边缘化？"
        ),
    )

    assert report.passed is True
    assert report.score >= 5
    assert report.total == 7


def test_editorial_score_rejects_news_summary_without_argument() -> None:
    report = evaluate_hotspot_editorial_quality(
        title="辽宁中考调整",
        topic="辽宁中考科目调整",
        original_thesis="",
        research_urls=("https://a.gov.cn/1",),
        body="辽宁发布通知。\n\n三科调整为考查。\n\n消息受到关注。",
    )

    assert report.passed is False
    assert report.score < 5


def test_rejects_paired_self_review_voice() -> None:
    body = (
        "公开资料显示，北大图灵班采用多轮招生机制，并非只有高考招生这一条进入路径。"
        "因此，不能把这个结果简单理解成‘复读1年就能直接锁定图灵班’，"
        "更不能把个案当成可以复制的升学方案。"
    )
    findings = scan_hotspot_public_copy(
        title="孩子已被北大录取，家长该不该支持他复读？",
        digest="讨论复读选择的风险。",
        body=body,
        research_urls=("https://www.pku.edu.cn/article",),
    )

    assert any(item.code == "self_review_voice" for item in findings)


def test_rejects_data_usage_disclaimer_voice() -> None:
    findings = scan_hotspot_public_copy(
        title="大一新生每月1000元，究竟能覆盖多少大学生活？",
        digest="讨论大学生活的实际花费。",
        body=(
            "麦可思调查中，受访学生月均生活费为1744元。"
            "1744元可以用来观察消费分布，不能拿来划一条全国统一的生活费标准。"
        ),
        research_urls=("https://example.com/report",),
    )

    assert "data_usage_disclaimer_voice" in {item.code for item in findings}


@pytest.mark.parametrize(
    "body",
    (
        "为了避免读者误解，这篇文章并不是要否定学校已经做的工作。",
        "本文想讨论的不是学校好坏，而是家长应该怎样理解这项政策。",
        "这篇稿子不能被理解为对所有民办学校的批评。",
    ),
)
def test_rejects_article_level_self_explanation(body: str) -> None:
    findings = scan_hotspot_public_copy(
        title="教育政策怎样落到家庭？",
        digest="讨论家庭承担的现实成本。",
        body=body,
        research_urls=("https://www.moe.gov.cn/policy",),
    )

    assert "self_review_voice" in {item.code for item in findings}


@pytest.mark.parametrize(
    "body",
    (
        "这项减免不包括伙食费，家庭仍需按实际就餐天数结算。",
        "校方通报只能说明学校已经作出这一回应，最终结论仍待主管部门核查。",
        "政府购买学位不等于学费全免，超过购买标准的差额仍由家庭承担。",
    ),
)
def test_allows_direct_fact_boundaries(body: str) -> None:
    findings = scan_hotspot_public_copy(
        title="教育政策怎样落到家庭？",
        digest="讨论家庭承担的现实成本。",
        body=body,
        research_urls=("https://www.moe.gov.cn/policy",),
    )

    assert "self_review_voice" not in {item.code for item in findings}


@pytest.mark.parametrize(
    "body",
    (
        "学校不能把管理成本转嫁给家长。",
        "不能把地方政策写成全国统一政策。",
        "家长不能把一次考试失利当成孩子能力不足的证明。",
    ),
)
def test_allows_single_real_world_boundary_judgment(body: str) -> None:
    findings = scan_hotspot_public_copy(
        title="教育政策怎样落到家庭？",
        digest="讨论家庭承担的现实成本。",
        body=body,
        research_urls=("https://www.moe.gov.cn/policy",),
    )

    assert not any(item.code == "self_review_voice" for item in findings)
