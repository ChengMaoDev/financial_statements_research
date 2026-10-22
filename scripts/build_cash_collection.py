"""计算收现比、海外收入占比和税费薪酬占营收。

现金流和收入来自报表，海外收入来自主营构成。收现比受增值税、票据和预收
影响，不能视为收入真实性结论。已移除按内销13%/外销0%统一还原的估算列，
因为海外销售不等于从中国出口，集团实际税率和结算结构无法据此确认。

用法：
    uv run python3 scripts/build_cash_collection.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "财务数据"
OUT = DATA / "收现质量.csv"

COMPANIES = ["美的集团", "海尔智家", "格力电器"]
YEARS = [str(y) for y in range(2019, 2026)]


def main() -> int:
    revenue: dict[tuple[str, str], float] = {}
    collection: dict[tuple[str, str], float] = {}
    tax: dict[tuple[str, str], float] = {}
    employees_cost: dict[tuple[str, str], float] = {}

    with (DATA / "利润表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if not row["报告期"].endswith("1231"):
                continue
            year = row["报告期"][:4]
            if year not in YEARS or row["科目"] != "营业收入":
                continue
            try:
                revenue[(row["公司"], year)] = float(row["数值"]) / 1e8
            except ValueError:
                continue

    with (DATA / "现金流量表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if not row["报告期"].endswith("1231"):
                continue
            year = row["报告期"][:4]
            if year not in YEARS:
                continue
            try:
                value = float(row["数值"]) / 1e8
            except ValueError:
                continue
            if row["科目"] == "销售商品、提供劳务收到的现金":
                collection[(row["公司"], year)] = value
            elif row["科目"] == "支付的各项税费":
                tax[(row["公司"], year)] = value
            elif row["科目"] == "支付给职工以及为职工支付的现金":
                employees_cost[(row["公司"], year)] = value

    # 海外收入仅作为收入结构列，不推算税率。
    overseas: dict[tuple[str, str], float] = {}
    with (DATA / "主营构成.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["分类类型"] != "按地区分类" or not row["报告日期"].endswith("12-31"):
                continue
            year = row["报告日期"][:4]
            name = row["主营构成"]
            # 分地区名称逐年变化，必须按关键词匹配而不是精确等值：
            # 美的：国外(2019—2023) → 海外(2024—2025)
            # 海尔：国外地区 / 国外 / 海外 / 其他国家/地区
            # 格力：外销 / 外销-主营业务
            if name.startswith("其中"):
                continue
            if row["公司"] == "海尔智家":
                is_overseas = name in ("海外", "国外", "国外地区", "其他国家/地区")
            else:
                is_overseas = name in ("海外", "国外", "外销", "外销-主营业务")
            if not is_overseas:
                continue
            try:
                overseas[(row["公司"], year)] = float(row["主营收入"]) / 1e8
            except ValueError:
                continue

    rows: list[list[str]] = []
    for company in COMPANIES:
        for year in YEARS:
            rev = revenue.get((company, year))
            cash = collection.get((company, year))
            if not rev or cash is None:
                continue

            ratio = cash / rev
            foreign = overseas.get((company, year))
            foreign_share = foreign / rev if foreign is not None else None

            # 现金流出侧：税费 + 职工薪酬占营收，反映「收到的钱有多少被刚性支出吃掉」
            outflow = (
                (tax.get((company, year), 0.0) + employees_cost.get((company, year), 0.0))
                / rev
                * 100
            )

            rows.append(
                [
                    company,
                    year,
                    f"{rev:.2f}",
                    f"{cash:.2f}",
                    f"{ratio:.4f}",
                    "" if foreign_share is None else f"{foreign_share * 100:.2f}",
                    f"{outflow:.2f}",
                    "计算值",
                ]
            )

    fields = [
        "公司",
        "年度",
        "营业收入(亿元)",
        "销售商品收到现金(亿元)",
        "收现比",
        "海外收入占比%",
        "税费+薪酬占营收%",
        "数据性质",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    print(f"{'公司':<8}{'年度':<6}{'收现比':>8}{'海外%':>8}{'税费薪酬%':>11}")
    print("-" * 52)
    for row in rows:
        print(f"{row[0]:<8}{row[1]:<6}{float(row[4]):>8.3f}{row[5]:>8}{float(row[6]):>11.2f}")

    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
