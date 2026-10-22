"""生成 2026 年半年报三家横向对比表。

与 `build_comparison.py` 的分工：
- `build_comparison.py` 输出 2025 年**年度**对比，含薪酬、返利、集中度等
  只有年报才披露的指标。
- 本脚本输出 2026 年**半年度**对比，只用利润表、资产负债表、现金流量表、
  主营构成这些中期即披露的口径，保证每一项都能逐位对平。

半年度口径的三个注意点（脚本已处理）：
1. 半年报的利润表是**当期累计**（1—6 月），不是单季，不需要再加总。
2. ROE、周转率等年化指标不能直接乘 2，本表只给半年实际值，不年化。
3. 经营现金流有季节性（空调旺季备货在前），半年值不能外推全年。

用法：
    uv run python3 scripts/build_comparison_h1.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "财务数据"
OUT = DATA / "三家对比_2026H1.csv"

COMPANIES = ["美的集团", "海尔智家", "格力电器"]
PERIOD = "20260630"
PREV = "20250630"

# 科目 → 取值来源
INCOME_ITEMS = {
    "营业收入": "营业收入",
    "营业成本": "营业成本",
    "营业总成本": "营业总成本",
    "销售费用": "销售费用",
    "管理费用": "管理费用",
    "研发费用": "研发费用",
    "财务费用": "财务费用",
    "营业利润": "营业利润",
    "利润总额": "利润总额",
    "净利润": "净利润",
    "归母净利润": "归属于母公司所有者的净利润",
}

# 分地区口径三家不同，必须按各自的关键词映射，不能用一个「海外」通吃：
# - 美的：国内 / 海外
# - 海尔：中国大陆地区 / 其他国家地区，另有「其中:」子项（需排除）
# - 格力：内销 / 外销 / 其他(补充)
REGION_RULES = {
    "美的集团": {"国内": ("国内",), "海外": ("海外",), "其他": ()},
    "海尔智家": {"国内": ("中国大陆地区",), "海外": ("其他国家/地区",), "其他": ()},
    "格力电器": {"国内": ("内销",), "海外": ("外销",), "其他": ("其他(补充)",)},
}


def load_statement(filename: str, periods: tuple[str, ...]) -> dict[tuple[str, str, str], float]:
    path = DATA / filename
    result: dict[tuple[str, str, str], float] = {}
    if not path.exists():
        return result
    with path.open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["报告期"] not in periods:
                continue
            try:
                result[(row["公司"], row["报告期"], row["科目"])] = float(row["数值"])
            except ValueError:
                continue
    return result


def load_indicators(period: str) -> dict[tuple[str, str], float]:
    path = DATA / "主要财务指标.csv"
    result: dict[tuple[str, str], float] = {}
    if not path.exists():
        return result
    with path.open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["报告期"] != period:
                continue
            try:
                result[(row["公司"], row["指标"])] = float(row["数值"])
            except ValueError:
                continue
    return result


def main() -> int:
    income = load_statement("利润表.csv", (PERIOD, PREV))
    balance = load_statement("资产负债表.csv", (PERIOD, PREV))
    cashflow = load_statement("现金流量表.csv", (PERIOD, PREV))
    indicators = load_indicators(PERIOD)

    if not income:
        print("缺少 2026H1 利润表数据", file=sys.stderr)
        return 1

    rows: list[list[str]] = []
    header = ["指标", "单位", *COMPANIES]

    def add(label: str, unit: str, values: dict[str, str]) -> None:
        rows.append([label, unit] + [values.get(c, "") for c in COMPANIES])

    # ---- 利润表绝对额 ----
    for label, account in INCOME_ITEMS.items():
        add(
            label,
            "亿元",
            {
                c: f"{income[(c, PERIOD, account)] / 1e8:,.2f}"
                for c in COMPANIES
                if (c, PERIOD, account) in income
            },
        )

    # ---- 同比 ----
    add(
        "营业收入同比",
        "%",
        {
            c: f"{(income[(c, PERIOD, '营业收入')] / income[(c, PREV, '营业收入')] - 1) * 100:+.2f}"
            for c in COMPANIES
            if (c, PERIOD, "营业收入") in income and (c, PREV, "营业收入") in income
        },
    )
    add(
        "归母净利润同比",
        "%",
        {
            c: (
                f"{(income[(c, PERIOD, '归属于母公司所有者的净利润')] / income[(c, PREV, '归属于母公司所有者的净利润')] - 1) * 100:+.2f}"
            )
            for c in COMPANIES
            if (c, PERIOD, "归属于母公司所有者的净利润") in income
            and (c, PREV, "归属于母公司所有者的净利润") in income
        },
    )

    # ---- 比率 ----
    for label, key in (
        ("毛利率", "毛利率"),
        ("销售净利率", "销售净利率"),
        ("ROE(半年,未年化)", "净资产收益率(ROE)"),
    ):
        add(
            label,
            "%",
            {c: f"{indicators[(c, key)]:.2f}" for c in COMPANIES if (c, key) in indicators},
        )
    add(
        "资产负债率",
        "%",
        {
            c: f"{indicators[(c, '资产负债率')]:.2f}"
            for c in COMPANIES
            if (c, "资产负债率") in indicators
        },
    )

    # 费用率（用利润表，不依赖指标库）
    for label, key in (
        ("销售费用率", "销售费用"),
        ("管理费用率", "管理费用"),
        ("研发费用率", "研发费用"),
    ):
        add(
            label,
            "%",
            {
                c: f"{income[(c, PERIOD, key)] / income[(c, PERIOD, '营业收入')] * 100:.2f}"
                for c in COMPANIES
                if (c, PERIOD, key) in income and (c, PERIOD, "营业收入") in income
            },
        )

    # 经营利润率
    add(
        "营业利润率",
        "%",
        {
            c: f"{income[(c, PERIOD, '营业利润')] / income[(c, PERIOD, '营业收入')] * 100:.2f}"
            for c in COMPANIES
            if (c, PERIOD, "营业利润") in income
        },
    )

    # ---- 资产负债 ----
    for label in (
        "资产总计",
        "负债合计",
        "归属于母公司股东权益合计",
        "货币资金",
        "应收账款",
        "存货",
    ):
        add(
            label,
            "亿元",
            {
                c: f"{balance[(c, PERIOD, label)] / 1e8:,.2f}"
                for c in COMPANIES
                if (c, PERIOD, label) in balance
            },
        )

    add(
        "应收+存货占总资产",
        "%",
        {
            c: (
                f"{(balance[(c, PERIOD, '应收账款')] + balance[(c, PERIOD, '存货')]) / balance[(c, PERIOD, '资产总计')] * 100:.2f}"
            )
            for c in COMPANIES
            if (c, PERIOD, "应收账款") in balance
            and (c, PERIOD, "存货") in balance
            and (c, PERIOD, "资产总计") in balance
        },
    )

    # ---- 现金流 ----
    for label in ("经营活动产生的现金流量净额", "购建固定资产、无形资产和其他长期资产所支付的现金"):
        add(
            label,
            "亿元",
            {
                c: f"{cashflow[(c, PERIOD, label)] / 1e8:,.2f}"
                for c in COMPANIES
                if (c, PERIOD, label) in cashflow
            },
        )

    add(
        "净现比(经营现金流/归母净利润)",
        "倍",
        {
            c: (
                f"{cashflow[(c, PERIOD, '经营活动产生的现金流量净额')] / income[(c, PERIOD, '归属于母公司所有者的净利润')]:.2f}"
            )
            for c in COMPANIES
            if (c, PERIOD, "经营活动产生的现金流量净额") in cashflow
            and (c, PERIOD, "归属于母公司所有者的净利润") in income
        },
    )

    # ---- 主营构成（分地区）----
    # 海尔的分地区表含「其中:」子项，直接求和会虚增，必须按精确名称匹配。
    region: dict[tuple[str, str], float] = {}
    region_path = DATA / "主营构成.csv"
    if region_path.exists():
        with region_path.open(encoding="utf-8-sig") as stream:
            for row in csv.DictReader(stream):
                if row["报告日期"] != "2026-06-30" or row["分类类型"] != "按地区分类":
                    continue
                rules = REGION_RULES.get(row["公司"])
                if not rules:
                    continue
                name = row["主营构成"]
                if name.startswith("其中"):
                    continue
                try:
                    value = float(row["主营收入"])
                except ValueError:
                    continue
                for key, candidates in rules.items():
                    if name in candidates:
                        region[(row["公司"], key)] = value

    add(
        "海外收入",
        "亿元",
        {c: f"{region[(c, '海外')] / 1e8:,.2f}" for c in COMPANIES if (c, "海外") in region},
    )
    add(
        "海外收入占比",
        "%",
        {
            c: (f"{region[(c, '海外')] / income[(c, PERIOD, '营业收入')] * 100:.2f}")
            for c in COMPANIES
            if (c, "海外") in region
        },
    )

    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)

    print(f"{'指标':<26}{'单位':<6}" + "".join(f"{c:>14}" for c in COMPANIES))
    print("-" * 76)
    for row in rows:
        print(f"{row[0]:<26}{row[1]:<6}" + "".join(f"{v:>14}" for v in row[2:]))

    print(f"\n写入 {OUT.relative_to(ROOT)}：{len(rows)} 项")
    print("口径：2026 年半年报（1—6 月累计），未年化；境外收入按主营构成「按地区分类」")
    return 0


if __name__ == "__main__":
    sys.exit(main())
