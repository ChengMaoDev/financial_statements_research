"""应付职工薪酬明细 + 应交税费明细：利润里压了多少没发出去的钱。

为什么重要：
「本期计提」与「本期支付」的差额，是判断「利润里压了多少没发出去的钱」的直接证据。
期末余额只是存量，把计提和支付拆开，才能看出当年是「多提少发」（占用员工的钱、
经营现金流虚高）还是「少提多发」（释放以前年度的负债、一次性减成本）。

2025 年三家（亿元）：

| 公司 | 期末余额 | 本期计提 | 本期支付 | 净计提 |
|---|---|---|---|---|
| 美的 | 96.45 | 413.40（仅短期薪酬） | 410.16（仅短期薪酬） | +4.85（总口径倒挤） |
| 海尔 | 56.18 | 363.06（含短期薪酬 345.03） | 357.45（含短期薪酬 339.38） | +5.61 |
| 格力 | 34.29 | 114.65（含短期薪酬 104.79） | 124.27（含短期薪酬 114.41） | **−9.62** |

格力是三家唯一「发得比提得多」的：期末余额从 43.91 亿降到 34.29 亿，一年净释放
9.62 亿，主要来自「工资、奖金、津贴和补贴」余额从 30.33 亿降到 19.63 亿——2024
年末计提的工资奖金在 2025 年集中发放。同期员工 71,966 人（2024 年 72,808 人）、
人均薪酬 16.63 万（海尔 26.18 万、美的 22.05 万）。海尔多提 5.61 亿、美的净增
4.85 亿，两家都在用应付薪酬沉淀现金，只有格力在释放。

应交税费是税负节奏的镜子（2025，亿元）：

| 公司 | 应交税费期末 | 应交税费期初 | 其中应交所得税 | 所得税费用 | 应交/费用 |
|---|---|---|---|---|---|
| 美的 | 71.64 | 61.94 | 44.85 | 85.65 | 52.4% |
| 海尔 | 33.93 | 39.15 | 21.30 | 33.16 | 64.2% |
| 格力 | 19.32 | 27.13 | 8.62 | 57.82 | **14.9%** |

格力应交所得税只占当年所得税费用的 14.9%，税缴得最急（预缴多、留抵少）；海尔
64.2% 挂在账上，美的居中。只看利润表的「所得税费用」看不出这个差异。

六个陷阱（都是实际踩到的）：

1. **美的单位是千元**。美的年报附注写「金额单位为人民币千元」，海尔/格力是元。
   美的数值要 ×1000 再折亿元，漏乘会让美的所有数字小 1000 倍。
2. **海尔 2024 年比较数被 2025 年报重述**。2025 年 3 月同一控制下合并卡奥斯模具
   （青岛），2025 年报把 2024 年末数重述了：应付职工薪酬 5,040,549,927.87 →
   5,057,260,277.99（+16,710,350.12 元），应交税费 3,915,081,920.18 →
   3,915,219,916.17（+137,995.99 元）。`财务数据/资产负债表.csv` 的 2024 年数用
   重述后口径，本表 2024 行取 2024 年报原披露值（否则 2024 年的计提/支付没有对应
   表），所以**海尔 2024 行与资产负债表差 0.17 亿，这是重述不是错误**。
3. **三家的薪酬项目名不一致，不能强行合并**。美的叫「其他短期薪酬」，海尔叫
   「其他」并多一行「短期带薪缺勤」，格力没有「其他」行（合计里也不含）。三家都
   有「其中：医疗保险费 / 工伤保险费 / 生育保险费」，它们是「社会保险费」的子项，
   直接相加会让短期薪酬虚增 25.38 亿（2025 年本期增加口径；期末口径 1.65 亿）。
   本表**保留附注原名**，只按统一顺序排列，不做名称合并；格力缺的「其他」写
   「未披露」，不补 0。

   应交税费则按本表九个标准项目归集，附注原名对应关系：

   | 附注原名 | 本表项目 | 谁在用 |
   |---|---|---|
   | 未交增值税 | 增值税 | 美的 |
   | 应交企业所得税 | 企业所得税 | 美的 |
   | 其他税费 | 其他 | 海尔 |
   | 其他 | 其他 | 美的、格力 |
   | 废弃电器电子产品处理基金 | 原样保留（额外行） | 海尔 2024 |
4. **变动表的列是「期初/增加/减少/期末」，不是「本期/上期」**。美的表头还跨行
   （「2024 年 / 12 月 31 日」与「2025 年 / 12 月 31 日」），按表头文字取数会把
   期末当期初。本脚本按数字右对齐的字符位置聚类分列。
5. **应付职工薪酬 ≠ 全部职工薪酬负债**。三家都另有「长期应付职工薪酬」：美的
   13.77 亿（补充退休福利 10.38 亿）、海尔 24.44 亿（含辞退福利 5.81 亿）、格力
   2.12 亿（设定受益计划净负债 2.11 亿）。本表只覆盖流动负债科目，否则「明细
   相加 = 资产负债表应付职工薪酬」这条勾稽永远对不上。
6. **空白格不是 0，但有时可以反推**。海尔 2025 年「一年内到期的其他福利」本期
   增加栏空白，用 期初 45,041,951.84 − 减少 10,781,769.04 = 期末 34,260,182.80
   可证增加为 0，本表填 0.00 并标「计算值」；海尔 2024 年「废弃电器电子产品处理
   基金」期末栏空白，合计倒挤为 0（该行 2025 年已消失）。其余取不到的写「未披露」，
   不填 0。

口径说明：
- 「本期计提」取附注「本期增加」，「本期支付」取「本期减少」（含非现金结转，不
  等于现金流量表「支付给职工以及为职工支付的现金」）。
- 应交税费只披露期末/期初余额，没有计提/支付列，中间两列留空。
- 美的附注只有「应付短期薪酬」+「其他」两行，不拆离职后福利/辞退福利/其他长期
  职工福利。那个「其他」3.37 亿是残差，本表归入「其他长期职工福利」并在项目名
  写明「附注未拆分」，同时把前两类标「未披露」，不假装是三项各自的披露值。
- 美的/格力的应交税费附注只拆「企业所得税 / 增值税 / 其他」三项，个人所得税、
  城建税、教育费附加、房产税、土地使用税、印花税都并进「其他」。本表那几行标
  「未披露」**不等于金额为 0**，而是没有单独披露、已包含在「其他」里。海尔的
  附注拆得较细（增值税、企业所得税、个人所得税、城建税、教育费附加、其他税费），
  但也没有房产税/土地使用税/印花税。
- 每个数字独立四舍五入到 0.01 亿元，所以明细相加与合计可能差 0.01~0.02 亿；
  自校验用元值，不受此影响。
- 类别：短期薪酬 / 离职后福利 / 辞退福利 / 其他长期职工福利 / 应交税费。
- 数据性质：披露值（附注原数）/ 计算值（勾稽倒挤）/ 未披露。

用法：
    uv run python3 scripts/extract_payroll_tax_payable.py --all
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
OUT = FIN / "职工薪酬与税费明细.csv"

# 公司 -> 年度 -> (PDF, 换算到元的倍数, 薪酬附注号, 税费附注号, 短期薪酬表号)
SOURCES: dict[str, dict[str, tuple[str, int, str, str, str]]] = {
    "美的集团": {
        "2025": ("美的2025.pdf", 1_000, "四(32)", "四(33)", "(a)"),
        "2024": ("美的2024.pdf", 1_000, "四(33)", "四(34)", "(a)"),
    },
    "海尔智家": {
        "2025": ("海尔2025.pdf", 1, "七、30", "七、31", "(2)"),
        "2024": ("海尔2024.pdf", 1, "七、30", "七、31", "(2)"),
    },
    "格力电器": {
        "2025": ("格力2025.pdf", 1, "五、36", "五、37", "(2)"),
        "2024": ("格力2024.pdf", 1, "五、36", "五、37", "(2)"),
    },
}

# 报表标准项目：缺哪项就补一行「未披露」，不做名称合并
SHORT_ITEMS = [
    "工资、奖金、津贴和补贴",
    "职工福利费",
    "社会保险费",
    "住房公积金",
    "工会经费和职工教育经费",
    "其他",
]
TAX_ITEMS = [
    "增值税",
    "企业所得税",
    "个人所得税",
    "城市维护建设税",
    "教育费附加",
    "房产税",
    "土地使用税",
    "印花税",
    "其他",
]
# 应交税费附注原名 -> 标准项目（只用于对齐，输出保留原名于「项目」列）
TAX_ALIAS = {
    "未交增值税": "增值税",
    "应交企业所得税": "企业所得税",
    "其他税费": "其他",
}

NUMBER = r"\(?-?[\d,]+(?:\.\d+)?\)?"
TAIL = re.compile(rf"((?:{NUMBER}|-)(?:\s{{2,}}(?:{NUMBER}|-))*)\s*$")
SPLIT = re.compile(r"\s{2,}")
CJK = re.compile(r"[\u4e00-\u9fa5]")
HEAD = re.compile(r"^(?:\((\d+)\)|（(\d+)）|(\d+)、)\.?\s*(.+)$")
ORDINAL = re.compile(r"^(?:[一二三四五六七八九十]+、|\d+、)")
CHILD = re.compile(r"^(?:其中|基本养老保险|失业保险费|企业年金|医疗保险费|工伤保险费|生育保险费)")


def number(token: str) -> float:
    token = token.strip()
    negative = token.startswith("(") and token.endswith(")")
    return -float(token.strip("()").replace(",", "")) if negative else float(token.replace(",", ""))


def split_row(line: str) -> tuple[str, list[tuple[float, int]]] | None:
    """返回 (去空白标签, [(数值, 行内结尾位置)])。

    结尾位置是分列的唯一依据：三家列宽不同，且有空白格（海尔 2025「一年内到期的
    其他福利」只有 3 个数），按位置聚类才不会把「减少」当成「增加」。
    """
    # 用保留缩进的行做坐标：美的合计行没有标签、从第 0 列开始，若先 strip 会让它的
    # 数字位置比同表其他行左移 24 个字符，聚类出多一列。
    body = line.rstrip()
    match = TAIL.search(body)
    if not match:
        return None
    segment, start = match.group(1), match.start(1)
    label = "".join(body[:start].split())
    numbers: list[tuple[float, int]] = []
    cursor = start
    for token in (part for part in SPLIT.split(segment) if part):
        offset = body.index(token, cursor)
        cursor = offset + len(token)
        numbers.append((0.0 if token == "-" else number(token), cursor))
    if not label and len(numbers) < 2:  # 页码
        return None
    if label and not CJK.search(label):  # 页眉/表头里的数字
        return None
    return label, numbers


def note_head(line: str) -> tuple[int, str] | None:
    match = HEAD.match(re.sub(r"\s+", "", line))
    if not match:
        return None
    index = match.group(1) or match.group(2) or match.group(3)
    return int(index), match.group(4)


def note_block(lines: list[str], title: str) -> list[str]:
    """截到下一个附注编号，避免把「长期应付职工薪酬」「其他应付款」混进来。"""
    start = next(
        (i for i, line in enumerate(lines) if (head := note_head(line)) and head[1] == title),
        None,
    )
    if start is None:
        return []
    number_ = note_head(lines[start])[0]
    for index in range(start + 1, len(lines)):
        head = note_head(lines[index])
        if head and head[0] == number_ + 1:
            return lines[start:index]
    return lines[start : start + 200]


def sections(lines: list[str]) -> dict[str, list[tuple[str, list[tuple[float, int]]]]]:
    """按小节切分：total（变动表）、short（短期薪酬明细）。

    短期薪酬表后面紧跟「设定提存计划列示」「辞退福利列示」，它们同属应付职工薪酬
    附注但**不属于短期薪酬**。不在这里截断，海尔的设定提存 2,759 万、辞退福利
    2,110 万会被算进短期薪酬明细，合计虚增 0.45 亿。
    """
    section = "total"
    out: dict[str, list[tuple[str, list[tuple[float, int]]]]] = {"total": [], "short": []}
    for raw in lines:
        norm = re.sub(r"\s+", "", raw)
        if not norm:
            continue
        if "应付职工薪酬列示" in norm:
            section = "total"
            continue
        if "短期薪酬列示" in norm or (norm.endswith("短期薪酬") and "应付" not in norm):
            section = "short"
            continue
        if "列示" in norm:  # 设定提存计划列示 / 辞退福利列示，不属于短期薪酬
            section = "stop"
            continue
        row = split_row(raw)
        if row and section in out:
            out[section].append(row)
    return out


def to_columns(
    rows: list[tuple[str, list[tuple[float, int]]]], n_cols: int
) -> dict[str, list[float | None]]:
    """按数字右对齐位置聚类分列；空缺格留 None，无标签行记为「合计」。

    美的的合计行没有标签（「9,645,445  9,160,841」整行只有数字）。无标签行按出现
    顺序直接铺满 n 列，不参与列边界聚类；否则它会被当成标签为空的行，与有标签行
    争夺同一列。
    """
    if not rows:
        return {}
    labeled = [row for row in rows if row[0]] or rows
    ends = sorted({end for _, numbers in labeled for _, end in numbers})
    groups: list[list[int]] = [[ends[0]]]
    for end in ends[1:]:
        if end - groups[-1][-1] <= 6:
            groups[-1].append(end)
        else:
            groups.append([end])
    while len(groups) > n_cols:  # 多出来的簇是标签内数字或跨列噪声
        gaps = [groups[i + 1][0] - groups[i][-1] for i in range(len(groups) - 1)]
        index = min(range(len(gaps)), key=lambda i: gaps[i])
        groups[index] += groups.pop(index + 1)
    if len(groups) < n_cols:
        raise ValueError(f"只识别出 {len(groups)} 列，期望 {n_cols} 列")
    edges = [max(group) for group in groups]
    out: dict[str, list[float | None]] = {}
    for label, numbers in rows:
        if not label and len(numbers) == n_cols:
            out.setdefault("合计", [value for value, _ in numbers])
            continue
        values: list[float | None] = [None] * n_cols
        for value, end in numbers:
            index = min(range(n_cols), key=lambda i: abs(edges[i] - end))
            if values[index] is None:
                values[index] = value
        out.setdefault(label or "合计", values)
    return out


def normalize(label: str) -> str:
    return ORDINAL.sub("", re.sub(r"\((?:附注[^)]*|[a-z])\)$", "", label))


def flow(values: list[float | None]) -> tuple[list[float | None], bool]:
    """四列变动表缺一个流量数时，用 期初+增加−减少=期末 反推。"""
    start, add, cut, end = values
    if start is None or end is None:
        return values, False
    if add is None and cut is not None:
        add = end - start + cut
    elif cut is None and add is not None:
        cut = start + add - end
    else:
        return values, False
    return [start, 0.0 if abs(add) < 0.5 else add, 0.0 if abs(cut) < 0.5 else cut, end], True


def signed(values: list[float | None]) -> list[float | None]:
    """美的的「本年减少」用括号印成负数，海尔/格力印正数。统一为「正=支付」。"""
    out = list(values)
    if len(out) > 2 and out[2] is not None:
        out[2] = abs(out[2])
    return out


def yi(value: float | None, factor: int) -> str:
    return "" if value is None else f"{value * factor / 1e8:.2f}"


def make_row(
    company: str,
    year: str,
    category: str,
    item: str,
    values: list[float | None] | None,
    nature: str,
    source: str,
    factor: int = 1,
) -> list[str]:
    """CSV 行：[期初, 计提, 支付, 期末]；values=None 表示整行未披露（留空，不填 0）。"""
    cells = [yi(value, factor) for value in (values or [None] * 4)]
    return [company, year, category, item, *cells, nature, source]


def parse_company(lines: list[str], company: str) -> dict:
    """返回 {'short': {标准项目: 四列}, 'short_total': 四列, 'total': {类别: (名, 四列)}}。"""
    parts = sections(note_block(lines, "应付职工薪酬"))
    two_col = company == "美的集团"
    raw_total = to_columns(parts["total"], 2 if two_col else 4)
    raw_short = to_columns(parts["short"], 4)

    short: dict[str, list[float | None]] = {}
    for label, values in raw_short.items():
        if label == "合计" or CHILD.match(label):
            continue
        short[normalize(label)] = signed(values)
    short_total = raw_short.get("合计")
    if short_total is not None:
        short_total = signed(short_total)

    total: dict[str, tuple[str, list[float | None], str]] = {}
    for label, values in raw_total.items():
        name = normalize(label)
        if name in ("合计", "") or name.startswith("短期薪酬") or name.startswith("应付短期薪酬"):
            continue
        if name.startswith("离职后福利"):
            total["离职后福利"] = ("设定提存计划", values, "披露值")
        elif name.startswith("辞退福利"):
            total["辞退福利"] = ("辞退福利", values, "披露值")
        elif "一年内到期的其他福利" in name:
            total["其他长期职工福利"] = (name, values, "披露值")
        elif name == "其他":  # 美的：短期薪酬之外的残差，附注未拆成三类
            total["其他长期职工福利"] = ("其他（附注未拆分）", values, "披露值")
        else:
            total["其他长期职工福利"] = (name, values, "披露值")

    total_row = raw_total.get("合计")
    return {"short": short, "short_total": short_total, "total": total, "total_row": total_row}


def parse_tax(lines: list[str]) -> dict[str, list[float | None]]:
    raw = to_columns(sections(note_block(lines, "应交税费"))["total"], 2)
    out: dict[str, list[float | None]] = {}
    for label, values in raw.items():
        name = normalize(label)
        if name == "合计":
            out["__total__"] = values
            continue
        out[TAX_ALIAS.get(name, name)] = values
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="提取三家 2025/2024 全部明细")
    args = parser.parse_args()
    if not args.all:
        parser.print_help()
        return 0

    rows: list[list[str]] = []
    checks: list[tuple[str, str, str, float, float]] = []
    problems: list[str] = []
    summary: dict[tuple[str, str], dict[str, float | None]] = {}
    balance = load_balance()

    for company, years in SOURCES.items():
        for year, (filename, factor, payroll_ref, tax_ref, short_ref) in years.items():
            pdf = PDF_DIR / filename
            if not pdf.exists():
                problems.append(f"缺少 {filename}")
                continue
            lines = pdf_text(pdf).splitlines()
            payroll = parse_company(lines, company)
            tax = parse_tax(lines)
            two_col = company == "美的集团"
            tag = f"{company} {year}"

            # —— 短期薪酬明细（保留附注原名，按统一顺序排列；缺项写「未披露」）——
            short = payroll["short"]
            order = [name for name in SHORT_ITEMS if name in short and name != "其他"]
            order += [name for name in short if name not in SHORT_ITEMS]
            order += [name for name in short if name == "其他"]
            # 格力没有「其他」行；美的叫「其他短期薪酬」，两个都算「其他」位
            if not any(name in short for name in ("其他", "其他短期薪酬")):
                order.append("其他")
            for name in order:
                values = short.get(name)
                if values is None:
                    rows.append(
                        make_row(
                            company,
                            year,
                            "短期薪酬",
                            name,
                            None,
                            "未披露",
                            f"附注{payroll_ref}{short_ref}",
                        )
                    )
                    continue
                start, add, cut, end = values
                rows.append(
                    make_row(
                        company,
                        year,
                        "短期薪酬",
                        name,
                        values,
                        "披露值",
                        f"附注{payroll_ref}{short_ref}",
                        factor,
                    )
                )
                if None not in values:
                    checks.append(
                        ("变动表勾稽", company, f"{year} {name}", 0.0, start + add - cut - end)
                    )

            # —— 离职后福利 / 辞退福利 / 其他长期职工福利 ——
            for category in ("离职后福利", "辞退福利", "其他长期职工福利"):
                item = payroll["total"].get(category)
                if item is None:
                    rows.append(
                        make_row(
                            company, year, category, "未单列", None, "未披露", f"附注{payroll_ref}"
                        )
                    )
                    continue
                name, values, nature = item
                if two_col:  # 美的两列表是「期末 / 期初」，无计提/支付
                    start, end = values[1], values[0]
                    values = [start, None, None, end]
                else:
                    values, filled = flow(values)
                    nature = "计算值" if filled else nature
                    if None not in values:
                        start, add, cut, end = values
                        checks.append(
                            (
                                "变动表勾稽",
                                company,
                                f"{year} {category}",
                                0.0,
                                start + add - cut - end,
                            )
                        )
                rows.append(
                    make_row(
                        company, year, category, name, values, nature, f"附注{payroll_ref}", factor
                    )
                )

            # —— 应交税费（按标准项目顺序，缺项补「未披露」）——
            extras = [name for name in tax if name not in TAX_ITEMS and name != "__total__"]
            for name in TAX_ITEMS + extras:
                values = tax.get(name)
                if values is None:
                    rows.append(
                        make_row(company, year, "应交税费", name, None, "未披露", f"附注{tax_ref}")
                    )
                    continue
                end, start = values[0], values[1]
                nature = "披露值"
                if end is None and start is not None:  # 期末栏空白，合计倒挤为 0
                    end, nature = 0.0, "计算值"
                rows.append(
                    make_row(
                        company,
                        year,
                        "应交税费",
                        name,
                        [start, None, None, end],
                        nature,
                        f"附注{tax_ref}",
                        factor,
                    )
                )

            # —— 自校验（全部用元，避免亿元四舍五入产生假差异）——
            total_row = payroll["total_row"]
            if total_row is None:
                problems.append(f"{tag} 未取到应付职工薪酬合计")
                continue
            note_start, note_end = (
                (total_row[1], total_row[0]) if two_col else (total_row[0], total_row[3])
            )
            short_total = payroll["short_total"] or [None] * 4

            def short_sum(index: int, items: dict[str, list[float | None]] = short) -> float:
                return sum((v[index] or 0.0) for v in items.values() if v)

            for label, index in (("期末", 3), ("期初", 0)):
                checks.append(
                    (
                        f"短期薪酬明细=表内合计({label})",
                        company,
                        year,
                        short_sum(index),
                        short_total[index] or 0.0,
                    )
                )

            # 应付职工薪酬合计 = 短期薪酬 + 其余三类（美的的「其他」是残差）
            cat_end = sum(
                (v[1][0] if two_col else v[1][3]) or 0.0 for v in payroll["total"].values()
            )
            cat_start = sum(
                (v[1][1] if two_col else v[1][0]) or 0.0 for v in payroll["total"].values()
            )
            checks.append(
                ("全部明细=附注合计(期末)", company, year, short_sum(3) + cat_end, note_end)
            )
            checks.append(
                ("全部明细=附注合计(期初)", company, year, short_sum(0) + cat_start, note_start)
            )

            tax_total = tax.get("__total__") or [None, None]
            tax_end = sum((v[0] or 0.0) for k, v in tax.items() if k != "__total__")
            tax_start = sum((v[1] or 0.0) for k, v in tax.items() if k != "__total__")
            checks.append(
                ("应交税费明细=附注合计(期末)", company, year, tax_end, tax_total[0] or 0.0)
            )
            checks.append(
                ("应交税费明细=附注合计(期初)", company, year, tax_start, tax_total[1] or 0.0)
            )

            summary[(company, year)] = {
                "end": note_end * factor,
                "start": note_start * factor,
                "add": (total_row[1] or 0.0) * factor if not two_col else None,
                "cut": (total_row[2] or 0.0) * factor if not two_col else None,
                "short_add": (short_total[1] or 0.0) * factor,
                "short_cut": (short_total[2] or 0.0) * factor,
                "tax_end": (tax_total[0] or 0.0) * factor,
                "tax_start": (tax_total[1] or 0.0) * factor,
            }
            # 附注合计 vs 资产负债表
            book = balance.get((company, year, "应付职工薪酬"))
            if book is not None:
                checks.append(
                    ("应付职工薪酬附注=资产负债表", company, year, note_end * factor, book)
                )
            book = balance.get((company, year, "应交税费"))
            if book is not None:
                checks.append(
                    ("应交税费附注=资产负债表", company, year, (tax_total[0] or 0.0) * factor, book)
                )
                # 用户要求的另一条：明细直接对报表，而不是只对附注合计
                checks.append(("应交税费明细=资产负债表", company, year, tax_end * factor, book))
            book = balance.get((company, year, "应付职工薪酬"))
            if book is not None:
                # 短期薪酬 + 其余三类（明细相加）直接对资产负债表
                checks.append(
                    (
                        "应付职工薪酬明细=资产负债表",
                        company,
                        year,
                        (short_sum(3) + cat_end) * factor,
                        book,
                    )
                )

    fields = [
        "公司",
        "年度",
        "类别",
        "项目",
        "期初(亿元)",
        "本期计提/增加(亿元)",
        "本期支付/减少(亿元)",
        "期末(亿元)",
        "数据性质",
        "来源",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    print(
        f"\n{'公司':<8}{'年度':<6}{'期末':>8}{'计提':>10}{'支付':>10}{'净计提':>9}{'税费期末':>9}"
    )
    print("-" * 60)
    for (company, year), v in summary.items():
        add = "未披露" if v["add"] is None else f"{v['add'] / 1e8:.2f}"
        cut = "未披露" if v["cut"] is None else f"{v['cut'] / 1e8:.2f}"
        net = (v["end"] - v["start"]) / 1e8
        print(
            f"{company:<8}{year:<6}{v['end'] / 1e8:>8.2f}{add:>10}{cut:>10}"
            f"{net:>+9.2f}{v['tax_end'] / 1e8:>9.2f}"
        )
    print("美的附注只披露短期薪酬的计提/支付；总口径净计提由期初、期末余额倒挤")

    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行", file=sys.stderr)
    report(checks, balance, summary)
    for problem in problems:
        print(f"注意：{problem}", file=sys.stderr)
    return 0


def load_balance() -> dict[tuple[str, str, str], float]:
    out: dict[tuple[str, str, str], float] = {}
    with (FIN / "资产负债表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["报告期"] not in ("20251231", "20241231"):
                continue
            if row["科目"] not in ("应付职工薪酬", "应交税费"):
                continue
            out[(row["公司"], row["报告期"][:4], row["科目"])] = float(row["数值"])
    return out


def report(
    checks: list[tuple[str, str, str, float, float]],
    balance: dict[tuple[str, str, str], float],
    summary: dict[tuple[str, str], dict[str, float | None]],
) -> None:
    print("\n【自校验】明细 / 勾稽 / 报表对照（单位：元）", file=sys.stderr)
    passed = 0
    for name, company, year, left, right in checks:
        gap = left - right
        if abs(gap) <= 1.0:
            passed += 1
            continue
        note = "（2025 年报重述 2024 比较数）" if "资产负债表" in name else ""
        print(
            f"  差异 {name} {company} {year}: {left:,.2f} vs {right:,.2f}"
            f"（差 {gap:+,.2f} 元）{note}",
            file=sys.stderr,
        )
    print(f"  {passed}/{len(checks)} 项通过（容差 1 元）", file=sys.stderr)

    print("\n【附注合计 vs 资产负债表】", file=sys.stderr)
    for (company, year), v in summary.items():
        for item, key in (("应付职工薪酬", "end"), ("应交税费", "tax_end")):
            book = balance.get((company, year, item))
            if book is None:
                print(f"  {company} {year} {item}: 资产负债表无数据", file=sys.stderr)
                continue
            note = v[key] or 0.0
            gap = (note - book) / 1e8
            flag = "OK" if abs(gap) <= 0.01 else f"差异 {gap:+.2f} 亿（重述）"
            print(
                f"  {company} {year} {item}: 附注 {note / 1e8:.2f} / 报表 {book / 1e8:.2f}  {flag}",
                file=sys.stderr,
            )

    print("\n【上年期末 = 本年期初】", file=sys.stderr)
    for company in SOURCES:
        last, now = summary.get((company, "2024")), summary.get((company, "2025"))
        if not last or not now:
            continue
        gap = ((now["start"] or 0.0) - (last["end"] or 0.0)) / 1e8
        flag = "OK" if abs(gap) <= 0.01 else f"差 {gap:+.2f} 亿（2025 年报重述 2024 比较数）"
        print(
            f"  {company}: 2025 期初 {now['start'] / 1e8:.2f} / "
            f"2024 期末 {last['end'] / 1e8:.2f}  {flag}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    sys.exit(main())
