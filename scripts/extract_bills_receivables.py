"""应收票据 / 应收款项融资 / 应收账款 三分结构，以及票据背书贴现。

为什么重要：
这三项合计是家电公司「渠道话语权」在资产负债表上的直接体现，也是「收现比」
失真的根源——卖货收的是票据而不是现金，收现比就难看；把票据贴现掉，收现比
又好看。只看「应收账款」会漏掉票据，只看「应收票据及应收账款」又会漏掉应收
款项融资（它在报表上是独立一行，不在前者里）。

2025 年末三家三分结构（亿元）：

| 公司 | 应收票据 | 应收账款 | 应收款项融资 | 合计 | 占营业收入 |
|---|---|---|---|---|---|
| 美的 | 52.47 | 404.50 | 149.35 | 606.32 | 13.28% |
| 海尔 | 64.82 | 270.66 | 17.88 | 353.36 | 11.69% |
| 格力 | 0.01 | 159.87 | 64.96 | 224.84 | 13.19% |

占比几乎一样，结构完全不同：应收款项融资占三分合计，美的 24.6%、格力 28.9%、
海尔只有 5.1%。海尔把票据留在「应收票据」里（商业承兑 46.33 亿，占其票据
71.5%），美的/格力则把银行承兑装进「应收款项融资」随时准备贴现。

陷阱（都是实际踩到的）：

1. **「已终止确认」的年度累计流量 ≠ 期末未到期存量，差 3 倍**。美的 2025 年
   背书贴现并终止确认的银行承兑汇票全年 373.79 亿，但期末尚未到期的只有
   121.48 亿（应收票据 4.46 亿 + 应收款项融资 117.01 亿）。拿 373.79 亿当「表外
   票据余额」，或拿它跟 149.35 亿的应收款项融资比，都会错得离谱。
2. **「未终止确认」仍挂在表内，方向和已终止确认相反**。美的 2025 年末未终止
   确认 25.82 亿（银行承兑 25.67 + 商业承兑 0.14），风险报酬没转移，还在应收
   票据里；格力 2024 年末未终止确认 131.11 万（商业承兑）。两者不能相加成
   「票据总规模」。
3. **美的年报单位是千元**。应收票据 5,246,763 是千元（52.47 亿），直接除以 1e8
   会读成 0.05 亿。海尔/格力是元。三家混表必须先统一乘数。
4. **「应收票据及应收账款」不含应收款项融资**，三家都严格勾稽：美的
   45,696,860 千元 = 5,246,763 + 40,450,097；海尔 335.48 = 64.82 + 270.66；
   格力 159.88 = 0.88 + 159.87。把应收款项融资也塞进去会多算 149.35 / 17.88 /
   64.96 亿。
5. **海尔 2024 年比较数被追溯重述**（同一控制下企业合并：优瑾、卡奥斯模具）。
   2024 年报应收账款净额 264.73 亿，2025 年报比较列 264.95 亿（差 0.22 亿）；
   应收票据 121.19 → 121.80 亿（差 0.61 亿）；应收款项融资 3.60 → 4.13 亿（差
   0.53 亿）。本表 2024 年一律取 2025 年报比较列，才和 `资产负债表.csv` 对得上。
6. **空白列 ≠ 漏印**。格力 2024 年末应收票据整列为空（2024 年报、2025 年报都
   空），实为 0；若按「取最后一个数」解析，会把 2023 年末的 0.87 亿当成 2024
   年末。海尔 2025 年应收款项融资里的「应收账款」也是空白（2024 年末 1.77 亿），
   空白=0。
7. **列位置会跨页漂移**。海尔 2024 年应收票据的坏账准备行在第二页，表头重排后
   列位置差 12 个字符；沿用第一页锚点会把本期 98.76 万读成上期。另外格力
   `46,500.00` 这种短数字，用「数字中点」判列会落在两列正中，必须用「数字
   起点」比表头锚点中点。
8. **美的正文与附注互相矛盾**。第三节写「不存在主要资产被抵押、质押等权利受限
   情形」，附注四(27) 却披露 80.49 亿质押借款以应收票据为质押物，另有 4.27 亿
   以房产+应收账款质押。正文那句话不能当「零质押」用。
9. **美的的应收款项融资不拆票据/应收账款**。149.35 亿只有一个总数，附注只说
   「应收账款和银行承兑汇票」；海尔、格力都拆。因此无法判断美的这 149.35 亿里
   有多少是票据。
10. **海尔不披露应收票据的背书贴现表**。它只披露了应收款项融资口径的 99.69 亿
    已终止确认，而应收票据一年掉了 46.8%（121.80 → 64.82 亿，「主要是票据贴现
    所致」），贴现规模无处可查——这是披露缺口，不是零。
11. **「减：坏账准备」是两家共用的标签**。应收票据表和应收账款表都叫这个名字，
    同一家公司的两个区块里各有一份，按标签取数必须限定在各自的区块内，否则
    格力的 30.79 亿应收坏账会被当成应收票据坏账（实际只有 4.65 万）。

用法：
    uv run python3 scripts/extract_bills_receivables.py --all
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from pdf_util import pdf_text

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "年度报告"
FIN = ROOT / "财务数据"
OUT = FIN / "票据与应收结构.csv"

COMPANIES = ("美的集团", "海尔智家", "格力电器")
SHORT = {"美的集团": "美的", "海尔智家": "海尔", "格力电器": "格力"}
# 美的年报金额单位是千元，海尔/格力是元
UNIT = {"美的集团": 1_000, "海尔智家": 1, "格力电器": 1}
AGING = {
    "美的集团": ("1年以内", "1-2年", "2-3年", "3-5年", "5年以上"),
    "海尔智家": ("1年以内", "1-2年", "2-3年", "3年以上"),
    "格力电器": ("1年以内", "1-2年", "2-3年", "3年以上"),
}
NOTE = {
    "美的集团": {
        "2025": {
            "notes": "附注四(4)",
            "ar": "附注四(5)",
            "arf": "附注四(7)",
            "endorse": "附注四(4)(b)、四(7)",
            "pledge": "附注四(27)",
        },
        "2024": {
            "notes": "附注四(4)",
            "ar": "附注四(5)",
            "arf": "附注四(7)",
            "endorse": "附注四(4)(b)、四(7)",
            "pledge": "附注四(28)",
        },
    },
    "海尔智家": {
        "2025": {
            "notes": "附注七、4",
            "ar": "附注七、5",
            "arf": "附注七、6(1)",
            "endorse": "附注七、6(3)",
            "pledge": "附注七、4、6(2)",
        },
        "2024": {
            "notes": "附注七、4",
            "ar": "附注七、5",
            "arf": "附注七、6(1)",
            "endorse": "附注七、6(3)",
            "pledge": "附注七、4、6(2)",
        },
    },
    "格力电器": {
        "2025": {
            "notes": "附注五、3",
            "ar": "附注五、4",
            "arf": "附注五、6(1)",
            "endorse": "附注五、3(3)、6(3)",
            "pledge": "附注五、3(2)、6(2)",
        },
        "2024": {
            "notes": "附注五、4",
            "ar": "附注五、5",
            "arf": "附注五、7(1)",
            "endorse": "附注五、4(3)、7(3)",
            "pledge": "附注五、4(2)、7(2)",
        },
    },
}

NUMBER = re.compile(r"\(?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?|\(?\d{4,}(?:\.\d+)?\)?")
ANCHOR = re.compile(
    r"期末未终止确认金额|期末终止确认金额|期末已质押金额|未终止确认|已终止确认"
    r"|期末余额|期初余额|\d{4}\s*年\s*12\s*月\s*31\s*日"
)
AGING_LABEL = re.compile(
    r"^(?:一年以内|一到二年|二到三年|三到五年|五年以上"
    r"|1年以内|1-2年|1至2年|2-3年|2至3年|3年以上)$"
)
PAREN_NOTE = re.compile(r"\([a-zA-Z0-9]\)|（[a-zA-Z0-9]）")

Rows = dict[str, tuple[float | None, float | None]]


@dataclass(frozen=True)
class Entry:
    company: str
    year: str
    category: str
    item: str
    value: float | None
    nature: str
    source: str


def squash(text: str) -> str:
    """去掉所有空白，用于匹配被换行/对齐空格劈开的句子。"""
    return re.sub(r"\s+", "", text)


def load_text(short: str, year: str) -> list[str]:
    pdf = PDF_DIR / f"{short}{year}.pdf"
    return pdf_text(pdf).split("\n")


def number(token: str) -> float:
    token = token.strip()
    negative = token.startswith("(") and token.endswith(")")
    value = float(token.strip("()").replace(",", ""))
    return -value if negative else value


def heading(lines: list[str], pattern: str) -> int:
    """找标题行的下标；squash 后 match，避免命中正文里的交叉引用。"""
    regex = re.compile(pattern)
    for index, line in enumerate(lines):
        if regex.match(squash(line)):
            return index
    raise LookupError(f"未找到标题 {pattern}")


def header_line(lines: list[str], pattern: str) -> int:
    """找表头行的下标（表头本身不含数据，只看锚点词）。"""
    regex = re.compile(pattern)
    for index, line in enumerate(lines):
        if regex.search(squash(line)) and anchor_starts(line):
            return index
    raise LookupError(f"未找到表头 {pattern}")


def anchor_starts(line: str) -> tuple[int, ...]:
    """表头里各列锚点的起始位置；带句读的长句不是表头。"""
    if "。" in line or "，" in line or len(line.strip()) > 90:
        return ()
    return tuple(match.start() for match in ANCHOR.finditer(line))


def clean_label(text: str) -> str:
    text = PAREN_NOTE.sub("", text)
    return re.sub(r"\s+", "", text.replace("—", "").replace("－", ""))


def assign(
    numbers: list[tuple[float, int]], layout: tuple[int, ...]
) -> tuple[float | None, float | None]:
    """按「数字起点 vs 表头锚点中点」判断落在哪一列。

    不能用数字中点：格力 2025 应收票据的 `46,500.00` 很短，中点正好落在两列
    之间，会被误判成期初。金额是右对齐的，起点比中点稳。
    """
    if len(numbers) >= 2:
        return numbers[0][0], numbers[-1][0]
    value, start = numbers[0]
    if len(layout) == 1 or start < (layout[0] + layout[1]) / 2:
        return value, None
    return None, value


def read_pairs(lines: list[str], start: int, stop: str, limit: int = 60) -> Rows:
    """读一张「项目 + 本期 + 上期」表，返回 {项目: (本期, 上期)}。

    跨页时表头会重复，遇到就重新锚定列位置：海尔 2024 应收票据的坏账准备行
    在第二页，列位置和第一页差 17 个字符，沿用第一页锚点会把本期读成上期。
    """
    layout: tuple[int, ...] = ()
    rows: Rows = {}
    for raw in lines[start : start + limit]:
        if stop and re.search(stop, squash(raw)):
            break
        anchors = anchor_starts(raw)
        if anchors:
            layout = anchors
            continue
        numbers = [(number(m.group()), m.start()) for m in NUMBER.finditer(raw)]
        if not numbers or not layout:
            continue
        label = clean_label(raw[: numbers[0][1]])
        rows.setdefault(label, assign(numbers, layout))
    return rows


def get(rows: Rows, *names: str) -> tuple[float | None, float | None]:
    for name in names:
        if name in rows:
            return rows[name]
    return (None, None)


def yi(value: float | None, factor: float) -> float | None:
    """原始金额（年报单位）折亿元。"""
    return None if value is None else value * factor / 1e8


def magnitude(value: float | None) -> float | None:
    """坏账准备的符号不统一（美的带括号，海尔/格力不带），统一成正值。"""
    return None if value is None else abs(value)


def plus(
    left: tuple[float | None, float | None], right: tuple[float | None, float | None]
) -> tuple[float | None, float | None]:
    out: list[float | None] = []
    for a, b in zip(left, right, strict=True):
        out.append(None if a is None and b is None else (a or 0.0) + (b or 0.0))
    return out[0], out[1]


def to_yi(rows: Rows, factor: float) -> Rows:
    return {
        key: tuple(None if v is None else v * factor / 1e8 for v in pair)  # type: ignore[misc]
        for key, pair in rows.items()
    }


def aging_rows(rows: Rows, company: str) -> Rows:
    buckets = [value for label, value in rows.items() if AGING_LABEL.match(label)]
    names = AGING[company]
    if len(buckets) != len(names):
        raise ValueError(f"{company} 账龄分档 {len(buckets)} 档，预期 {len(names)} 档")
    return {f"aging_{name}": value for name, value in zip(names, buckets, strict=True)}


def structure(company: str, lines: list[str]) -> Rows:
    """从 2025 年报取本期 + 比较期两列，统一折算成亿元。"""
    factor = UNIT[company]
    out: Rows = {}
    if company == "美的集团":
        notes = read_pairs(lines, heading(lines, r"^\(4\)应收票据$"), r"^\(a\)坏账准备")
        out["notes_bank"] = get(notes, "银行承兑汇票")
        out["notes_comm"] = get(notes, "商业承兑汇票")
        out["notes_gross"] = plus(out["notes_bank"], out["notes_comm"])
        out["notes_prov"] = get(notes, "减：坏账准备")
        out["notes_net"] = get(notes, "")
        single, combo = midea_provision_split(lines)
        out["notes_prov_single"] = single
        out["notes_prov_combo"] = combo

        ar = read_pairs(lines, heading(lines, r"^\(5\)应收账款$"), r"^\(a\)应收账款账龄")
        out["ar_gross"] = get(ar, "应收账款")
        out["ar_prov"] = get(ar, "减：坏账准备")
        out["ar_net"] = get(ar, "")
        aging = read_pairs(lines, heading(lines, r"^\(a\)应收账款账龄分析如下"), r"^于\d")
        out.update(aging_rows(aging, company))

        arf = read_pairs(
            lines, heading(lines, r"^\(7\)应收款项融资$"), r"^本集团的应收款项融资", limit=10
        )
        out["arf_total"] = get(arf, "应收款项融资")
    elif company == "海尔智家":
        notes = read_pairs(
            lines, heading(lines, r"^4、应收票据$"), r"^[（(]2[）)][.．]?[\u4e00-\u9fa5]"
        )
        out["notes_bank"] = get(notes, "银行承兑汇票")
        out["notes_comm"] = get(notes, "商业承兑汇票")
        out["notes_gross"] = get(notes, "应收票据余额")
        out["notes_prov"] = get(notes, "坏账准备")
        out["notes_net"] = get(notes, "应收票据净额")

        ar = read_pairs(
            lines, heading(lines, r"^5、应收账款$"), r"^[（(]2[）)][.．]?[\u4e00-\u9fa5]"
        )
        out["ar_gross"] = get(ar, "应收账款余额")
        out["ar_prov"] = get(ar, "坏账准备")
        out["ar_net"] = get(ar, "应收账款净额")
        out.update(aging_rows(ar, company))

        arf = read_pairs(
            lines,
            heading(lines, r"^6、应收款项融资$"),
            r"^[（(]2[）)][.．]?[\u4e00-\u9fa5]",
            limit=16,
        )
        out["arf_notes"] = get(arf, "应收票据")
        out["arf_ar"] = get(arf, "应收账款")
        out["arf_total"] = get(arf, "合计")
    else:
        notes = read_pairs(
            lines, heading(lines, r"^3、应收票据$"), r"^[（(]2[）)][.．]?[\u4e00-\u9fa5]"
        )
        out["notes_comm"] = get(notes, "商业承兑汇票")
        out["notes_gross"] = get(notes, "小计")
        out["notes_prov"] = get(notes, "减：坏账准备")
        out["notes_net"] = get(notes, "合计")

        ar = read_pairs(
            lines, heading(lines, r"^4、应收账款$"), r"^[（(]2[）)][.．]?[\u4e00-\u9fa5]"
        )
        out["ar_gross"] = get(ar, "小计")
        out["ar_prov"] = get(ar, "减：坏账准备")
        out["ar_net"] = get(ar, "合计")
        out.update(aging_rows(ar, company))

        arf = read_pairs(
            lines,
            heading(lines, r"^6、应收款项融资$"),
            r"^[（(]2[）)][.．]?[\u4e00-\u9fa5]",
            limit=30,
        )
        out["arf_notes"] = get(arf, "以公允价值计量的应收票据")
        out["arf_bank"] = get(arf, "其中：银行承兑汇票")
        out["arf_fin"] = get(arf, "财务公司承兑汇票")
        out["arf_ar"] = get(arf, "以公允价值计量的应收账款")
        out["arf_total"] = get(arf, "合计")
    return to_yi(out, factor)


def midea_provision_split(
    lines: list[str],
) -> tuple[tuple[float | None, float | None], tuple[float | None, float | None]]:
    """美的「应收票据坏账准备按类别」表：本期块 + 上期块。

    这张表有 5 列（余额、占比%、坏账准备、计提比例%、账面价值），不是普通的
    两列表；坏账准备带括号，且「计提比例%」的百分号会被 NUMBER 跳过，所以
    「取前两个数」会拿到（余额, 坏账准备）当成（本期, 上期）。这里显式只认
    带括号的那个数。
    """
    single: list[float | None] = [None, None]
    combo: list[float | None] = [None, None]
    block = -1
    for raw in lines[heading(lines, r"^\(a\)坏账准备") :][:40]:
        text = squash(raw)
        if re.match(r"^\d{4}年12月31日$", text):
            block += 1
            continue
        if block < 0 or block > 1:
            continue
        values = [number(m.group()) for m in NUMBER.finditer(raw)]
        negatives = [v for v in values if v < 0]
        if not negatives:
            continue
        if text.startswith("单项计提坏账准备"):
            single[block] = negatives[0]
        elif text.startswith("按组合计提坏账准备"):
            combo[block] = negatives[0]
    return (single[0], single[1]), (combo[0], combo[1])


def endorse(company: str, lines: list[str]) -> dict[str, float | None]:
    """已背书/贴现且期末未到期的存量（亿元）；美的另取年度累计流量。

    注意单位：表格里的金额跟年报单位走（美的千元），但美的附注四(7) 的正文
    句子直接写「元」（37,379,046,000 元），两者不能共用一个乘数。
    """
    out: dict[str, float | None] = {}
    factor = UNIT[company]
    text = squash("\n".join(lines))

    def prose(pattern: str) -> float | None:
        """正文里带「元」的金额，已经是元，直接折亿。"""
        match = re.search(pattern, text)
        return number(match.group(1)) / 1e8 if match else None

    if company == "美的集团":
        table = read_pairs(
            lines, header_line(lines, r"已终止确认.*未终止确认"), r"^\(i\)", limit=12
        )
        # 「—」= 零，不是未披露
        out["notes_comm_derec"] = get(table, "商业承兑汇票")[0] or 0.0
        out["notes_comm_underec"] = get(table, "商业承兑汇票")[1]
        out["notes_bank_derec"] = get(table, "银行承兑汇票")[0]
        out["notes_bank_underec"] = get(table, "银行承兑汇票")[1]
        out["notes_derec"] = get(table, "")[0]
        out["notes_underec"] = get(table, "")[1]
        # 表格是千元，先折亿；下面两句正文写的是「元」，不能再乘
        scaled = {key: None if v is None else v * factor / 1e8 for key, v in out.items()}
        scaled["arf_derec"] = prose(
            r"已背书或已贴现但尚未到期的银行承兑汇票为([\d,.]+)元\(\d{4}年12月31日：[\d,]+元\)"
        )
        scaled["arf_bank_derec"] = scaled["arf_derec"]
        scaled["arf_underec"] = 0.0 if scaled["arf_derec"] is not None else None
        scaled["flow_derec"] = prose(
            r"终止确认的银行承兑汇票账面价值为([\d,.]+)元\(\d{4}年度：[\d,]+元\)"
        )
        scaled["flow_loss"] = prose(r"相关贴现损失([\d,.]+)元\(\d{4}年度：[\d,]+元\)")
        return scaled

    if company == "海尔智家":
        # 年报没有应收票据的背书贴现表，只有应收款项融资口径
        out["notes_derec"] = None
        out["notes_underec"] = None
        table = read_pairs(
            lines,
            heading(lines, r"^[（(]3[）)][.．]?期末公司已背书或贴现"),
            r"^[（(]4[）)][.．]?[\u4e00-\u9fa5]",
            limit=10,
        )
        out["arf_notes_derec"] = get(table, "应收票据")[0]
        out["arf_derec"] = get(table, "合计")[0]
        out["arf_underec"] = 0.0
        return {key: None if v is None else v * factor / 1e8 for key, v in out.items()}

    start = heading(lines, r"^[（(]3[）)][.．]?期末已背书或贴现")
    if "无。" in squash("".join(lines[start : start + 10])):
        out["notes_derec"] = 0.0
        out["notes_underec"] = 0.0
    else:
        notes = read_pairs(lines, start, r"^[（(]4[）)][.．]?[\u4e00-\u9fa5]", limit=12)
        # 该列整列空白 = 0：格力 2024 只有商业承兑 131.11 万在「未终止确认」列
        out["notes_derec"] = get(notes, "合计")[0] or 0.0
        out["notes_underec"] = get(notes, "合计")[1] or 0.0
        out["notes_comm_derec"] = get(notes, "商业承兑汇票")[0] or 0.0
        out["notes_comm_underec"] = get(notes, "商业承兑汇票")[1]
    arf = read_pairs(
        lines,
        heading(lines, r"^[（(]3[）)][.．]?期末公司已背书或贴现"),
        r"^[（(]4[）)][.．]?[\u4e00-\u9fa5]",
        limit=14,
    )
    out["arf_derec"] = get(arf, "合计")[0]
    out["arf_underec"] = get(arf, "合计")[1] or 0.0
    out["arf_bank_derec"] = get(arf, "银行承兑汇票")[0]
    out["arf_fin_derec"] = get(arf, "财务公司承兑汇票")[0]
    out["arf_ar_derec"] = get(arf, "应收账款")[0]
    return {key: None if v is None else v * factor / 1e8 for key, v in out.items()}


def pledge(company: str, lines: list[str]) -> dict[str, float | None]:
    """已质押的票据 / 应收款项融资 / 应收账款（亿元），取当期（年报本期列）。"""
    out: dict[str, float | None] = {}
    factor = UNIT[company]
    text = squash("\n".join(lines))

    if company == "美的集团":
        # 只披露质押借款金额，没披露质押票据的账面价值；正文写「元」
        match = re.search(r"折合人民币约为([\d,.]+)元的质押借款，质押物为应收票据", text)
        out["loan_pledged_notes"] = number(match.group(1)) / 1e8 if match else None
        out["notes"] = None
        out["arf"] = None
        out["ar"] = None
        return out

    if company == "海尔智家":
        match = re.search(r"期末质押的应收票据为([\d,.]+)元", text)
        out["notes"] = number(match.group(1)) / 1e8 if match else None
        match = re.search(r"期末公司已质押的应收款项融资金额为([\d,.]+)元", text)
        if match:
            out["arf"] = number(match.group(1)) / 1e8
        else:
            # 2024 年报该节勾「□适用 √不适用」= 零，不是未披露。
            # 必须限定在标题后 3 行内，全文有几十处「不适用」。
            start = heading(lines, r"^[（(]2[）)][.．]?期末公司已质押的应收款项融资")
            out["arf"] = 0.0 if "不适用" in squash("".join(lines[start + 1 : start + 3])) else None
        match = re.search(r"期末受限的应收账款金额为([\d,.]+)元", text)
        out["ar"] = number(match.group(1)) / 1e8 if match else None
        return out

    start = heading(lines, r"^[（(]2[）)][.．]?期末已质押的应收票据")
    if "无。" in squash("".join(lines[start : start + 10])):
        out["notes"] = 0.0
    else:
        table = read_pairs(lines, start, r"^[（(]3[）)]", limit=10)
        out["notes"] = get(table, "合计")[0]
    table = read_pairs(
        lines,
        heading(lines, r"^[（(]2[）)][.．]?期末公司已质押的应收款项融资"),
        r"^[（(]3[）)]",
        limit=12,
    )
    out["arf"] = get(table, "合计")[0]
    out["arf_bank"] = get(table, "银行承兑汇票")[0]
    out["arf_fin"] = get(table, "财务公司承兑汇票")[0]
    out["ar"] = None  # 年报未披露应收账款质押
    return {key: None if v is None else v * factor / 1e8 for key, v in out.items()}


def load_revenue() -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    with (FIN / "利润表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["科目"] != "营业收入" or row["报告期"] not in ("20241231", "20251231"):
                continue
            out[(row["公司"], row["报告期"][:4])] = float(row["数值"]) / 1e8
    return out


def load_balance() -> dict[tuple[str, str, str], float]:
    out: dict[tuple[str, str, str], float] = {}
    with (FIN / "资产负债表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["报告期"] not in ("20241231", "20251231"):
                continue
            try:
                out[(row["公司"], row["报告期"][:4], row["科目"])] = float(row["数值"]) / 1e8
            except ValueError:
                # 每个报告期末尾有一行「数据源,定期报告」，不是金额
                continue
    return out


def build(
    company: str,
    year: str,
    index: int,
    struct: Rows,
    pledged: dict[str, float | None],
    endorsed: dict[str, float | None],
    balance: dict[tuple[str, str, str], float],
) -> list[Entry]:
    """把一家公司一年的原始数字展开成 CSV 行。index=0 本期，1 上期。"""
    short = SHORT[company]
    # 结构表/账龄表取自 2025 年报（含 2024 比较列），附注编号按 2025 年报；
    # 背书贴现与质押表按年度取各自年报，编号会变（格力 2024 是 五、4，2025 是 五、3）
    note = NOTE[company]["2025"]
    note_year = NOTE[company][year]
    rows: list[Entry] = []

    def add(category: str, item: str, value: float | None, nature: str, source: str) -> None:
        # 取不到值一律标「未披露」：不能让空金额配上「披露值」，否则下游
        # 会把「没这个数」当成「这个数是空的」，和真正的 0 混淆。
        if value is None:
            nature = "未披露"
        rows.append(Entry(company, year, category, item, value, nature, source))

    def pick(key: str) -> float | None:
        return struct.get(key, (None, None))[index]

    src = f"{short}2025.pdf {note['notes']}"
    bs_notes = balance.get((company, year, "应收票据"))
    bs_ar = balance.get((company, year, "应收账款"))
    bs_arf = balance.get((company, year, "应收款项融资"))
    combined = balance.get((company, year, "应收票据及应收账款"))
    # 资产负债表没有「应收票据」行时，用「应收票据及应收账款 − 应收账款」反推
    notes_nature = "披露值"
    if bs_notes is None and combined is not None and bs_ar is not None:
        bs_notes = combined - bs_ar
        notes_nature = "计算值"

    # ---------- 应收票据 ----------
    for key, name in (
        ("notes_bank", "银行承兑汇票（原值）"),
        ("notes_comm", "商业承兑汇票（原值）"),
        ("notes_fin", "财务公司承兑汇票（原值）"),
    ):
        if pick(key) is not None:
            add("应收票据", name, pick(key), "披露值", src)
    gross = pick("notes_gross")
    # 美的印「(63,840)」带负号，海尔/格力印「1,060,089.74」不带。标签本身已写
    # 「减：」，统一取绝对值，否则美的会变成 53.11 −(−0.64) = 53.75。
    prov = magnitude(pick("notes_prov"))
    net = pick("notes_net")
    # 格力 2024 年应收票据整列空白（附注与资产负债表都不列这一行），实为 0：
    # 资产负债表「应收票据及应收账款」正好等于「应收账款」。空白不能读成未披露，
    # 也不能读成 2023 年的 0.87 亿。
    if gross is None and net is None and bs_notes is not None and bs_notes < 0.005:
        gross = prov = net = 0.0
        add(
            "应收票据",
            "应收票据原值合计",
            gross,
            "计算值",
            "资产负债表 应收票据及应收账款−应收账款=0；附注整列空白",
        )
        add("应收票据", "减：坏账准备", prov, "计算值", "附注整列空白，随票据余额为零")
    else:
        add("应收票据", "应收票据原值合计", gross, "计算值", f"{src} 各类型加总")
        add("应收票据", "减：坏账准备", prov, "披露值", src)
    add("应收票据", "应收票据账面价值", net, "计算值", f"{src} 原值−坏账准备")
    add(
        "应收票据",
        "应收票据账面价值（资产负债表）",
        bs_notes,
        notes_nature,
        "资产负债表.csv"
        if notes_nature == "披露值"
        else "资产负债表.csv 应收票据及应收账款−应收账款",
    )
    if pick("notes_prov_single") is not None:
        # 美的另有一张「按类别」表：单项计提（=商业承兑全额）、组合计提（=银行
        # 承兑），恰好能把坏账准备拆到票据类型
        add(
            "应收票据",
            "坏账准备：商业承兑汇票（单项计提）",
            magnitude(pick("notes_prov_single")),
            "披露值",
            f"{src}(a)",
        )
        add(
            "应收票据",
            "坏账准备：银行承兑汇票（组合计提）",
            magnitude(pick("notes_prov_combo")),
            "披露值",
            f"{src}(a)",
        )
    else:
        add("应收票据", "坏账准备（按票据类型拆分）", None, "未披露", f"{src} 仅披露坏账准备总额")
    if pick("notes_bank") is not None and pick("notes_prov_combo") is not None:
        # 银行承兑 52.24 − 组合计提 0.05；商业承兑 0.87 − 单项计提 0.59 = 0.28
        add(
            "应收票据",
            "账面价值：银行承兑汇票",
            (pick("notes_bank") or 0) - abs(pick("notes_prov_combo") or 0),
            "计算值",
            f"{src} 银行承兑原值−组合计提",
        )
        add(
            "应收票据",
            "账面价值：商业承兑汇票",
            (pick("notes_comm") or 0) - abs(pick("notes_prov_single") or 0),
            "计算值",
            f"{src} 商业承兑原值−单项计提",
        )
    elif pick("notes_comm") is not None and pick("notes_bank") is None:
        # 格力只有商业承兑一种（2025 年末 93 万），账面价值自然等于该类型的
        # 账面价值，不算「未披露」
        add(
            "应收票据",
            "账面价值：商业承兑汇票",
            net,
            "计算值",
            f"{src} 仅商业承兑一种，账面价值=该类型",
        )
    else:
        add(
            "应收票据",
            "账面价值（按票据类型拆分）",
            None,
            "未披露",
            f"{src} 只披露账面价值总额",
        )

    # ---------- 应收账款 ----------
    ar_src = f"{short}2025.pdf {note['ar']}"
    add("应收账款", "应收账款账面余额", pick("ar_gross"), "披露值", ar_src)
    add("应收账款", "减：坏账准备", magnitude(pick("ar_prov")), "披露值", ar_src)
    add("应收账款", "应收账款账面价值", pick("ar_net"), "计算值", "余额−坏账准备")
    add("应收账款", "应收账款账面价值（资产负债表）", bs_ar, "披露值", "资产负债表.csv")
    for name in AGING[company]:
        add("应收账款", f"账龄：{name}", pick(f"aging_{name}"), "披露值", f"{ar_src} 账龄表")
    add("应收账款", "账龄合计", pick("ar_gross"), "计算值", "账龄各档加总")

    # ---------- 应收款项融资 ----------
    arf_src = f"{short}2025.pdf {note['arf']}"
    for key, name in (
        ("arf_notes", "其中：应收票据"),
        ("arf_bank", "其中：银行承兑汇票"),
        ("arf_fin", "其中：财务公司承兑汇票"),
        ("arf_ar", "其中：应收账款"),
    ):
        if pick(key) is not None:
            add("应收款项融资", name, pick(key), "披露值", arf_src)
    add("应收款项融资", "应收款项融资合计", pick("arf_total"), "披露值", arf_src)
    add("应收款项融资", "应收款项融资合计（资产负债表）", bs_arf, "披露值", "资产负债表.csv")
    if pick("arf_notes") is None and pick("arf_ar") is None:
        add("应收款项融资", "按票据/应收账款拆分", None, "未披露", f"{arf_src} 只披露总数")
    if company == "海尔智家" and index == 0:
        add(
            "应收款项融资",
            "其中：应收账款（本期为零，附注该行空白）",
            0.0,
            "披露值",
            f"{arf_src} 该行本期空白，上期 1.77 亿",
        )

    # ---------- 已质押 ----------
    pledge_src = f"{short}{year}.pdf {note_year['pledge']}"
    for key, name in (
        ("notes", "已质押应收票据"),
        ("arf", "已质押应收款项融资"),
        ("arf_bank", "其中：银行承兑汇票"),
        ("arf_fin", "其中：财务公司承兑汇票"),
        ("ar", "已质押应收账款"),
    ):
        if key in pledged:
            add(
                "已质押",
                name,
                pledged[key],
                "披露值" if pledged[key] is not None else "未披露",
                pledge_src,
            )
    if pledged.get("loan_pledged_notes") is not None:
        add(
            "已质押",
            "质押借款（质押物为应收票据，是借款额不是票据账面值）",
            pledged.get("loan_pledged_notes"),
            "披露值",
            pledge_src,
        )

    # ---------- 已背书贴现 ----------
    endorse_src = f"{short}{year}.pdf {note_year['endorse']}"
    for derec, underec, label in (
        ("notes_bank_derec", "notes_bank_underec", "应收票据｜银行承兑汇票"),
        ("notes_comm_derec", "notes_comm_underec", "应收票据｜商业承兑汇票"),
    ):
        if endorsed.get(derec) is not None or endorsed.get(underec) is not None:
            add("已背书贴现", f"已终止确认｜{label}", endorsed.get(derec), "披露值", endorse_src)
            add("已背书贴现", f"未终止确认｜{label}", endorsed.get(underec), "披露值", endorse_src)
    add(
        "已背书贴现", "已终止确认｜应收票据小计", endorsed.get("notes_derec"), "披露值", endorse_src
    )
    add(
        "已背书贴现",
        "未终止确认｜应收票据小计",
        endorsed.get("notes_underec"),
        "披露值",
        endorse_src,
    )
    for key, label in (
        ("arf_bank_derec", "应收款项融资｜银行承兑汇票"),
        ("arf_fin_derec", "应收款项融资｜财务公司承兑汇票"),
        ("arf_ar_derec", "应收款项融资｜应收账款"),
        ("arf_notes_derec", "应收款项融资｜应收票据"),
    ):
        if endorsed.get(key) is not None:
            add("已背书贴现", f"已终止确认｜{label}", endorsed.get(key), "披露值", endorse_src)
    add(
        "已背书贴现",
        "已终止确认｜应收款项融资小计",
        endorsed.get("arf_derec"),
        "披露值",
        endorse_src,
    )
    add(
        "已背书贴现",
        "未终止确认｜应收款项融资小计",
        endorsed.get("arf_underec"),
        "披露值",
        endorse_src,
    )
    # 两类口径相加，才是「期末未到期且已背书贴现」的全貌。必须分开看的是
    # 「已终止确认」与「未终止确认」；这里只是把同一性质的两个科目口径合并。
    derec_parts = (endorsed.get("notes_derec"), endorsed.get("arf_derec"))
    underec_parts = (endorsed.get("notes_underec"), endorsed.get("arf_underec"))
    if any(v is not None for v in derec_parts):
        add(
            "已背书贴现",
            "已终止确认｜合计（应收票据+应收款项融资）",
            sum(v or 0.0 for v in derec_parts),
            "计算值",
            "上两行小计相加",
        )
    if any(v is not None for v in underec_parts):
        add(
            "已背书贴现",
            "未终止确认｜合计（应收票据+应收款项融资）",
            sum(v or 0.0 for v in underec_parts),
            "计算值",
            "上两行小计相加",
        )
    if endorsed.get("flow_derec") is not None:
        add(
            "已背书贴现",
            "年度累计｜背书贴现并终止确认（流量，非期末余额）",
            endorsed.get("flow_derec"),
            "披露值",
            endorse_src,
        )
        add(
            "已背书贴现",
            "年度累计｜贴现损失（计入投资收益）",
            endorsed.get("flow_loss"),
            "披露值",
            endorse_src,
        )

    # ---------- 合计 ----------
    notes = bs_notes if bs_notes is not None else 0.0
    add(
        "合计",
        "应收票据+应收账款+应收款项融资",
        notes + (bs_ar or 0.0) + (bs_arf or 0.0),
        "计算值",
        "资产负债表.csv",
    )
    add("合计", "应收票据及应收账款（资产负债表）", combined, "披露值", "资产负债表.csv")
    add("合计", "应收票据+应收账款", notes + (bs_ar or 0.0), "计算值", "资产负债表.csv")
    return rows


def check(entries: list[Entry], revenue: dict[tuple[str, str], float]) -> list[str]:
    """自校验：附注内部勾稽 + 与资产负债表勾稽 + 占比可复算。

    按「类别+项目」取数，不能按项目名：应收票据表和应收账款表都有
    「减：坏账准备」，按名字取会把格力 30.79 亿应收坏账当票据坏账。
    """
    report: list[str] = []
    for company in COMPANIES:
        for year in ("2025", "2024"):
            block = {
                (e.category, e.item): e.value
                for e in entries
                if e.company == company and e.year == year
            }
            rev = revenue.get((company, year))

            gross = block.get(("应收票据", "应收票据原值合计"))
            prov = block.get(("应收票据", "减：坏账准备"))
            net = block.get(("应收票据", "应收票据账面价值"))
            bs_notes = block.get(("应收票据", "应收票据账面价值（资产负债表）"))
            if None not in (gross, prov, net):
                diff = (gross or 0) - (prov or 0) - (net or 0)
                report.append(
                    f"[票据] {company} {year} 原值 {gross:.2f} − 坏账 {prov:.2f} = "
                    f"{net:.2f}（表内 {net:.2f}，差 {diff:+.4f}）"
                )
            if None not in (net, bs_notes):
                report.append(
                    f"[勾稽] {company} {year} 票据附注 {net:.2f} vs 资产负债表 {bs_notes:.2f}"
                    f"（差 {(net or 0) - (bs_notes or 0):+.4f}）"
                )

            ar_gross = block.get(("应收账款", "应收账款账面余额"))
            ar_prov = block.get(("应收账款", "减：坏账准备"))
            ar_net = block.get(("应收账款", "应收账款账面价值"))
            bs_ar = block.get(("应收账款", "应收账款账面价值（资产负债表）"))
            if None not in (ar_gross, ar_prov, ar_net):
                diff = (ar_gross or 0) - (ar_prov or 0) - (ar_net or 0)
                report.append(
                    f"[应收] {company} {year} 余额 {ar_gross:.2f} − 坏账 {ar_prov:.2f} = "
                    f"{ar_net:.2f}（表内 {ar_net:.2f}，差 {diff:+.4f}）"
                )
            if None not in (ar_net, bs_ar):
                report.append(
                    f"[勾稽] {company} {year} 应收附注 {ar_net:.2f} vs 资产负债表 {bs_ar:.2f}"
                    f"（差 {(ar_net or 0) - (bs_ar or 0):+.4f}）"
                )

            pieces = block.get(("合计", "应收票据+应收账款"))
            combined = block.get(("合计", "应收票据及应收账款（资产负债表）"))
            if None not in (combined, pieces):
                report.append(
                    f"[勾稽] {company} {year} 应收票据及应收账款 {combined:.2f} vs "
                    f"票据+应收 {pieces:.2f}（差 {(combined or 0) - (pieces or 0):+.4f}）"
                )

            total = block.get(("合计", "应收票据+应收账款+应收款项融资"))
            arf = block.get(("应收款项融资", "应收款项融资合计（资产负债表）"))
            if None not in (total, combined, arf):
                report.append(
                    f"[勾稽] {company} {year} 三分合计 {total:.2f} vs 应收票据及应收账款"
                    f"+应收款项融资 {(combined or 0) + (arf or 0):.2f}"
                    f"（差 {(total or 0) - (combined or 0) - (arf or 0):+.4f}）"
                )

            if rev and total is not None:
                report.append(
                    f"[占比] {company} {year} {total:.2f} / 营业收入 {rev:.2f} = "
                    f"{total / rev * 100:.2f}%"
                )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--all", action="store_true", help="提取三家 2025/2024 全部数据")
    args = parser.parse_args()
    if not args.all:
        parser.print_help()
        return 0

    revenue = load_revenue()
    balance = load_balance()
    entries: list[Entry] = []

    for company in COMPANIES:
        lines_2025 = load_text(SHORT[company], "2025")
        struct = structure(company, lines_2025)
        for year, index in (("2025", 0), ("2024", 1)):
            lines = lines_2025 if year == "2025" else load_text(SHORT[company], year)
            entries.extend(
                build(
                    company,
                    year,
                    index,
                    struct,
                    pledge(company, lines),
                    endorse(company, lines),
                    balance,
                )
            )
        print(f"  {company}: 结构 {len(struct)} 项", file=sys.stderr)

    fields = ["公司", "年度", "类别", "项目", "金额(亿元)", "占营业收入%", "数据性质", "来源"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        for entry in entries:
            rev = revenue.get((entry.company, entry.year))
            share = f"{entry.value / rev * 100:.2f}" if entry.value is not None and rev else ""
            writer.writerow(
                [
                    entry.company,
                    entry.year,
                    entry.category,
                    entry.item,
                    "" if entry.value is None else f"{entry.value:.2f}",
                    share,
                    entry.nature,
                    entry.source,
                ]
            )

    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(entries)} 行", file=sys.stderr)
    print("\n自校验：", file=sys.stderr)
    for line in check(entries, revenue):
        print("  " + line, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
