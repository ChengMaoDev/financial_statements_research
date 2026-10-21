"""长期股权投资回报：投出去的钱赚了多少。

为什么重要：
三家的长期股权投资规模差 5 倍，回报率差 20 倍：

| 公司 | 2025 长投账面 | 权益法收益 | 回报率 | 占净利润 |
|---|---|---|---|---|
| 美的 | 47.75 亿 | 5.89 亿 | 12.33% | 1.32% |
| 海尔 | 217.57 亿 | 13.28 亿 | 6.10% | 6.59% |
| 格力 | 42.35 亿 | 0.36 亿 | 0.86% | 0.12% |

海尔的 217.57 亿里，最大两笔是 **Controladora Mabe（墨西哥，54.09 亿）**
和 **青岛银行（40.28 亿）**，属于「战略持股 + 金融股权」的混合体，
不是经营性投资，所以回报率低不代表投资能力差。

格力的长投从 2021 年 103.37 亿降到 2025 年 42.35 亿，同期权益法收益从 0.52 亿
降到 0.36 亿 —— 处置了资产但没改善回报率。

四个陷阱：

1. **「回报率」= 权益法收益 / 期末长投**，分母用期末数不是平均数；长投当年大幅
   增减时（格力 2022 年从 103.37 亿降到 58.92 亿）会失真。本表同时给出期初期末
   平均口径。
2. **长投里可能有非权益法部分**（如对子公司的成本法长投在母公司报表），
   本表用的是**合并报表长投**，全部为权益法或成本法计量的对外投资。
3. **「取得投资收益收到的现金 / 权益法收益」不能当现金回收率**。这个现金流科目
   同时含理财、票据、股利，美的 2025 年 92.01 亿对应权益法 5.89 亿（1563%），
   显然不是权益法回收。本表不采用这个比值。
4. **亏损的联营企业不确认损失**（超额亏损），格力有 4 家联营/合营企业累计未确认
   损失 1,157 万至 857 万，金额小但说明有「表外亏损」。

用法：
    uv run python3 scripts/build_equity_investment.py
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIN = ROOT / "财务数据"
OUT = FIN / "长期股权投资回报.csv"

YEARS = ("2019", "2020", "2021", "2022", "2023", "2024", "2025")
COMPANIES = ("美的集团", "海尔智家", "格力电器")


def load(name: str) -> list[dict[str, str]]:
    with (FIN / name).open(encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def numeric(row: dict[str, str]) -> float | None:
    try:
        return float(row["数值"])
    except (KeyError, ValueError):
        return None


def main() -> int:
    balance: dict[tuple[str, str], float] = {}
    for row in load("资产负债表.csv"):
        if row["科目"] != "长期股权投资":
            continue
        if not row["报告期"].endswith("1231") or row["报告期"][:4] not in YEARS:
            continue
        value = numeric(row)
        if value is not None:
            balance[(row["公司"], row["报告期"][:4])] = value / 1e8

    equity_income: dict[tuple[str, str], float] = {}
    net_profit: dict[tuple[str, str], float] = {}
    for row in load("利润表.csv"):
        if not row["报告期"].endswith("1231") or row["报告期"][:4] not in YEARS:
            continue
        if row["科目"] not in ("对联营企业和合营企业的投资收益", "归属于母公司所有者的净利润"):
            continue
        value = numeric(row)
        if value is None:
            continue
        key = (row["公司"], row["报告期"][:4])
        if row["科目"] == "对联营企业和合营企业的投资收益":
            equity_income[key] = value / 1e8
        else:
            net_profit[key] = value / 1e8

    rows: list[list[str]] = []
    for company in COMPANIES:
        previous: float | None = None
        for year in YEARS:
            invested = balance.get((company, year))
            income = equity_income.get((company, year))
            if invested is None:
                continue

            if income is not None:
                rows.append(
                    [
                        company,
                        year,
                        "权益法投资收益",
                        f"{income:.2f}",
                        "",
                        "利润表「对联营企业和合营企业的投资收益」",
                        "披露值",
                    ]
                )
            rows.append(
                [
                    company,
                    year,
                    "长期股权投资(期末)",
                    f"{invested:.2f}",
                    "",
                    "合并资产负债表",
                    "披露值",
                ]
            )
            if income is not None and invested:
                rows.append(
                    [
                        company,
                        year,
                        "回报率(期末口径)",
                        f"{income / invested * 100:.2f}",
                        f"{income / invested * 100:.2f}",
                        "权益法收益 / 期末长投",
                        "计算值",
                    ]
                )
            if income is not None and previous is not None:
                average = (previous + invested) / 2
                if average > 0:
                    rows.append(
                        [
                            company,
                            year,
                            "回报率(平均口径)",
                            f"{income / average * 100:.2f}",
                            f"{income / average * 100:.2f}",
                            "权益法收益 / 期初期末平均长投",
                            "计算值",
                        ]
                    )
            if income is not None and net_profit.get((company, year)):
                rows.append(
                    [
                        company,
                        year,
                        "权益法收益占归母净利润",
                        f"{income / net_profit[(company, year)] * 100:.2f}",
                        f"{income / net_profit[(company, year)] * 100:.2f}",
                        "识别利润对参股企业的依赖度",
                        "计算值",
                    ]
                )
            previous = invested

    fields = ["公司", "年度", "项目", "数值", "百分比", "口径说明", "数据性质"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    table = defaultdict(dict)
    for row in rows:
        table[(row[0], row[1])][row[2]] = row[3]

    print(f"{'公司':<8}{'年度':<6}{'长投(亿)':>10}{'权益法(亿)':>11}{'回报率':>8}{'占归母':>8}")
    print("-" * 52)
    for company in COMPANIES:
        for year in YEARS:
            data = table.get((company, year))
            if not data:
                continue
            print(
                f"{company:<8}{year:<6}{data['长期股权投资(期末)']:>10}"
                f"{data.get('权益法投资收益', '—'):>11}"
                f"{data.get('回报率(期末口径)', '—'):>8}"
                f"{data.get('权益法收益占归母净利润', '—'):>8}"
            )
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
