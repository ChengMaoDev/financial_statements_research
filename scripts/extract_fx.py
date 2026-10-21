"""提取汇兑损益，统一为「正数=收益、负数=损失」，并计算对归母净利润的影响。

为什么重要：
2025 年人民币汇率波动让三家的汇兑方向完全反转。海尔的海外收入占比最高，
汇兑从 2024 年损失 1.19 亿变成 2025 年收益 10.01 亿，一正一负相差 11.20 亿，
相当于当年归母净利润的 5.7%。如果不剥离，会误判海尔的经营改善幅度。

符号陷阱（本表已统一）：
- 美的在「财务收入」表里列示，括号表示负数，汇兑损益 (234,369) 千元 = 损失 2.34 亿
- 海尔在「财务费用」表里列示，明确写「收益以“－”填列」，-10.01 亿 = 收益 10.01 亿
- 格力在「财务费用」表里以「加：汇兑损益」列示，-2.51 亿 = 收益 2.51 亿

三家符号方向相反，直接抄数会得到完全错误的结论。

用法：
    uv run python3 scripts/extract_fx.py --all
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
OUT = FIN / "汇兑损益.csv"

# 公司 → (文件, 单位, 是否已在「财务费用」口径下把收益记为正)
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


def extract(company: str, flat: str) -> tuple[float, float] | None:
    if company == "美的集团":
        # 财务收入表：汇兑损益 (234,369) (1,398,470)，括号即负
        match = re.search(r"汇兑损益\s*\(([\d,]+)\)\s*\(([\d,]+)\)", flat)
        if not match:
            return None
        # 括号是损失，统一成「正=收益」要取负
        return -num(match.group(1)), -num(match.group(2))

    if company == "海尔智家":
        # 财务费用表：收益以「－」填列，负号即收益，取负得到「正=收益」
        match = re.search(r"汇兑损益（收益以[“\"]－[”\"]填列）\s*(-?[\d,.]+)\s*(-?[\d,.]+)", flat)
        if not match:
            return None
        return -num(match.group(1)), -num(match.group(2))

    # 格力：加：汇兑损益 -251,325,953.52 250,076,580.51
    match = re.search(r"加：汇兑损益\s*(-?[\d,.]+)\s*(-?[\d,.]+)", flat)
    if not match:
        return None
    return -num(match.group(1)), -num(match.group(2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all", action="store_true", default=True, help="默认执行全部；保留该开关用于兼容旧命令"
    )
    args = parser.parse_args()
    if not args.all:  # 默认 True；仅显式 --no-all 时才打印帮助
        parser.print_help()
        return 1

    profit = {}
    with (FIN / "利润表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["科目"] != "归属于母公司所有者的净利润":
                continue
            if not row["报告期"].endswith("1231"):
                continue
            try:
                profit[(row["公司"], row["报告期"][:4])] = float(row["数值"]) / 1e8
            except ValueError:
                continue

    revenue = {}
    with (FIN / "利润表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["科目"] != "营业收入" or not row["报告期"].endswith("1231"):
                continue
            try:
                revenue[(row["公司"], row["报告期"][:4])] = float(row["数值"]) / 1e8
            except ValueError:
                continue

    rows: list[list[str]] = []
    for company, (filename, factor) in REPORTS.items():
        pdf = PDF_DIR / filename
        if not pdf.exists():
            print(f"  缺少 {filename}", file=sys.stderr)
            continue
        flat = flatten(pdf_text(pdf))
        result = extract(company, flat)
        if result is None:
            print(f"  {company} 未匹配到汇兑损益", file=sys.stderr)
            continue

        for year, raw in zip(("2025", "2024"), result, strict=True):
            value = raw * factor / 1e8
            net = profit.get((company, year), 0.0)
            rev = revenue.get((company, year), 0.0)
            rows.append(
                [
                    company,
                    year,
                    f"{value:.2f}",
                    f"{value / net * 100:.2f}" if net else "",
                    f"{value / rev * 100:.2f}" if rev else "",
                    "收益" if value > 0 else "损失",
                    "披露值（已统一为 正=收益）",
                ]
            )
        print(
            f"  {company}: 2025 {result[0] * factor / 1e8:+.2f}亿  "
            f"2024 {result[1] * factor / 1e8:+.2f}亿"
        )

    fields = [
        "公司",
        "年度",
        "汇兑损益(亿元)",
        "占归母净利润%",
        "占营业收入%",
        "方向",
        "数据性质",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    header = f"{'公司':<8}{'年度':<6}{'汇兑损益(亿)':>13}{'占归母净利%':>12}  方向"
    print()
    print(header)
    print("-" * len(header))
    for row in rows:
        print(f"{row[0]:<8}{row[1]:<6}{float(row[2]):>13.2f}{float(row[3]):>12.2f}  {row[5]}")
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
