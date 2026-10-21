"""提取各期中期分红方案，覆盖 2026 年半年报。

为什么重要：
三家的中期分红政策差异极大，只看年度分红会漏掉一半信息：

- 美的：2024 年起每年中期派息。2025 中期 10 派 5 元（37.24 亿），
  2026 中期同样是 10 派 5 元，另以回购方式分红 69.66 亿，
  中期分红总额 106.91 亿，占 2026H1 归母净利润 40.4%。
- 海尔：2026 半年报明确「是否分配或转增：否」，中期不分红。
  2025 年度的中期分红是在年报里作为「年度+中期合计」的一部分披露的。
- 格力：2026 半年报写「结合公司经营情况、资金需求等因素另行决定中期利润分配事宜」，
  实际是暂不分配。但格力历史上多次做中期分红（如 2024 年 10 派 10 元）。

「是否分配」的表述三家完全不同：
- 美的：「以……为基数，向全体股东每 10 股派发现金 5 元」
- 海尔：「是否分配或转增　否」
- 格力：「另行决定中期利润分配事宜」（等于暂不分配，但不是明确否定）

本表把 2026H1 的中期分红方案结构化，并计算占当期归母净利润的比例。
格力留空标注「另行决定」，不填 0。

用法：
    uv run python3 scripts/extract_interim_dividend.py --all
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
OUT = FIN / "中期分红.csv"

REPORTS = {
    "美的集团": "美的2026半年度.pdf",
    "海尔智家": "海尔2026半年度.pdf",
    "格力电器": "格力2026半年度.pdf",
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all", action="store_true", default=True, help="默认执行全部；保留该开关用于兼容旧命令"
    )
    args = parser.parse_args()
    if not args.all:  # 默认 True；仅显式 --no-all 时才打印帮助
        parser.print_help()
        return 1

    profit: dict[str, float] = {}
    with (FIN / "利润表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["报告期"] != "20260630":
                continue
            if row["科目"] != "归属于母公司所有者的净利润":
                continue
            try:
                profit[row["公司"]] = float(row["数值"]) / 1e8
            except ValueError:
                continue

    rows: list[list[str]] = []
    for company, filename in REPORTS.items():
        pdf = PDF_DIR / filename
        if not pdf.exists():
            print(f"  缺少 {filename}", file=sys.stderr)
            continue
        flat = flatten(pdf_text(pdf))
        net = profit.get(company, 0.0)

        if company == "美的集团":
            per10 = re.search(r"每 10 股派发现金\s*([\d.]+)\s*元", flat)
            cash = re.search(r"合计现金分红总额为\s*([\d,]+)\s*元", flat)
            other = re.search(r"以其他方式（如回购股份）现金分红金额（元）\s*([\d,]+)", flat)
            total = re.search(r"现金分红总额（含其他方式）\s*（元）\s*([\d,]+)", flat)
            ratio = re.search(
                r"半年度现金\s*分红总额占归属于上市公司股东的净利润比例为\s*([\d.]+)%", flat
            )

            cash_b = num(cash.group(1)) / 1e8 if cash else 0.0
            other_b = num(other.group(1)) / 1e8 if other else 0.0
            total_b = num(total.group(1)) / 1e8 if total else cash_b + other_b

            rows.append(
                [
                    company,
                    "2026H1",
                    "每股派息(元/10股)",
                    f"{per10.group(1) if per10 else ''}",
                    "",
                    "",
                    "披露值",
                ]
            )
            # 年报披露的 14.06% 只算「现金分红」3,724,298,992 元，
            # **不含**回购 69.66 亿。两者相差 26 个百分点，必须分两行，
            # 否则会把「含回购回报率」误当成「分红率」。
            rows.append(
                [
                    company,
                    "2026H1",
                    "现金分红",
                    f"{cash_b:.2f}",
                    f"{cash_b / net * 100:.2f}" if net else "",
                    f"{ratio.group(1)}%" if ratio else "",
                    "披露值",
                ]
            )
            rows.append(
                [
                    company,
                    "2026H1",
                    "回购方式分红",
                    f"{other_b:.2f}",
                    f"{other_b / net * 100:.2f}" if net else "",
                    "",
                    "披露值",
                ]
            )
            rows.append(
                [
                    company,
                    "2026H1",
                    "分红+回购合计",
                    f"{total_b:.2f}",
                    f"{total_b / net * 100:.2f}" if net else "",
                    "",
                    "计算值",
                ]
            )
            print(
                f"  {company}: 现金 {cash_b:.2f}亿（{cash_b / net * 100:.2f}%）"
                f" + 回购 {other_b:.2f}亿 = {total_b:.2f}亿（{total_b / net * 100:.2f}%）"
            )
        elif company == "海尔智家":
            no = re.search(r"是否分配或转增\s*否", flat)
            rows.append(
                [
                    company,
                    "2026H1",
                    "中期分红",
                    "0.00",
                    "0.00",
                    "",
                    "披露值（「是否分配或转增：否」）" if no else "需核对",
                ]
            )
            print(f"  {company}: 中期不分红（原文明示「是否分配或转增 否」）")
        else:
            defer = "另行决定中期利润分配事宜" in flat
            rows.append(
                [
                    company,
                    "2026H1",
                    "中期分红",
                    "",
                    "",
                    "",
                    "未分配（原文「另行决定中期利润分配事宜」）" if defer else "需核对",
                ]
            )
            print(f"  {company}: 中期暂不分配（原文「另行决定」，非明确否定）")

    fields = ["公司", "期间", "项目", "金额(亿元)", "占归母净利润%", "年报披露比例", "数据性质"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
