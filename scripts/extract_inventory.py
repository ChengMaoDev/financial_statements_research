"""提取年报附注「存货分类」：原材料/在产品/库存商品/开发成本等。

三家口径差异（不可强行对齐）：
- 美的：千元；库存商品/原材料/在产品/委托加工物资/合同履约成本
- 海尔：元；原材料/在产品/库存商品（三项）
- 格力：元；原材料/在产品及合同履约成本/产成品/开发成本/开发产品
  格力含房地产业务存货（开发成本、开发产品），与家电主业不可比。

这张表的价值：
- 原材料占比高 → 对大宗商品价格敏感
- 库存商品占比高 → 渠道压货或备货，跌价风险
- 跌价准备计提率 → 会计稳健性

用法：
    uv run python3 scripts/extract_inventory.py --all
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
OUT = ROOT / "财务数据" / "存货明细.csv"

REPORTS = {
    "美的集团": ["美的2024.pdf", "美的2025.pdf"],
    "海尔智家": ["海尔2024.pdf", "海尔2025.pdf"],
    "格力电器": ["格力2024.pdf", "格力2025.pdf"],
}

# 标准化类别；「原口径」保留年报用词
CATEGORY_MAP = {
    "原材料": "原材料",
    "在产品": "在产品",
    "在产品及合同履约成本": "在产品及合同履约成本",
    "库存商品": "库存商品",
    "产成品": "产成品",
    "委托加工物资": "委托加工物资",
    "合同履约成本": "合同履约成本",
    "开发成本": "开发成本",
    "开发产品": "开发产品",
    "周转材料": "周转材料",
}

# 各公司报表单位
UNIT = {"美的集团": 1_000, "海尔智家": 1, "格力电器": 1}


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


def extract(flat: str, company: str, year: str) -> list[dict[str, str]]:
    # 定位存货分类表：优先「存货分类」「存货明细情况」，找不到再退到附注标题
    start = -1
    for marker in ("存货分类", "存货明细情况", "存货的分类"):
        pos = flat.find(marker)
        if pos > 0:
            start = pos
            break
    if start < 0:
        return []

    pattern = "|".join(sorted((re.escape(k) for k in CATEGORY_MAP), key=len, reverse=True))

    # 表头里也有「存货跌价准备/合同履约成本减值准备」字样，必须从第一个
    # 「类别 + 数字」的位置开始，否则会把表头当成数据行
    first = re.search(rf"(?:{pattern})\s*[\d(]", flat[start : start + 1200])
    if not first:
        return []
    block_start = start + first.start()
    block = flat[block_start : block_start + 1200]

    # 只保留「期末余额」表：遇到续表/期初标记就截断
    for stop_marker in ("（续表）", "（续）", "期初余额", "期初数"):
        stop = block.find(stop_marker)
        if stop > 0:
            block = block[:stop]

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    factor = UNIT[company]

    # 先切出所有类别标签的位置，每行只取到下一个标签之前，避免串行
    label_hits = list(re.finditer(pattern, block))
    for index, match in enumerate(label_hits):
        raw = match.group(0)
        if raw in seen:
            continue
        stop = label_hits[index + 1].start() if index + 1 < len(label_hits) else match.end() + 120
        tail = block[match.end() : min(stop, match.end() + 120)]
        # 「合计」行不属于任何类别，遇到就截断，避免把合计金额当成账面价值
        total_pos = tail.find("合计")
        if total_pos > 0:
            tail = tail[:total_pos]
        tokens = re.findall(r"\([\d,]+(?:\.\d+)?\)|[\d,]+(?:\.\d+)?|-", tail)[:3]
        if len(tokens) < 2:
            continue

        def to_float(token: str) -> float:
            if token == "-":
                return 0.0
            return float(token.strip("()").replace(",", ""))

        parsed = [to_float(t) for t in tokens]
        seen.add(raw)

        if len(parsed) >= 3:
            balance, provision, value = parsed[0], parsed[1], parsed[2]
        else:
            balance, provision, value = parsed[0], 0.0, parsed[1]

        rows.append(
            {
                "公司": company,
                "年度": year,
                "存货类别": CATEGORY_MAP[raw],
                "原口径类别": raw,
                "账面余额(亿元)": f"{balance * factor / 1e8:.2f}",
                "跌价准备(亿元)": f"{provision * factor / 1e8:.2f}",
                "账面价值(亿元)": f"{value * factor / 1e8:.2f}",
                "计提率%": f"{provision / balance * 100:.2f}" if balance else "",
                "数据性质": "披露值",
            }
        )

    if rows:
        total_balance = sum(float(r["账面余额(亿元)"]) for r in rows)
        total_provision = sum(float(r["跌价准备(亿元)"]) for r in rows)
        rows.append(
            {
                "公司": company,
                "年度": year,
                "存货类别": "合计（分项相加）",
                "原口径类别": "计算",
                "账面余额(亿元)": f"{total_balance:.2f}",
                "跌价准备(亿元)": f"{total_provision:.2f}",
                "账面价值(亿元)": f"{total_balance - total_provision:.2f}",
                "计提率%": f"{total_provision / total_balance * 100:.2f}" if total_balance else "",
                "数据性质": "计算值",
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
            year = re.search(r"(20\d{2})", filename).group(1)
            items = extract(flatten(pdf_text(pdf)), company, year)
            rows.extend(items)
            print(f"  {company} {year}: {len(items)} 类")
            for item in items:
                if item["存货类别"] != "合计（分项相加）":
                    print(
                        f"    {item['存货类别']:<12}{item['账面余额(亿元)']:>9}亿  计提{item['计提率%']:>5}%"
                    )

    fields = [
        "公司",
        "年度",
        "存货类别",
        "原口径类别",
        "账面余额(亿元)",
        "跌价准备(亿元)",
        "账面价值(亿元)",
        "计提率%",
        "数据性质",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
