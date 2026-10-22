"""构建利润质量表：非经常性损益占比与各项「非主营」利润来源。

为什么需要这张表：
净利润受政府补助、投资收益、资产处置、公允价值变动影响很大，
只看归母净利润会高估主业的盈利能力。

指标定义：
- 非经常性损益 = 净利润 - 扣非净利润（扣非净利润为年报披露值）
- 其他收益 = 政府补助主入口（部分公司含软件退税等经营性补助，
  新准则下与日常经营相关的政府补助计入此科目，因此「其他收益」
  不完全是「非经常性」，仅作为规模参考）
- 投资收益 = 联营企业损益、理财收益、处置收益等
- 减值损失 = 信用减值 + 资产减值（正数表示计提）

用法：
    uv run python3 scripts/build_earnings_quality.py
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIN = ROOT / "财务数据"
OUT = FIN / "利润质量.csv"

COMPANIES = ["美的集团", "海尔智家", "格力电器"]
YEARS = [str(y) for y in range(2023, 2027)]


def load_annual_stmt(name: str) -> dict[tuple[str, str], dict[str, float]]:
    out: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    path = FIN / f"{name}.csv"
    with path.open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            period = row.get("报告期", "")
            if len(period) != 8 or not period.endswith("1231"):
                continue
            try:
                out[(row["公司"], period[:4])][row["科目"]] = float(row["数值"])
            except (ValueError, KeyError):
                continue
    return out


def load_indicators() -> dict[tuple[str, str], dict[str, float]]:
    out: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    with (FIN / "主要财务指标.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            period = row.get("报告期", "")
            if len(period) != 8 or not period.endswith("1231"):
                continue
            try:
                out[(row["公司"], period[:4])][row["指标"]] = float(row["数值"])
            except (ValueError, KeyError):
                continue
    return out


def pct(value: float, base: float) -> str:
    return f"{value / base * 100:.2f}" if base else ""


def main() -> int:
    pl = load_annual_stmt("利润表")
    bs = load_annual_stmt("资产负债表")
    ind = load_indicators()

    rows: list[list[str]] = []
    for company in COMPANIES:
        for year in YEARS:
            profit = pl.get((company, year))
            if not profit:
                continue
            metrics = ind.get((company, year), {})
            total_profit = profit.get("利润总额", 0.0)
            net_profit = profit.get("净利润", 0.0)
            # 非经常性损益必须用**归母**口径：`扣非净利润` 是「归属于母公司股东的
            # 扣除非经常性损益后的净利润」，与归母净利润配对。若用总净利润相减，
            # 差额会把少数股东损益一并算进非经常性损益。
            # 实测 2025 年偏差：美的 32.53 vs 26.78 亿、海尔 15.59 vs 9.49 亿、
            # 格力 11.56 vs 12.97 亿（格力少数股东为负，偏差方向还相反）。
            parent_profit = profit.get("归属于母公司所有者的净利润", 0.0)
            deducted = metrics.get("扣非净利润")
            non_recurring = (parent_profit - deducted) if deducted is not None else None

            other_income = profit.get("其他收益", 0.0)
            investment = profit.get("投资收益", 0.0)
            impairment = abs(profit.get("信用减值损失", 0.0)) + abs(profit.get("资产减值损失", 0.0))
            non_op = profit.get("营业外收入", 0.0) - profit.get("营业外支出", 0.0)
            goodwill = bs.get((company, year), {}).get("商誉", 0.0)

            rows.append(
                [
                    company,
                    year,
                    f"{net_profit / 1e8:.2f}" if net_profit else "",
                    f"{deducted / 1e8:.2f}" if deducted is not None else "",
                    f"{non_recurring / 1e8:.2f}" if non_recurring is not None else "",
                    pct(non_recurring, parent_profit) if non_recurring is not None else "",
                    f"{other_income / 1e8:.2f}",
                    pct(other_income, total_profit),
                    f"{investment / 1e8:.2f}",
                    pct(investment, total_profit),
                    f"{impairment / 1e8:.2f}",
                    pct(impairment, total_profit),
                    f"{non_op / 1e8:.2f}",
                    pct(non_op, total_profit),
                    f"{goodwill / 1e8:.2f}" if goodwill else "0.00",
                    "计算值",
                ]
            )

    fields = [
        "公司",
        "年度",
        "净利润(亿元)",
        "扣非净利润(亿元)",
        "非经常性损益(亿元)",
        "非经常性损益占净利润%",
        "其他收益(亿元)",
        "其他收益占利润总额%",
        "投资收益(亿元)",
        "投资收益占利润总额%",
        "减值损失(亿元)",
        "减值损失占利润总额%",
        "营业外收支净额(亿元)",
        "营业外收支占利润总额%",
        "商誉(亿元)",
        "数据性质",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    header = f"{'公司':<8}{'年度':<6}{'扣非占比%':>10}{'其他收益%':>10}{'投资收益%':>10}{'减值%':>9}{'商誉':>9}"
    print(header)
    print("-" * len(header))
    for row in rows:
        if row[1] >= "2021":
            print(
                f"{row[0]:<8}{row[1]:<6}{row[5]:>10}{row[7]:>10}{row[9]:>10}"
                f"{row[11]:>9}{row[14]:>9}"
            )
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
