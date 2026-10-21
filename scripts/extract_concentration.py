"""提取年报「主要销售客户和主要供应商」集中度。

三家披露单位和格式完全不同，必须按各自口径解析：
- 美的：千元，分字段列示，「前五名客户合计销售金额（千元）」
- 海尔：万元，整句叙述，「前五名客户销售额 5,927,312.85 万元，占年度销售总额 19.6%」
- 格力：元，分字段列示，「前五名客户合计销售金额（元）」

集中度是判断议价能力和渠道结构的关键指标：
- 客户集中度高 → 大客户议价能力强，应收账款风险集中
- 供应商集中度高 → 关键零部件依赖，成本传导受限

用法：
    uv run python3 scripts/extract_concentration.py --all
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
OUT = ROOT / "财务数据" / "客户供应商集中度.csv"

REPORTS = {
    "美的集团": ["美的2023.pdf", "美的2024.pdf", "美的2025.pdf"],
    "海尔智家": ["海尔2023.pdf", "海尔2024.pdf", "海尔2025.pdf"],
    "格力电器": ["格力2023.pdf", "格力2024.pdf", "格力2025.pdf"],
}

# 单位换算到元
UNIT = {"千元": 1_000, "万元": 10_000, "元": 1}


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


def num(text: str) -> float | None:
    try:
        return float(text.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def parse_field(flat: str, label: str) -> tuple[float, str] | None:
    """匹配「标签（单位） 数值」，返回 (数值, 单位)。"""
    pattern = rf"{re.escape(label)}（(千元|万元|元)）\s*([\d,]+(?:\.\d+)?)"
    match = re.search(pattern, flat)
    if not match:
        return None
    value = num(match.group(2))
    return (value, match.group(1)) if value is not None else None


def parse_sentence(flat: str, label: str) -> float | None:
    """海尔句式：「前五名客户销售额 5,927,312.85 万元」。"""
    pattern = rf"{re.escape(label)}\s*([\d,]+(?:\.\d+)?)\s*(千元|万元|元)"
    match = re.search(pattern, flat)
    return num(match.group(1)) if match else None


def extract(flat: str, company: str, year: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    specs = [
        ("客户", "前五名客户合计销售金额", "customer"),
        ("供应商", "前五名供应商合计采购金额", "supplier"),
    ]

    for dimension, field_label, short in specs:
        amount: float | None = None
        unit = ""
        ratio: float | None = None

        # 字段式（美的、格力）
        parsed = parse_field(flat, field_label)
        if parsed:
            amount, unit = parsed
            ratio_match = re.search(
                rf"{re.escape(field_label)}占年度(?:销售|采购)总额比例\s*([\d.]+)%",
                flat,
            )
            if ratio_match:
                ratio = float(ratio_match.group(1))

        # 句式（海尔）：前五名客户销售额 X 万元，占年度销售总额 Y%
        if amount is None:
            sentence_label = "前五名客户销售额" if short == "customer" else "前五名供应商采购额"
            amount = parse_sentence(flat, sentence_label)
            if amount is not None:
                unit = "万元"
                ratio_match = re.search(
                    rf"{sentence_label}\s*[\d,.]+\s*万元\s*，?\s*占年度(?:销售|采购)总额\s*([\d.]+)%",
                    flat,
                )
                if ratio_match:
                    ratio = float(ratio_match.group(1))

        if amount is None:
            continue

        amount_yuan = amount * UNIT.get(unit, 1)
        rows.append(
            {
                "公司": company,
                "年度": year,
                "维度": dimension,
                "前五名金额": f"{amount_yuan:.2f}",
                "占总额比例%": f"{ratio:.2f}" if ratio is not None else "",
                "年报原单位": unit,
                "数据性质": "披露值",
            }
        )

    # 关联方占比
    for dimension, short in (("客户", "customer"), ("供应商", "supplier")):
        pattern = rf"前五名{dimension}销售额中关联方销售额占年度销售总额比例\s*([\d.]+)%"
        if short == "supplier":
            pattern = r"前五名供应商采购额中关联方采购额占年度采购总额比例\s*([\d.]+)%"
        match = re.search(pattern, flat)
        if match:
            rows.append(
                {
                    "公司": company,
                    "年度": year,
                    "维度": f"{dimension}-关联方占比",
                    "前五名金额": "",
                    "占总额比例%": match.group(1),
                    "年报原单位": "",
                    "数据性质": "披露值",
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all", action="store_true", default=True, help="默认执行全部；保留该开关用于兼容旧命令"
    )
    args = parser.parse_args()
    if not args.all:  # 默认 True；仅显式 --no-all 时才打印帮助
        parser.print_help()
        return 1

    rows: list[dict[str, str]] = []
    for company, files in REPORTS.items():
        for filename in files:
            pdf = PDF_DIR / filename
            if not pdf.exists():
                continue
            year_match = re.search(r"(20\d{2})", filename)
            if not year_match:
                continue
            year = year_match.group(1)
            items = extract(flatten(pdf_text(pdf)), company, year)
            rows.extend(items)
            summary = {
                i["维度"]: f"{float(i['前五名金额']) / 1e8:,.1f}亿/{i['占总额比例%']}%"
                for i in items
                if i["前五名金额"]
            }
            print(f"  {company} {year}: {summary}")

    fields = ["公司", "年度", "维度", "前五名金额", "占总额比例%", "年报原单位", "数据性质"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
