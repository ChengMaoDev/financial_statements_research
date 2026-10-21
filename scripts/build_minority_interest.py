"""少数股东损益与少数股东权益：谁的利润、谁的净资产。

为什么重要：
三家的并表范围里「别人的股份」占比差异很大，直接影响归母口径的可比性：

| 公司 | 2025 少数股东损益 | 占净利润 | 少数股东权益 | 占所有者权益 |
|---|---|---|---|---|
| 美的 | +5.75 亿 | 1.29% | 132.03 亿 | 5.58% |
| 海尔 | +6.10 亿 | 3.02% | 72.79 亿 | 5.78% |
| 格力 | -1.40 亿 | -0.48% | 38.62 亿 | 2.58% |

格力是唯一出现过**大额负少数股东损益**的公司：2022 年 -14.95 亿、2023 年 -12.98 亿。
来源是格力钛（原银隆）持股 55.01%，亏损按比例由少数股东分担。这也是为什么格力
2022/2023 年归母净利润（230.11 / 277.19 亿）**高于**净利润（222.79 / 277.19 亿）。

三个陷阱：

1. **归母净利润 > 净利润不等于「经营好」**，只说明少数股东在亏钱。
   格力 2022 年归母比净利润高 7.32 亿，全部来自少数股东承担的亏损。
2. **少数股东权益为负时，ROE 分母失真**。格力 2022 年少数股东权益 51.17 亿、
   2023 年降到 38.52 亿，若子公司继续亏损会转负，届时少数股东损益与权益的关系
   不再线性，「少数股东 ROE」也就失去意义。
3. **少数股东权益的变动不等于少数股东损益**：还有增资、减资、分红、其他综合收益、
   同一控制下企业合并等。本表把「损益」与「权益变动」分开列，差额单列一行。

用法：
    uv run python3 scripts/build_minority_interest.py
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIN = ROOT / "财务数据"
OUT = FIN / "少数股东损益与权益.csv"

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
    income: dict[tuple[str, str, str], float] = {}
    for row in load("利润表.csv"):
        if not row["报告期"].endswith("1231") or row["报告期"][:4] not in YEARS:
            continue
        if row["科目"] not in ("净利润", "少数股东损益", "归属于母公司所有者的净利润"):
            continue
        value = numeric(row)
        if value is None:
            continue
        income[(row["公司"], row["报告期"][:4], row["科目"])] = value / 1e8

    balance: dict[tuple[str, str, str], float] = {}
    for row in load("资产负债表.csv"):
        if not row["报告期"].endswith("1231") or row["报告期"][:4] not in YEARS:
            continue
        if row["科目"] not in (
            "少数股东权益",
            "归属于母公司股东权益合计",
            "所有者权益(或股东权益)合计",
        ):
            continue
        value = numeric(row)
        if value is None:
            continue
        balance[(row["公司"], row["报告期"][:4], row["科目"])] = value / 1e8

    rows: list[list[str]] = []
    previous_equity: dict[str, float] = {}
    for company in COMPANIES:
        for year in YEARS:
            net = income.get((company, year, "净利润"))
            minority_pl = income.get((company, year, "少数股东损益"))
            parent_pl = income.get((company, year, "归属于母公司所有者的净利润"))
            if net is None or minority_pl is None:
                continue
            equity = balance.get((company, year, "少数股东权益"))
            total_equity = balance.get((company, year, "所有者权益(或股东权益)合计"))

            rows.append(
                [
                    company,
                    year,
                    "少数股东损益",
                    f"{minority_pl:.2f}",
                    f"{minority_pl / net * 100:.2f}" if net else "",
                    "利润表，正=少数股东分享利润",
                    "披露值",
                ]
            )
            rows.append(
                [
                    company,
                    year,
                    "少数股东权益(期末)",
                    f"{equity:.2f}" if equity is not None else "",
                    f"{equity / total_equity * 100:.2f}"
                    if equity is not None and total_equity
                    else "",
                    "资产负债表，占所有者权益合计",
                    "披露值",
                ]
            )
            rows.append(
                [
                    company,
                    year,
                    "少数股东权益(期初)",
                    f"{previous_equity[company]:.2f}" if company in previous_equity else "",
                    "",
                    "上年期末数",
                    "披露值",
                ]
            )
            if equity is not None and company in previous_equity:
                change = equity - previous_equity[company]
                rows.append(
                    [
                        company,
                        year,
                        "权益变动(未解释部分)",
                        f"{change - minority_pl:.2f}",
                        "",
                        "期末 − 期初 − 少数股东损益；含增资/分红/其他综合收益",
                        "计算值",
                    ]
                )
            if equity is not None:
                previous_equity[company] = equity

            rows.append(
                [
                    company,
                    year,
                    "少数股东ROE(期末权益口径)",
                    f"{minority_pl / equity * 100:.2f}" if equity and equity > 0 else "",
                    "",
                    "少数股东损益 / 期末少数股东权益；权益为负时不计算",
                    "计算值",
                ]
            )
            rows.append(
                [
                    company,
                    year,
                    "归母净利润 − 净利润",
                    f"{(parent_pl or 0.0) - net:.2f}",
                    "",
                    "正=少数股东承担亏损，归母高于合并净利润",
                    "计算值",
                ]
            )

    fields = ["公司", "年度", "项目", "金额(亿元)", "占比%", "口径说明", "数据性质"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    print(
        f"{'公司':<8}{'年度':<6}{'少数股东损益':>12}{'占净利润':>9}{'少数股东权益':>12}{'占权益':>8}{'归母-净利':>10}"
    )
    print("-" * 68)
    table: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for row in rows:
        table[(row[0], row[1])][row[2]] = row[3]
        if row[2] in ("少数股东损益", "少数股东权益(期末)", "归母净利润 − 净利润"):
            table[(row[0], row[1])][f"{row[2]}#占比"] = row[4]
    for company in COMPANIES:
        for year in YEARS:
            data = table.get((company, year))
            if not data:
                continue
            print(
                f"{company:<8}{year:<6}{data['少数股东损益']:>12}"
                f"{data.get('少数股东损益#占比', ''):>8}%"
                f"{data['少数股东权益(期末)']:>12}"
                f"{data.get('少数股东权益(期末)#占比', ''):>7}%"
                f"{data['归母净利润 − 净利润']:>10}"
            )
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
