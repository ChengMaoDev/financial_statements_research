"""保留2023—2026研究记录；原件及报告内期初/比较列保持原样。

逐表选定报告期或观测日期，不按正文、商品ID、上市时间筛选。分红按财年，
报告索引按报告期，港股公告按披露日。2023年指标所需期初数可从2023年报
读取，不能将缺失的期初余额替换为期末余额。CSV全部通过本脚本裁剪。
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
START_YEAR = 2023
END_YEAR = 2026
DATE_FIELDS = (
    "年度",
    "报告期",
    "期间",
    "报告日期",
    "报告时间",
    "股东户数统计截止日",
    "日期",
    "date",
    "持股日期",
    "月份",
    "披露日期",
)


def in_scope(value: str) -> bool:
    match = re.match(r"^(\d{4})", value.strip())
    return match is not None and START_YEAR <= int(match.group(1)) <= END_YEAR


def usable_report(company: str, period: str) -> bool:
    """采集入口统一按报告期过滤，company保留以兼容调用方。"""
    return in_scope(period)


def usable_segment(company: str, period: str, category: str) -> bool:
    """主营构成按报告日期过滤。"""
    return in_scope(period)


def filter_file(path: Path, *, apply: bool = True) -> tuple[int, int]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or ())
        rows = list(reader)
    date_field = next((field for field in DATE_FIELDS if field in fields), None)
    if date_field is None:
        return len(rows), 0
    kept = [row for row in rows if in_scope(row[date_field])]
    removed = len(rows) - len(kept)
    if apply and removed:
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(kept)
    return len(kept), removed


def enforce(root: Path = ROOT, *, apply: bool = True) -> tuple[int, int]:
    removed = total = 0
    for folder in ("财务数据", "市场数据", "定期报告"):
        for path in sorted((root / folder).rglob("*.csv")):
            kept, dropped = filter_file(path, apply=apply)
            total += kept
            removed += dropped
            if dropped:
                print(f"{path.relative_to(root)}：保留 {kept}，范围外 {dropped}")
    return total, removed


def opening_2023(company: str, metrics: tuple[str, ...]) -> dict[str, float]:
    """从2023年报资产负债表比较列获取期初余额，只用于2023指标计算。"""
    from verify_against_pdf import extract

    values = {
        entry.metric: entry.value
        for entry in extract(
            ROOT / "年度报告" / f"{company[:2]}2023.pdf",
            "资产负债表",
            metrics={metric: (metric,) for metric in metrics},
        )
        if entry.column == "比较期" and entry.metric in metrics
    }
    missing = set(metrics) - values.keys()
    if missing:
        raise ValueError(f"{company}2023年报缺少期初科目：{sorted(missing)}")
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="写入裁剪后的CSV")
    args = parser.parse_args()
    total, removed = enforce(apply=args.apply)
    print(f"2023—2026范围内 {total} 行，{'已删除' if args.apply else '待删除'} {removed} 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
