"""提取研发人员数量、学历结构、年龄结构，并核对与「员工构成-技术人员」是否一致。

为什么重要：
研发人员的「量」和「质」是判断技术投入的两个方面，但三家的披露完整度差异很大，
直接画柱状图会误导：

| 公司 | 学历结构 | 年龄结构 |
|---|---|---|
| 美的 | 本科/硕士/博士/其他/隐私保护，5 项，合计 = 总数 | 3 段，合计比总数少 23 人 |
| 海尔 | 博士/硕士/本科/专科/高中及以下，5 项，合计 = 总数 | 5 段，合计 = 总数 |
| 格力 | **只有本科、硕士及以上 2 项**，缺专科及以下约 5,710 人 | **只有 30 岁以下、30—40 岁 2 段**，缺 40 岁以上 |

所以「硕士及以上占比」只有格力能直接算（因为分母就是这两项之和会虚高），
本表统一用「研发人员总数」作分母，并对覆盖不全的项标注覆盖人数与覆盖率。

另外，美的学历里出现「隐私保护 2,845 人」这一行，是年报把员工隐私保护选项
单独列示，不是学历类别。若不排除，美的研发人员学历合计会超出总数。

校验：研发人员数量 = 员工构成.csv 的「技术人员」人数（三家均逐位一致）。

用法：
    uv run python3 scripts/extract_rd_staff.py --all
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
OUT = FIN / "研发人员结构.csv"

REPORTS = {
    "美的集团": "美的2025.pdf",
    "海尔智家": "海尔2025.pdf",
    "格力电器": "格力2025.pdf",
}

# 学历层级标准顺序（用于输出排序与覆盖率计算）
EDU_ORDER = ["博士", "硕士", "本科", "专科", "高中及以下", "其他", "保密未披露"]


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


def parse_midea(flat: str) -> tuple[int, dict[str, int], dict[str, int]]:
    # 必须锚定「公司研发人员情况」小节：全文中「其他」出现多次
    # （分产品收入里也有「其他」），不锚定会取到 33,771,534 这种营收数字。
    start = flat.find("研发人员数量（人）")
    if start < 0:
        return 0, {}, {}
    block = flat[start : start + 700]
    total = int(num(re.search(r"研发人员数量（人）\s*([\d,]+)", block).group(1)))

    edu: dict[str, int] = {}
    for label, key in (
        ("本科", "本科"),
        ("硕士", "硕士"),
        ("博士", "博士"),
        ("其他", "其他"),
        # 「隐私保护」是学历结构表里的一行：员工选择不披露学历。
        # 本科 11,820 + 硕士 5,791 + 博士 903 + 其他 2,567 + 隐私保护 2,845
        # = 23,926，正好等于总数，因此它是学历类别的一部分，不是额外项。
        ("隐私保护", "保密未披露"),
    ):
        match = re.search(rf"{label}\s+([\d,]+)\s+[\d,]+", block)
        if match:
            edu[key] = int(num(match.group(1)))

    age: dict[str, int] = {}
    for label, key in (
        ("30 岁及以下", "30岁以下"),
        ("30~40 岁", "30-40岁"),
        ("40 岁以上", "40岁以上"),
    ):
        match = re.search(rf"{label}\s+([\d,]+)\s+[\d,]+", block)
        if match:
            age[key] = int(num(match.group(1)))
    return total, edu, age


def parse_haier(flat: str) -> tuple[int, dict[str, int], dict[str, int]]:
    start = flat.find("研发人员情况表")
    block = flat[start : start + 900]
    total = int(num(re.search(r"公司研发人员的数量\s*([\d,]+)", block).group(1)))
    edu = {}
    for label, key in (
        ("博士研究生", "博士"),
        ("硕士研究生", "硕士"),
        ("本科", "本科"),
        ("专科", "专科"),
        ("高中及以下", "高中及以下"),
    ):
        match = re.search(rf"{label}\s*([\d,]+)", block)
        if match:
            edu[key] = int(num(match.group(1)))
    age = {}
    for label, key in (
        ("30 岁以下（不含 30 岁）", "30岁以下"),
        ("30-40 岁（含 30 岁，不含 40 岁）", "30-40岁"),
        ("40-50 岁（含 40 岁，不含 50 岁）", "40-50岁"),
        ("50-60 岁（含 50 岁，不含 60 岁）", "50-60岁"),
        ("60 岁及以上", "60岁以上"),
    ):
        match = re.search(rf"{re.escape(label)}\s*([\d,]+)", block)
        if match:
            age[key] = int(num(match.group(1)))
    return total, edu, age


def parse_gree(flat: str) -> tuple[int, dict[str, int], dict[str, int]]:
    total = int(num(re.search(r"研发人员数量（人）\s*([\d,]+)", flat).group(1)))
    edu = {}
    bachelor = re.search(r"本科\s+([\d,]+)\s+[\d,]+", flat)
    if bachelor:
        edu["本科"] = int(num(bachelor.group(1)))
    master = re.search(r"硕士及以上\s+([\d,]+)\s+[\d,]+", flat)
    if master:
        edu["硕士"] = int(num(master.group(1)))
    age = {}
    young = re.search(r"30 岁以下\s+([\d,]+)\s+[\d,]+", flat)
    if young:
        age["30岁以下"] = int(num(young.group(1)))
    mid = re.search(r"30~40 岁\s+([\d,]+)\s+[\d,]+", flat)
    if mid:
        age["30-40岁"] = int(num(mid.group(1)))
    return total, edu, age


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all", action="store_true", default=True, help="默认执行全部；保留该开关用于兼容旧命令"
    )
    args = parser.parse_args()
    if not args.all:  # 默认 True；仅显式 --no-all 时才打印帮助
        parser.print_help()
        return 1

    # 员工构成.csv 的「技术人员」人数，用于校验
    technician: dict[str, int] = {}
    with (FIN / "员工构成.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["年度"] != "2025" or row["维度"] != "专业构成":
                continue
            if row["类别"] != "技术人员":
                continue
            technician[row["公司"]] = int(num(row["人数"]))

    rows: list[list[str]] = []
    for company, filename in REPORTS.items():
        pdf = PDF_DIR / filename
        if not pdf.exists():
            print(f"  缺少 {filename}", file=sys.stderr)
            continue
        flat = flatten(pdf_text(pdf))
        if company == "美的集团":
            total, edu, age = parse_midea(flat)
        elif company == "海尔智家":
            total, edu, age = parse_haier(flat)
        else:
            total, edu, age = parse_gree(flat)

        edu_covered = sum(edu.values())
        age_covered = sum(age.values())
        check = technician.get(company)
        print(
            f"  {company}: {total:,} 人  学历覆盖 {edu_covered:,} ({edu_covered / total * 100:.1f}%)"
            f"  年龄覆盖 {age_covered:,} ({age_covered / total * 100:.1f}%)"
            f"  vs 技术人员 {check:,} {'OK' if check == total else '差异'}"
        )

        for key in EDU_ORDER:
            if key not in edu:
                continue
            rows.append(
                [
                    company,
                    "2025",
                    "学历",
                    key,
                    str(edu[key]),
                    f"{edu[key] / total * 100:.2f}",
                    f"{total:,}",
                    "披露值",
                ]
            )
        for key, value in edu.items():
            if key in EDU_ORDER:
                continue
            rows.append(
                [
                    company,
                    "2025",
                    "学历",
                    key,
                    str(value),
                    f"{value / total * 100:.2f}",
                    f"{total:,}",
                    "披露值（员工选择不披露学历）",
                ]
            )
        for key, value in age.items():
            rows.append(
                [
                    company,
                    "2025",
                    "年龄",
                    key,
                    str(value),
                    f"{value / total * 100:.2f}",
                    f"{total:,}",
                    "披露值",
                ]
            )
        rows.append(
            [
                company,
                "2025",
                "汇总",
                "研发人员总数",
                str(total),
                "100.00",
                f"{total:,}",
                "披露值",
            ]
        )
        rows.append(
            [
                company,
                "2025",
                "汇总",
                "学历项覆盖合计",
                str(edu_covered),
                f"{edu_covered / total * 100:.2f}",
                f"{total:,}",
                "计算值",
            ]
        )
        rows.append(
            [
                company,
                "2025",
                "汇总",
                "年龄项覆盖合计",
                str(age_covered),
                f"{age_covered / total * 100:.2f}",
                f"{total:,}",
                "计算值",
            ]
        )

    fields = [
        "公司",
        "年度",
        "维度",
        "类别",
        "人数",
        "占研发人员总数%",
        "研发人员总数",
        "数据性质",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
