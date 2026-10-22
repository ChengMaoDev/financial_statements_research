"""从累计报表反推单季度毛利率与净利率。

A 股披露的是累计数：Q1、H1、9M、FY。单季度必须相减：
  Q1 = Q1 累计
  Q2 = H1 − Q1
  Q3 = 9M − H1
  Q4 = FY − 9M

这个口径能暴露 Q4 的异常：
家电行业通常在 Q4 集中兑现销售返利、计提减值，单季毛利率常显著低于前三季。
只看全年毛利率会完全看不到这个季节性。

用法：
    uv run python3 scripts/build_quarterly_margin.py
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIN = ROOT / "财务数据"
OUT = FIN / "分季度盈利能力.csv"

COMPANIES = ["美的集团", "海尔智家", "格力电器"]
YEARS = ["2024", "2025", "2026"]
QUARTERS = [
    ("Q1", "0331", "0"),
    ("Q2", "0630", "0331"),
    ("Q3", "0930", "0630"),
    ("Q4", "1231", "0930"),
]

ITEMS = ["营业收入", "营业成本", "归属于母公司所有者的净利润"]


def load() -> dict[tuple[str, str], dict[str, float]]:
    out: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    with (FIN / "利润表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row.get("科目") not in ITEMS:
                continue
            try:
                out[(row["公司"], row["报告期"])][row["科目"]] = float(row["数值"])
            except (ValueError, KeyError):
                continue
    return out


def main() -> int:
    data = load()
    with (FIN / "分季度经营.csv").open(encoding="utf-8-sig") as stream:
        disclosed = {
            (row["公司"], row["年度"], row["季度"], row["指标"]): float(row["数值"])
            for row in csv.DictReader(stream)
        }
    rows: list[list[str]] = []
    for company in COMPANIES:
        for year in YEARS:
            for label, period, previous in QUARTERS:
                current = data.get((company, f"{year}{period}"))
                if not current:
                    continue
                base = data.get((company, f"{year}{previous}"), {}) if previous != "0" else {}
                revenue = current.get("营业收入", 0.0) - base.get("营业收入", 0.0)
                cost = current.get("营业成本", 0.0) - base.get("营业成本", 0.0)
                profit = current.get("归属于母公司所有者的净利润", 0.0) - base.get(
                    "归属于母公司所有者的净利润", 0.0
                )
                if revenue <= 0:
                    continue
                restated = label == "Q4" and company == "海尔智家" and year == "2024"
                if restated:
                    revenue = disclosed[(company, year, label, "营业收入")]
                    profit = disclosed[(company, year, label, "归母净利润")]
                rows.append(
                    [
                        company,
                        year,
                        label,
                        f"{revenue / 1e8:.2f}",
                        "" if restated else f"{cost / 1e8:.2f}",
                        "" if restated else f"{(revenue - cost) / revenue * 100:.2f}",
                        f"{profit / 1e8:.2f}",
                        f"{profit / revenue * 100:.2f}",
                        "披露值/计算值" if restated else "计算值",
                        "收入和归母采用年报分季披露；已删除版本混用的成本及毛利率"
                        if restated
                        else "利润表累计相减；未独立核验各累计报告的版本一致性",
                    ]
                )

    fields = [
        "公司",
        "年度",
        "季度",
        "单季营业收入(亿)",
        "单季营业成本(亿)",
        "单季毛利率%",
        "单季归母净利润(亿)",
        "单季净利率%",
        "数据性质",
        "口径说明",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    header = f"{'公司':<8}{'年度':<6}{'季度':<5}{'营收(亿)':>10}{'毛利率%':>9}{'净利率%':>9}"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row[0]:<8}{row[1]:<6}{row[2]:<5}{float(row[3]):>10.1f}"
            f"{row[5] or '不可得':>9}{float(row[7]):>9.1f}"
        )
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
