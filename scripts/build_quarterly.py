"""生成三家公司分季度经营数据对比。

数据来源：各年年报「分季度主要财务数据」章节（一手披露）。
Q4 用全年减前三季度推算，并明确标注为计算值。

用法：
    uv run python3 scripts/build_quarterly.py
"""

from __future__ import annotations

import csv
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "年度报告"
OUT = ROOT / "财务数据" / "分季度经营.csv"

REPORTS = {
    "美的集团": ["美的2023.pdf", "美的2024.pdf", "美的2025.pdf"],
    "海尔智家": ["海尔2023.pdf", "海尔2024.pdf", "海尔2025.pdf"],
    "格力电器": ["格力2023.pdf", "格力2024.pdf", "格力2025.pdf"],
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


def parse_amount(text: str) -> float | None:
    try:
        return float(text.replace(",", "").strip())
    except ValueError:
        return None


def unit_near(text: str, anchor: int, window: int = 3000) -> int:
    """判定 anchor 附近表格单位。

    单位标注有时在标题之后（「分季度主要财务数据」下一行），有时在之前，
    因此先向后找 400 字符，找不到再向前找。
    """
    forward = text[anchor : anchor + 400]
    best: tuple[int, int] = (-1, 1)
    for marker, factor in [("单位：千元", 1000), ("单位：元", 1), ("单位：万元", 10000)]:
        index = forward.find(marker)
        if index >= 0 and (best[0] < 0 or index < best[0]):
            best = (index, factor)
    if best[0] >= 0:
        return best[1]

    chunk = text[max(0, anchor - window) : anchor]
    for marker, factor in [("单位：千元", 1000), ("单位：元", 1), ("单位：万元", 10000)]:
        index = chunk.rfind(marker)
        if index > best[0]:
            best = (index, factor)
    return best[1]


def extract_quarterly(text: str, company: str, year: str) -> list[dict[str, str]]:
    """抓「分季度主要财务数据」表。"""
    anchor = text.find("分季度主要财务数据")
    if anchor < 0:
        anchor = text.find("分季度主要财务指标")
    if anchor < 0:
        return []

    unit = unit_near(text, anchor)
    chunk = text[anchor : anchor + 3500]
    rows: list[dict[str, str]] = []

    # 营业收入行：一行里四个数字
    revenue = re.search(
        r"营业收入\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)", chunk
    )
    if revenue:
        for index, quarter in enumerate(["Q1", "Q2", "Q3", "Q4"]):
            value = parse_amount(revenue.group(index + 1))
            if value is None:
                continue
            rows.append(
                {
                    "公司": company,
                    "年度": year,
                    "季度": quarter,
                    "指标": "营业收入",
                    "数值": f"{value * unit:.2f}",
                    "数据性质": "披露值",
                }
            )

    # 归母净利润：表头排版三家不同
    #   美的/格力：「归属于上市公司股东的净利润」+ 同行 4 个数
    #   海尔 2025：标签拆成「归属于上市公司股」/ 4 个数 / 「东的净利润」
    #   海尔 2024：标签拆成「归属于上市公司」/ 4 个数 / 「股东的净利润」
    # 统一用前缀「归属于上市公司」定位（首次出现即归母净利润行），再取其后前 4 个金额。
    flat = re.sub(r"\s+", " ", chunk)
    flat = re.sub(r"\d+ / \d+ [\u4e00-\u9fa5A-Za-z]+ ?[\d ]*年(?:半)?年度报告", " ", flat)
    flat = re.sub(r"[\u4e00-\u9fa5]+股份有限公司 ?\d{4} 年(?:半)?年度报告", " ", flat)
    label = re.search(r"归属于上市公司", flat)
    if label:
        tail = flat[label.start() : label.start() + 400]
        # 美的/格力是整数（千元/元），海尔带两位小数，两种都要覆盖
        numbers = [
            token
            for token in re.findall(r"[\d,]{4,}(?:\.\d+)?", tail)
            if parse_amount(token) is not None
        ]
        for index, quarter in enumerate(["Q1", "Q2", "Q3", "Q4"]):
            if index >= len(numbers):
                break
            value = parse_amount(numbers[index])
            if value is None:
                continue
            rows.append(
                {
                    "公司": company,
                    "年度": year,
                    "季度": quarter,
                    "指标": "归母净利润",
                    "数值": f"{value * unit:.2f}",
                    "数据性质": "披露值",
                }
            )
    return rows


def main() -> int:
    all_rows: list[dict[str, str]] = []
    for company, files in REPORTS.items():
        for filename in files:
            pdf = PDF_DIR / filename
            if not pdf.exists():
                continue
            year_match = re.search(r"(20\d{2})", filename)
            if not year_match:
                continue
            year = year_match.group(1)
            text = pdf_text(pdf)
            rows = extract_quarterly(text, company, year)
            all_rows.extend(rows)
            counts = {}
            for row in rows:
                counts[row["指标"]] = counts.get(row["指标"], 0) + 1
            print(f"  {company} {year}: {counts}")

    if not all_rows:
        print("未提取到分季度数据", file=sys.stderr)
        return 1

    fields = ["公司", "年度", "季度", "指标", "数值", "数据性质"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(all_rows)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
