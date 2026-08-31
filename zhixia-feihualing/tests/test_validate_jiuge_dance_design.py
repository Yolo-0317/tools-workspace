from __future__ import annotations

import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = PROJECT_ROOT / "scripts" / "validate_jiuge_dance_design.py"
SPEC = importlib.util.spec_from_file_location(
    "validate_jiuge_dance_design", VALIDATOR_PATH
)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def prompt_text(extra_body: str = "") -> str:
    windows = "\n".join(validator.WINDOWS)
    required = "\n".join((
        "原创虚构数字角色",
        "九歌祭舞 v03",
        "严格两个",
        "不复刻角色卡排版",
        "不得生成可辨识人声",
    ))
    return f"""# 东皇太一
## 原典与现代转译
说明
## 十五秒舞蹈设计卡
{windows}
## Seedance 完整提示词
{required}
双手始终空着，全程不触碰、不拿取任何器物。
{extra_body}
## 验收要点
完成
"""


def future_prompt_text() -> str:
    windows = "\n".join(validator.WINDOWS)
    return f"""# 湘君
> 状态：待按15秒诗舞剧规范重写，不得直接付费生成。
## 原典与现代转译
说明
## 十五秒舞蹈设计卡
- 视线对象：神境
- 初始表情：克制
- 情绪转折：发生
- 结束状态：余势
{windows}
## Seedance 完整提示词
原创虚构数字角色
九歌祭舞 v03
严格两个
不复刻角色卡排版
双手始终空着，全程不触碰、不拿取任何器物。
声音分工：Seedance 不得生成可辨识人声，只生成无人声电影感国风音乐、自然环境声和动作声。
栀夏不张嘴说话、不做朗诵口型。
准确诗文与当代映射使用当前栀夏固定音色后期生成。
## 验收要点
完成
"""


class PromptRulesTests(unittest.TestCase):
    def validate_text(self, text: str) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "01-donghuang-taiyi-15s.md"
            path.write_text(text, encoding="utf-8")
            validator.validate_prompt(path, "东皇太一")

    def validate_future_text(self, text: str) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "03-xiangjun-15s.md"
            path.write_text(text, encoding="utf-8")
            validator.validate_prompt(path, "湘君")

    def test_future_prompt_accepts_post_tts_pending_rewrite_contract(self) -> None:
        try:
            self.validate_future_text(future_prompt_text())
        except ValueError as error:
            self.fail(f"post-TTS pending rewrite should be accepted: {error}")

    def test_future_prompt_requires_pending_rewrite_marker(self) -> None:
        text = future_prompt_text().replace(
            "> 状态：待按15秒诗舞剧规范重写，不得直接付费生成。\n", ""
        )
        with self.assertRaisesRegex(ValueError, "pending poetry-drama rewrite marker"):
            self.validate_future_text(text)

    def test_future_prompt_requires_post_tts_contract(self) -> None:
        text = future_prompt_text().replace("后期生成", "另行处理")
        with self.assertRaisesRegex(ValueError, "post-TTS phrase"):
            self.validate_future_text(text)

    def test_future_prompt_rejects_native_offscreen_recitation(self) -> None:
        text = future_prompt_text().replace(
            "## 验收要点",
            "年轻中国女性的画外朗诵，只朗诵这些文字。\n## 验收要点",
        )
        with self.assertRaisesRegex(ValueError, "forbidden native audio phrase"):
            self.validate_future_text(text)

    def test_prompt_requires_global_empty_hands_sentence(self) -> None:
        text = prompt_text().replace(
            "双手始终空着，全程不触碰、不拿取任何器物。\n", ""
        )
        with self.assertRaisesRegex(
            ValueError, "prompt body missing 双手始终空着"
        ):
            self.validate_text(text)

    def test_prompt_rejects_legacy_handheld_action(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "forbidden handheld term 道具牵引"
        ):
            self.validate_text(prompt_text("第二高潮使用道具牵引。"))

    def test_future_chapter_requires_gaze_and_expression_contract(self) -> None:
        text = prompt_text().replace("# 东皇太一", "# 云中君", 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "02-yunzhongjun-15s.md"
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(
                ValueError, "missing design-card field 视线对象"
            ):
                validator.validate_prompt(path, "云中君")


class LedgerRulesTests(unittest.TestCase):
    def write_ledger(self, rows: list[dict[str, str]], directory: str) -> Path:
        path = Path(directory) / "ledger.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=validator.CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def no_prop_rows(self) -> list[dict[str, str]]:
        source = PROJECT_ROOT / "operations" / "jiuge-dance-design-history.csv"
        with source.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        for index, row in enumerate(rows):
            row["prop"] = "无"
            if index:
                row["notes"] += (
                    "；视线对象=神境承接物；"
                    "表情弧线=初始情绪→关系转折→结束余势；"
                    "声音模式=栀夏克制女声"
                )
        return rows

    def test_all_no_prop_rows_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            try:
                validator.validate_ledger(
                    self.write_ledger(self.no_prop_rows(), directory)
                )
            except ValueError as error:
                self.fail(f"all-no-prop ledger should be accepted: {error}")

    def test_any_non_empty_prop_is_rejected(self) -> None:
        rows = self.no_prop_rows()
        rows[0]["prop"] = "礼剑"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "expected prop 无"):
                validator.validate_ledger(self.write_ledger(rows, directory))

    def test_future_chapter_requires_aesthetic_notes(self) -> None:
        rows = self.no_prop_rows()
        rows[1]["notes"] = "不悬浮且不生成翅膀"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                ValueError, "missing notes token 视线对象="
            ):
                validator.validate_ledger(self.write_ledger(rows, directory))


if __name__ == "__main__":
    unittest.main()
