"""财务净收益：卖家电的钱在账上生息，还是靠经营赚钱。

为什么重要：
三家的财务科目**都是净收益**，规模足以影响利润表结论：

| 公司 | 财务净收益 | 占利润总额 | 利息收入 | 利息费用 | 汇兑损益 |
|---|---|---|---|---|---|
| 美的 | +59.04 亿 | 11.12% | 84.44 亿 | 22.11 亿 | -2.34 亿 |
| 海尔 | +0.51 亿 | 0.22% | 17.20 亿 | 26.79 亿 | +10.01 亿 |
| 格力 | +40.86 亿 | 11.79% | 58.85 亿 | 19.65 亿 | +2.51 亿 |

格力利息收入 58.85 亿是归母净利润的 20.3%，美的 84.44 亿是 19.2%，
海尔 17.20 亿只有 8.8%。这是「类金融」程度差异，不是经营效率差异。

四个陷阱：

1. **科目名与符号都不同**：美的叫「财务收入」（正数=收益），海尔/格力叫「财务费用」
   （负数=收益）。直接比大小会把美的的正数当成费用。
2. **表内行的方向要靠「加：/减：」前缀判断**。海尔把「减：利息收入」印成正数，
   格力把「减：利息收入」印成正数，数字本身不含方向。而美的把利息费用印成
   括号负数、利息收入印成正数，方向已含在数字里，不能再套前缀。
3. **美的把金融业务利息单列**（附注 49，发放贷款/存放同业 20.50 亿），
   这部分不在「财务收入」里，在「营业总收入」的「利息收入」行。
4. **汇兑损益方向必须统一为「正=收益」**：海尔 2025 年 +10.01 亿（人民币贬值受益），
   格力 +2.51 亿，美的是 -2.34 亿损失。海尔的财务费用从 2024 年 9.72 亿降到
   2025 年 -0.51 亿，几乎全靠这 10 亿汇兑收益。

用法：
    uv run python3 scripts/extract_finance_income.py --all
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
OUT = FIN / "财务净收益.csv"

# (文件名, 换算到元的倍数, 附注标题)
SOURCES = {
    "美的集团": ("美的2025.pdf", 1_000, "(54) 财务收入"),
    "海尔智家": ("海尔2025.pdf", 1, "53、 财务费用"),
    "格力电器": ("格力2025.pdf", 1, "60、 财务费用"),
}

# 原始项目（去掉「加：/减：」前缀后）→ 统一项目
MAPPING = {
    "美的集团": {
        "利息费用(a)": "利息费用",
        "减：利息收入": "利息收入",
        "汇兑损益": "汇兑损益",
        "其他": "其他",
    },
    "海尔智家": {
        "利息费用": "利息费用",
        "减：利息收入": "利息收入",
        "减：现金折扣": "现金折扣",
        "汇兑损益（收益以“－”填列）": "汇兑损益",
        "其他": "其他",
    },
    "格力电器": {
        "利息费用": "利息费用",
        "减：利息收入【注】": "利息收入",
        "加：汇兑损益": "汇兑损益",
        "手续费": "手续费",
        "设定受益福利义务的利息费用": "设定受益计划利息",
        "其他": "其他",
    },
}

NUMBER = r"\(?-?[\d,]+(?:\.\d+)?\)?"
ROW = re.compile(rf"^(?P<label>[^\d]*?)\s{{2,}}(?P<cur>{NUMBER})\s*(?P<prev>{NUMBER}|-)?\s*$")


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


def block_lines(text: str, title: str) -> list[str]:
    target = re.sub(r"\s+", "", title)
    lines = text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if re.sub(r"\s+", "", line).startswith(target)),
        None,
    )
    return lines[start : start + 22] if start is not None else []


def extract(company: str, lines: list[str]) -> dict[str, tuple[float, float]]:
    """返回 {统一项目: (本期原值, 上期原值)}，符号保持报表印刷原样。"""
    rules = MAPPING[company]
    items: dict[str, tuple[float, float]] = {}
    for raw in lines:
        line = raw.strip()
        if not line or "单位：" in line or line.startswith("项目"):
            continue
        if line.startswith("合计"):
            break
        match = ROW.match(line)
        if not match:
            continue
        label = re.sub(r"\s+", "", match.group("label"))
        if label not in rules:
            continue
        unified = rules[label]
        previous = 0.0 if match.group("prev") in (None, "-") else number(match.group("prev"))
        if unified not in items:
            items[unified] = (number(match.group("cur")), previous)
    return items


def to_profit(company: str, label: str, value: float) -> float:
    """把报表原值折成「对利润的贡献」，正=增厚利润。

    美的「财务收入」表：数字符号已含方向（利息费用印成括号负数），直接取用。
    海尔/格力的「财务费用」表：数字只有大小，方向靠「加：/减：」前缀：
    「减：利息收入」「减：现金折扣」是收益（正号），其余是支出（取负）。
    汇兑损益在两家表里都印成「收益以负号填列」，取负后即为收益。
    """
    if company == "美的集团":
        return value
    if label in ("利息收入", "现金折扣"):
        return value
    return -value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all", action="store_true", default=True, help="默认执行全部；保留该开关用于兼容旧命令"
    )
    args = parser.parse_args()
    if not args.all:  # 默认 True；仅显式 --no-all 时才打印帮助
        parser.print_help()
        return 1

    profit_total: dict[tuple[str, str], float] = {}
    net_income: dict[tuple[str, str], float] = {}
    with (FIN / "利润表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if not row["报告期"].endswith("1231") or row["报告期"][:4] not in ("2024", "2025"):
                continue
            if row["科目"] not in ("利润总额", "归属于母公司所有者的净利润"):
                continue
            try:
                value = float(row["数值"]) / 1e8
            except ValueError:
                continue
            target = profit_total if row["科目"] == "利润总额" else net_income
            target[(row["公司"], row["报告期"][:4])] = value

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
            profit = profit_total.get((company, year), 0.0)
            net = net_income.get((company, year), 0.0)

            # 逐项折算成「对利润的贡献」
            contribution: dict[str, float] = {}
            for unified, values in items.items():
                if index >= len(values):
                    continue
                contribution[unified] = to_profit(company, unified, values[index] * factor / 1e8)

            total = sum(contribution.values())
            for unified, value in contribution.items():
                rows.append(
                    [
                        company,
                        year,
                        unified,
                        f"{value:.2f}",
                        f"{value / profit * 100:.2f}" if profit else "",
                        f"{value / net * 100:.2f}" if net else "",
                        "披露值",
                    ]
                )
            rows.append(
                [
                    company,
                    year,
                    "财务净收益合计",
                    f"{total:.2f}",
                    f"{total / profit * 100:.2f}" if profit else "",
                    f"{total / net * 100:.2f}" if net else "",
                    "计算值",
                ]
            )
            interest_net = contribution.get("利息收入", 0.0) + contribution.get("利息费用", 0.0)
            rows.append(
                [
                    company,
                    year,
                    "利息净收入",
                    f"{interest_net:.2f}",
                    "",
                    f"{interest_net / net * 100:.2f}" if net else "",
                    "计算值",
                ]
            )
        print(f"  {company}: 明细 {len(items)} 项")

    fields = ["公司", "年度", "项目", "金额(亿元)", "占利润总额%", "占归母净利润%", "数据性质"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    print(
        f"\n{'公司':<8}{'年度':<6}{'财务净收益':>11}{'利息收入':>10}{'利息费用':>10}{'汇兑':>9}{'占利润总额':>11}"
    )
    print("-" * 66)
    for row in rows:
        if row[2] != "财务净收益合计":
            continue
        pick = {r[2]: r[3] for r in rows if r[0] == row[0] and r[1] == row[1]}
        print(
            f"{row[0]:<8}{row[1]:<6}{row[3]:>11}{pick.get('利息收入', '—'):>10}"
            f"{pick.get('利息费用', '—'):>10}{pick.get('汇兑损益', '—'):>9}{row[4]:>10}%"
        )

    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    for warning in warnings:
        print(f"注意：{warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
