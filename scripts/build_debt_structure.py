"""构建有息负债结构、净现金与偿债能力指标。

口径说明（重要）：
- 「有息负债」只计需要付息的科目：短期借款、一年内到期的非流动负债、
  长期借款、应付债券、应付短期债券、租赁负债。
  应付票据、应付账款是经营性无息负债，不计入。
- 「一年内到期的非流动负债」并非全部有息（可能含一年内到期的预计负债等），
  作为口径上限处理，在输出中单列，便于剔除。
- 「净有息负债」= 有息负债 - 货币资金 - 交易性金融资产。
  负数表示净现金。

用法：
    uv run python3 scripts/build_debt_structure.py
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIN = ROOT / "财务数据"
OUT = FIN / "有息负债与偿债能力.csv"

COMPANIES = ["美的集团", "海尔智家", "格力电器"]
YEARS = [str(y) for y in range(2019, 2027)]

# 有息负债科目
DEBT_ITEMS = {
    "短期借款": "短期借款",
    "应付短期债券": "应付短期债券",
    "一年内到期的非流动负债": "一年内到期非流动负债",
    "长期借款": "长期借款",
    "应付债券": "应付债券",
    "租赁负债": "租赁负债",
}
# 单列但不计入有息负债总额的项
MEMO_ITEMS = {"一年内到期的非流动负债": "其中：一年内到期非流动负债"}

CASH_ITEMS = {"货币资金": "货币资金", "交易性金融资产": "交易性金融资产"}


def load_bs() -> dict[tuple[str, str], dict[str, float]]:
    """(公司, 报告期) → {科目: 数值}，只取年报（12-31）。"""
    out: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    with (FIN / "资产负债表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            period = row.get("报告期", "")
            if len(period) != 8 or not period.endswith("1231"):
                continue
            try:
                out[(row["公司"], period)][row["科目"]] = float(row["数值"])
            except (ValueError, KeyError):
                continue
    return out


def load_pl() -> dict[tuple[str, str], dict[str, float]]:
    out: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    with (FIN / "利润表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            period = row.get("报告期", "")
            if len(period) != 8 or not period.endswith("1231"):
                continue
            try:
                out[(row["公司"], period)][row["科目"]] = float(row["数值"])
            except (ValueError, KeyError):
                continue
    return out


def load_indicators() -> dict[tuple[str, str], dict[str, float]]:
    """归母净资产等指标，来自主要财务指标。"""
    out: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    path = FIN / "主要财务指标.csv"
    if not path.exists():
        return out
    with path.open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            period = row.get("报告期", "")
            if len(period) != 8 or not period.endswith("1231"):
                continue
            out[(row["公司"], period)][row.get("指标", "")] = row
    return out


def main() -> int:
    bs = load_bs()
    pl = load_pl()

    rows: list[list[str]] = []
    for company in COMPANIES:
        for year in YEARS:
            period = f"{year}1231"
            if (company, period) not in bs:
                continue
            data = bs[(company, period)]
            debt_total = 0.0
            item_values: dict[str, float] = {}
            for key, label in DEBT_ITEMS.items():
                value = data.get(key, 0.0)
                item_values[label] = value
                debt_total += value

            cash = sum(data.get(k, 0.0) for k in CASH_ITEMS)
            net_debt = debt_total - cash
            equity = data.get("归属于母公司股东权益合计")
            if equity is None:
                raise ValueError(f"{company} {period} 缺少归母净资产，不能计算净负债率")
            total_assets = data.get("资产总计", 0.0)

            profit = pl.get((company, period), {})
            ebit = profit.get("利润总额", 0.0) + profit.get("利息费用", 0.0)
            interest = profit.get("利息费用", 0.0)
            # 利息费用为负（利息收入大于支出）时，倍数无经济含义，留空
            coverage = f"{ebit / interest:.2f}" if interest > 0 else ""

            rows.append(
                [
                    company,
                    year,
                    f"{debt_total / 1e8:.2f}",
                    f"{item_values['短期借款'] / 1e8:.2f}",
                    f"{item_values['一年内到期非流动负债'] / 1e8:.2f}",
                    f"{item_values['长期借款'] / 1e8:.2f}",
                    f"{item_values['应付债券'] / 1e8:.2f}",
                    f"{item_values['租赁负债'] / 1e8:.2f}",
                    f"{cash / 1e8:.2f}",
                    f"{net_debt / 1e8:.2f}",
                    f"{(debt_total / total_assets * 100) if total_assets else 0:.2f}",
                    f"{(net_debt / equity * 100) if equity else 0:.2f}",
                    coverage,
                    "计算值",
                    "有息负债为科目加总上限，含一年内到期的预计负债等；净负债率分母为归母净资产",
                    f"{item_values['应付短期债券'] / 1e8:.2f}",
                ]
            )

    fields = [
        "公司",
        "年度",
        "有息负债合计(亿元)",
        "短期借款(亿元)",
        "一年内到期非流动负债(亿元)",
        "长期借款(亿元)",
        "应付债券(亿元)",
        "租赁负债(亿元)",
        "货币资金及交易性金融资产(亿元)",
        "净有息负债(亿元)",
        "有息负债率%",
        "净负债率%",
        "利息保障倍数",
        "数据性质",
        "口径说明",
        "应付短期债券(亿元)",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    header = f"{'公司':<8}{'年度':<6}{'有息负债':>10}{'货币资金':>10}{'净负债':>10}{'净负债率%':>10}{'保障倍数':>9}"
    print(header)
    print("-" * len(header))
    for row in rows:
        if row[1] >= "2022":
            print(
                f"{row[0]:<8}{row[1]:<6}{float(row[2]):>10.1f}{float(row[8]):>10.1f}"
                f"{float(row[9]):>10.1f}{float(row[11]):>10.1f}{row[12]:>9}"
            )
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    print(
        "口径：有息负债含短期借款/一年内到期非流动负债/长期借款/应付债券/租赁负债；负数净负债=净现金"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
