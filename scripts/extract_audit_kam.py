"""提取审计报告中的关键审计事项与审计费用。

关键审计事项（KAM）是审计师判定为「对本期财报最重要」的领域，
其中的数字经过审计师核对，可信度高于管理层讨论。

三家 2025 年的关键审计事项：
- 美的：智能家居业务收入确认
- 海尔：收入确认、应收账款减值
- 格力：存货跌价准备、收入确认

用法：
    uv run python3 scripts/extract_audit_kam.py --all
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
OUT = ROOT / "财务数据" / "关键审计事项.csv"

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


def flatten(text: str) -> str:
    text = re.sub(r"\d+ / \d+\s*", " ", text)
    return re.sub(r"\s+", " ", text)


def extract_kam(text: str) -> list[dict[str, str]]:
    """抓关键审计事项标题及其中的金额。"""
    flat = flatten(text)
    anchor = flat.find("关键审计事项是我们根据职业判断")
    if anchor < 0:
        anchor = flat.find("关键审计事项")
    if anchor < 0:
        return []

    chunk = flat[anchor : anchor + 6000]
    rows: list[dict[str, str]] = []

    # 事项标题形如「(一) 智能家居业务收入确认」「1、收入确认」
    titles = re.findall(
        r"[（(][一二三四五六][)）]\s*([\u4e00-\u9fa5A-Za-z（）()、\s]{4,40}?)(?=\s{2,}|参见|请参阅|我们)",
        chunk,
    )
    if not titles:
        titles = re.findall(
            r"[（(][一二三四五六][)）]\s*([\u4e00-\u9fa5A-Za-z（）()]{4,30})", chunk
        )

    # 清理：去掉粘连的模板文字、去重、保序
    cleaned: list[str] = []
    normalized: list[str] = []
    for title in titles:
        name = re.sub(r"\s*关键审计事项.*$", "", title)
        name = re.sub(r"\s*在审计中如何应对.*$", "", name)
        name = name.strip(" 、，。")
        if len(name) < 4:
            continue
        # 同一事项可能在标题行和正文中重复出现，空格排版不同，归一化后比较
        key = re.sub(r"\s+", "", name)
        if any(key.startswith(existing) or existing.startswith(key) for existing in normalized):
            continue
        normalized.append(key)
        cleaned.append(name)

    # 金额：人民币 X 千元 / X 万元 / X 亿元
    amounts = re.findall(r"(?:人民币|约为人民币)?\s*([\d,]+\.?\d*)\s*(千元|万元|亿元)", chunk)

    for index, title in enumerate(cleaned):
        rows.append(
            {
                "序号": str(index + 1),
                "事项": title,
                "金额原文": "",
                "数据性质": "审计报告",
            }
        )

    # 把金额挂到第一条事项上（通常该事项正文含金额）
    if rows and amounts:
        formatted = "；".join(f"{value}{unit}" for value, unit in amounts[:4])
        rows[0]["金额原文"] = formatted
    return rows


def extract_fee(text: str) -> dict[str, str]:
    """审计费用。

    三家表述不同：
    - 美的：境内会计师事务所报酬（万元）940.5
    - 格力：境内会计师事务所报酬（万元）396
    - 海尔：境内会计师事务所报酬 655（单位标注在表头）
    """
    flat = flatten(text)
    result = {"境内审计报酬_万元": "", "境外审计报酬_万元": "", "内控审计费用_万元": ""}

    domestic = re.search(r"境内会计师事务所报酬(?:（万元）)?\s*([\d,\.]+)", flat)
    if domestic:
        result["境内审计报酬_万元"] = domestic.group(1).replace(",", "")
    overseas = re.search(r"境外会计师事务所报酬(?:（万元）)?\s*([\d,\.]+)", flat)
    if overseas:
        result["境外审计报酬_万元"] = overseas.group(1).replace(",", "")
    internal = re.search(r"内部控制审计[^。]{0,60}?审计费用为人民币\s*([\d,\.]+)\s*万元", flat)
    if internal:
        result["内控审计费用_万元"] = internal.group(1).replace(",", "")
    return result


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
            year_match = re.search(r"(20\d{2})", filename)
            if not year_match:
                continue
            year = year_match.group(1)
            text = pdf_text(pdf)
            items = extract_kam(text)
            fee = extract_fee(text)
            for item in items:
                item["公司"] = company
                item["年度"] = year
                item.update(fee)
                rows.append(item)
            names = [i["事项"] for i in items]
            print(
                f"  {company} {year}: {len(items)} 项 {names}, "
                f"境内审计费 {fee['境内审计报酬_万元'] or '未提取'} 万元"
            )

    fields = [
        "公司",
        "年度",
        "序号",
        "事项",
        "金额原文",
        "境内审计报酬_万元",
        "境外审计报酬_万元",
        "内控审计费用_万元",
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
