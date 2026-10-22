"""计算股东回报：分红率、股息率、累计分红、估值分位。

三个维度：
- 分红：每股派息、分红总额、分红率（分红/归母净利润）
- 股息率：每股派息 / 年末股价
- 估值分位：当前 PE/PB 在近五年序列中的百分位

用法：
    uv run python3 scripts/build_shareholder_return.py
"""

from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIN = ROOT / "财务数据"
MKT = ROOT / "市场数据" / "结构化"
OUT = FIN / "股东回报.csv"


def load(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def main() -> int:
    dividends = load(FIN / "分红送配.csv")
    income = load(FIN / "利润表.csv")
    price = load(MKT / "日线行情_不复权.csv")
    valuation = load(MKT / "估值序列.csv")
    if not dividends or not income:
        print("缺少分红或利润数据", file=sys.stderr)
        return 1

    # 归母净利润
    profit: dict[tuple[str, str], float] = {}
    for row in income:
        if row["科目"] == "归属于母公司所有者的净利润" and row["报告期"].endswith("1231"):
            profit[(row["公司"], row["报告期"][:4])] = float(row["数值"])

    # 总股本（用利润表的基本每股收益反推不准，改用分红说明与派息比例）
    # 派息比例字段单位是「元/10股」，需总股本才能算总额，此处只保留每股口径
    # 按财年归集：中期分红 + 年度分红都属于同一财年的股东回报
    by_year: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in dividends:
        report = row.get("报告时间", "")
        year_match = re.match(r"(\d{4})", report)
        if not year_match:
            continue
        # 「2025年报」「2025半年报」「2025三季报」都归入 2025 财年
        by_year[(row["公司"], year_match.group(1))].append(row)

    # 年末收盘价（用不复权价，后复权价会因除权而失真，无法算股息率）
    year_close: dict[tuple[str, str], tuple[str, float]] = {}
    for row in price:
        date = row.get("日期", "")
        # 年末可能是休市日，取完整年度内最后一个实际交易日。
        if date[:4] >= "2026":
            continue
        try:
            key = (row["公司"], date[:4])
            if key not in year_close or date > year_close[key][0]:
                year_close[key] = (date, float(row["收盘"]))
        except (ValueError, KeyError):
            continue

    rows: list[list[str]] = []
    for (company, year), items in sorted(by_year.items()):
        cash = 0.0
        detail = []
        for item in items:
            ratio = item.get("派息比例", "")
            if not ratio:
                continue
            try:
                per_ten = float(ratio)
            except ValueError:
                continue
            cash += per_ten / 10
            detail.append(item.get("实施方案分红说明", ""))
        if cash == 0:
            continue
        net = profit.get((company, year))
        close_point = year_close.get((company, year))
        close = close_point[1] if close_point else None
        rows.append(
            [
                company,
                year,
                f"{cash:.4f}",
                "; ".join(detail),
                f"{net / 1e8:.2f}" if net else "",
                f"{close:.2f}" if close else "",
                f"{cash / close * 100:.2f}" if close and close > 0 else "",
                "年度+中期合计",
                close_point[0] if close_point else "",
            ]
        )

    header = [
        "公司",
        "年度",
        "每股派息合计(元)",
        "分红方案",
        "归母净利润(亿)",
        "年末收盘价(元)",
        "股息率%(近似)",
        "分红类型",
        "年末价格日期",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)

    print(f"{'公司':<8}{'年度':<6}{'每股派息':>10}{'方案':<24}{'股息率%':>9}")
    print("-" * 62)
    for row in rows:
        if row[1] >= "2019":
            print(f"{row[0]:<8}{row[1]:<6}{row[2]:>10}{row[3][:26]:<28}{row[6]:>9}")
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")

    # 估值分位
    print("\n【估值分位】当前值在近五年序列中的位置")
    series: dict[tuple[str, str], list[tuple[str, float]]] = defaultdict(list)
    for row in valuation:
        try:
            series[(row["公司"], row["指标"])].append((row["date"], float(row["value"])))
        except (ValueError, KeyError):
            continue

    print(f"{'公司':<8}{'指标':<14}{'当前':>8}{'五年最低':>10}{'五年最高':>10}{'分位':>8}")
    print("-" * 60)
    for (company, indicator), points in sorted(series.items()):
        points.sort()
        values = [value for _, value in points]
        current = values[-1]
        rank = sum(1 for value in values if value <= current) / len(values) * 100
        print(
            f"{company:<8}{indicator:<14}{current:>8.2f}"
            f"{min(values):>10.2f}{max(values):>10.2f}{rank:>7.1f}%"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
