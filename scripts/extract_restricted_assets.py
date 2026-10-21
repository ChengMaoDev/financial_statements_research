"""提取受限资产（所有权或使用权受限制的资产），并计算占总资产比例。

为什么重要：
受限资产是「账上有、但用不了」的部分，直接削弱清偿能力。三家披露形式完全不同：

- **美的**：正文「截至报告期末的资产权利受限情况」明确写
  「公司不存在主要资产被查封、扣押、冻结或者被抵押、质押等权利受限情形」。
  但附注里仍有受限资金（保证金等），两者口径不同——正文说的是「主要资产」。
- **格力**：附注「所有权或使用权受限资产」有完整明细表，合计 479.63 亿，
  占总资产 12.26%。其中最大两项是「其他非流动资产 133.00 亿（质押）」
  与「一年内到期的非流动资产 104.70 亿（质押）」——这是定期存款质押开票，
  属于票据池业务的抵押，不是经营资产受限。
- **海尔**：没有单列受限资产表，只有「不属于现金及现金等价物的货币资金」
  一项，需从现金等价物附表取数。

本表按「项目 / 账面价值 / 受限原因」逐项列出格力明细，美的与海尔只列汇总，
并在口径说明里注明披露差异。**三家不可横向比较规模**，只能各自看趋势与结构。

用法：
    uv run python3 scripts/extract_restricted_assets.py --all
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
OUT = FIN / "受限资产.csv"

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

    assets: dict[str, float] = {}
    with (FIN / "资产负债表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["科目"] != "资产总计" or row["报告期"] != "20251231":
                continue
            try:
                assets[row["公司"]] = float(row["数值"]) / 1e8
            except ValueError:
                continue

    rows: list[list[str]] = []
    for company, filename in REPORTS.items():
        pdf = PDF_DIR / filename
        if not pdf.exists():
            print(f"  缺少 {filename}", file=sys.stderr)
            continue
        flat = flatten(pdf_text(pdf))
        total_assets = assets.get(company, 0.0)

        if company == "格力电器":
            # 这张表分「期末」与「（续）期初」两段，必须在「（续）」处截断，
            # 否则期初数据会混进本期，项目数翻倍、合计翻倍。
            start = flat.find("所有权或使用权受限资产")
            end = flat.find("（续）", start)
            block = flat[start : end if end > 0 else start + 1600]
            # 跨页时表头会重复出现（「期末 项目 账面价值 受限原因」），
            # 夹在金额与下一项目之间会让正则的前瞻锚点失效，先剔除。
            block = block.replace("期末 项目 账面价值 受限原因", " ")
            items = []
            names = (
                "货币资金|应收账款|应收款项融资|合同资产|其他流动资产"
                "|一年内到期的非流动资产|其他债权投资|长期股权投资"
                "|投资性房地产|固定资产|在建工程|无形资产|其他非流动资产"
            )
            # 项目名 + 金额 + 受限原因；用下一项目名或「合计」作为结束锚点
            pattern = re.compile(
                rf"({names})\s+([\d,.]+)\s+([\u4e00-\u9fa5A-Za-z、，]{{2,20}})"
                rf"(?=\s+(?:{names}|合计))"
            )
            for match in pattern.finditer(block):
                items.append(
                    (
                        match.group(1),
                        num(match.group(2)) / 1e8,
                        re.sub(r"\s+", "", match.group(3)),
                    )
                )

            total_match = re.search(r"合计\s*([\d,.]+)", block)
            total = num(total_match.group(1)) / 1e8 if total_match else sum(i[1] for i in items)

            for name, value, reason in items:
                rows.append(
                    [
                        company,
                        "2025",
                        name,
                        f"{value:.2f}",
                        f"{value / total_assets * 100:.2f}" if total_assets else "",
                        reason,
                        "披露值",
                    ]
                )
            rows.append(
                [
                    company,
                    "2025",
                    "合计",
                    f"{total:.2f}",
                    f"{total / total_assets * 100:.2f}" if total_assets else "",
                    "明细相加",
                    "披露值",
                ]
            )
            print(
                f"  {company}: {len(items)} 项，合计 {total:,.2f} 亿"
                f"（占总资产 {total / total_assets * 100:.2f}%）"
            )

        elif company == "美的集团":
            no_restriction = (
                "公司不存在主要资产被查封、扣押、冻结或者被抵押、质押等权利受限情形" in flat
            )
            rows.append(
                [
                    company,
                    "2025",
                    "主要资产",
                    "",
                    "",
                    "正文明确「不存在主要资产被查封、扣押、冻结或抵押质押」（附注另有保证金等受限资金）"
                    if no_restriction
                    else "需人工核对",
                    "披露值",
                ]
            )
            print(f"  {company}: 正文声明无主要资产受限（附注口径另计）")

        else:
            # 海尔：不属于现金及现金等价物的货币资金
            block = flat[flat.find("不属于现金及现金等价物的货币资金") :][:300]
            match = re.search(r"([\d,.]+)\s+([\d,.]+)", block)
            if match:
                value = num(match.group(1)) / 1e8
                rows.append(
                    [
                        company,
                        "2025",
                        "不属于现金及现金等价物的货币资金",
                        f"{value:.2f}",
                        f"{value / total_assets * 100:.2f}" if total_assets else "",
                        "无单列受限资产表；仅货币资金口径",
                        "披露值",
                    ]
                )
                print(f"  {company}: 受限货币资金 {value:,.2f} 亿")
            else:
                print(f"  {company}: 未匹配", file=sys.stderr)

    fields = [
        "公司",
        "年度",
        "项目",
        "账面价值(亿元)",
        "占总资产%",
        "受限原因/口径说明",
        "数据性质",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    print("注意：三家披露粒度不同，合计口径不可横向比较")
    return 0


if __name__ == "__main__":
    sys.exit(main())
