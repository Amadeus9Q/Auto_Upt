import csv
from collections import Counter
from pathlib import Path


CATALOG_PATH = Path(__file__).parents[1] / "docs" / "test-cases-full-lifecycle.csv"
EXPECTED_COLUMNS = [
    "用例ID",
    "阶段",
    "模块",
    "测试类型",
    "优先级",
    "用例名称",
    "前置条件",
    "测试数据",
    "测试步骤",
    "预期结果",
    "自动化建议",
]
UNIMPLEMENTED_SUCCESS_PATTERNS = (
    "知乎真实发布成功",
    "知乎草稿成功",
    "小红书账号连接成功",
    "小红书真实发布成功",
)


def _catalog_rows() -> list[dict[str, str]]:
    with CATALOG_PATH.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def test_catalog_has_valid_unique_complete_rows() -> None:
    rows = _catalog_rows()
    ids = [row["用例ID"] for row in rows]

    assert len(rows) >= 150
    assert len(ids) == len(set(ids))
    assert list(rows[0]) == EXPECTED_COLUMNS
    assert all(all(row[column].strip() for column in EXPECTED_COLUMNS) for row in rows)


def test_catalog_prioritizes_critical_lifecycle_cases() -> None:
    priorities = Counter(row["优先级"] for row in _catalog_rows())

    assert priorities["P0"] >= 75
    assert priorities["P1"] >= 60


def test_catalog_does_not_claim_unimplemented_success_paths() -> None:
    catalog_text = CATALOG_PATH.read_text(encoding="utf-8")

    assert all(pattern not in catalog_text for pattern in UNIMPLEMENTED_SUCCESS_PATTERNS)

