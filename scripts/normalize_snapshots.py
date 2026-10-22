"""离线清理重复字段、股东户数副本和已确认无法解释的异常记录。

只去除每行取值一致的重复列。股东户数逐字段一致且冗余「代码/名称」
与主字段一致后，才删除市场数据下的副本；财务数据/股东户数.csv 为唯一入口。
默认只检查，--apply 才写盘；不改变行情数值，不发起外部请求。
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_REPORTS = frozenset(
    {
        ("格力电器", "20020930"),
        ("格力电器", "20060331"),
        ("海尔智家", "20060630"),
        ("海尔智家", "20060930"),
        ("美的集团", "20110630"),
    }
)


def usable_report(company: str, period: str) -> bool:
    """这五期曾出现报表恒等式异常，原因未确认，排除整期而非猜测改数。"""
    return (company, period) not in EXCLUDED_REPORTS


def usable_segment(company: str, period: str, category: str) -> bool:
    """海尔2018产品分类合计缺口未经原文确认，不保留该组构成。"""
    return (company, period, category) != ("海尔智家", "2018-12-31", "按产品分类")


def exclude_segments(apply: bool) -> None:
    path = ROOT / "财务数据/主营构成.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or ())
        rows = list(reader)
    kept = [row for row in rows if usable_segment(row["公司"], row["报告日期"], row["分类类型"])]
    print(f"{path.name}：删除 {len(rows) - len(kept)} 行未确认的产品构成")
    if apply and len(kept) != len(rows):
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(kept)


def exclude_reports(apply: bool) -> None:
    for name in ("资产负债表", "利润表", "现金流量表", "主要财务指标"):
        path = ROOT / "财务数据" / f"{name}.csv"
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            fields = list(reader.fieldnames or ())
            rows = list(reader)
        kept = [row for row in rows if usable_report(row["公司"], row["报告期"])]
        print(f"{path.name}：删除 {len(rows) - len(kept)} 行异常报告期")
        if apply and len(kept) != len(rows):
            with path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fields, lineterminator="\n")
                writer.writeheader()
                writer.writerows(kept)


def normalize_price(apply: bool) -> None:
    path = ROOT / "市场数据/结构化/日线行情.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        header, *rows = list(csv.reader(stream))
    keep: list[int] = []
    for index, field in enumerate(header):
        if field not in header[:index]:
            keep.append(index)
            continue
        prior = header.index(field)
        if any(row[index] != row[prior] for row in rows):
            raise ValueError(f"{path.name} 重复列 {field} 取值冲突，拒绝删除")
    print(f"{path.name}：{len(header)} → {len(keep)} 列，{len(rows)} 行")
    if apply and len(keep) != len(header):
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow([header[index] for index in keep])
            writer.writerows([row[index] for index in keep] for row in rows)


def consolidate_holders(apply: bool) -> None:
    canonical = ROOT / "财务数据/股东户数.csv"
    duplicate = ROOT / "市场数据/结构化/股东户数明细.csv"
    if not duplicate.exists():
        print("股东户数：已使用唯一入口")
        return
    with canonical.open(encoding="utf-8-sig", newline="") as stream:
        original = list(csv.DictReader(stream))
    with duplicate.open(encoding="utf-8-sig", newline="") as stream:
        copied = list(csv.DictReader(stream))
    projected = [{key: row[key] for key in original[0]} for row in copied]
    redundant_match = all(
        row["代码"] == row["股票代码"] and row["名称"] == row["公司"] for row in copied
    )
    if original != projected or not redundant_match:
        raise ValueError("股东户数副本存在独有数据，拒绝删除")
    print(f"股东户数：{len(original)} 行逐字段一致，可删除冗余副本")
    if apply:
        duplicate.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    normalize_price(args.apply)
    consolidate_holders(args.apply)
    exclude_reports(args.apply)
    exclude_segments(args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
