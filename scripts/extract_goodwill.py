"""提取商誉明细：按被投资单位/资产组拆分原值、减值准备与账面价值。

为什么重要：
商誉是并购溢价的资本化，减值测试依赖管理层假设。三家的商誉结构差异极大：
- 美的 342.57 亿，其中 KUKA 234.35 亿，是最大单一风险敞口
- 海尔 273.00 亿，主要是 GEA 208.83 亿
- 格力 13.24 亿，格力钛、南京华新、合肥晶弘已全额减值

格力把收购标的几乎全部减值完毕，美的/海尔尚未减值。这不代表谁对谁错，
但说明三家的商誉风险完全不在一个量级。

校验：各家明细合计 = 资产负债表「商誉」。

用法：
    uv run python3 scripts/extract_goodwill.py --all
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
OUT = FIN / "商誉明细.csv"

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


def parse_midea(flat: str) -> list[tuple[str, float, float]]:
    """KUKA 与 TLSC 在关键审计事项中单列，其余合并为「其他」。

    年报关键审计事项是双栏排版，pdftotext 会把左右栏交错，金额常落在
    「……约为人民币」之后 100 多个字符处，因此用 DOTALL 跨栏取数。
    """
    total = re.search(r"商誉的账面价值约为人民币\s*([\d,]+)\s*千\s*元", flat)
    kuka = re.search(
        r"KUKA\s*集团[”」]?\s*）?\s*业务产生的商誉约为人民币.{0,160}?([\d,]{7,})\s*千",
        flat,
        re.DOTALL,
    )
    tlsc = re.search(
        r"TLSC\s*集团[”」]?\s*）?\s*业务产生的商誉约为人民币.{0,160}?([\d,]{7,})\s*千",
        flat,
        re.DOTALL,
    )
    if not total or not kuka or not tlsc:
        return []
    total_v = num(total.group(1))
    kuka_v = num(kuka.group(1))
    tlsc_v = num(tlsc.group(1))
    return [
        ("KUKA 集团", kuka_v, 0.0),
        ("TLSC 集团（东芝生活电器）", tlsc_v, 0.0),
        ("其他并购", total_v - kuka_v - tlsc_v, 0.0),
    ]


def parse_haier(flat: str) -> list[tuple[str, float, float]]:
    start = flat.find("21、 商誉")
    if start < 0:
        start = flat.find("商誉 期初余额 本期增加")
    block = flat[start : start + 700]
    rows: list[tuple[str, float, float]] = []
    for label in ("GEA", "Candy", "CCR", "其他"):
        match = re.search(rf"\b{label}\s*([\d,.]+)\s+(?:-?[\d,.]+)\s+(-?[\d,.]+)", block)
        if match:
            rows.append((label, num(match.group(2)), 0.0))
    return rows


def parse_gree(flat: str) -> list[tuple[str, float, float]]:
    gross_start = flat.find("商誉账面原值")
    gross_block = flat[gross_start : gross_start + 900]
    impair_start = flat.find("商誉减值准备", gross_start)
    impair_block = flat[impair_start : impair_start + 900]

    gross: dict[str, float] = {}
    for match in re.finditer(r"([\u4e00-\u9fa5]{3,20}(?:公司|有限公司))\s*([\d,.]+)", gross_block):
        gross.setdefault(match.group(1), num(match.group(2)))

    # 减值表里被投资单位名会跨行断开（如「格力钛新能源股份有 限公司」），
    # 用短关键词定位，再取该行最后一个金额（期末余额）。
    keys = {
        "格力钛新能源": "格力钛新能源股份有限公司",
        "南京华新有色金属": "南京华新有色金属有限公司",
        "合肥晶弘电器": "合肥晶弘电器有限公司",
        "上海大创汽车技术": "上海大创汽车技术有限公司",
    }
    impair: dict[str, float] = {}
    for key, full in keys.items():
        match = re.search(rf"{key}[^\d]{{0,20}}?([\d,.]+(?:\s+[\d,.]+)*)", impair_block)
        if not match:
            continue
        numbers = re.findall(r"[\d,.]+", match.group(0))
        if numbers:
            impair[full] = num(numbers[-1])

    rows: list[tuple[str, float, float]] = []
    for name, value in gross.items():
        rows.append((name, value, impair.get(name, 0.0)))
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

    goodwill = {}
    with (FIN / "资产负债表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row.get("科目") == "商誉" and row.get("报告期") == "20251231":
                try:
                    goodwill[row["公司"]] = float(row["数值"]) / 1e8
                except ValueError:
                    continue

    out_rows: list[list[str]] = []
    for company, (filename, factor) in REPORTS.items():
        pdf = PDF_DIR / filename
        if not pdf.exists():
            continue
        flat = flatten(pdf_text(pdf))
        if company == "美的集团":
            items = parse_midea(flat)
        elif company == "海尔智家":
            items = parse_haier(flat)
        else:
            items = parse_gree(flat)

        total_gross = sum(g * factor / 1e8 for _, g, _ in items)
        total_provision = sum(p * factor / 1e8 for _, _, p in items)
        print(f"  {company}: {len(items)} 个资产组")
        for name, gross, provision in items:
            gross_b = gross * factor / 1e8
            provision_b = provision * factor / 1e8
            net_b = gross_b - provision_b
            out_rows.append(
                [
                    company,
                    name,
                    f"{gross_b:.2f}",
                    f"{provision_b:.2f}",
                    f"{net_b:.2f}",
                    f"{gross_b / total_gross * 100:.2f}" if total_gross else "",
                    "披露值",
                ]
            )
            print(f"    {name:<24}{gross_b:>9.2f}亿  减值 {provision_b:>7.2f}  净 {net_b:>9.2f}")
        out_rows.append(
            [
                company,
                "合计（明细相加）",
                f"{total_gross:.2f}",
                f"{total_provision:.2f}",
                f"{total_gross - total_provision:.2f}",
                "100.00",
                "计算值",
            ]
        )
        out_rows.append(
            [
                company,
                "校验：资产负债表商誉",
                "",
                "",
                f"{goodwill.get(company, 0):.2f}",
                "",
                "计算值",
            ]
        )

    fields = [
        "公司",
        "资产组/被投资单位",
        "商誉原值(亿元)",
        "减值准备(亿元)",
        "账面价值(亿元)",
        "占商誉总额%",
        "数据性质",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(out_rows)
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(out_rows)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
