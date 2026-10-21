"""提取「其他收益」明细：政府补助与增值税加计抵减，并计算对利润总额的贡献。

为什么重要：
「其他收益」是新准则下政府补助的主要出口，直接进营业利润、不进营业外收入。
三家把它拆成不同名目，直接加总会被误导：

- 美的：专项补助 + 进项税加计扣除
- 海尔：与收益相关的政府补助 + 与资产相关的政府补助
- 格力：政府补助 + 增值税加计抵减及其他

其中「增值税加计抵减」是税收优惠政策（先进制造业企业按可抵扣进项税额加计 5%
抵减应纳税额），本质是政策红利，不是经营性收益。格力 2024 年这一项 8.08 亿，
2025 年降到 3.58 亿，是当年其他收益腰斩的主因。

口径统一：本表把「增值税加计抵减 / 进项税加计扣除」单列为一列，
剩下的才是「政府补助」。美的的「专项补助」与海尔/格力的「政府补助」可比。

用法：
    uv run python3 scripts/extract_gov_subsidy.py --all
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
OUT = FIN / "政府补助与其他收益.csv"

REPORTS = {
    "美的集团": ("美的2025.pdf", 1_000),
    "海尔智家": ("海尔2025.pdf", 1),
    "格力电器": ("格力2025.pdf", 1),
}


def pdf_text(pdf: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    return result.stdout


def flatten(text: str) -> str:
    text = re.sub(r"\b\d{1,3}\s*/\s*\d{1,3}\b", " ", text)
    text = re.sub(
        r"[\u4e00-\u9fa5（）()]+股份有限公司\s*\d{4}\s*年(?:半)?年度报告(?:全文)?", " ", text
    )
    text = re.sub(r"(?m)^\s*\d{2,3}\s*$", " ", text)
    return re.sub(r"\s+", " ", text)


def num(text: str) -> float:
    return float(text.replace(",", ""))


def extract(company: str, flat: str) -> dict[str, tuple[float, float]] | None:
    """返回 {项目: (本期, 上期)}，单位为报表原单位。"""
    if company == "美的集团":
        block = flat[flat.find("(61) 其他收益") : flat.find("(61) 其他收益") + 400]
        items = {}
        for label in ("专项补助", "进项税加计扣除"):
            match = re.search(rf"{label}\s*([\d,]+)\s*([\d,]+)", block)
            if match:
                items[label] = (num(match.group(1)), num(match.group(2)))
        total = re.search(r"([\d,]+)\s+([\d,]+)\s*\(62\)\s*所得税费用", block)
        if total:
            items["合计"] = (num(total.group(1)), num(total.group(2)))
        return items or None

    if company == "海尔智家":
        block = flat[flat.find("54、 其他收益") : flat.find("54、 其他收益") + 500]
        items = {}
        for label in ("与收益相关的政府补助", "与资产相关的政府补助"):
            match = re.search(rf"{label}\s*([\d,.]+)\s*([\d,.]+)", block)
            if match:
                items[label] = (num(match.group(1)), num(match.group(2)))
        total = re.search(r"合计\s*([\d,.]+)\s*([\d,.]+)", block)
        if total:
            items["合计"] = (num(total.group(1)), num(total.group(2)))
        return items or None

    block = flat[flat.find("61、 其他收益") : flat.find("61、 其他收益") + 400]
    items = {}
    for label in ("政府补助", "增值税加计抵减及其他"):
        match = re.search(rf"{label}\s*([\d,.]+)\s*([\d,.]+)", block)
        if match:
            items[label] = (num(match.group(1)), num(match.group(2)))
    total = re.search(r"合计\s*([\d,.]+)\s*([\d,.]+)", block)
    if total:
        items["合计"] = (num(total.group(1)), num(total.group(2)))
    return items or None


# 统一口径映射：项目 → (统一科目, 是否属于政府补助)
MAPPING = {
    "美的集团": {
        "专项补助": ("政府补助", True),
        "进项税加计扣除": ("增值税加计抵减", False),
    },
    "海尔智家": {
        "与收益相关的政府补助": ("政府补助", True),
        "与资产相关的政府补助": ("政府补助", True),
    },
    "格力电器": {
        "政府补助": ("政府补助", True),
        "增值税加计抵减及其他": ("增值税加计抵减", False),
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all", action="store_true", default=True, help="默认执行全部；保留该开关用于兼容旧命令"
    )
    args = parser.parse_args()
    if not args.all:  # 默认 True；仅显式 --no-all 时才打印帮助
        parser.print_help()
        return 1

    profit_total = {}
    with (FIN / "利润表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["科目"] != "利润总额" or not row["报告期"].endswith("1231"):
                continue
            try:
                profit_total[(row["公司"], row["报告期"][:4])] = float(row["数值"]) / 1e8
            except ValueError:
                continue

    rows: list[list[str]] = []
    for company, (filename, factor) in REPORTS.items():
        pdf = PDF_DIR / filename
        if not pdf.exists():
            print(f"  缺少 {filename}", file=sys.stderr)
            continue
        flat = flatten(pdf_text(pdf))
        items = extract(company, flat)
        if not items:
            print(f"  {company} 未匹配", file=sys.stderr)
            continue

        mapping = MAPPING[company]
        for year_index, year in enumerate(("2025", "2024")):
            total_profit = profit_total.get((company, year), 0.0)
            gov = subsidy = tax_credit = 0.0
            for label, values in items.items():
                if label == "合计":
                    continue
                unified, is_gov = mapping[label]
                amount = values[year_index] * factor / 1e8
                if is_gov:
                    gov += amount
                else:
                    tax_credit += amount
                subsidy += amount
                rows.append(
                    [
                        company,
                        year,
                        unified,
                        label,
                        f"{amount:.2f}",
                        f"{amount / total_profit * 100:.2f}" if total_profit else "",
                        "披露值",
                    ]
                )

            total = items.get("合计")
            total_value = total[year_index] * factor / 1e8 if total else subsidy
            rows.append(
                [
                    company,
                    year,
                    "政府补助小计",
                    "统一口径：仅政府补助",
                    f"{gov:.2f}",
                    f"{gov / total_profit * 100:.2f}" if total_profit else "",
                    "计算值",
                ]
            )
            rows.append(
                [
                    company,
                    year,
                    "增值税加计抵减小计",
                    "统一口径：税收优惠，非补助",
                    f"{tax_credit:.2f}",
                    f"{tax_credit / total_profit * 100:.2f}" if total_profit else "",
                    "计算值",
                ]
            )
            rows.append(
                [
                    company,
                    year,
                    "其他收益合计",
                    "利润表「其他收益」",
                    f"{total_value:.2f}",
                    f"{total_value / total_profit * 100:.2f}" if total_profit else "",
                    "披露值",
                ]
            )
        print(f"  {company}: 明细 {len(items)} 项")

    fields = ["公司", "年度", "统一科目", "原始项目", "金额(亿元)", "占利润总额%", "数据性质"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    print(
        f"\n{'公司':<8}{'年度':<6}{'政府补助':>10}{'加计抵减':>10}{'合计':>10}{'占利润总额%':>12}"
    )
    print("-" * 58)
    for company in REPORTS:
        for year in ("2025", "2024"):
            pick = {
                (r[2], r[1]): float(r[4])
                for r in rows
                if r[0] == company
                and r[2] in ("政府补助小计", "增值税加计抵减小计", "其他收益合计")
            }
            gov = pick.get(("政府补助小计", year), 0.0)
            tax = pick.get(("增值税加计抵减小计", year), 0.0)
            total = pick.get(("其他收益合计", year), 0.0)
            ratio = total / profit_total.get((company, year), 1) * 100
            print(f"{company:<8}{year:<6}{gov:>10.2f}{tax:>10.2f}{total:>10.2f}{ratio:>12.2f}")
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
