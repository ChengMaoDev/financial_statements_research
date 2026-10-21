"""提取股份支付费用与股权激励/员工持股计划规模。

为什么重要：
股份支付是「不发钱但计入费用」的激励成本，直接压低当期利润，且三家的处理差异极大：

- **格力**：第三期员工持股计划 2025 年确认费用 **14.46 亿**，占归母净利润 4.99%。
  格力在正文明确写「公司第三期员工持股计划确认的费用总额为 1,446,182,575.49 元」，
  同时披露「扣除股份支付影响后的净利润」。
- **美的**：2025 年度股份支付费用摊销 **8.73 亿**，占归母净利润 1.99%，
  分七个股权激励计划（第八期股票期权、限制性股票等）。
- **海尔**：披露「扣除股份支付影响后的净利润」20,652,748,587.38 元，
  与归母净利润 19,552,798,223 元相差 **11.00 亿**，但正文未单列股份支付费用金额，
  只能从「扣除后净利润」反推。

三种口径：
1. 股份支付费用（利润表影响额）
2. 扣除股份支付影响后的净利润（海尔/格力披露）
3. 反推的股份支付影响 = 扣除后净利润 − 归母净利润（可能含少数股东部分）

注意：海尔的「扣除股份支付影响后的净利润」是**净利润**口径（含少数股东），
不是归母口径，直接与归母净利润相减会混入少数股东损益。本表同时列出两个基数。

用法：
    uv run python3 scripts/extract_share_payment.py --all
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
OUT = FIN / "股份支付.csv"

REPORTS = {
    "美的集团": "美的2025.pdf",
    "海尔智家": "海尔2025.pdf",
    "格力电器": "格力2025.pdf",
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

    profit_parent: dict[str, float] = {}
    profit_total: dict[str, float] = {}
    with (FIN / "利润表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["报告期"] != "20251231":
                continue
            try:
                value = float(row["数值"]) / 1e8
            except ValueError:
                continue
            if row["科目"] == "归属于母公司所有者的净利润":
                profit_parent[row["公司"]] = value
            elif row["科目"] == "净利润":
                profit_total[row["公司"]] = value

    rows: list[list[str]] = []
    for company, filename in REPORTS.items():
        pdf = PDF_DIR / filename
        if not pdf.exists():
            print(f"  缺少 {filename}", file=sys.stderr)
            continue
        flat = flatten(pdf_text(pdf))
        net_parent = profit_parent.get(company, 0.0)
        net_total = profit_total.get(company, 0.0)

        if company == "格力电器":
            match = re.search(r"第三期员工持股计划确认的费用总额为\s*([\d,.]+)\s*元", flat)
            if not match:
                print(f"  {company} 未匹配", file=sys.stderr)
                continue
            expense = num(match.group(1)) / 1e8
            rows.append(
                [
                    company,
                    "2025",
                    "股份支付费用",
                    f"{expense:.2f}",
                    f"{expense / net_parent * 100:.2f}" if net_parent else "",
                    "第三期员工持股计划确认的费用总额",
                    "披露值",
                ]
            )
            print(
                f"  {company}: 股份支付 {expense:,.2f} 亿"
                f"（占归母净利润 {expense / net_parent * 100:.2f}%）"
            )

        elif company == "美的集团":
            match = re.search(r"股份支付激励方案在\s*2025\s*年度的费用摊销为\s*([\d,]+)\s*元", flat)
            if not match:
                print(f"  {company} 未匹配", file=sys.stderr)
                continue
            expense = num(match.group(1)) / 1e8
            rows.append(
                [
                    company,
                    "2025",
                    "股份支付费用",
                    f"{expense:.2f}",
                    f"{expense / net_parent * 100:.2f}" if net_parent else "",
                    "股份支付激励方案 2025 年度费用摊销",
                    "披露值",
                ]
            )
            print(
                f"  {company}: 股份支付 {expense:,.2f} 亿"
                f"（占归母净利润 {expense / net_parent * 100:.2f}%）"
            )

        else:
            # 原始排版：「扣除股份支付影 / 20,652,748,587.38 19,939,606,025.96 ... / 响后的净利润」，
            # 金额夹在标签的两半之间。全文有多个「扣除股份支付影」，必须挑出中间夹着金额的那个。
            after = None
            for match in re.finditer(r"扣除股份支付影(.{0,220}?)响后的净利润", flat, re.DOTALL):
                numbers = re.findall(r"[\d,]{10,}", match.group(1))
                if numbers:
                    after = num(numbers[0]) / 1e8
                    break
            if after is None:
                print(f"  {company} 未匹配", file=sys.stderr)
                continue
            implied = after - net_total
            rows.append(
                [
                    company,
                    "2025",
                    "扣除股份支付影响后净利润",
                    f"{after:.2f}",
                    "",
                    "净利润口径（含少数股东）",
                    "披露值",
                ]
            )
            rows.append(
                [
                    company,
                    "2025",
                    "反推股份支付影响",
                    f"{implied:.2f}",
                    f"{implied / net_parent * 100:.2f}" if net_parent else "",
                    "扣除后净利润 − 净利润（含少数股东），为近似值",
                    "计算值",
                ]
            )
            print(
                f"  {company}: 扣除股份支付后 {after:,.2f} 亿，"
                f"反推影响 {implied:,.2f} 亿（未单列费用金额）"
            )

        rows.append(
            [
                company,
                "2025",
                "归母净利润",
                f"{net_parent:.2f}",
                "100.00",
                "利润表口径",
                "披露值",
            ]
        )

    fields = ["公司", "年度", "项目", "金额(亿元)", "占归母净利润%", "口径说明", "数据性质"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    print("注意：海尔未单列股份支付费用金额，反推值为净利润口径（含少数股东）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
