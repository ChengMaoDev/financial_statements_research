"""从年报提取三家的套期保值衍生品投资表。

## 为什么需要这份数据

原材料占白电制造成本 82%–88%，铜铝价格波动会直接冲击毛利率。
但「铜价涨 10% → 毛利率跌多少」取决于公司有没有做套期保值、
做了多少。缺了这一块，成本传导分析只能做情景假设，不能落到实际。

## 表的结构（三家格式略有差异，但字段可对齐）

年报「报告期内以套期保值为目的的衍生品投资」表：
- 衍生品投资类型（期货合约 / 远期外汇 / 商品合约 / 利率互换）
- 初始投资金额、期初金额
- 本期公允价值变动损益
- 计入权益的累计公允价值变动
- 报告期内购入/售出金额
- 期末金额
- 期末投资金额占报告期末净资产比例

## 三家的关键差异

| 公司 | 披露粒度 | 商品类套保 |
|---|---|---|
| 美的 | 期货合约 / 外汇合约 / 交叉货币利率互换，分类清晰 | 期货合约期末 80,568.9 万元 |
| 海尔 | 只有「远期外汇」和「远期商品」两行，商品类极小 | 远期商品期末 0（购入 913 万后全部结清） |
| 格力 | 「期货套保合约」与「远期金融合约」两行，且**远期金融为负数** | 期货套保期末 6,015.51 万元 |

**格力的负数不是录入错误**：远期金融合约的初始投资、期初、期末都是负数，
表示净负债头寸（卖出远期）。合计 -493.99 万元。

## 重要限制

这些是**衍生品合约的名义/账面金额**，不是被套保的现货规模。
不能用「期货合约期末金额 ÷ 原材料采购额」算「套保覆盖率」——
真正的覆盖率 = 被套保的现货量 / 总现货量，年报不披露。
本表只能说明「有没有做、做了多大规模」。

用法：
    uv run python3 scripts/extract_hedging.py
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "年度报告"
OUT = ROOT / "财务数据" / "套期保值.csv"

# 文件名 → (公司, 年度)
SOURCES = {
    "美的2025.pdf": ("美的集团", "2025"),
    "美的2024.pdf": ("美的集团", "2024"),
    "海尔2025.pdf": ("海尔智家", "2025"),
    "海尔2024.pdf": ("海尔智家", "2024"),
    "格力2025.pdf": ("格力电器", "2025"),
    "格力2024.pdf": ("格力电器", "2024"),
}

# 每家的行模式：类型名 + 一串数字
ROW_PATTERNS = {
    "美的集团": [
        ("期货合约", "商品"),
        ("外汇合约", "外汇"),
        ("交叉货币利率互换", "利率"),
    ],
    "海尔智家": [
        ("远期外汇合约", "外汇"),
        ("远期商品合约", "商品"),
    ],
    "格力电器": [
        ("期货套保合约", "商品"),
        ("远期金融合约", "外汇"),
    ],
}


def pdf_text(pdf: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext 失败: {pdf}")
    # 美的的年报 PDF 带字符间隔加密痕迹，pdftotext 会在两个汉字之间插入 `**`，
    # 导致「以套期保值为目的的衍生品投资」被拆成「以**套**期**保**...」而匹配不到。
    # 把 `**` 连同两侧空白一起压掉后再解析。
    return re.sub(r"\*\*", "", result.stdout)


def parse_numbers(line: str) -> list[float]:
    """从一行中取出所有数字（含负号、千分位）。"""
    out: list[float] = []
    for token in re.findall(r"-?[\d,]+(?:\.\d+)?", line):
        cleaned = token.replace(",", "")
        try:
            out.append(float(cleaned))
        except ValueError:
            continue
    return out


def extract(text: str, company: str) -> list[dict[str, str]]:
    """定位套保表并逐行解析。"""
    rows: list[dict[str, str]] = []
    anchor = text.find("以套期保值为目的的衍生品投资")
    if anchor < 0:
        return rows
    chunk = text[anchor : anchor + 4000]

    for label, kind in ROW_PATTERNS.get(company, []):
        # 行格式（美的/海尔/格力一致）：
        #   「     期货合约      0.0   -4,269.0   0.0   84,837.9   0.0   0.0   80,568.9   0.13%」
        # 标签前有空格、后跟 7–8 个数字，可能以百分号结尾。
        # 注意「交叉货币利率互换」在 PDF 里被折行成「交叉货币利率互」+「换」，
        # 因此匹配时允许标签在行内任意位置出现（该行没有其他中文字符）。
        pattern = rf"^\s*{re.escape(label)}\s+(-?[\d,\.\s\-%]+)$"
        match = re.search(pattern, chunk, re.MULTILINE)
        if not match:
            # 折行版本：标签被截断，数字在下一行
            head = label[: len(label) - 1]
            pattern2 = rf"^\s*{re.escape(head)}\s*\n\s*(-?[\d,\.\s\-%]+)$"
            match = re.search(pattern2, chunk, re.MULTILINE)
        if not match:
            continue
        numbers = parse_numbers(match.group(1))
        if len(numbers) < 5:
            continue
        # 三家表格的列顺序一致，但**空列会导致数字个数不同**：
        #   美的/海尔：初始、期初、公允价值变动、计入权益、购入、售出、期末、占净资产%
        #   格力：购入/售出两列常为空 → 只有 5 个数 + 1 个百分号
        # 用百分号是否存在定位最后一列，再据此推断「期末金额」的位置。
        has_pct = "%" in match.group(1)
        if has_pct:
            numbers = numbers[:-1]  # 剥离百分号（已在 parse 时变成纯数字）
        fields_map = [
            "初始投资金额",
            "期初金额",
            "本期公允价值变动损益",
            "计入权益的累计公允价值变动",
            "报告期内购入金额",
            "报告期内售出金额",
            "期末金额",
        ]
        if has_pct:
            # 格力两行的列填充情况不同，必须区分：
            #   期货套保：初始/期初/公允价值/计入权益/[购入空]/[售出空]/期末/占比 → 6 数
            #   远期金融：初始/期初/公允价值/[计入权益空]/[购入空]/[售出空]/期末/占比 → 4 数
            if len(numbers) >= 6:
                seq = [
                    "初始投资金额",
                    "期初金额",
                    "本期公允价值变动损益",
                    "计入权益的累计公允价值变动",
                    "报告期内购入金额",
                    "报告期内售出金额",
                    "期末金额",
                ]
            elif len(numbers) == 4:
                seq = ["初始投资金额", "期初金额", "本期公允价值变动损益", "期末金额"]
            else:
                seq = [
                    "初始投资金额",
                    "期初金额",
                    "本期公允价值变动损益",
                    "计入权益的累计公允价值变动",
                    "期末金额",
                ][: len(numbers)]
        else:
            seq = fields_map[: len(numbers)]
        fields = [(name, numbers[i]) for i, name in enumerate(seq) if i < len(numbers)]
        if has_pct:
            fields.append(("占期末净资产比例", parse_numbers(match.group(1))[-1]))
        for name, value in fields:
            if value is None:
                continue
            rows.append(
                {
                    "衍生品类型": label,
                    "类别": kind,
                    "字段": name,
                    "数值": f"{value:.2f}",
                    "单位": "万元" if name != "占期末净资产比例" else "%",
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all", action="store_true", default=True, help="提取全部已登记年报（默认）"
    )
    parser.parse_args()

    out_rows: list[list[str]] = []
    problems: list[str] = []

    for filename, (company, year) in SOURCES.items():
        pdf = PDF_DIR / filename
        if not pdf.exists():
            problems.append(f"缺少 {filename}")
            continue
        # 用 PDF 的文件时间戳，不用当前时间：同一份 PDF 重跑必须产出逐字节相同的 CSV，
        # 否则每次重跑都会产生 diff，「可重跑复现」就失去了意义。
        stamp = datetime.fromtimestamp(pdf.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        try:
            text = pdf_text(pdf)
        except (RuntimeError, FileNotFoundError) as exc:
            problems.append(f"{filename}: {exc}")
            continue
        found = extract(text, company)
        if not found:
            problems.append(f"{company} {year}: 未匹配到套保表")
            continue
        for row in found:
            out_rows.append(
                [
                    company,
                    year,
                    row["衍生品类型"],
                    row["类别"],
                    row["字段"],
                    row["数值"],
                    row["单位"],
                    "披露值",
                    filename,
                    stamp,
                ]
            )
        print(f"  {company} {year}: {len(found)} 项")

    if not out_rows:
        print("未提取到任何数据", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            [
                "公司",
                "年度",
                "衍生品类型",
                "类别",
                "字段",
                "数值",
                "单位",
                "数据性质",
                "来源文件",
                "采集时间",
            ]
        )
        writer.writerows(out_rows)

    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(out_rows)} 行")
    if problems:
        print("未取到：", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
    print("\n注意：这是衍生品合约金额，不是被套保的现货规模。")
    print("年报不披露「被套保现货量 / 总现货量」，因此无法计算真正的套保覆盖率。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
