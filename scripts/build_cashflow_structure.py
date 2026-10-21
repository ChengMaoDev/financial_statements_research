"""构建三大现金流结构与自由现金流。

为什么不能只看经营现金流：
一家公司经营现金流很好，但投资现金流大量流出（并购、扩产），
或筹资现金流大量流出（分红、还债），最终现金可能在减少。
必须把三张现金流放在一起看。

指标定义：
- 自由现金流 = 经营活动净额 − 购建固定资产等支付的现金（不含并购）
- 资本开支强度 = capex / 营业收入
- 分红与利息支出 / 经营现金流：衡量分红是否由经营现金流覆盖
- 现金净增加额 = 经营 + 投资 + 筹资 + 汇率影响

用法：
    uv run python3 scripts/build_cashflow_structure.py
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIN = ROOT / "财务数据"
OUT = FIN / "现金流结构.csv"

COMPANIES = ["美的集团", "海尔智家", "格力电器"]
YEARS = [str(y) for y in range(2019, 2027)]


def load() -> dict[tuple[str, str], dict[str, float]]:
    out: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    with (FIN / "现金流量表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            period = row.get("报告期", "")
            if len(period) != 8 or not period.endswith("1231"):
                continue
            try:
                out[(row["公司"], period[:4])][row["科目"]] = float(row["数值"])
            except (ValueError, KeyError):
                continue
    return out


def load_revenue() -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    with (FIN / "利润表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row.get("科目") != "营业收入":
                continue
            period = row.get("报告期", "")
            if len(period) != 8 or not period.endswith("1231"):
                continue
            try:
                out[(row["公司"], period[:4])] = float(row["数值"])
            except ValueError:
                continue
    return out


def main() -> int:
    cf = load()
    revenue = load_revenue()

    rows: list[list[str]] = []
    for company in COMPANIES:
        for year in YEARS:
            data = cf.get((company, year))
            if not data:
                continue
            ocf = data.get("经营活动产生的现金流量净额", 0.0)
            capex = data.get("购建固定资产、无形资产和其他长期资产所支付的现金", 0.0)
            icf = data.get("投资活动产生的现金流量净额", 0.0)
            fcf_fin = data.get("筹资活动产生的现金流量净额", 0.0)
            dividends = data.get("分配股利、利润或偿付利息所支付的现金", 0.0)
            borrow = data.get("取得借款收到的现金", 0.0)
            repay = data.get("偿还债务支付的现金", 0.0)
            acquisition = data.get("取得子公司及其他营业单位支付的现金净额", 0.0)
            net_change = data.get("现金及现金等价物净增加额", 0.0)
            fcf = ocf - capex
            rev = revenue.get((company, year), 0.0)

            rows.append(
                [
                    company,
                    year,
                    f"{ocf / 1e8:.2f}",
                    f"{capex / 1e8:.2f}",
                    f"{fcf / 1e8:.2f}",
                    f"{icf / 1e8:.2f}",
                    f"{fcf_fin / 1e8:.2f}",
                    f"{dividends / 1e8:.2f}",
                    f"{borrow / 1e8:.2f}",
                    f"{repay / 1e8:.2f}",
                    f"{acquisition / 1e8:.2f}",
                    f"{net_change / 1e8:.2f}",
                    f"{capex / rev * 100:.2f}" if rev else "",
                    f"{dividends / ocf * 100:.2f}" if ocf > 0 else "",
                    "计算值",
                ]
            )

    fields = [
        "公司",
        "年度",
        "经营现金流净额(亿元)",
        "资本开支(亿元)",
        "自由现金流(亿元)",
        "投资活动净额(亿元)",
        "筹资活动净额(亿元)",
        "分红付息支出(亿元)",
        "取得借款(亿元)",
        "偿还债务(亿元)",
        "并购支出(亿元)",
        "现金净增加额(亿元)",
        "资本开支强度%",
        "分红付息占经营现金流%",
        "数据性质",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    header = (
        f"{'公司':<8}{'年度':<6}{'经营':>9}{'资本开支':>9}{'自由现金流':>11}"
        f"{'分红付息':>9}{'现金净增':>9}"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        if row[1] >= "2022":
            print(
                f"{row[0]:<8}{row[1]:<6}{float(row[2]):>9.1f}{float(row[3]):>9.1f}"
                f"{float(row[4]):>11.1f}{float(row[7]):>9.1f}{float(row[11]):>9.1f}"
            )
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    print("自由现金流 = 经营现金流 − 资本开支，不含并购支出")
    return 0


if __name__ == "__main__":
    sys.exit(main())
