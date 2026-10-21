"""提取「投资收益」明细，拆出权益法收益与金融资产处置收益。

为什么重要：
投资收益是三家利润表里结构差异最大的科目，2025 年占利润总额：

- 美的 3.19%（16.95 亿），其中权益法 5.89 亿（34.7%）
- 海尔 6.52%（15.30 亿），其中权益法 13.28 亿（86.8%）
- 格力 1.16%（4.02 亿），其中权益法 0.36 亿（9.0%）

**权益法收益是联营企业利润的份额**，可持续但不产生现金流入；
**处置收益是一次性兑现**，不可持续。两者混在「投资收益」一行里，
只看总额会把一次性收益当成经常性盈利能力。

三家结构完全不同：

| 公司 | 权益法 | 金融工具/理财 | 处置与衍生 | 其他 |
|---|---|---|---|---|
| 美的 | 5.89 亿 | 0.75 亿 | 12.77 - 2.01 亿 | -0.45 亿 |
| 海尔 | 13.28 亿 | 0.94 亿 | 0.06 + 0.66 亿 | 0.48 亿 |
| 格力 | 0.36 亿 | 2.79 亿 | -0.37 亿 | 1.24 亿 |

海尔的投资收益几乎全部来自权益法（联营企业），格力的几乎全部来自交易性金融工具
（票据、理财），美的介于两者之间且以处置交易性金融资产为主。

口径陷阱：
1. **「其他权益工具投资在持有期间的投资收益」是股利**，不是公允价值变动。
   这类资产的公允价值变动进其他综合收益、不进利润表，只有分红才进投资收益。
2. **三家分项不能逐项对齐**：格力把「衍生金融工具」单列，美的也算单列但用括号负数，
   海尔没有衍生品行。只能按「权益法 / 非权益法」二分后再看细项。
3. **美的附注单位是千元**，海尔/格力是元。
4. **海尔的一行标签跨两行**（「处置以公允价值计量且其变动计入当期损益的金融资产 /
   取得的投资收益」），数字在第一行末尾，必须按行解析而不是全文正则。

用法：
    uv run python3 scripts/extract_investment_income.py --all
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
OUT = FIN / "投资收益结构.csv"

# (文件名, 换算到元的倍数, 附注标题)
SOURCES = {
    "美的集团": ("美的2025.pdf", 1_000, "(59) 投资收益"),
    "海尔智家": ("海尔2025.pdf", 1, "55、 投资收益"),
    "格力电器": ("格力2025.pdf", 1, "62、 投资收益"),
}

# 附注原始项目 → (统一科目, 类别)。按顺序匹配，先命中者优先。
MAPPING = {
    "美的集团": [
        ("对联营企业和合营企业的投资收益", "权益法收益", "权益法"),
        ("处置交易性金融资产", "处置交易性金融资产", "非权益法"),
        ("处置衍生金融资产", "衍生金融工具", "非权益法"),
        ("交易性金融资产持有期间", "持有期间收益", "非权益法"),
        ("其他", "其他", "非权益法"),
    ],
    "海尔智家": [
        ("权益法核算的长期股权投资收益", "权益法收益", "权益法"),
        ("处置长期股权投资", "处置长期股权投资", "非权益法"),
        ("其他权益工具投资在持有期间", "其他权益工具股利", "非权益法"),
        ("理财产品收益", "理财产品", "非权益法"),
        ("处置以公允价值计量", "处置交易性金融资产", "非权益法"),
    ],
    "格力电器": [
        ("交易性金融工具取得的投资收益", "交易性金融工具", "非权益法"),
        ("权益法核算的长期股权投资收益", "权益法收益", "权益法"),
        ("衍生金融工具取得的投资收益", "衍生金融工具", "非权益法"),
        ("其他", "其他", "非权益法"),
    ],
}

NUMBER = r"\(?-?[\d,]+(?:\.\d+)?\)?"
ROW = re.compile(rf"^(?P<label>[^\d]*?)\s{{2,}}(?P<cur>{NUMBER})\s+(?P<prev>{NUMBER}|-)\s*$")
# 纯数字行：标签在上一行（海尔「处置以公允价值…金融资产 / 65,568,029.58 -1,038,171.65 / 取得的投资收益」）
NUMBERS_ONLY = re.compile(rf"^(?P<cur>{NUMBER})\s+(?P<prev>{NUMBER}|-)\s*$")


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
    value = float(token.strip("()").replace(",", ""))
    return -value if negative else value


def block_lines(text: str, title: str) -> list[str]:
    """按「(59)投资收益」这种去空格后的形式定位，避免附注标题栏宽不一。"""
    target = re.sub(r"\s+", "", title)
    lines = text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if re.sub(r"\s+", "", line).startswith(target)),
        None,
    )
    if start is None:
        return []
    return lines[start : start + 25]


def extract(company: str, lines: list[str]) -> dict[str, tuple[float, float]]:
    """返回 {统一科目: (本期, 上期)}，单位为报表原单位。"""
    rules = MAPPING[company]
    items: dict[str, tuple[float, float]] = {}
    pending = ""
    for raw in lines:
        line = raw.strip()
        if not line or "单位：" in line or line.startswith("项目"):
            continue
        if line.startswith("合计"):
            break
        match = ROW.match(line)
        if not match:
            numbers = NUMBERS_ONLY.match(line)
            if numbers and pending:
                # 标签在上、数字单独一行
                label, pending = re.sub(r"\s+", "", pending), ""
                cur, prev = numbers.group("cur"), numbers.group("prev")
            elif re.fullmatch(r"[\u4e00-\u9fa5（）()、]+", line):
                pending += line
                continue
            else:
                continue
        else:
            label = re.sub(r"\s+", "", pending + match.group("label"))
            pending = ""
            cur, prev = match.group("cur"), match.group("prev")
        previous = 0.0 if prev == "-" else number(prev)
        for original, unified, _ in rules:
            if label.startswith(original[:10]) and unified not in items:
                items[unified] = (number(cur), previous)
                break
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all", action="store_true", default=True, help="默认执行全部；保留该开关用于兼容旧命令"
    )
    args = parser.parse_args()
    if not args.all:  # 默认 True；仅显式 --no-all 时才打印帮助
        parser.print_help()
        return 1

    stated: dict[tuple[str, str], float] = {}
    profit: dict[tuple[str, str], float] = {}
    with (FIN / "利润表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if not row["报告期"].endswith("1231"):
                continue
            year = row["报告期"][:4]
            if year not in ("2025", "2024"):
                continue
            if row["科目"] not in ("投资收益", "利润总额"):
                continue
            try:
                value = float(row["数值"]) / 1e8
            except ValueError:
                continue
            target = stated if row["科目"] == "投资收益" else profit
            target[(row["公司"], year)] = value

    rows: list[list[str]] = []
    warnings: list[str] = []
    for company, (filename, factor, title) in SOURCES.items():
        pdf = PDF_DIR / filename
        if not pdf.exists():
            print(f"  缺少 {filename}", file=sys.stderr)
            continue
        items = extract(company, block_lines(pdf_text(pdf), title))
        if not items:
            print(f"  {company} 未匹配", file=sys.stderr)
            warnings.append(f"{company} 未匹配")
            continue

        for index, year in enumerate(("2025", "2024")):
            reported = stated.get((company, year), 0.0)
            total_profit = profit.get((company, year), 0.0)
            parts = {
                unified: values[index] * factor / 1e8
                for unified, values in items.items()
                if index < len(values)
            }

            gap = sum(parts.values()) - reported
            if abs(gap) > max(0.05, abs(reported) * 0.005):
                warnings.append(f"{company} {year} 明细合计差 {gap:+.2f} 亿")

            equity = parts.get("权益法收益", 0.0)
            for _, unified, category in MAPPING[company]:
                if unified not in parts:
                    continue
                value = parts[unified]
                rows.append(
                    [
                        company,
                        year,
                        category,
                        unified,
                        f"{value:.2f}",
                        f"{value / reported * 100:.2f}" if reported else "",
                        f"{value / total_profit * 100:.2f}" if total_profit else "",
                        "披露值",
                    ]
                )
            rows.append(
                [
                    company,
                    year,
                    "小计",
                    "投资收益合计（利润表）",
                    f"{reported:.2f}",
                    "100.00",
                    f"{reported / total_profit * 100:.2f}" if total_profit else "",
                    "披露值",
                ]
            )
            rows.append(
                [
                    company,
                    year,
                    "小计",
                    "其中：权益法收益",
                    f"{equity:.2f}",
                    f"{equity / reported * 100:.2f}" if reported else "",
                    f"{equity / total_profit * 100:.2f}" if total_profit else "",
                    "计算值",
                ]
            )
            rows.append(
                [
                    company,
                    year,
                    "小计",
                    "其中：非权益法（处置/持有收益）",
                    f"{reported - equity:.2f}",
                    f"{(reported - equity) / reported * 100:.2f}" if reported else "",
                    f"{(reported - equity) / total_profit * 100:.2f}" if total_profit else "",
                    "计算值",
                ]
            )
        print(f"  {company}: 明细 {len(items)} 项")

    fields = [
        "公司",
        "年度",
        "类别",
        "统一科目",
        "金额(亿元)",
        "占投资收益%",
        "占利润总额%",
        "数据性质",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    print(
        f"\n{'公司':<8}{'年度':<6}{'投资收益':>10}{'权益法':>9}{'权益法占比':>11}{'占利润总额':>11}"
    )
    print("-" * 58)
    for row in rows:
        if row[3] != "投资收益合计（利润表）":
            continue
        equity = next(
            r[4] for r in rows if r[0] == row[0] and r[1] == row[1] and r[3] == "其中：权益法收益"
        )
        ratio = float(equity) / float(row[4]) * 100 if float(row[4]) else 0.0
        print(f"{row[0]:<8}{row[1]:<6}{row[4]:>10}{equity:>9}{ratio:>10.1f}%{row[6]:>10}%")

    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    for warning in warnings:
        print(f"注意：{warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
