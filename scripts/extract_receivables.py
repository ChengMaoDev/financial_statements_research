"""提取应收账款规模与坏账准备，并与资产负债表交叉校验。

三家披露结构不同，这里只取三个任何一家都能对上的数：
1. 应收账款账面余额（计提坏账前）
2. 坏账准备余额
3. 应收账款净额 = 1 − 2，必须等于资产负债表「应收账款」

账龄分档各家用词、分档边界、是否按账龄计提都不一致（美的按境内/境外业务组合，
海尔/格力按账龄），强行对齐会失真，因此不在本表展开，只记录整体计提率。

用法：
    uv run python3 scripts/extract_receivables.py --all
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
OUT = FIN / "应收账款质量.csv"

REPORTS = [
    ("美的集团", "美的2025.pdf", "2025", 1_000),
    ("海尔智家", "海尔2025.pdf", "2025", 1),
    ("格力电器", "格力2025.pdf", "2025", 1),
]

NOTE = {
    "美的集团": "组合预期信用损失模型（境内 3.89%、境外 1.07%），无账龄分档计提",
    "海尔智家": "账龄组合（1 年以内 1.24%、3 年以上 64.56%）",
    "格力电器": "账龄组合（1 年以内 3.34%、3 年以上 97.81%）+ 单项 100%",
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


def parse_midea(flat: str) -> tuple[float, float]:
    combo1 = re.search(r"境内业务组合\s*([\d,]+)\s*([\d.]+)%\s*\(([\d,]+)\)", flat)
    combo2 = re.search(r"境外业务组合\s*([\d,]+)\s*([\d.]+)%\s*\(([\d,]+)\)", flat)
    single1 = re.search(r"境内客户\s*([\d,]+)\s*([\d.]+)%\s*\(([\d,]+)\)", flat)
    single2 = re.search(r"境外客户\s*([\d,]+)\s*([\d.]+)%\s*\(([\d,]+)\)", flat)
    gross = provision = 0.0
    for match in (combo1, combo2, single1, single2):
        if match:
            gross += num(match.group(1))
            provision += num(match.group(3))
    return gross, provision


def parse_haier(flat: str) -> tuple[float, float]:
    match = re.search(r"合计\s*([\d,.]+)\s*100\.00\s*([\d,.]+)\s*([\d.]+)\s*([\d,.]+)", flat)
    if not match:
        return 0.0, 0.0
    return num(match.group(1)), num(match.group(2))


def parse_gree(flat: str) -> tuple[float, float]:
    gross = 0.0
    provision = 0.0

    # 1) 单项计提余额：「共 N 家单位」行
    single = re.search(r"共 \d+ 家单位\s*([\d,.]+)", flat)
    if single:
        gross += num(single.group(1))

    # 2) 账龄组合小计：紧跟在 3 年以上 行之后的 合计 行
    aging = re.search(
        r"3 年以上\s*([\d,.]+)\s*([\d,.]+)\s*([\d.]+)\s*合计\s*([\d,.]+)\s*([\d,.]+)\s*([\d.]+)",
        flat,
    )
    if aging:
        gross += num(aging.group(4))

    # 3) 低风险组合余额
    low = re.search(r"低风险组合\s*([\d,.]+)\s*([\d,.]+)\s*([\d.]+)", flat)
    if low:
        gross += num(low.group(1))

    # 4) 坏账准备期末余额：在「本期计提、收回或转回」变动表内逐行取
    anchor = flat.find("本期计提、收回或转回的坏账准备情况")
    if anchor < 0:
        return gross, 0.0
    movement = flat[anchor : anchor + 700]
    for label in ("单项计提", "账龄组合", "低风险组合"):
        row = re.search(
            rf"{label}\s*([\d,.]+)\s*(-?[\d,.]+)\s*([\d,.]+)(?:\s*([\d,.]+))?", movement
        )
        if not row:
            continue
        last = row.group(4) if row.group(4) else row.group(3)
        try:
            provision += num(last)
        except ValueError:
            continue
    return gross, provision


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all", action="store_true", default=True, help="默认执行全部；保留该开关用于兼容旧命令"
    )
    args = parser.parse_args()
    if not args.all:  # 默认 True；仅显式 --no-all 时才打印帮助
        parser.print_help()
        return 1

    net = {}
    with (FIN / "资产负债表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row.get("科目") == "应收账款" and row.get("报告期") == "20251231":
                try:
                    net[row["公司"]] = float(row["数值"]) / 1e8
                except ValueError:
                    continue

    rows: list[list[str]] = []
    for company, filename, year, factor in REPORTS:
        pdf = PDF_DIR / filename
        if not pdf.exists():
            continue
        flat = flatten(pdf_text(pdf))
        if company == "美的集团":
            gross, provision = parse_midea(flat)
        elif company == "海尔智家":
            gross, provision = parse_haier(flat)
        else:
            gross, provision = parse_gree(flat)

        gross_b = gross * factor / 1e8
        provision_b = provision * factor / 1e8
        net_calc = gross_b - provision_b
        net_actual = net.get(company, 0.0)
        rows.append(
            [
                company,
                year,
                f"{gross_b:.2f}",
                f"{provision_b:.2f}",
                f"{provision_b / gross_b * 100:.2f}" if gross_b else "",
                f"{net_calc:.2f}",
                f"{net_actual:.2f}",
                f"{net_calc - net_actual:+.2f}",
                NOTE[company],
                "计算值",
            ]
        )
        print(
            f"  {company}: 余额 {gross_b:,.2f}亿  坏账 {provision_b:,.2f}亿  "
            f"计提 {provision_b / gross_b * 100:.2f}%  净额 {net_calc:,.2f} / 报表 {net_actual:,.2f}"
        )

    fields = [
        "公司",
        "年度",
        "应收账款余额(亿元)",
        "坏账准备(亿元)",
        "整体计提率%",
        "净额(亿元)",
        "资产负债表净额(亿元)",
        "差异(亿元)",
        "计提方法",
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
