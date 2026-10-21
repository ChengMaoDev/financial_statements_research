"""提取分销售模式（线上/线下、直销/经销）收入与毛利率。

为什么重要：
三家对渠道的披露粒度差异很大，这是判断「增长来自哪里」的关键：

- 美的：明确给「线上 / 线下」两行，含收入、成本、毛利率、同比。
- 海尔：给「国内-直销用户 / 国内-经销及其他 / 海外-直销用户 / 海外-贸易」四行，
  用的是**直销 vs 经销**维度，不是线上 vs 线下。
- 格力：年报「主营业务分销售模式」栏**不存在**，只有分行业/分产品/分地区。
  格力 2025 年报正文提到「超 2 万家销售门店」，但没有收入拆分。

因此本表列出的渠道口径三家**不可横向比较**，只能各自看趋势。
格力一行留空并标注「未披露」，不填 0。

线上毛利率通常低于线下（电商比价、平台扣点），若某家线上占比快速提升而
整体毛利率不降，需要检查是不是把平台费用计入了销售费用而非冲减收入。

用法：
    uv run python3 scripts/extract_channels.py --all
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
OUT = FIN / "渠道结构.csv"

# (公司, 口径标签, 关键词, 单位)
SPECS = {
    "美的集团": [
        ("线上", r"线上\s*([\d,]+)\s+([\d,]+)\s+([\d.]+)%?\s+([\d.]+)%", 1_000),
        ("线下", r"线下\s*([\d,]+)\s+([\d,]+)\s+([\d.]+)%?\s+([\d.]+)%", 1_000),
    ],
    "海尔智家": [
        (
            "国内-直销用户",
            r"国内-直销\s*([\d,.]+)\s*([\d,.]+)\s+([\d.]+)\s+([\d.-]+)\s+([\d.-]+)",
            1,
        ),
        (
            "国内-经销及其他",
            r"国内-经销\s*([\d,.]+)\s*([\d,.]+)\s+([\d.]+)\s+([\d.-]+)\s+([\d.-]+)",
            1,
        ),
        (
            "海外-直销用户",
            r"海外-直销\s*([\d,.]+)\s*([\d,.]+)\s+([\d.]+)\s+([\d.-]+)\s+([\d.-]+)",
            1,
        ),
        (
            "海外-贸易",
            r"海外-贸易\s*([\d,.]+)\s+(\S+)\s+([\d.]+)\s+([\d.-]+)\s+([\d.-]+)",
            1,
        ),
    ],
}

# 海尔成本列出现过科学计数法（1.10253E+11），需要单独处理
SCI = re.compile(r"^[\d.]+E[+-]?\d+$", re.IGNORECASE)


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
    if SCI.match(text):
        return float(text)
    return float(text.replace(",", ""))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all", action="store_true", default=True, help="默认执行全部；保留该开关用于兼容旧命令"
    )
    args = parser.parse_args()
    if not args.all:  # 默认 True；仅显式 --no-all 时才打印帮助
        parser.print_help()
        return 1

    revenue = {}
    with (FIN / "利润表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["科目"] != "营业收入" or row["报告期"] != "20251231":
                continue
            try:
                revenue[row["公司"]] = float(row["数值"]) / 1e8
            except ValueError:
                continue

    rows: list[list[str]] = []
    for company, specs in SPECS.items():
        pdf = PDF_DIR / f"{'美的' if company == '美的集团' else '海尔'}2025.pdf"
        if not pdf.exists():
            print(f"  缺少 {pdf.name}", file=sys.stderr)
            continue
        flat = flatten(pdf_text(pdf))
        # 锚定「分销售模式」小节，避免匹配到前面只含收入/占比的汇总表
        anchor = flat.find("分销售模式")
        if anchor > 0:
            flat = flat[anchor:]
        base = revenue.get(company, 0.0)
        for label, pattern, factor in specs:
            match = re.search(pattern, flat)
            if not match:
                print(f"  {company} {label} 未匹配", file=sys.stderr)
                continue
            amount = num(match.group(1)) * factor / 1e8
            gross = match.group(3)
            rows.append(
                [
                    company,
                    "2025",
                    label,
                    f"{amount:.2f}",
                    f"{amount / base * 100:.2f}" if base else "",
                    gross,
                    "纯线上/纯线下" if company == "美的集团" else "直销/经销",
                    "披露值",
                ]
            )
            print(f"  {company} {label}: {amount:,.1f}亿 毛利率 {gross}%")

    rows.append(
        [
            "格力电器",
            "2025",
            "未披露",
            "",
            "",
            "",
            "年报无「分销售模式」栏",
            "未披露",
        ]
    )

    fields = [
        "公司",
        "年度",
        "销售模式",
        "营业收入(亿元)",
        "占营业收入%",
        "毛利率%",
        "口径",
        "数据性质",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
