"""资产减值与信用减值：减值去了哪类资产。

为什么重要：
三家 2025 年减值合计（资产减值 + 信用减值）占利润总额：

- 美的 2.85%（15.12 亿）
- 海尔 5.71%（13.40 亿）
- 格力 5.39%（18.69 亿）

只看总额会漏掉结构差异：

| 公司 | 最大一项 | 金额 | 说明 |
|---|---|---|---|
| 美的 | 存货跌价 | 6.78 亿 | 家电存货常规计提 |
| 海尔 | 存货跌价 | 9.94 亿 | 家电存货常规计提 |
| 格力 | **在建工程减值** | **9.96 亿** | 格力钛工程不再建设，按残值计提 |

格力 2025 年在建工程减值 9.96 亿，是「格力钛工程后续不再建设，相关资产已无法
为企业带来预期经济利益流入」。这是**一次性资产报废**，不是经营性减值。

四个陷阱：

1. **「资产减值损失」与「信用减值损失」是两个科目**，前者针对存货/固定资产/商誉，
   后者针对应收款项。三家的拆分口径一致，但**符号相反**：美的印正数（损失），
   海尔/格力印负数（损失）。本表统一为「正=损失」。
2. **格力「存货跌价损失」2025 年是 +55.38 万（转回）**，2024 年是 −1.44 亿（计提）。
   正数代表转回，会增厚利润。这种符号翻转在表格里极易误读。
3. **美的 2025 年新增「长期股权投资减值损失」3.67 亿**，2024 年为 0。对应的是
   哪家联营企业年报未点名，只注明附注四(15)。
4. **商誉减值只有格力还在计提**（0.44 亿），美的/海尔 2025 年商誉零减值。
   格力商誉账面 13.24 亿，已累计减值较多（格力钛 6.13 亿全额、南京华新 2.74 亿全额）。

用法：
    uv run python3 scripts/extract_impairment.py --all
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
OUT = FIN / "减值明细.csv"

# (文件名, 换算到元的倍数, 资产减值标题, 信用减值标题)
SOURCES = {
    "美的集团": ("美的2025.pdf", 1_000, "(56) 资产减值损失", "(57) 信用减值损失"),
    "海尔智家": ("海尔2025.pdf", 1, "58、 资产减值损失", "57、 信用减值损失"),
    "格力电器": ("格力2025.pdf", 1, "65、 资产减值损失", "64、 信用减值损失"),
}

NUMBER = r"\(?-?[\d,]+(?:\.\d+)?\)?"
TOKEN = re.compile(rf"^(?:{NUMBER}|-)$")
# 行尾最多两个「数字或空缺符」，其余都是标签。用 2+ 空格切分而不是正则整行匹配，
# 因为「某年空缺、某年有数」的行（`投资性房地产减值损失   -   3,584`）用整行正则会
# 把空缺符 "-" 吃进标签，把上期数字误当本期。
SPLIT = re.compile(r"\s{2,}")
HEADING = re.compile(r"^(?:\(\d+\)|\d+、)\s*[\u4e00-\u9fa5]")
BARE_TOTAL = re.compile(r"^\s*(?:\(?-?[\d,]+\)?\s*){2,}$")
HEADER = re.compile(r"本年|上年|本期|上期|项目")

# 原始项目名 → 统一项目。用前缀匹配，因为附注名里带「(附注四(11))」这类后缀。
NORMALIZE = [
    ("存货跌价", "存货跌价"),
    ("长期股权投资减值", "长期股权投资减值"),
    ("固定资产减值", "固定资产减值"),
    ("在建工程减值", "在建工程减值"),
    ("无形资产减值", "无形资产减值"),
    ("商誉减值", "商誉减值"),
    ("合同资产减值", "合同资产减值"),
    ("投资性房地产减值", "投资性房地产减值"),
    ("其他非流动资产减值", "其他非流动资产减值"),
    ("其他流动资产减值", "其他流动资产减值"),
    ("其他资产减值", "其他资产减值"),
    ("预付账款减值", "预付账款减值"),
    ("应收账款坏账", "应收账款坏账"),
    ("其他应收账款坏账", "其他应收款坏账"),
    ("其他应收款坏账", "其他应收款坏账"),
    ("应收票据坏账", "应收票据坏账"),
    ("发放贷款和垫款", "发放贷款和垫款"),
    ("长期应收款减值", "长期应收款减值"),
    ("坏账损失", "其他坏账"),
    ("买入返售", "买入返售"),
]


def pdf_text(pdf: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    return result.stdout


def number(token: str) -> float:
    token = token.strip()
    negative = token.startswith("(") and token.endswith(")")
    return -float(token.strip("()").replace(",", "")) if negative else float(token.replace(",", ""))


def block_lines(text: str, title: str) -> list[str]:
    """截到下一个小节标题为止，否则下一张表的行会混进来。"""
    target = re.sub(r"\s+", "", title)
    lines = text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if re.sub(r"\s+", "", line).startswith(target)),
        None,
    )
    if start is None:
        return []
    body = [lines[start]]
    for line in lines[start + 1 : start + 40]:
        stripped = line.strip()
        if HEADING.match(stripped) and target not in re.sub(r"\s+", "", stripped):
            break
        if BARE_TOTAL.match(stripped) and "," in stripped:
            body.append(line)
            break
        body.append(line)
    return body


def split_row(line: str) -> tuple[str, list[tuple[float, int]]] | None:
    """返回 (标签, [(数值, 结尾列位置)])。结尾列位置用于判断数字落在哪一列。"""
    parts = [part for part in SPLIT.split(line.strip()) if part.strip()]
    numbers: list[tuple[float, int]] = []
    while parts and TOKEN.match(parts[-1]) and len(numbers) < 2:
        token = parts.pop()
        # 用「该 token 在原始行中的结尾位置」定位列
        end = line.rindex(token) + len(token)
        numbers.insert(0, (0.0 if token == "-" else number(token), end))
    if not numbers or not parts:
        return None
    return "".join(paragraph.strip() for paragraph in parts), numbers


def column_edges(rows: list[tuple[str, list[tuple[float, int]]]]) -> tuple[int, int] | None:
    """两列表的数字各自右对齐，聚类出两个右边界。只有一列时返回 None。"""
    ends = sorted({end for _, numbers in rows for _, end in numbers})
    if len(ends) < 2:
        return None
    clusters: list[list[int]] = [[ends[0]]]
    for value in ends[1:]:
        if value - clusters[-1][-1] <= 2:
            clusters[-1].append(value)
        else:
            clusters.append([value])
    if len(clusters) < 2:
        return None
    left = max(clusters[0])
    right = max(max(cluster) for cluster in clusters[1:])
    return left, right


def normalize(label: str) -> str | None:
    label = re.sub(r"\(附注[^)]*\)|（附注[^）]*）|【注】", "", label)
    label = re.sub(r"\(.*?\)|（.*?）", "", label)
    for prefix, unified in NORMALIZE:
        if label.startswith(prefix):
            return unified
    return None


def extract(lines: list[str], company: str) -> dict[str, tuple[float, float]]:
    parsed: list[tuple[str, list[tuple[float, int]]]] = []
    pending = ""
    for raw in lines:
        line = raw.strip()
        if (
            not line
            or "单位：" in line
            or "适用" in line
            or line.startswith("项目")
            or "本期发生额" in line
            or "上期发生额" in line
        ):
            continue
        if line.startswith("合计"):
            break
        if HEADING.match(line):
            # 小节标题不是续行，清空缓存，否则第一行标签会被拼成「58、资产减值损失…存货跌价」
            pending = ""
            continue
        row = split_row(line)
        if row is None:
            # 续行一定不含数字（「长期股权投资减值损失(附注四」），
            # 含数字的是表头（「2025 年度  2024 年度」），拼进去会污染标签。
            if re.search(r"\d", line) or not re.search(r"[\u4e00-\u9fa5]", line):
                pending = ""
                continue
            pending += line
            continue
        label, numbers = row
        parsed.append((pending + label, numbers))
        pending = ""

    edges = column_edges(parsed)

    items: dict[str, tuple[float, float]] = {}
    for label, numbers in parsed:
        unified = normalize(label)
        if unified is None or unified in items:
            continue
        if len(numbers) == 2:
            current, previous = numbers[0][0], numbers[1][0]
        elif edges is None:
            current, previous = numbers[0][0], 0.0
        elif numbers[0][1] <= edges[0] + 2:
            # 只印了一个数且落在左列 → 只有本期
            current, previous = numbers[0][0], 0.0
        else:
            # 落在右列 → 本期空缺，数字是上期
            current, previous = 0.0, numbers[0][0]
        items[unified] = (current, previous)
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

    profit_total: dict[tuple[str, str], float] = {}
    with (FIN / "利润表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["科目"] != "利润总额" or not row["报告期"].endswith("1231"):
                continue
            if row["报告期"][:4] not in ("2024", "2025"):
                continue
            try:
                profit_total[(row["公司"], row["报告期"][:4])] = float(row["数值"]) / 1e8
            except ValueError:
                continue

    rows: list[list[str]] = []
    warnings: list[str] = []
    for company, (filename, factor, asset_title, credit_title) in SOURCES.items():
        pdf = PDF_DIR / filename
        if not pdf.exists():
            print(f"  缺少 {filename}", file=sys.stderr)
            continue
        text = pdf_text(pdf)
        asset_items = extract(block_lines(text, asset_title), company)
        credit_items = extract(block_lines(text, credit_title), company)
        if not asset_items:
            print(f"  {company} 未匹配资产减值", file=sys.stderr)
            warnings.append(f"{company} 资产减值未匹配")
            continue

        for index, year in enumerate(("2025", "2024")):
            profit = profit_total.get((company, year), 0.0)
            totals: dict[str, float] = {"资产减值": 0.0, "信用减值": 0.0}
            for kind, items in (("资产减值", asset_items), ("信用减值", credit_items)):
                for unified, values in items.items():
                    if index >= len(values):
                        continue
                    raw = values[index] * factor / 1e8
                    # 统一为「正=损失」：海尔/格力印负数，美的印正数
                    loss = raw if company == "美的集团" else -raw
                    totals[kind] += loss
                    rows.append(
                        [
                            company,
                            year,
                            kind,
                            unified,
                            f"{loss:.2f}",
                            f"{loss / profit * 100:.2f}" if profit else "",
                            "披露值",
                        ]
                    )
            total = totals["资产减值"] + totals["信用减值"]
            rows.append(
                [
                    company,
                    year,
                    "小计",
                    "资产减值合计",
                    f"{totals['资产减值']:.2f}",
                    f"{totals['资产减值'] / profit * 100:.2f}" if profit else "",
                    "计算值",
                ]
            )
            rows.append(
                [
                    company,
                    year,
                    "小计",
                    "信用减值合计",
                    f"{totals['信用减值']:.2f}",
                    f"{totals['信用减值'] / profit * 100:.2f}" if profit else "",
                    "计算值",
                ]
            )
            rows.append(
                [
                    company,
                    year,
                    "小计",
                    "减值合计",
                    f"{total:.2f}",
                    f"{total / profit * 100:.2f}" if profit else "",
                    "计算值",
                ]
            )
        print(f"  {company}: 资产 {len(asset_items)} 项，信用 {len(credit_items)} 项")

    fields = ["公司", "年度", "类别", "项目", "金额(亿元)", "占利润总额%", "数据性质"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    print(f"\n{'公司':<8}{'年度':<6}{'资产减值':>10}{'信用减值':>10}{'合计':>9}{'占利润总额':>11}")
    print("-" * 56)
    for row in rows:
        if row[3] != "减值合计":
            continue
        pick = {r[3]: r[4] for r in rows if r[0] == row[0] and r[1] == row[1]}
        print(
            f"{row[0]:<8}{row[1]:<6}{pick.get('资产减值合计', '0'):>10}"
            f"{pick.get('信用减值合计', '0'):>10}{row[4]:>9}{row[5]:>10}%"
        )

    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    for warning in warnings:
        print(f"注意：{warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
