"""类现金与金融资产：家电公司其实是「半个资产管理公司」。

为什么重要：
三家 2025 年末的「类现金 + 金融资产」占总资产比例：

| 公司 | 类现金与金融资产 | 占总资产 | 有息负债 | 净类现金 | 占归母净资产 |
|---|---|---|---|---|---|
| 美的 | 3,198.76 亿 | 52.5% | 674.81 亿 | 2,523.95 亿 | 113.1% |
| 海尔 | 833.01 亿 | 28.2% | 453.17 亿 | 379.84 亿 | 32.0% |
| 格力 | 2,707.76 亿 | 69.2% | 854.13 亿 | 1,853.63 亿 | 127.0% |

也就是说：**格力 68% 的资产、美的 53% 的资产不是生产经营性资产**。两家的净类现金
都超过归母净资产，海尔的净类现金只有净资产的 31%。

这解释了为什么三家的「财务净收益」能占到利润总额的 11%–12%（美的 11.12%、
格力 11.80%），而海尔只有 0.22%——它不是经营效率差异，是**资产负债表结构差异**。

五个陷阱：

1. **「其他流动资产」「其他非流动资产」混着大量非金融项目**。美的的待抵扣增值税
   90.40 亿、套期工具及保证金 32.01 亿；海尔的预付设备土地款 16.80 亿；格力的
   待抵扣进项税 49.09 亿。整科目计入会把类现金虚增数百亿，必须按附注扣掉非金融项。
2. **「一年内到期的非流动资产」是「其他非流动资产」的减项**。美的 1,553.63 亿的
   一年内到期固定收益类产品已经列在「一年内到期的非流动资产」里，「其他非流动资产」
   的 2,096.51 亿毛额已经把它减掉了。用毛额会双算 1,553.63 亿。
3. **同一笔钱三家放三个科目**：美的叫「固定收益类产品」，海尔叫「债权投资—定期存款」
   加「其他流动资产—短期存款」，格力叫「货币性投资产品」（含可转让大额存单），
   且格力把「应计利息」25.11 亿单列。按科目名横向比必然错配。
4. **美的 2025 年做了一次大规模科目腾挪**：货币资金从 1,404.10 亿降到 852.47 亿，
   同时「一年内到期的非流动资产」从 554.72 亿升到 1,556.18 亿（其中一年内到期的
   固定收益类产品从 485.82 亿升到 1,553.63 亿）。这不是钱变少了，是「三个月以上
   定期存款」从货币资金重分类到了固定收益类产品。只看「货币资金」会得出
   「美的现金大幅减少」的错误结论。
5. **格力的「买入返售金融资产」48.01 亿、海尔「存放财务公司存款」113.31 亿**
   属于同业或集团内往来，流动性受关联方约束，不能与银行存款等同看待。

**口径**：类现金与金融资产 = 货币资金 + 交易性金融资产 + 衍生金融资产 + 买入返售
金融资产 + 发放贷款及垫款 + 债权投资 + 其他债权投资 + 应收款项融资 + 其他权益工具
投资 + 其他非流动金融资产 + 一年内到期的非流动资产 + 其他流动资产中的金融部分
+ 其他非流动资产中的金融部分。**应收款项融资**性质是经营性（银行承兑汇票），
列在这里只为完整反映「可快速变现资产」，算经营效率时应剔除。

用法：
    uv run python3 scripts/build_financial_assets.py --all
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "年度报告"
FIN = ROOT / "财务数据"
OUT = FIN / "类现金与金融资产.csv"

REPORTS = {
    "美的集团": ("美的2025.pdf", 1_000),
    "海尔智家": ("海尔2025.pdf", 1),
    "格力电器": ("格力2025.pdf", 1),
}

BASE_ITEMS = [
    "货币资金",
    "交易性金融资产",
    "衍生金融资产",
    "买入返售金融资产",
    "发放贷款及垫款",
    "债权投资",
    "其他债权投资",
    "应收款项融资",
    "其他权益工具投资",
    "其他非流动金融资产",
    "一年内到期的非流动资产",
]

# 其他流动资产里的金融部分：(附注标题, 附注标签)
CURRENT_ASSET_FINANCIAL = {
    "美的集团": ("(13)   其他流动资产", "固定收益类产品(a)"),
    "海尔智家": ("12、 其他流动资产", "短期存款"),
    "格力电器": ("12、 其他流动资产", "货币性投资产品【注】"),
}

# 其他非流动资产里的非金融部分（要从资产负债表金额里扣掉）
NON_CURRENT_NONFINANCIAL = {
    "美的集团": ("(24)   其他非流动资产", ["其他"]),
    "海尔智家": ("24、 其他非流动资产", ["预付设备土地款", "其他"]),
    "格力电器": ("28、 其他非流动资产", ["其他"]),
}

# 一家公司可能披露多个「其他」，用标记区分，取第一个匹配
NUMBER = re.compile(r"^\(?-?[\d,]+(?:\.\d+)?\)?$")
SPLIT = re.compile(r"\s{2,}")


def pdf_text(pdf: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    return result.stdout


def number(token: str) -> float:
    token = token.strip()
    negative = token.startswith("(") and token.endswith(")")
    return -float(token.strip("()").replace(",", "")) if negative else float(token.replace(",", ""))


def section(lines: list[str], heading: str, limit: int = 45) -> list[str]:
    target = re.sub(r"\s+", "", heading)
    start = next(
        (i for i, line in enumerate(lines) if re.sub(r"\s+", "", line).startswith(target)),
        None,
    )
    return lines[start : start + limit] if start is not None else []


def note_rows(lines: list[str]) -> list[tuple[str, list[float]]]:
    """把附注小节切成 (标签, 全部数值)。标签会被金额劈成多行，需累积拼回。"""
    out: list[tuple[str, list[float]]] = []
    pending = ""
    for raw in lines:
        parts = [p for p in SPLIT.split(raw.strip()) if p]
        if not parts:
            continue
        values: list[str] = []
        while parts and NUMBER.match(parts[-1]):
            values.insert(0, parts.pop())
        label = "".join(parts)
        if not values:
            pending += label
            continue
        full = pending + label
        pending = ""
        if len(values) < 2:
            continue
        out.append((full, [number(v) for v in values]))
    return out


# 列取值规则：三家的附注表列数不同，不能统一「取最后两个」
#   last2  —— 两列（期末、期初）
#   index  —— 显式指定（格力「其他非流动资产」是 6 列，账面价值在第 3、6 个）
COLUMNS: dict[tuple[str, str], tuple[str, list[int]]] = {
    ("美的集团", "固定收益类产品(a)"): ("last2", []),
    ("美的集团", "其他"): ("last2", []),
    ("海尔智家", "短期存款"): ("last2", []),
    ("海尔智家", "预付设备土地款"): ("last2", []),
    ("海尔智家", "其他"): ("last2", []),
    ("格力电器", "货币性投资产品【注】"): ("last2", []),
    ("格力电器", "其他"): ("index", [2, 5]),
}


def find(
    company: str, rows: list[tuple[str, list[float]]], label: str
) -> tuple[float, float] | None:
    """按标签后缀匹配。附注的标签会被金额劈成多段，前缀不可靠。"""
    key = re.sub(r"\s+", "", label)
    mode, indices = COLUMNS[(company, label)]
    for text, values in rows:
        if not text.endswith(key):
            continue
        if mode == "index":
            if len(values) < max(indices) + 1:
                continue
            return values[indices[0]], values[indices[1]]
        if len(values) < 2:
            continue
        return values[-2], values[-1]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all", action="store_true", default=True, help="默认执行全部；保留该开关用于兼容旧命令"
    )
    args = parser.parse_args()
    if not args.all:  # 默认 True；仅显式 --no-all 时才打印帮助
        parser.print_help()
        return 1

    balance = load_balance()
    debts = load_series("有息负债与偿债能力.csv", "有息负债合计(亿元)")
    equity = load_balance_item("归属于母公司股东权益合计")
    assets = load_balance_item("资产总计")

    rows: list[list[str]] = []
    problems: list[str] = []

    for company, (filename, factor) in REPORTS.items():
        lines = pdf_text(PDF_DIR / filename).splitlines()
        current_rows = note_rows(section(lines, CURRENT_ASSET_FINANCIAL[company][0]))
        heading, label = CURRENT_ASSET_FINANCIAL[company]
        financial_current = find(company, current_rows, label)
        if financial_current is None:
            problems.append(f"{company} {heading} 未找到「{label}」")

        heading2, labels2 = NON_CURRENT_NONFINANCIAL[company]
        non_current_rows = note_rows(section(lines, heading2))
        excluded_now = excluded_before = 0.0
        for name in labels2:
            found = find(company, non_current_rows, name)
            if found is None:
                problems.append(f"{company} {heading2} 未找到「{name}」")
                continue
            excluded_now += found[0]
            excluded_before += found[1]

        for year_index, year in enumerate(("2025", "2024")):
            period = f"{year}1231"
            total = 0.0

            def add(
                name: str,
                value: float,
                source: str,
                company: str = company,
                year: str = year,
                period: str = period,
            ) -> None:
                nonlocal total
                total += value
                rows.append(
                    [
                        company,
                        year,
                        "类现金与金融资产",
                        name,
                        f"{value:.2f}",
                        pct(value, assets.get((company, period))),
                        source,
                        "计算值" if "−" in source else "披露值",
                    ]
                )

            for item in BASE_ITEMS:
                value = balance.get((company, period, item))
                if value is not None:
                    add(item, value, "资产负债表")

            if financial_current is not None:
                value = financial_current[year_index] * factor / 1e8
                add(
                    f"其他流动资产中的{CURRENT_ASSET_FINANCIAL[company][1]}",
                    value,
                    f"附注 {CURRENT_ASSET_FINANCIAL[company][0]}",
                )

            book_other = balance.get((company, period, "其他非流动资产"))
            if book_other is not None:
                # 附注同一张表就给了期末/期初的非金融部分，按年份取
                skip = (excluded_now if year_index == 0 else excluded_before) * factor / 1e8
                add(
                    "其他非流动资产中的金融部分",
                    book_other - skip,
                    "资产负债表 − 附注非金融项",
                )

            debt = debts.get((company, year))
            eq = equity.get((company, period))
            rows.append(
                [
                    company,
                    year,
                    "小计",
                    "类现金与金融资产合计",
                    f"{total:.2f}",
                    pct(total, assets.get((company, period))),
                    "明细相加",
                    "计算值",
                ]
            )
            if debt is not None:
                rows.append(
                    [
                        company,
                        year,
                        "小计",
                        "减：有息负债",
                        f"{debt:.2f}",
                        pct(debt, assets.get((company, period))),
                        "有息负债与偿债能力.csv",
                        "计算值",
                    ]
                )
                net = total - debt
                rows.append(
                    [
                        company,
                        year,
                        "小计",
                        "净类现金",
                        f"{net:.2f}",
                        pct(net, assets.get((company, period))),
                        "合计 − 有息负债",
                        "计算值",
                    ]
                )
                if eq:
                    rows.append(
                        [
                            company,
                            year,
                            "小计",
                            "净类现金占归母净资产%",
                            f"{net / eq * 100:.2f}",
                            "",
                            "资产负债表",
                            "计算值",
                        ]
                    )

    fields = [
        "公司",
        "年度",
        "类别",
        "项目",
        "金额(亿元)",
        "占总资产%",
        "来源",
        "数据性质",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    print(
        f"\n{'公司':<8}{'年度':<6}{'类现金金融':>11}{'占总资产':>9}{'有息负债':>10}{'净类现金':>10}{'占净资产':>9}"
    )
    print("-" * 64)
    for company in REPORTS:
        for year in ("2025", "2024"):
            pick = {row[3]: float(row[4]) for row in rows if row[0] == company and row[1] == year}
            total = pick.get("类现金与金融资产合计", 0.0)
            debt = pick.get("减：有息负债", 0.0)
            ratio = pick.get("净类现金占归母净资产%", 0.0)
            asset = assets.get((company, f"{year}1231")) or 1.0
            print(
                f"{company:<8}{year:<6}{total:>11.2f}{total / asset * 100:>8.1f}%"
                f"{debt:>10.2f}{total - debt:>10.2f}{ratio:>8.1f}%"
            )

    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    for problem in problems:
        print(f"注意：{problem}", file=sys.stderr)
    return 0


def pct(value: float, base: float | None) -> str:
    return f"{value / base * 100:.2f}" if base else ""


def load_balance() -> dict[tuple[str, str, str], float]:
    out: dict[tuple[str, str, str], float] = {}
    subjects = set(BASE_ITEMS) | {"其他非流动资产"}
    with (FIN / "资产负债表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["科目"] not in subjects or row["数值"] in ("", "nan"):
                continue
            try:
                value = float(row["数值"]) / 1e8
            except ValueError:
                continue
            out.setdefault((row["公司"], row["报告期"], row["科目"]), value)
    return out


def load_balance_item(subject: str) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    with (FIN / "资产负债表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["科目"] != subject or row["数值"] in ("", "nan"):
                continue
            try:
                out[(row["公司"], row["报告期"])] = float(row["数值"]) / 1e8
            except ValueError:
                continue
    return out


def load_series(filename: str, column: str) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    with (FIN / filename).open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            try:
                out[(row["公司"], row["年度"])] = float(row[column])
            except (ValueError, KeyError):
                continue
    return out


if __name__ == "__main__":
    sys.exit(main())
