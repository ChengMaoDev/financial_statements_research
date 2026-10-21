"""交叉校验 akshare 数据与年报 PDF 原文。

「来源绝对可靠」要求每个关键数字都能回溯到一手披露。
本脚本从年报 PDF 抽取「主要会计数据」表，与 akshare 采集值逐项比对，
输出差异报告。任何不一致都必须解释清楚（口径差异 / 提取错误 / 数据源问题）。

用法：
    uv run python3 scripts/verify_against_pdf.py
"""

from __future__ import annotations

import csv
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "年度报告"
DATA_CSV = ROOT / "财务数据" / "主要财务指标.csv"

# 校验目标：2025 年报的 2025 年度值
TARGET_PERIOD = "20251231"

# akshare 指标名 → PDF 中的行标签（年报「主要会计数据」表）
# 注意：PDF 的「营业收入」对应 akshare 的「营业总收入」有口径差，
# 这里分开处理，差异单独报告。
CHECKS = {
    "美的集团": "美的2025.pdf",
    "海尔智家": "海尔2025.pdf",
    "格力电器": "格力2025.pdf",
}


def pdf_text(pdf: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    return result.stdout


def detect_unit(text: str, near_line: int) -> int:
    """判定表格单位。美的年报用千元，海尔/格力用元，差 1000 倍。

    在表格附近向上找最近一次「单位：X」声明。
    """
    lines = text.splitlines()
    for index in range(near_line, max(0, near_line - 60), -1):
        line = lines[index]
        if "单位：千元" in line or "单位:千元" in line:
            return 1000
        if "单位：元" in line or "单位:元" in line:
            return 1
        if "单位：万元" in line or "单位:万元" in line:
            return 10000
    return 1


def find_number_near(text: str, label: str, max_lines: int = 3) -> tuple[float, int] | None:
    """在 label 之后若干行内找第一个大额数字，同时返回单位倍数。"""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if label not in line:
            continue
        # 单位常直接写在标签里，如「营业收入（千元）」
        inline_unit = 1
        if "千元" in line:
            inline_unit = 1000
        elif "万元" in line:
            inline_unit = 10000
        unit = inline_unit if inline_unit != 1 else detect_unit(text, index)
        tail = line.split(label, 1)[1]
        candidates = re.findall(r"\d[\d,]{6,}(?:\.\d+)?", tail)
        if candidates:
            return float(candidates[0].replace(",", "")), unit
        # 跨行：label 单独成行，数字在下一行
        for offset in range(1, max_lines + 1):
            if index + offset >= len(lines):
                break
            candidates = re.findall(r"\d[\d,]{6,}(?:\.\d+)?", lines[index + offset])
            if candidates:
                return float(candidates[0].replace(",", "")), unit
    return None


def load_akshare() -> dict[tuple[str, str], float]:
    values: dict[tuple[str, str], float] = {}
    with DATA_CSV.open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["报告期"] != TARGET_PERIOD:
                continue
            try:
                values[(row["公司"], row["指标"])] = float(row["数值"])
            except ValueError:
                continue
    return values


def main() -> int:
    if not DATA_CSV.exists():
        print(f"缺少 {DATA_CSV}，先运行 fetch_akshare.py", file=sys.stderr)
        return 1

    akshare = load_akshare()
    print(f"载入 akshare {TARGET_PERIOD} 数据 {len(akshare)} 项\n")

    # (公司, PDF标签, akshare指标, 是否允许口径差)
    plan = [
        ("美的集团", "营业收入", "营业总收入", True),
        ("美的集团", "归属于上市公司股东的净利润", "归母净利润", False),
        ("海尔智家", "营业收入", "营业总收入", True),
        ("海尔智家", "归属于上市公司股东的净利润", "归母净利润", False),
        ("格力电器", "营业收入", "营业总收入", True),
        ("格力电器", "归属于上市公司股东的净利润", "归母净利润", False),
    ]

    print(f"{'公司':<8} {'指标':<14} {'PDF':>20} {'akshare':>20} {'差异%':>8} 判定")
    print("-" * 82)
    problems = 0
    for company, pdf_label, ak_key, allow_diff in plan:
        pdf = PDF_DIR / CHECKS[company]
        if not pdf.exists():
            print(f"{company}: 缺少 {pdf.name}")
            problems += 1
            continue
        text = pdf_text(pdf)
        found = find_number_near(text, pdf_label)
        ak_value = akshare.get((company, ak_key))
        if found is None or ak_value is None:
            print(f"{company:<8} {ak_key:<14} {'提取失败' if found is None else '':>20}")
            problems += 1
            continue
        raw_value, unit = found
        pdf_value = raw_value * unit
        unit_label = {1000: "千元", 1: "元", 10000: "万元"}[unit]
        diff = (ak_value - pdf_value) / pdf_value * 100
        if abs(diff) < 0.01:
            verdict = "一致"
        elif allow_diff and abs(diff) < 1.0:
            verdict = "口径差(含其他业务收入)"
        else:
            verdict = "需复核"
            problems += 1
        print(
            f"{company:<8} {ak_key:<14} {pdf_value:>20,.0f} {ak_value:>20,.0f} "
            f"{diff:>7.2f}% {verdict} [{unit_label}]"
        )

    print()
    if problems:
        print(f"{problems} 项需复核")
        return 1
    print("全部一致或已解释")
    return 0


if __name__ == "__main__":
    sys.exit(main())
