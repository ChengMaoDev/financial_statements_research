"""构建渠道返利规模与上下游占款表。

为什么这张表重要：
家电行业普遍对经销商「先收款/后返利」，销售返利计提在「其他流动负债」，
本质是公司无偿占用的经销商资金。返利规模越大、越稳定，说明渠道话语权越强，
但也意味着未来要以价格折让兑现，是利润的「隐性负债」。

美的与格力把「预提销售返利」单列在附注中；海尔只披露计提政策，未单列金额，
因此海尔该列留空，不可用 0 填充。

上下游占款（净额，正数=占用上下游资金）：
  占用 = 应付票据 + 应付账款 + 合同负债 + 预提销售返利
  被占 = 应收票据 + 应收账款 + 应收款项融资 + 预付款项 + 存货 + 合同资产

用法：
    uv run python3 scripts/build_channel_float.py
"""

from __future__ import annotations

import csv
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIN = ROOT / "财务数据"
PDF_DIR = ROOT / "年度报告"
OUT = FIN / "渠道返利与占款.csv"

COMPANIES = ["美的集团", "海尔智家", "格力电器"]
YEARS = [str(y) for y in range(2023, 2027)]

# 返利披露位置与单位
REBATE = {
    "美的集团": ("预提销售返利", 1_000),
    "格力电器": ("销售返利", 1),
}

OCCUPY = ["应付票据", "应付账款", "合同负债"]
OCCUPIED = ["应收票据", "应收账款", "应收款项融资", "预付款项", "存货", "合同资产"]


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


def rebate_from_pdf(company: str, year: str) -> float | None:
    label, factor = REBATE[company]
    pdf = PDF_DIR / f"{company[:2]}{year}.pdf"
    if not pdf.exists():
        return None
    flat = flatten(pdf_text(pdf))
    match = re.search(rf"{re.escape(label)}\s*([\d,]+(?:\.\d+)?)", flat)
    if not match:
        return None
    return float(match.group(1).replace(",", "")) * factor / 1e8


def load_bs() -> dict[tuple[str, str], dict[str, float]]:
    out: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    with (FIN / "资产负债表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            period = row.get("报告期", "")
            if len(period) != 8 or not period.endswith("1231"):
                continue
            try:
                out[(row["公司"], period[:4])][row["科目"]] = float(row["数值"])
            except (ValueError, KeyError):
                continue
    return out


def main() -> int:
    bs = load_bs()
    rebates = {
        (company, year): rebate_from_pdf(company, year)
        for company in REBATE
        for year in ("2023", "2024", "2025")
    }

    rows: list[list[str]] = []
    for company in COMPANIES:
        for year in YEARS:
            data = bs.get((company, year))
            if not data:
                continue
            occupy = sum(data.get(k, 0.0) for k in OCCUPY) / 1e8
            occupied = sum(data.get(k, 0.0) for k in OCCUPIED) / 1e8
            rebate = rebates.get((company, year))
            # 返利只对 2023-2025 做了提取；更早年份留空
            occupy_with_rebate = occupy + rebate if rebate is not None else None

            rows.append(
                [
                    company,
                    year,
                    f"{rebate:.2f}" if rebate is not None else "",
                    f"{occupy:.2f}",
                    f"{occupied:.2f}",
                    f"{occupy - occupied:.2f}",
                    f"{occupy_with_rebate - occupied:.2f}"
                    if occupy_with_rebate is not None
                    else "",
                    "计算值",
                ]
            )

    fields = [
        "公司",
        "年度",
        "预提销售返利(亿元)",
        "占用上下游合计(亿元)",
        "被占用合计(亿元)",
        "净占款-不含返利(亿元)",
        "净占款-含返利(亿元)",
        "数据性质",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    header = f"{'公司':<8}{'年度':<6}{'销售返利':>10}{'净占款':>10}{'含返利':>10}"
    print(header)
    print("-" * len(header))
    for row in rows:
        if row[1] >= "2022":
            print(f"{row[0]:<8}{row[1]:<6}{row[2]:>10}{row[5]:>10}{row[6]:>10}")
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    print("海尔未单列销售返利金额，留空而非填 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
