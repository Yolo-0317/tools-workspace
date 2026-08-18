from stock_ai.sector_rotation.models import RawSectorRow
from stock_ai.sector_rotation.normalization import load_chain_rules, merge_sector_rows


def _row(code: str, name: str, rank: int) -> RawSectorRow:
    return RawSectorRow(code, name, rank, 2.0, "000001", "示例", 5.0)


def test_agriculture_subsectors_merge_into_one_stable_chain() -> None:
    chains = merge_sector_rows(
        (
            _row("BK1", "种子", 1),
            _row("BK2", "粮食种植", 5),
            _row("BK3", "种植业", 9),
        ),
        load_chain_rules(),
    )

    assert [(value.chain_code, value.chain_name) for value in chains] == [
        ("agriculture_planting", "农业种植")
    ]
    assert chains[0].raw_sector_codes == ("BK1", "BK2", "BK3")


def test_unmapped_valid_sector_gets_a_stable_fallback_chain() -> None:
    chains = merge_sector_rows((_row("BK999", "新型材料", 12),), load_chain_rules())

    assert chains[0].chain_code == "raw_bk999"
    assert chains[0].chain_name == "新型材料"


def test_navigation_labels_are_rejected_before_merging() -> None:
    chains = merge_sector_rows((_row("BK0", "今日资金流排行", 1),), load_chain_rules())

    assert chains == ()
