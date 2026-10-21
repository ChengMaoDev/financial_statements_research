"""从年报 PDF 提取治理与经营披露数据。

这些字段不在标准三张表里，但分析价值很高：
- 研发投入（费用化 / 资本化 / 合计 / 占收入比）
- 审计意见类型与会计师事务所
- 员工人数与构成
- 分季度经营数据

三家公司年报的表格排版不一致（美的用千元、海尔格力用元；
研发投入表在不同章节），因此按正则锚点定位而非固定页码。

用法：
    uv run python3 scripts/fetch_pdf_disclosures.py --all
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
OUT = ROOT / "财务数据" / "治理与经营披露.csv"

# 公司 → 年报文件（按报告期）
REPORTS = {
    "美的集团": ["美的2023.pdf", "美的2024.pdf", "美的2025.pdf"],
    "海尔智家": ["海尔2023.pdf", "海尔2024.pdf", "海尔2025.pdf"],
    "格力电器": ["格力2023.pdf", "格力2024.pdf", "格力2025.pdf"],
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


def parse_amount(text: str) -> float | None:
    """把 '10,716,600,069.65' 解析为 float。"""
    cleaned = text.replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def grab(text: str, pattern: str, group: int = 1) -> str:
    match = re.search(pattern, text)
    return match.group(group).strip() if match else ""


def unit_of(text: str, anchor: int, window: int = 3000) -> int:
    """判定 anchor 附近表格单位。"""
    chunk = text[max(0, anchor - window) : anchor]
    positions = []
    for marker, factor in [("单位：千元", 1000), ("单位：元", 1), ("单位：万元", 10000)]:
        index = chunk.rfind(marker)
        if index >= 0:
            positions.append((index, factor))
    if not positions:
        return 1
    return max(positions)[1]


def extract_research(text: str) -> dict[str, str]:
    """研发投入。三家格式不同，逐种尝试。

    海尔：本期费用化/资本化/研发投入合计
    美的：研发费用金额（千元）+ 占营业收入比例
    格力：研发投入金额（元）+ 占营业收入比例 + 资本化金额
    """
    result = {
        "研发投入_合计": "",
        "研发投入占收入比": "",
        "研发投入_资本化": "",
        "研发投入资本化比重": "",
        "研发投入_口径": "",
    }

    # 海尔式：费用化 + 资本化 = 合计
    total = re.search(r"研发投入合计\s+([\d,]+\.?\d*)", text)
    if total:
        value = parse_amount(total.group(1))
        if value:
            result["研发投入_合计"] = f"{value:.2f}"
            result["研发投入_口径"] = "研发投入合计(含资本化)"
        capital = re.search(r"本期资本化研发投入\s+([\d,]+\.?\d*)", text)
        if capital:
            cap_value = parse_amount(capital.group(1))
            if cap_value:
                result["研发投入_资本化"] = f"{cap_value:.2f}"
        ratio = re.search(r"研发投入总额占营业收入比例（%）\s+([\d.]+)", text)
        if ratio:
            result["研发投入占收入比"] = ratio.group(1)
        cap_ratio = re.search(r"研发投入资本化的比重（%）\s+([\d.]+)", text)
        if cap_ratio:
            result["研发投入资本化比重"] = cap_ratio.group(1)
        return result

    # 美的式：研发费用金额（千元）或研发投入金额（千元）
    # 2023/2024 年报用「研发投入金额（千元）」，2025 年报改为「研发费用金额（千元）」
    if "（千元）" in text and re.search(r"研发(?:费用|投入)金额（千元）", text):
        match = re.search(r"研发(?:费用|投入)金额（千元）\s+([\d,]+)", text)
        if match:
            value = parse_amount(match.group(1))
            if value:
                result["研发投入_合计"] = f"{value * 1000:.2f}"
                label = "研发费用金额" if "研发费用金额（千元）" in text else "研发投入金额"
                result["研发投入_口径"] = f"{label}(千元转元)"
        ratio = re.search(r"研发(?:费用|投入)占营业收入比例\s+([\d.]+)%", text)
        if ratio:
            result["研发投入占收入比"] = ratio.group(1)
        return result

    # 格力式：研发投入金额（元）
    match = re.search(r"研发投入金额（元）\s+([\d,]+\.?\d*)", text)
    if match:
        value = parse_amount(match.group(1))
        if value:
            result["研发投入_合计"] = f"{value:.2f}"
            result["研发投入_口径"] = "研发投入金额(元)"
        ratio = re.search(r"研发投入占营业收入比例\s+([\d.]+)%", text)
        if ratio:
            result["研发投入占收入比"] = ratio.group(1)
        cap = re.search(r"研发投入资本化的金额（元）\s+([\d,]+\.?\d*)", text)
        if cap:
            cap_value = parse_amount(cap.group(1))
            if cap_value:
                result["研发投入_资本化"] = f"{cap_value:.2f}"
        cap_ratio = re.search(r"资本化研发投入占研发投入的比\s*例?\s+([\d.]+)%", text)
        if cap_ratio:
            result["研发投入资本化比重"] = cap_ratio.group(1)
    return result


def extract_audit(text: str) -> dict[str, str]:
    """审计意见与会计师事务所。"""
    result = {"审计意见": "", "会计师事务所": ""}
    # 优先用「境内会计师事务所名称 XXX」这种明确标注
    match = re.search(r"境内会计师事务所名称\s+([\u4e00-\u9fa5（）()]{4,40})", text)
    if not match:
        match = re.search(r"会计师事务所名称\s+([\u4e00-\u9fa5（）()]{4,40})", text)
    if not match:
        # 兜底：正文里第一次出现的「XX会计师事务所（特殊普通合伙）」
        match = re.search(r"([\u4e00-\u9fa5]{2,12}会计师事务所（特殊普通合伙）)", text)
    if match:
        result["会计师事务所"] = match.group(1).strip()

    if "标准无保留意见" in text:
        result["审计意见"] = "标准无保留意见"
    elif "带强调事项段的无保留意见" in text:
        result["审计意见"] = "带强调事项段的无保留意见"
    elif "保留意见" in text:
        result["审计意见"] = "保留意见"
    elif "无法表示意见" in text:
        result["审计意见"] = "无法表示意见"
    return result


def extract_employees(text: str) -> dict[str, str]:
    """员工人数。"""
    result = {"员工人数": ""}
    for pattern in [
        r"在职员工的数量合计（人）\s*([\d,]+)",
        r"在职员工的数量合计\s*([\d,]+)",
        r"母公司在职员工的数量（人）\s*([\d,]+)",
    ]:
        match = re.search(pattern, text)
        if match:
            value = parse_amount(match.group(1))
            if value:
                result["员工人数"] = f"{value:.0f}"
                break
    return result


def extract_quarterly(text: str) -> list[dict[str, str]]:
    """分季度主要财务数据。表头含「分季度主要财务数据」。"""
    rows: list[dict[str, str]] = []
    anchor = text.find("分季度主要财务数据")
    if anchor < 0:
        return rows
    chunk = text[anchor : anchor + 4000]
    unit = unit_of(text, anchor)
    # 抓营业收入与归母净利润两行
    for label, key in [
        (r"营业收入\s+([\d,]+\.?\d*)", "营业收入"),
        (r"归属于上市公司股东的净利润\s+([\d,]+\.?\d*)", "归母净利润"),
    ]:
        match = re.search(label, chunk)
        if match:
            value = parse_amount(match.group(1))
            if value:
                rows.append(
                    {
                        "指标": key,
                        "Q1": f"{value * unit:.2f}",
                        "单位倍数": str(unit),
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

    rows: list[list[str]] = []
    for company, files in REPORTS.items():
        for filename in files:
            pdf = PDF_DIR / filename
            if not pdf.exists():
                print(f"  缺少 {filename}", file=sys.stderr)
                continue
            year = re.search(r"(20\d{2})", filename)
            period = f"{year.group(1)} 年度" if year else ""
            text = pdf_text(pdf)
            record: dict[str, str] = {"公司": company, "报告期": period, "文件": filename}
            record.update(extract_research(text))
            record.update(extract_audit(text))
            record.update(extract_employees(text))
            if not rows:
                header = list(record.keys())
            rows.append(list(record.values()))
            print(
                f"  {company} {period}: 研发合计 {record['研发投入_合计'] or '未提取'}, "
                f"审计 {record['审计意见'] or '未提取'}, 员工 {record['员工人数'] or '未提取'}"
            )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
