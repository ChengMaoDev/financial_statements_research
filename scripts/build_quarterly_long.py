"""单季营收与归母净利润（2017Q1—2026Q2）：披露优先、相减兜底。

为什么重要：
`分季度经营.csv` 只有 2023—2025（从仓库里的 3 份年报分季表抄来）。本表把区间
扩到 2017Q1，是判断经营节奏与季节性的底座。

单季数有两条来源，**必须分清**：

1. **年报「分季度主要财务数据」表**（披露值，最可靠，但只有 2023—2025 在仓库内）；
2. **累计数相减**（akshare 利润表，覆盖 2017 起，但有口径陷阱，见下）。

本表对「营业收入」与「归母净利润」两列采用**披露优先**：有年报分季表就用，
没有才用相减；`营业总收入` 与 `营业成本` 只能相减。每行都带
「营业收入口径」标明来源，并给出「披露−相减」差异列。

核心陷阱：akshare 的季度累计数混合口径
--------------------------------------------
akshare 的**期中报告（Q1/Q2/Q3）是当时披露值，年报（1231）是最新重述值**。
因此「年报累计 − 三季报累计」会把**整年的追溯重述增量全部塞进 Q4**。

实测海尔 2023 年（海尔 2024 年 12 月完成物流业务同一控制下并表，
按准则重述 2023 年前三季度，2023 全年营收由 2,614.28 亿重述为 2,742.05 亿）：

| 季度 | 相减单季 | 年报披露单季 | 差 |
|---|---|---|---|
| Q1 | 650.68 | 650.66 | 0.01 |
| Q2 | 665.61 | 665.60 | 0.01 |
| Q3 | 670.31 | 670.31 | 0.00 |
| **Q4** | **755.45** | **627.70** | **+127.75** |

Q1–Q3 只差四舍五入，Q4 凭空多出 **127.75 亿**——那是重述增量，不是经营。
**若不做披露优先，Q4 会被虚增 20.3%，并直接得出「海尔 2023Q4 大爆发」的错误结论。**

用法：
    uv run python3 scripts/build_quarterly_long.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIN = ROOT / "财务数据"
OUT = FIN / "单季度经营_2017起.csv"

COMPANIES = ("美的集团", "海尔智家", "格力电器")
YEARS = [str(y) for y in range(2017, 2026)] + ["2026"]
MASKS = ("0331", "0630", "0930", "1231")
PREV = {  # 本期累计要减去的上一期累计
    "0331": None,
    "0630": "0331",
    "0930": "0630",
    "1231": "0930",
}
# akshare 里 2026 半年报之后不存在，Q3/Q4 会被自动跳过

DISCLOSED = FIN / "分季度经营.csv"
RESTATE_FLAG = 5.0  # 亿元；披露与相减差超此值即提示疑似追溯重述


def load_income() -> dict[tuple[str, str, str], float]:
    out: dict[tuple[str, str, str], float] = {}
    with (FIN / "利润表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["数值"] in ("", "nan") or not row["报告期"].endswith(MASKS):
                continue
            try:
                out[(row["公司"], row["报告期"], row["科目"])] = float(row["数值"]) / 1e8
            except ValueError:
                continue
    return out


def load_disclosed() -> dict[tuple[str, str, str, str], float]:
    """(公司, 年度, 季度, 指标) → 年报披露单季值（亿元）。"""
    out: dict[tuple[str, str, str, str], float] = {}
    if not DISCLOSED.exists():
        return out
    with DISCLOSED.open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            try:
                out[(row["公司"], row["年度"], row["季度"], row["指标"])] = float(row["数值"]) / 1e8
            except (ValueError, KeyError):
                continue
    return out


def derived_single(
    income: dict[tuple[str, str, str], float],
    company: str,
    year: str,
    mask: str,
    subject: str,
) -> float | None:
    """由累计数相减得到单季数；缺任一累计数时返回 None（不填 0）。"""
    current = income.get((company, f"{year}{mask}", subject))
    if current is None:
        return None
    base = PREV[mask]
    if base is None:
        return current
    prior = income.get((company, f"{year}{base}", subject))
    return None if prior is None else current - prior


def main() -> int:
    income = load_income()
    disclosed = load_disclosed()

    rows: list[list[str]] = []
    problems: list[str] = []

    for company in COMPANIES:
        for year in YEARS:
            for quarter, mask in enumerate(MASKS, start=1):
                period = f"{year}{mask}"
                if not any(k[1] == period for k in income if k[0] == company):
                    continue
                qn = f"Q{quarter}"

                rev_derived = derived_single(income, company, year, mask, "营业收入")
                rev_disc = disclosed.get((company, year, qn, "营业收入"))
                profit_derived = derived_single(
                    income, company, year, mask, "归属于母公司所有者的净利润"
                )
                profit_disc = disclosed.get((company, year, qn, "归母净利润"))

                revenue = rev_disc if rev_disc is not None else rev_derived
                profit = profit_disc if profit_disc is not None else profit_derived
                gross = derived_single(income, company, year, mask, "营业总收入")
                cost = derived_single(income, company, year, mask, "营业成本")

                if revenue is None and gross is None:
                    continue

                # 口径标注：披露优先，相减兜底
                notes: list[str] = []
                notes.append(
                    "年报披露分季表"
                    if rev_disc is not None
                    else ("累计相减" if rev_derived is not None else "缺")
                )
                if profit_disc is not None:
                    notes.append("归母:披露")
                elif profit_derived is not None:
                    notes.append("归母:相减")

                # 重述检测：披露与相减差过大，说明该年被追溯重述
                for label, d, v in (
                    ("营业收入", rev_disc, rev_derived),
                    ("归母净利润", profit_disc, profit_derived),
                ):
                    if d is not None and v is not None and abs(d - v) > RESTATE_FLAG:
                        problems.append(
                            f"{company} {year}{qn} {label} 披露 {d:.2f} 与"
                            f" 相减 {v:.2f} 差 {v - d:+.2f} 亿（疑似追溯重述）"
                        )

                restated = (company, year, qn) in {
                    ("美的集团", "2023", "Q4"),
                    ("格力电器", "2023", "Q4"),
                    ("海尔智家", "2023", "Q4"),
                    ("海尔智家", "2024", "Q4"),
                }
                if restated:
                    notes.append("已删除混合披露版本的累计相减数；仅保留年报分季披露")
                margin = (
                    f"{(rev_derived - cost) / rev_derived * 100:.2f}"
                    if rev_derived and cost is not None and not restated
                    else ""
                )
                net = (
                    f"{profit / revenue * 100:.2f}"
                    if revenue and profit is not None and revenue
                    else ""
                )
                rows.append(
                    [
                        company,
                        year,
                        qn,
                        period,
                        "" if restated else num(gross),
                        num(revenue),
                        "" if restated else num(cost),
                        num(profit),
                        num(rev_derived) if rev_disc is not None and not restated else "",
                        num(profit_derived) if profit_disc is not None and not restated else "",
                        margin,
                        net,
                        ";".join(notes),
                    ]
                )

    fields = [
        "公司",
        "年度",
        "季度",
        "报告期",
        "营业总收入(亿元)",
        "营业收入(亿元)",
        "营业成本(亿元)",
        "归母净利润(亿元)",
        "营业收入_累计相减(亿元)",
        "归母净利润_累计相减(亿元)",
        "单季毛利率%",
        "单季净利率%",
        "口径",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    print(
        f"\n{'公司':<8}{'年度':<6}{'季度':<4}{'单季营收':>10}{'单季归母':>10}"
        f"{'相减营收':>10}{'毛利率':>8}  口径"
    )
    print("-" * 72)
    for row in rows[-9:]:
        print(
            f"{row[0]:<8}{row[1]:<6}{row[2]:<4}{row[5] or '-':>10}{row[7] or '-':>10}"
            f"{row[8] or '-':>10}{row[10] or '-':>8}  {row[12]}"
        )

    # 勾稽：单季相加 = 年报全年。差异有两种合法来源，都打出来而不是悄悄通过。
    reconcile(rows, income, problems)

    tail = OUT.relative_to(ROOT)
    print(f"\n写入 {tail}: {len(rows)} 行")
    for problem in problems:
        print(f"注意：{problem}", file=sys.stderr)
    return 0


def reconcile(
    rows: list[list[str]],
    income: dict[tuple[str, str, str], float],
    problems: list[str],
) -> None:
    for company in COMPANIES:
        for year in YEARS:
            single = sum(float(r[5]) for r in rows if r[0] == company and r[1] == year and r[5])
            annual = income.get((company, f"{year}1231", "营业收入"))
            if annual is None or not single:
                continue
            gap = single - annual
            if abs(gap) <= 0.05:
                continue
            # 有年报分季表的年份出现差异，说明分季表是重述前、年报全年是重述后
            has_disclosed = any(r[0] == company and r[1] == year and "披露" in r[12] for r in rows)
            reason = (
                "——分季表为当年披露口径、akshare 年度数为最新年报重述口径，"
                "差异须按披露版本区分（见数据源分级.md）"
                if has_disclosed
                else ""
            )
            problems.append(
                f"{company} {year} 单季相加 {single:.2f} ≠ 年报 {annual:.2f}"
                f"（差 {gap:+.2f} 亿）{reason}"
            )


def num(value: float | None) -> str:
    return "" if value is None else f"{value:.2f}"


if __name__ == "__main__":
    sys.exit(main())
