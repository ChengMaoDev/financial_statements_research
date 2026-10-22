"""提取关联方采购与销售金额，计算对成本/收入的依赖度。

为什么重要：
关联交易规模决定「利润有多少是内部定价的结果」。占比越高，横向比较的
可比性越差，也越需要看定价是否公允。

三家披露口径有实质差异，必须分别处理：
- 美的：采购、销售分两张表，清晰
- 格力：采购、销售分两张表，含经销商关联方
- 海尔：采购表使用「购销商品、提供和接受劳务」模板标题，销售另表披露；
  采购含物流、安装等服务，不能据标题把销售额再并入采购。

两期数据都取自 2025 年报的「本期/上期」两列，保证同一口径。

用法：
    uv run python3 scripts/extract_related_party.py --all
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
OUT = FIN / "关联交易.csv"

# 公司 → (文件, 单位换算, 采购锚点, 销售锚点)
SPECS = {
    "美的集团": (
        "美的2025.pdf",
        1_000,
        r"采购商品和服务\s*关联交易\s*关联方\s*内容\s*2025 年度\s*2024 年度\s*(.+?)\(c\)\s*销售商品",
        r"销售商品和提供服务\s*关联交易\s*关联方\s*内容\s*2025 年度\s*2024 年度\s*(.+?)\(d\)\s*利息收入",
    ),
    "海尔智家": (
        "海尔2025.pdf",
        1,
        r"购销商品、提供和接受劳务的关联交易\s*(.+?)\(2\)\.\s*本公司向关联方销售货物",
        r"本公司向关联方销售货物有关明细资料如下：\s*(.+?)\(3\)\.\s*关联方未结算项目",
    ),
    "格力电器": (
        "格力2025.pdf",
        1,
        r"采购商品/接受劳务情况表\s*(.+?)2\)\s*出售商品/提供劳务情况表",
        r"出售商品/提供劳务情况表\s*(.+?)（2）关联受托管理",
    ),
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


def totals(block: str) -> tuple[float, float]:
    """从区块的「合计」行取本期、上期两个数；美的无「合计」字样，回退取末尾两数。"""
    match = re.search(r"合计\s*([\d,]+(?:\.\d+)?)\s*([\d,]+(?:\.\d+)?)", block)
    if match:
        return float(match.group(1).replace(",", "")), float(match.group(2).replace(",", ""))
    numbers = re.findall(r"[\d,]+(?:\.\d+)?", block)
    if len(numbers) >= 2:
        return (
            float(numbers[-2].replace(",", "")),
            float(numbers[-1].replace(",", "")),
        )
    return 0.0, 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all", action="store_true", default=True, help="默认执行全部；保留该开关用于兼容旧命令"
    )
    args = parser.parse_args()
    if not args.all:  # 默认 True；仅显式 --no-all 时才打印帮助
        parser.print_help()
        return 1

    # 营业成本与营业收入（用于算占比）
    cost: dict[tuple[str, str], float] = {}
    revenue: dict[tuple[str, str], float] = {}
    with (FIN / "利润表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if not row["报告期"].endswith("1231"):
                continue
            try:
                value = float(row["数值"])
            except ValueError:
                continue
            if row["科目"] == "营业成本":
                cost[(row["公司"], row["报告期"][:4])] = value
            elif row["科目"] == "营业收入":
                revenue[(row["公司"], row["报告期"][:4])] = value

    rows: list[list[str]] = []
    for company, (filename, factor, purchase_pattern, sale_pattern) in SPECS.items():
        pdf = PDF_DIR / filename
        if not pdf.exists():
            print(f"  缺少 {filename}", file=sys.stderr)
            continue
        flat = flatten(pdf_text(pdf))

        purchase_match = re.search(purchase_pattern, flat)
        sale_match = re.search(sale_pattern, flat)
        if not purchase_match or not sale_match:
            print(
                f"  {company} 未匹配：采购={bool(purchase_match)} 销售={bool(sale_match)}",
                file=sys.stderr,
            )
            continue

        purchase_now, purchase_prev = totals(purchase_match.group(1))
        sale_now, sale_prev = totals(sale_match.group(1))

        for year, purchase, sale in (
            ("2025", purchase_now, sale_now),
            ("2024", purchase_prev, sale_prev),
        ):
            purchase_b = purchase * factor / 1e8
            sale_b = sale * factor / 1e8
            cost_b = cost.get((company, year), 0.0) / 1e8
            revenue_b = revenue.get((company, year), 0.0) / 1e8
            note = (
                "采购含货物与服务；销售另表。2024为2025年报可比列，可能与2024年报原披露不同"
                if company == "海尔智家"
                else "两期均取2025年报本期与可比列"
            )
            rows.append(
                [
                    company,
                    year,
                    f"{purchase_b:.2f}",
                    f"{sale_b:.2f}",
                    f"{purchase_b / cost_b * 100:.2f}" if cost_b else "",
                    f"{sale_b / revenue_b * 100:.2f}" if revenue_b else "",
                    note,
                    "披露值",
                ]
            )
        print(
            f"  {company}: 采购 {purchase_now * factor / 1e8:,.2f}亿  "
            f"销售 {sale_now * factor / 1e8:,.2f}亿"
        )

    fields = [
        "公司",
        "年度",
        "关联采购(亿元)",
        "关联销售(亿元)",
        "关联采购占营业成本%",
        "关联销售占营业收入%",
        "口径说明",
        "数据性质",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    header = f"{'公司':<8}{'年度':<6}{'关联采购':>10}{'占成本%':>9}{'关联销售':>10}{'占收入%':>9}"
    print()
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row[0]:<8}{row[1]:<6}{float(row[2]):>10.1f}{float(row[4]):>9.2f}"
            f"{float(row[3]):>10.1f}{float(row[5]):>9.2f}"
        )
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
