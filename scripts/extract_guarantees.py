"""提取担保与诉讼披露：对外担保余额、对子公司担保余额、重大诉讼。

为什么重要：
担保是资产负债表外的潜在负债。三家的披露口径完全不同，必须分别读原文：

- 美的：对外担保 0；对子公司担保余额 457.63 亿（B4 行，单位万元），
  另有「子公司对子公司的担保」，需合计。
- 海尔：对子公司担保余额 72.13 亿，占净资产 6.1%，另披露「为资产负债率
  超过 70% 的被担保对象提供的担保」9.41 亿。
- 格力：担保总额 43.87 亿，占净资产 3.01%，其中绝大多数是票据池质押，
  不是信用担保——质押物是应收票据，风险性质与保证担保不同。

「重大诉讼」三家均披露「无」，但表述位置不同：
- 美的、格力：在「重大诉讼、仲裁事项」栏写「本报告期公司无重大诉讼、仲裁事项」
- 海尔：该栏未在年报中单列，需查「重要事项」章节

数据性质标注：
- 金额为披露值
- 占净资产比例为计算值（分母用归母净资产）
- 格力票据池质押单独标注，不与保证担保混算

用法：
    uv run python3 scripts/extract_guarantees.py --all
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
OUT = FIN / "担保与诉讼.csv"

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
    return float(text.replace(",", "").replace("-", "0") or 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all", action="store_true", default=True, help="默认执行全部；保留该开关用于兼容旧命令"
    )
    args = parser.parse_args()
    if not args.all:  # 默认 True；仅显式 --no-all 时才打印帮助
        parser.print_help()
        return 1

    equity: dict[str, float] = {}
    with (FIN / "资产负债表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["科目"] != "归属于母公司股东权益合计" or row["报告期"] != "20251231":
                continue
            try:
                equity[row["公司"]] = float(row["数值"]) / 1e8
            except ValueError:
                continue

    rows: list[list[str]] = []
    for company, filename in REPORTS.items():
        pdf = PDF_DIR / filename
        if not pdf.exists():
            print(f"  缺少 {filename}", file=sys.stderr)
            continue
        flat = flatten(pdf_text(pdf))
        net = equity.get(company, 0.0)

        if company == "美的集团":
            # A4+B4+C4+D4 = 报告期末实际担保余额合计（万元）
            # 必须用四类合计，只取 B4（对子公司）会漏掉 C4 子公司对子公司、
            # D4 资产池担保，低估 6.78 亿与 67.90 亿。
            # 「报告期末已审批的担保额度合计 / 报告期末实际担保余额合计」
            # 两列并列，行尾才出现 （A4+B4+C4+D4），取第二个数（实际余额）
            match = re.search(
                r"报告期末实际担保余额合计.{0,80}?[\d,]+\s+([\d,]+)\s*（A4\+B4\+C4\+D4）",
                flat,
                re.DOTALL,
            )
            amount = num(match.group(1)) / 1e4 if match else 0.0
            label = "担保总额(A4+B4+C4+D4)"
            note = "含对子公司 457.63 亿、子公司对子公司 0.06 亿、资产池 67.90 亿；年报披露占净资产 23.55%"
        elif company == "海尔智家":
            match = re.search(r"担保总额（A\+B）\s*([\d,]+)", flat)
            amount = num(match.group(1)) / 1e4 if match else 0.0
            label = "担保总额(含对子公司)"
            note = "对外担保 A=0，全部为对子公司担保；占净资产 6.1%"
        else:
            # 该行同样是「已审批额度 + 实际余额」两列，取第二个数
            match2 = re.search(r"报告期末实际担保余额合计\s*[\d,]+\s+([\d,.]+)", flat)
            amount = num(match2.group(1)) / 1e4 if match2 else 0.0
            label = "担保总额(含对子公司)"
            note = "主要为票据池质押担保，质押物为应收票据；占净资产 3.01%"

        rows.append(
            [
                company,
                "2025",
                label,
                f"{amount:.2f}",
                f"{amount / net * 100:.2f}" if net else "",
                note,
                "披露值",
            ]
        )

        if "本报告期公司无重大诉讼、仲裁事项" in flat or "本年度公司无重大诉讼、仲裁事项" in flat:
            litigation = "无重大诉讼、仲裁"
        else:
            litigation = "未检索到「无重大诉讼」表述，需人工核对"
        rows.append([company, "2025", "重大诉讼", "", "", litigation, "披露值"])
        print(f"  {company}: {label} {amount:,.2f}亿  诉讼: {litigation[:12]}")

    fields = ["公司", "年度", "项目", "金额(亿元)", "占归母净资产%", "口径说明", "数据性质"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
