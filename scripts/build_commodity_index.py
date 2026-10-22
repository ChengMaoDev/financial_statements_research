"""原材料价格年度指数与成本传导分析。

把日频期货价格聚合成年度均价，计算同比变化，
再与三家公司的毛利率、营业成本率对照，观察成本传导的时滞与强度。

用法：
    uv run python3 scripts/build_commodity_index.py
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MKT = ROOT / "市场数据" / "结构化"
FIN = ROOT / "财务数据"
OUT = FIN / "原材料价格指数.csv"

COMPANIES = ["美的集团", "海尔智家", "格力电器"]
YEARS = ["2023", "2024", "2025", "2026"]


def load(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def main() -> int:
    prices = load(MKT / "原材料价格.csv")
    if not prices:
        print("缺少原材料价格数据", file=sys.stderr)
        return 1

    # 年度均价
    annual: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in prices:
        date = row["日期"]
        if len(date) < 4:
            continue
        try:
            value = float(row["收盘"])
        except (ValueError, KeyError):
            continue
        annual[(row["品种"], date[:4])].append(value)

    # 输出长表
    rows: list[list[str]] = []
    for (name, year), values in sorted(annual.items()):
        if year not in YEARS:
            continue
        mean = sum(values) / len(values)
        rows.append(
            [
                name,
                year,
                f"{mean:.2f}",
                f"{min(values):.2f}",
                f"{max(values):.2f}",
                str(len(values)),
            ]
        )

    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["品种", "年度", "年度均价", "年内最低", "年内最高", "交易日数"])
        writer.writerows(rows)

    # 控制台：年度均价与同比
    print("【原材料年度均价】")
    names = sorted({r[0] for r in rows})
    header = f"{'品种':<12}" + "".join(f"{y:>12}" for y in YEARS)
    print(header)
    print("-" * len(header))
    for name in names:
        line = f"{name:<12}"
        for year in YEARS:
            hit = [r for r in rows if r[0] == name and r[1] == year]
            line += f"{float(hit[0][2]):>12,.0f}" if hit else f"{'—':>12}"
        print(line)

    print("\n【同比变化 %】")
    print(header)
    print("-" * len(header))
    for name in names:
        line = f"{name:<12}"
        prev = None
        for year in YEARS:
            hit = [r for r in rows if r[0] == name and r[1] == year]
            if not hit:
                line += f"{'—':>12}"
                prev = None
                continue
            value = float(hit[0][2])
            line += f"{(value / prev - 1) * 100:>11.1f}%" if prev else f"{'基期':>12}"
            prev = value
        print(line)

    # 与毛利率对照
    print("\n【铜价同比 vs 毛利率变化】")
    copper = {r[1]: float(r[2]) for r in rows if r[0] == "沪铜"}
    cost = load(FIN / "成本结构与费用率.csv")
    print(f"{'公司':<8}{'年度':<6}{'铜价同比%':>11}{'毛利率%':>10}{'毛利率变化':>11}")
    print("-" * 48)
    for company in COMPANIES:
        previous = None
        for year in YEARS[:-1]:
            hit = [r for r in cost if r["公司"] == company and r["年度"] == year]
            if not hit:
                continue
            gross = 100 - float(hit[0]["营业成本(%)"])
            copper_yoy = (
                (copper[year] / copper[str(int(year) - 1)] - 1) * 100
                if str(int(year) - 1) in copper
                else None
            )
            change = f"{gross - previous:+.2f}" if previous is not None else "—"
            yoy_text = f"{copper_yoy:+.1f}" if copper_yoy is not None else "—"
            print(f"{company:<8}{year:<6}{yoy_text:>11}{gross:>10.2f}{change:>11}")
            previous = gross

    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    print("口径：年度均价为日频收盘价算术平均；毛利率来自 akshare 最新重述口径")
    return 0


if __name__ == "__main__":
    sys.exit(main())
