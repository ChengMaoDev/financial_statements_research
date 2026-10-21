"""提取年报「分部报告」附注。

分部报告比主营构成更细：除收入和成本外，还披露分部利润、资产、负债，
是判断各业务板块真实盈利能力的唯一来源。

三家的分部划分与表格位置完全不同：
- 美的：附注八，智能家居业务/楼宇科技/工业技术/其他分部及未分配
- 海尔：附注「分部信息」，含业务分部与地区信息（美洲、欧洲、南亚等）
- 格力：附注六(6)，消费电器/工业制品及绿色能源/智能装备/其他

用法：
    uv run python3 scripts/extract_segments_note.py --all
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
OUT = ROOT / "财务数据" / "分部报告.csv"

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


def parse_numbers(line: str) -> list[float]:
    """解析一行中的数字。

    年报表格里独立的「-」表示 0，必须计入，否则后续数值会整体左移一位。
    括号表示负值。
    """
    result: list[float] = []
    for token in re.findall(r"\(?[\d,]+\.?\d*\)?|(?<=\s)-(?=\s|$)", line):
        if token == "-":
            result.append(0.0)
            continue
        cleaned = token.replace(",", "")
        negative = cleaned.startswith("(") and cleaned.endswith(")")
        cleaned = cleaned.strip("()")
        try:
            value = float(cleaned)
        except ValueError:
            continue
        result.append(-value if negative else value)
    return result


def clean_line(line: str) -> str:
    """去掉页眉页脚与多余空白。"""
    line = re.sub(r"\d+ / \d+", "", line)
    line = re.sub(
        r"[\u4e00-\u9fa5]+(?:股份有限公司|集团股份有限公司)\s*\d{4}\s*年(?:半)?年度报告(?:全文)?",
        "",
        line,
    )
    line = re.sub(r"\d{4}\s*年财务报表附注", "", line)
    return line.strip()


def extract_meide(text: str, year: str) -> list[dict[str, str]]:
    """美的：附注八 分部报告，列名固定。"""
    rows: list[dict[str, str]] = []
    anchor = text.find("八     分部报告")
    if anchor < 0:
        anchor = text.find("分部报告")
    if anchor < 0:
        return rows
    chunk = text[anchor : anchor + 5000]
    segments = ["智能家居业务", "楼宇科技", "工业技术", "其他分部及未分配", "分部间抵销", "合计"]

    for label in ["对外交易收入", "分部利润", "资产总额", "负债总额"]:
        match = re.search(rf"^\s*{label}\s+([\d,\s\(\)\.-]+)$", chunk, re.MULTILINE)
        if not match:
            continue
        numbers = parse_numbers(match.group(1))[: len(segments)]
        for name, value in zip(segments, numbers, strict=False):
            rows.append(
                {
                    "公司": "美的集团",
                    "年度": year,
                    "分部": name,
                    "指标": label,
                    "数值": f"{value * 1000:.2f}",
                    "单位": "元",
                    "数据性质": "披露值",
                }
            )
    return rows


def extract_geli(text: str, year: str) -> list[dict[str, str]]:
    """格力：「6、分部报告」下的（2）报告分部的财务信息。

    注意：格力的「分部间抵销」列可能为空，此时只有 5 个数（4 分部 + 合计），
    不能简单按 6 列对齐。
    """
    rows: list[dict[str, str]] = []
    anchor = text.find("报告分部的财务信息")
    if anchor < 0:
        return rows
    chunk = text[anchor : anchor + 3000]
    segments = ["消费电器", "工业制品及绿色能源", "智能装备", "其他", "分部间抵销", "合计"]

    for label in ["对外交易收入", "对外交易成本", "资产总额", "负债总额"]:
        match = re.search(rf"^\s*{label}\s+([\d,\s\(\)\.-]+)$", chunk, re.MULTILINE)
        if not match:
            continue
        numbers = parse_numbers(match.group(1))
        # 5 个数说明「分部间抵销」列为空，补 0 占位
        if len(numbers) == 5:
            numbers.insert(4, 0.0)
        numbers = numbers[: len(segments)]
        # 格力年报把「分部间抵销」填成**正数**（表示被抵销的金额），但它在合计里是减项。
        # 若不取负，明细相加会比合计多出一个抵销额（资产 3000+ 亿、负债 3000+ 亿）。
        # 美的同列本身就是负数，所以只有格力需要翻转；对有符号依据的是「合计必须闭合」。
        if numbers[4] > 0:
            subtotal = numbers[5] if len(numbers) > 5 else None
            positive_sum = sum(numbers[:5])
            if subtotal is not None and abs(positive_sum - subtotal) > max(
                1.0, abs(subtotal) * 0.001
            ):
                numbers[4] = -numbers[4]
        for name, value in zip(segments, numbers, strict=False):
            rows.append(
                {
                    "公司": "格力电器",
                    "年度": year,
                    "分部": name,
                    "指标": label,
                    "数值": f"{value:.2f}",
                    "单位": "元",
                    "数据性质": "披露值",
                }
            )
    return rows


def extract_haier(text: str, year: str) -> list[dict[str, str]]:
    """海尔：业务分部 + 地区信息（地区拆分是海尔独有的高价值数据）。"""
    rows: list[dict[str, str]] = []

    # 地区信息：中国大陆、其他国家/地区及其细分
    anchor = text.find("（2） 地区信息")
    if anchor < 0:
        anchor = text.find("地区信息")
    if anchor >= 0:
        chunk = text[anchor : anchor + 2200]
        for region in [
            "中国大陆地区",
            "其他国家/地区",
            "美洲",
            "澳洲",
            "南亚",
            "欧洲",
            "东南亚",
            "中东非",
            "日本",
        ]:
            match = re.search(
                rf"^\s*{region}\s+(-?[\d,]+\.?\d*)\s+(-?[\d,]+\.?\d*)", chunk, re.MULTILINE
            )
            if not match:
                continue
            for index, label in enumerate(["本期", "上期"]):
                value = float(match.group(index + 1).replace(",", ""))
                rows.append(
                    {
                        "公司": "海尔智家",
                        "年度": year,
                        "分部": region,
                        "指标": f"对外交易收入_{label}",
                        "数值": f"{value:.2f}",
                        "单位": "元",
                        "数据性质": "披露值",
                    }
                )
        total = re.search(r"^\s*合计\s+(-?[\d,]+\.?\d*)\s+(-?[\d,]+\.?\d*)", chunk, re.MULTILINE)
        if total:
            for index, label in enumerate(["本期", "上期"]):
                value = float(total.group(index + 1).replace(",", ""))
                rows.append(
                    {
                        "公司": "海尔智家",
                        "年度": year,
                        "分部": "合计",
                        "指标": f"对外交易收入_{label}",
                        "数值": f"{value:.2f}",
                        "单位": "元",
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
            text = pdf_text(pdf)
            if company == "美的集团":
                items = extract_meide(text, year)
            elif company == "格力电器":
                items = extract_geli(text, year)
            else:
                items = extract_haier(text, year)
            rows.extend(items)
            labels = sorted({item["指标"] for item in items})
            if items:
                print(f"  {company} {year}: {len(items)} 条 {labels}")
            else:
                print(f"  {company} {year}: 年报未披露分部数据表（仅列会计政策）")

    if not rows:
        print("未提取到分部数据", file=sys.stderr)
        return 1

    fields = ["公司", "年度", "分部", "指标", "数值", "单位", "数据性质"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
