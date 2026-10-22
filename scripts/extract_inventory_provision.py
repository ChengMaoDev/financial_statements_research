"""存货跌价准备变动：计提、转回、转销各是多少。

为什么重要：
`存货明细.csv` 只有期末余额，看不出「这一年到底计提了多少、转回了多少、转销了多少」。
三者的经济含义完全不同：

- **计提**：当期利润的减项，直接压低毛利率；
- **转回**：可变现净值回升，利润的加项（准则允许范围内）；
- **转销**：存货已经卖掉或报废，准备随之注销，**不影响当期利润**。

把「转销」当成「转回」会让利润质量判断完全反过来。三家 2025 年的结构：

| 公司 | 期初准备 | 本期计提 | 转回/转销 | 期末准备 | 计提/期初 |
|---|---|---|---|---|---|
| 美的 | 9.24 亿 | 6.96 亿 | 5.54 亿 | 10.99 亿 | 75.3% |
| 海尔 | 16.98 亿 | 9.94 亿 | 7.94 亿 | 18.98 亿 | 58.5% |
| 格力 | 38.72 亿 | 4.76 亿 | 10.82 亿 | 32.67 亿 | 12.3% |

**格力是唯一「转销 > 计提」的**：期末准备从 38.72 亿降到 32.67 亿，减少 6.05 亿。
这不是它计提变谨慎，而是把 2024 年计提的准备随着存货卖掉而注销了。

五个坑：

1. **「转回」与「转销」在报表里合成一列**。三家都印成「转回或转销」/「转回数 + 转销及其他」
   的合并口径，只有极少数年份在附注文字里单独说明。**不能把这一列整体当成「转回」**
   （转回是利润加项，转销不是）。
2. **美的按千元、海尔/格力按元**。美的期初 924,408 千元 = 9.24 亿；按元读只有 0.09 亿。
3. **列数三家都不同，且有空单元格**：
   - 美的 5 列（期初 / 计提 / 转回或转销 / **外币折算差异** / 期末），**多一列汇率**；
   - 海尔 5 列（期初 / 计提 / 转回数 / 转销及其他 / 期末），**空单元格要按位置判**；
   - 格力 4 列（期初 / 计提 / 转回转销 / 期末）。
   按「取最后两个数」解析，美的会把「外币折算」当成期末。
4. **美的的变动表只有两个类别**（库存商品、原材料），而它的存货明细有五个类别。
   在产品、委托加工物资、合同履约成本**不计提跌价准备**，所以两行合计就是全部。
5. **海尔的「在产品」行整行空白**，不是 0——它在存货明细里也没有在产品跌价准备。
   空行与 0 在勾稽上等价，但在「是否披露」上不同，本表标「未披露」。

**格力存货跌价准备率 10.38% 是三家最高**（美的 1.67%、海尔 3.89%），
但它的计提率只有 12.3%，说明高准备率是**历史累积**的结果，不是当期谨慎。

用法：
    uv run python3 scripts/extract_inventory_provision.py --all
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

from pdf_util import pdf_text

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "年度报告"
FIN = ROOT / "财务数据"
OUT = FIN / "存货跌价准备变动.csv"

# (文件名, 换算倍数, 附注标题)
SOURCES = {
    "美的集团": ("美的2025.pdf", 1_000, "(b)    存货跌价准备分析如下："),
    "海尔智家": ("海尔2025.pdf", 1, "（2）存货跌价准备"),
    "格力电器": ("格力2025.pdf", 1, "（2）存货跌价准备及合同履约成本减值准备"),
}

# 类别名归一：三家叫法不同，语义对齐
NORMALIZE = {
    "库存商品": "库存商品",
    "产成品": "库存商品",
    "原材料": "原材料",
    "在产品及合同履约成本": "在产品及合同履约成本",
    "在产品": "在产品及合同履约成本",
    "开发成本": "开发成本",
}

NUMBER = re.compile(r"\(?-?[\d,]+(?:\.\d+)?\)?")
SPLIT = re.compile(r"\s{2,}")


def number(token: str) -> float:
    token = token.strip()
    negative = token.startswith("(") and token.endswith(")")
    return -float(token.strip("()").replace(",", "")) if negative else float(token.replace(",", ""))


def section(lines: list[str], heading: str, limit: int = 30) -> list[str]:
    target = re.sub(r"\s+", "", heading)
    start = next(
        (i for i, line in enumerate(lines) if re.sub(r"\s+", "", line).startswith(target)),
        None,
    )
    return lines[start : start + limit] if start is not None else []


# 序号（「（2）」「(2)」「2、」）不是金额，扫描前先摘掉
ENUM = re.compile(r"^\s*(?:[（(]\s*\d+\s*[）)]|\d+\s*[、.])")


def row_tokens(raw: str) -> tuple[str, list[tuple[int, float]]]:
    """拆出一行的标签与 (右边界列号, 数值)。"""
    body = ENUM.sub("", raw)
    offset = len(raw) - len(body)
    numbers: list[tuple[int, float]] = []
    for match in NUMBER.finditer(body):
        token = match.group(0)
        # 「2024 年」「12 月 31 日」这类表头日期不算金额
        if re.fullmatch(r"\d{1,2}", token) and _near_date(body, match.start()):
            continue
        if re.fullmatch(r"\d{4}", token) and body[match.end() : match.end() + 2].strip() == "年":
            continue
        numbers.append((match.end() + offset, number(token)))
    label = NUMBER.split(body)[0]
    return label.strip(), numbers


def _near_date(raw: str, pos: int) -> bool:
    after = raw[pos : pos + 3]
    return after.startswith(" 年") or after.startswith(" 月") or after.startswith(" 日")


def column_anchors(rows: list[list[tuple[int, float]]], count: int) -> list[int]:
    """用右边界聚类找出 count 个列锚点。"""
    ends = sorted({end for row in rows for end, _ in row})
    if len(ends) <= count:
        return ends
    # 单链聚类：相邻右边界差 ≤ 2 个字符视为同一列
    groups: list[list[int]] = [[ends[0]]]
    for value in ends[1:]:
        if value - groups[-1][-1] <= 2:
            groups[-1].append(value)
        else:
            groups.append([value])
    # 取最大的 count 个簇，按位置排序
    groups.sort(key=len, reverse=True)
    anchors = sorted(max(g) for g in groups[:count])
    return anchors


def assign(numbers: list[tuple[int, float]], anchors: list[int]) -> list[float | None]:
    """把每个数字分配到最近的列锚点。"""
    slots: list[float | None] = [None] * len(anchors)
    for end, value in numbers:
        nearest = min(range(len(anchors)), key=lambda i: abs(anchors[i] - end))
        slots[nearest] = value
    return slots


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    if not args.all:
        parser.print_help()
        return 0

    rows: list[list[str]] = []
    problems: list[str] = []

    for company, (filename, factor, heading) in SOURCES.items():
        lines = pdf_text(PDF_DIR / filename).splitlines()
        body = section(lines, heading)
        if not body:
            problems.append(f"{company} 未找到「{heading}」")
            continue

        # 先收集所有带数字的行，用来定列锚点
        parsed_rows: list[tuple[str, list[tuple[int, float]]]] = []
        for raw in body:
            label, numbers = row_tokens(raw)
            if not numbers:
                continue
            parsed_rows.append((label, numbers))
        if not parsed_rows:
            problems.append(f"{company} 无数据行")
            continue

        # 列数：取所有行里数字个数的众数
        counts: dict[int, int] = {}
        for _, numbers in parsed_rows:
            counts[len(numbers)] = counts.get(len(numbers), 0) + 1
        columns = max(counts, key=lambda k: counts[k])
        # 只用数据行（数字个数 = 众数）定锚点：表头行的「2024 年」会让锚点漂移
        anchors = column_anchors([n for _, n in parsed_rows if len(n) == columns], columns)

        collected: dict[str, list[float | None]] = {}
        total: list[float | None] | None = None
        for label, numbers in parsed_rows:
            # 表头行（「12 月 31 日  计提  转回或转销」）也会被拆成数字，
            # 但个数不等于列数，必须跳过，否则会覆盖掉真正的合计行
            if len(numbers) != columns:
                continue
            slots = assign(numbers, anchors)
            if "合计" in label:
                total = slots
                continue
            if not label:
                # 美的的合计行没有文字标签，整行只有数字。格力/海尔有「合计」二字。
                total = slots
                continue
            name = next((v for k, v in NORMALIZE.items() if k in label), None)
            if name is None:
                continue
            collected.setdefault(name, slots)

        if not collected:
            problems.append(f"{company} 未匹配到类别")
            continue

        def emit(
            name: str,
            item: str,
            value: float | None,
            company: str = company,
            factor: float = factor,
            heading: str = heading,
        ) -> None:
            if value is None:
                rows.append([company, "2025", name, item, "", "未披露", heading])
            else:
                rows.append(
                    [
                        company,
                        "2025",
                        name,
                        item,
                        f"{value * factor / 1e8:.2f}",
                        "披露值",
                        heading,
                    ]
                )

        for name, slots in collected.items():
            opening = slots[0] if slots else None
            increase = slots[1] if len(slots) > 1 else None
            # 中间列：美的的第 4 列是外币折算（加项），海尔的两列都是减项
            if company == "美的集团" and len(slots) > 4:
                middle = [abs(slots[2])] if slots[2] is not None else []
            else:
                middle = [abs(v) for v in slots[2:-1] if v is not None]
            closing = slots[-1] if slots else None
            emit(name, "期初余额", opening)
            emit(name, "本期计提", increase)
            turnover = slots[2] if len(slots) > 2 else None
            emit(name, "本期转回或转销", abs(turnover) if turnover is not None else None)
            if len(slots) > 4:
                # 5 列：第 4 列是「其他」（美的为外币报表折算差异，海尔为转销及其他）
                emit(name, "本期其他变动", slots[3])
            emit(name, "期末余额", closing)

            if None in (opening, increase, closing):
                continue
            adjusted = sum(middle) if middle else 0.0
            # 勾稽：期初 + 计提 − 转回/转销 (+ 外币折算) = 期末
            # 美的的第 4 列是「外币报表折算差异」，是**加项**；
            # 海尔/格力的中间列全是减项。方向搞反会正好差两倍的外币折算额。
            additive = (slots[3] or 0.0) if company == "美的集团" and len(slots) > 4 else 0.0
            gap = opening + increase - adjusted + additive - closing
            if abs(gap) > 1_000:
                problems.append(f"{company} {name} 勾稽差 {gap * factor / 1e8:.2f} 亿")

        if total is not None:
            for item, index in (("期初余额", 0), ("本期计提", 1), ("期末余额", -1)):
                if not total:
                    break
                value = total[index] if -len(total) <= index < len(total) else None
                rows.append(
                    [
                        company,
                        "2025",
                        "合计",
                        item,
                        f"{value * factor / 1e8:.2f}" if value is not None else "",
                        "披露值" if value is not None else "未披露",
                        heading,
                    ]
                )

    fields = ["公司", "年度", "存货类别", "项目", "金额(亿元)", "数据性质", "来源"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    print(f"\n{'公司':<8}{'期初准备':>10}{'本期计提':>10}{'期末准备':>10}{'计提/期初':>10}")
    print("-" * 50)
    for company in SOURCES:
        pick = {
            row[3]: float(row[4])
            for row in rows
            if row[0] == company and row[2] == "合计" and row[4]
        }
        opening = pick.get("期初余额", 0.0)
        increase = pick.get("本期计提", 0.0)
        closing = pick.get("期末余额", 0.0)
        ratio = increase / opening * 100 if opening else 0.0
        print(f"{company:<8}{opening:>10.2f}{increase:>10.2f}{closing:>10.2f}{ratio:>9.1f}%")

    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    for problem in problems:
        print(f"注意：{problem}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
