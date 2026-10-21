"""计算收现质量：销售商品收到的现金 / 营业收入，以及增值税还原后的含税收现比。

为什么重要：
营业收入是权责发生制，收现比是现金制，两者的差距能暴露三件事：
1. 应收账款的膨胀（卖了货没收到钱）
2. 票据结算的占比（收到的是银行/商业承兑汇票，不是现金）
3. 预收（合同负债）的变动（先收钱后发货，收现比会大于 1）

两个口径：
- **不含税收现比** = 销售商品、提供劳务收到的现金 / 营业收入
  这个比值受增值税影响，家电内销 13%、外销 0%（退税），
  所以内销占比高的公司天然更高，不能直接横向比较。
- **还原增值税后的收现比** = 收到的现金 /（营业收入 ×（1 + 加权税率））
  加权税率按内销 13%、外销 0% 估算，用分地区收入结构加权。
  这是估算值，不是披露值，仅用于消除税负差异后的横向观察。

还有一种干扰：票据。收到银行承兑汇票不产生现金流，但计入「销售商品收到的现金」
要等到贴现或到期。因此收现比长期低于 1 未必是坏事，可能是票据结算占比高。
三家都有大量应收票据，需要结合 `应收账款质量.csv` 与票据余额一起看。

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

# 内销增值税率：家电整机 13%。外销适用免抵退，销项不计，此处按 0% 计。
VAT_DOMESTIC = 0.13


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

    # 海外收入占比，用于加权增值税率
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
            foreign = overseas.get((company, year), 0.0)
            foreign_share = min(max(foreign / rev, 0.0), 1.0) if rev else 0.0
            weighted_vat = VAT_DOMESTIC * (1 - foreign_share)
            adjusted = cash / (rev * (1 + weighted_vat)) if weighted_vat else cash / rev

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
                    f"{foreign_share * 100:.2f}",
                    f"{weighted_vat * 100:.2f}",
                    f"{adjusted:.4f}",
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
        "加权增值税率%",
        "含税还原后收现比(估)",
        "税费+薪酬占营收%",
        "数据性质",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    print(f"{'公司':<8}{'年度':<6}{'收现比':>8}{'海外%':>8}{'含税还原':>10}{'税费薪酬%':>11}")
    print("-" * 52)
    for row in rows:
        print(
            f"{row[0]:<8}{row[1]:<6}{float(row[4]):>8.3f}{float(row[5]):>8.2f}"
            f"{float(row[7]):>10.3f}{float(row[8]):>11.2f}"
        )

    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    print("含税还原为估算值：按内销 13%、外销 0% 的分地区结构加权，仅用于消除税负差异后的横向观察")
    return 0


if __name__ == "__main__":
    sys.exit(main())
