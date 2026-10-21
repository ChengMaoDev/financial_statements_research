"""提取「会计利润与所得税费用调整过程」，计算有效税率与税收优惠依赖度。

为什么重要：
三家名义税率不同，直接比「实际税率」会得出错误结论：

- **美的**按 25% 法定税率做起点，靠「子公司适用不同税率」一项每年减税 47.9 亿
  （2025 年），主要是大量子公司为高新技术企业（15%）及西部大开发优惠。
- **海尔**同样以 25% 为起点，「子公司适用不同税率」减税 17.4 亿，另有西部大开发。
- **格力**母公司自身就是高新技术企业，**直接以 15% 为起点**，所以它表里的
  「按法定税率计算的所得税」本身就比另两家低 10 个百分点。

三个陷阱：

1. **起点税率不同**（25% / 25% / 15%），不能把「按法定税率计算的所得税」
   当作可比值，也不能用它反推利润总额。
2. **「子公司适用不同税率的影响」通常为负（减税）**，但格力 2025 年这一项是
   **正数 1.24 亿**（增税），说明有子公司适用税率高于 15%。
3. **格力 2025 年「本期未确认递延所得税资产的可抵扣亏损」11.56 亿**，
   把有效税率从 15% 抬到 16.69%，是当年 ETR 高于另两家的主因。

**口径**：每家公司取「当年年报」的第一列（本期）。海尔/格力的 2025 年报调整表
只有本期一列，所以 2024 年数据取自 2024 年报，而不是 2025 年报的对比列。

用法：
    uv run python3 scripts/extract_tax_reconciliation.py --all
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
OUT = FIN / "所得税与税收优惠.csv"

# (公司, 年度) → (文件名, 报表单位换算到元的倍数, 当年母公司适用税率)
SOURCES = {
    ("美的集团", "2025"): ("美的2025.pdf", 1_000, 0.25),
    ("美的集团", "2024"): ("美的2024.pdf", 1_000, 0.25),
    ("海尔智家", "2025"): ("海尔2025.pdf", 1, 0.25),
    ("海尔智家", "2024"): ("海尔2024.pdf", 1, 0.25),
    ("格力电器", "2025"): ("格力2025.pdf", 1, 0.15),
    ("格力电器", "2024"): ("格力2024.pdf", 1, 0.15),
}

ANCHORS = {
    "美的集团": "将基于合并利润表的利润总额采用适用税率计算的所得税调节为所得税费",
    "海尔智家": "当期会计利润与所得税费用调整过程",
    "格力电器": "会计利润与所得税费用调整过程",
}

# 表内项目名 → 统一项目名。三家措辞不同，但语义一一对应。
CANON = {
    "利润总额": "利润总额",
    "会计利润总额": "利润总额",
    "按25%税率计算的所得税": "按法定税率计算的所得税",
    "按法定税率计算的所得税": "按法定税率计算的所得税",
    "按法定/适用税率计算的所得税费用": "按法定税率计算的所得税",
    "子公司适用不同税率的影响": "子公司适用不同税率的影响",
    "以前期间所得税汇算清缴的影响": "以前期间所得税的影响",
    "调整以前期间所得税的影响": "以前期间所得税的影响",
    "非应纳税收入": "非应税收益的影响",
    "非应税收益的影响": "非应税收益的影响",
    "不得扣除的成本、费用和损失": "不可抵扣的成本费用损失",
    "不可抵扣的成本、费用和损失的影响": "不可抵扣的成本费用损失",
    "使用前期未确认递延所得税资产的暂时性差异或可抵扣亏损": "使用前期未确认递延所得税资产",
    "未确认递延税项的可抵扣暂时性差异或可抵扣亏损的影响": "本期未确认递延所得税资产",
    "本期未确认递延所得税资产的可抵扣暂时性差异或可抵扣亏损的影响": "本期未确认递延所得税资产",
    "其他": "其他",
    "所得税费用": "所得税费用",
    "所得税费用合计": "所得税费用",
}

# 输出顺序，也是加总校验的顺序
ORDERED = [
    "按法定税率计算的所得税",
    "子公司适用不同税率的影响",
    "以前期间所得税的影响",
    "非应税收益的影响",
    "不可抵扣的成本费用损失",
    "使用前期未确认递延所得税资产",
    "本期未确认递延所得税资产",
    "其他",
]

HEADER_WORDS = ("项目", "金额", "本期发生额", "上期发生额", "年度", "单位", "币种")

VALUE_TAIL = re.compile(r"^(.*?)\s{2,}(\(?-?[\d,]+(?:\.\d+)?\)?)\s*(\(?-?[\d,]+(?:\.\d+)?\)?)?$")
NUMBER_ONLY = re.compile(r"^(\(?-?[\d,]+(?:\.\d+)?\)?)\s*(\(?-?[\d,]+(?:\.\d+)?\)?)?$")


def pdf_text(pdf: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    return result.stdout


def to_number(token: str) -> float:
    """括号为负（美的），负号为负（海尔/格力）。"""
    token = token.strip()
    negative = token.startswith("(") and token.endswith(")")
    value = float(token.strip("()").replace(",", ""))
    return -value if negative else value


def block_of(text: str, company: str) -> str:
    index = text.find(ANCHORS[company])
    if index < 0:
        return ""
    return text[index : index + 2_200]


def clean(line: str, company: str) -> str:
    """剥掉锚点文字与表头残留，返回可用于拼标签的文本。"""
    line = line.replace(ANCHORS[company], "").replace("所得税费用调节为所得税费", "")
    line = line.replace("用：", "").replace("（续）", "").strip()
    if not line or not re.search(r"[\u4e00-\u9fa5]", line):
        return ""
    if any(word in line for word in HEADER_WORDS):
        return ""
    return line


def parse_rows(block: str, company: str) -> list[tuple[str, list[float]]]:
    """解析「标签 + 本期 [+ 上期]」。

    两个排版陷阱：
    1. 标签被数字截成两半（格力「本期未确认…或可 / 1,156,414,876.08 / 抵扣亏损的影响」），
       数字行只剩数字、没有标签，strip 后连前导空格都没了。
    2. 因此独立判断「纯数字行」，再向后找能把标签补全的那一行。
    """
    lines = [line.strip() for line in block.splitlines()]
    rows: list[tuple[str, list[float]]] = []
    buffer = ""
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line:
            index += 1
            continue

        bare = NUMBER_ONLY.match(line)
        paired = None if bare else VALUE_TAIL.match(line)
        if bare:
            if not buffer:
                index += 1
                continue
            label = buffer
            buffer = ""
            values = [to_number(bare.group(1))]
            if bare.group(2):
                values.append(to_number(bare.group(2)))
        elif paired:
            label = (buffer + clean(paired.group(1), company)).replace(" ", "")
            buffer = ""
            if not label:
                index += 1
                continue
            values = [to_number(paired.group(2))]
            if paired.group(3):
                values.append(to_number(paired.group(3)))
        else:
            buffer += clean(line, company)
            index += 1
            continue

        # 标签跨行：只吞掉「拼上去正好能在 CANON 里命中」的那一行
        look = index + 1
        while label not in CANON and look < len(lines):
            follower = lines[look]
            if not follower:
                look += 1
                continue
            if NUMBER_ONLY.match(follower) or VALUE_TAIL.match(follower):
                break
            candidate = (label + clean(follower, company)).replace(" ", "")
            if candidate in CANON:
                label = candidate
                index = look
                break
            look += 1

        if label in CANON:
            rows.append((label, values))
            if label == "所得税费用":
                break
        index += 1
    return rows


def extract(block: str, company: str) -> dict[str, float]:
    items: dict[str, float] = {}
    for label, values in parse_rows(block, company):
        if CANON[label] not in items:
            items[CANON[label]] = values[0]
    return items


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
    warnings: list[str] = []
    for (company, year), (filename, factor, statutory) in SOURCES.items():
        pdf = PDF_DIR / filename
        if not pdf.exists():
            print(f"  缺少 {filename}", file=sys.stderr)
            continue
        items = extract(block_of(pdf_text(pdf), company), company)
        if "利润总额" not in items or "所得税费用" not in items:
            print(f"  {company} {year} 未匹配调整表", file=sys.stderr)
            warnings.append(f"{company} {year} 未匹配")
            continue

        profit = items["利润总额"] * factor / 1e8
        tax = items["所得税费用"] * factor / 1e8

        # 校验：起点 + 各调整项 = 所得税费用
        recomputed = (
            (items["按法定税率计算的所得税"] + sum(items.get(k, 0.0) for k in ORDERED[1:]))
            * factor
            / 1e8
        )
        gap = recomputed - tax
        if abs(gap) > max(0.05, abs(tax) * 0.001):
            warnings.append(f"{company} {year} 明细合计差 {gap:+.2f} 亿")

        for name in ORDERED:
            if name not in items:
                continue
            value = items[name] * factor / 1e8
            rows.append(
                [
                    company,
                    year,
                    name,
                    f"{value:.2f}",
                    f"{value / profit * 100:.2f}",
                    f"{statutory * 100:.0f}%",
                    "披露值",
                ]
            )
        rows.append(
            [
                company,
                year,
                "有效税率",
                f"{tax / profit * 100:.2f}",
                f"{tax / profit * 100:.2f}",
                f"{statutory * 100:.0f}%",
                "计算值",
            ]
        )
        print(f"  {company} {year}: 调整项 {len(items)} 项，有效税率 {tax / profit * 100:.2f}%")

    fields = ["公司", "年度", "项目", "金额(亿元)", "占利润总额%", "母公司税率", "数据性质"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    print(
        f"\n{'公司':<8}{'年度':<6}{'母公司税率':>10}{'有效税率':>10}{'子公司税率影响':>15}{'未确认递延':>12}"
    )
    print("-" * 64)
    index: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        index.setdefault((row[0], row[1]), {})[row[2]] = row[3]

    for row in rows:
        if row[2] != "有效税率":
            continue
        data = index[(row[0], row[1])]
        print(
            f"{row[0]:<8}{row[1]:<6}{row[5]:>10}{row[4]:>9}%"
            f"{data.get('子公司适用不同税率的影响', '—'):>15}"
            f"{data.get('本期未确认递延所得税资产', '—'):>12}"
        )

    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    for warning in warnings:
        print(f"注意：{warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
