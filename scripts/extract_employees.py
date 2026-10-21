"""提取年报「员工情况」：专业构成、教育程度、人均薪酬。

三家的分类维度不统一，必须按各自口径原样保留，不能强行对齐：
- 美的：制造/销售/研发/财务/行政；教育程度含「其他」「隐私保护」两项
- 海尔：生产/销售/技术/财务/行政；教育程度为本科及以上/专科/中专及以下
- 格力：生产/销售/技术/财务/行政；教育程度为本科及以上/大学专科/中专及以下

薪酬总额取自现金流量表「支付给职工以及为职工支付的现金」，
与员工人数相除得到人均薪酬（含社保，不等于到手工资）。

用法：
    uv run python3 scripts/extract_employees.py --all
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
OUT = ROOT / "财务数据" / "员工构成.csv"
PAYROLL = ROOT / "财务数据" / "现金流量表.csv"

REPORTS = {
    "美的集团": ["美的2023.pdf", "美的2024.pdf", "美的2025.pdf"],
    "海尔智家": ["海尔2023.pdf", "海尔2024.pdf", "海尔2025.pdf"],
    "格力电器": ["格力2023.pdf", "格力2024.pdf", "格力2025.pdf"],
}

# 专业构成：各家用词不同，统一映射到标准类别
ROLE_MAP = {
    "制造人员": "生产人员",
    "生产人员": "生产人员",
    "销售人员": "销售人员",
    "研发人员": "技术人员",
    "技术人员": "技术人员",
    "财务人员": "财务人员",
    "行政人员": "行政人员",
}

# 教育程度映射（保持原口径标签，只做合并）
EDU_MAP = {
    "博士、硕士": "硕士及以上",
    "博士": "硕士及以上",
    "硕士": "硕士及以上",
    "本科及以上": "本科及以上",
    "大学本科": "本科",
    "大学专科": "专科",
    "专科": "专科",
    "中专及以下": "中专及以下",
    "高中及以下": "中专及以下",
    "其他": "其他",
    "隐私保护": "隐私保护",
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
    """去掉页眉、页码、多余空白，让跨页表格重新连成一行。"""
    # 页码形如 "76"、"77 / 245"
    text = re.sub(r"\b\d{1,3}\s*/\s*\d{1,3}\b", " ", text)
    # 页眉：公司名 + 年份 + 年报
    text = re.sub(
        r"[\u4e00-\u9fa5（）()]+股份有限公司\s*\d{4}\s*年(?:半)?年度报告(?:全文)?", " ", text
    )
    # 单独成行的纯页码（2-3 位）
    text = re.sub(r"(?m)^\s*\d{2,3}\s*$", " ", text)
    return re.sub(r"\s+", " ", text)


def extract_pairs(block: str, mapping: dict[str, str]) -> list[tuple[str, str, int]]:
    """从区块中按白名单标签抓 (原标签, 标准标签, 人数)，保持出现顺序。"""
    found: list[tuple[str, str, int]] = []
    seen: set[str] = set()
    pattern = "|".join(sorted((re.escape(k) for k in mapping), key=len, reverse=True))
    for match in re.finditer(rf"({pattern})\s*([\d,]+)", block):
        raw = match.group(1)
        if raw in seen:
            continue
        seen.add(raw)
        found.append((raw, mapping[raw], int(match.group(2).replace(",", ""))))
    return found


def extract(text: str, company: str, year: str) -> list[dict[str, str]]:
    flat = flatten(text)
    rows: list[dict[str, str]] = []

    total_match = re.search(r"在职员工的数量合计(?:（人）)?\s*([\d,]+)", flat)
    total = int(total_match.group(1).replace(",", "")) if total_match else 0

    # 「教育程度」在标题里也出现，必须从专业构成表头之后再找
    role_start = flat.find("专业构成人数")
    edu_start = flat.find("教育程度", role_start) if role_start >= 0 else -1
    if role_start < 0 or edu_start < 0:
        return rows

    roles = extract_pairs(flat[role_start:edu_start], ROLE_MAP)
    edus = extract_pairs(flat[edu_start : edu_start + 800], EDU_MAP)

    if total:
        rows.append(
            {
                "公司": company,
                "年度": year,
                "维度": "合计",
                "类别": "在职员工",
                "原口径类别": "在职员工的数量合计",
                "人数": str(total),
                "占员工总数%": "100.00",
                "数据性质": "披露值",
            }
        )

    for raw, mapped, count in roles:
        rows.append(
            {
                "公司": company,
                "年度": year,
                "维度": "专业构成",
                "类别": mapped,
                "原口径类别": raw,
                "人数": str(count),
                "占员工总数%": f"{count / total * 100:.2f}" if total else "",
                "数据性质": "披露值",
            }
        )

    for raw, mapped, count in edus:
        rows.append(
            {
                "公司": company,
                "年度": year,
                "维度": "教育程度",
                "类别": mapped,
                "原口径类别": raw,
                "人数": str(count),
                "占员工总数%": f"{count / total * 100:.2f}" if total else "",
                "数据性质": "披露值",
            }
        )
    return rows


def load_payroll() -> dict[tuple[str, str], float]:
    """支付给职工以及为职工支付的现金（元），仅取年度报告期。"""
    if not PAYROLL.exists():
        return {}
    out: dict[tuple[str, str], float] = {}
    with PAYROLL.open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if "支付给职工" not in row.get("科目", ""):
                continue
            period = row.get("报告期", "")
            if len(period) != 8 or not period.endswith("1231"):
                continue
            try:
                out[(row["公司"], period[:4])] = float(row["数值"])
            except (ValueError, KeyError):
                continue
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all", action="store_true", default=True, help="默认执行全部；保留该开关用于兼容旧命令"
    )
    args = parser.parse_args()
    if not args.all:  # 默认 True；仅显式 --no-all 时才打印帮助
        parser.print_help()
        return 1

    payroll = load_payroll()
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
            items = extract(pdf_text(pdf), company, year)
            rows.extend(items)
            total = next((i["人数"] for i in items if i["维度"] == "合计"), "?")
            roles = [i["类别"] for i in items if i["维度"] == "专业构成"]
            edus = [i["类别"] for i in items if i["维度"] == "教育程度"]
            print(f"  {company} {year}: 合计 {total}")
            print(f"    专业 {roles}")
            print(f"    学历 {edus}")

    # 人均薪酬（补充行）
    for company in REPORTS:
        for year in ("2023", "2024", "2025"):
            total_row = next(
                (
                    r
                    for r in rows
                    if r["公司"] == company and r["年度"] == year and r["维度"] == "合计"
                ),
                None,
            )
            if not total_row or (company, year) not in payroll:
                continue
            headcount = int(total_row["人数"])
            amount = payroll[(company, year)]
            rows.append(
                {
                    "公司": company,
                    "年度": year,
                    "维度": "薪酬",
                    "类别": "人均薪酬",
                    "原口径类别": "支付给职工以及为职工支付的现金/在职员工数",
                    "人数": f"{amount / headcount:,.0f}",
                    "占员工总数%": "",
                    "数据性质": "计算值",
                }
            )

    fields = [
        "公司",
        "年度",
        "维度",
        "类别",
        "原口径类别",
        "人数",
        "占员工总数%",
        "数据性质",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print("\n【人均薪酬（元/人/年，含社保）】")
    for company in REPORTS:
        line = f"{company:<8}"
        for year in ("2023", "2024", "2025"):
            hit = next(
                (
                    r
                    for r in rows
                    if r["公司"] == company and r["年度"] == year and r["类别"] == "人均薪酬"
                ),
                None,
            )
            line += f"{hit['人数']:>12}" if hit else f"{'—':>12}"
        print(line)

    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
