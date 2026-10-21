"""无形资产明细：按类别拆原值、累计摊销、减值准备、账面价值，以及摊销政策。

为什么重要：
三家的无形资产构成完全不同，用同一个「无形资产」科目横向比会得出错误结论。

| 公司 | 2025 账面价值 | 最大类别 | 占无形资产 | 当期摊销 |
|---|---|---|---|---|
| 美的 | 216.19 亿 | 商标权 69.98 亿 | 32.4% | 15.01 亿 |
| 海尔 | 142.25 亿 | 特许使用权 34.66 亿 | 24.4% | 14.13 亿 |
| 格力 | 98.65 亿 | 土地使用权 86.55 亿 | 87.7% | 4.56 亿 |

海尔通过收购 GEA / Candy / CCR 形成大额商标权（28.43 亿）与客户关系（15.03 亿）；
美的有 KUKA 的专利权及非专利技术（25.15 亿）和收购带来的商标权（69.98 亿）；
格力 87.7% 是土地使用权，几乎没有并购形成的无形资产。这决定了两件事：

1. **摊销负担不同**。有明确使用寿命的无形资产要摊销，直接压低利润；使用寿命不确定的
   （美的部分商标、海尔 27.05 亿商标）只做减值测试，不摊销。同样 100 亿无形资产，
   格力的土地使用权按 30-50 年摊、海尔的客户关系按较短年限摊，年度费用能差几倍。
   2025 年摊销/账面价值：美的 6.9%、海尔 9.9%、格力 4.6%。
2. **商誉之外还有一块并购形成的无形资产**。分析并购代价时不能只看商誉：海尔商誉
   273.00 亿之外还有商标权 + 客户关系 43.46 亿；美的商誉 342.57 亿之外还有并购增加的
   无形资产 49.98 亿（2025 年一次）。

八个陷阱（都是实际踩到的）：

1. **只有美的按千元列示**，海尔/格力按元。美的 21,618,860 是千元（216.19 亿），
   不是元（0.22 亿）。本脚本对美的乘 1000 再折算亿元。
2. **海尔的无形资产表是横向续表**：第一段「专有技术 / 特许使用权 / 土地使用权」，
   第二段「商标权 / 客户关系 / 应用管理软件及其他 / 合计」，两段各自带一套「一、账面原值
   …四、账面价值」。按「一张表六个类别」解析会把第二段的合计列当成「其他」，海尔无形
   资产虚增 10 倍（142.25 亿 vs 1,422 亿）。本脚本按 block 分别解析、按列偏移拼接。
3. **续表跨页后列宽重排**：海尔第 187 页与第 188 页的列宽不同（第一页数字右端约
   28/50/70/92，第二页约 28/54/72/91）。按全表统一字符位置取数会把「累计摊销」的
   184,372,755.73 落到商标权列。本脚本**逐页**按数字右边界聚类。
4. **标签被金额劈成三段**：美的「非同一控制下企业」+ 金额 +「合并」；格力
   「（2）投资性房地产」+ 金额 +「转入」、「（3）转至投资性房」+ 金额 +「地产」。
   不拼回就整行丢失，格力 2025 原值增加会少 0.52 亿、减少会少 0.16 亿。
5. **「处置」既是完整项目名，又是「处置及其他」「处置子公司」的前缀**。用「是不是某个
   完整名的前缀」判断待拼接标签，会把海尔的「(1)处置」（本年无发生额）带进下一行，
   把「4.汇率变动及其他」拼成「处置汇率变动及其他」，0.14 亿减值挂到不存在的项目上。
   本脚本先判「是否完整项目名」，再判「是否半截」。
6. **海尔减值准备页只有 1 个数字**（只有特许使用权列有余额）。按该页聚类只能识别 1 列，
   66,630,354.13 会从特许使用权列跑到土地使用权列。本脚本对该页回退到**同 block 上一页**
   的列边界。
7. **格力「本期增加金额」小计行与明细行都有数字**。两者都计入本期增加会翻倍
   （2025 年 55,924,067.20 → 111,848,134.40）。本脚本用表内小计做校验，明细只用来拆项。
8. **海尔不披露分类别摊销年限**，只有「使用寿命有限无形资产采用直线法摊销」一句；
   使用寿命不确定的金额也不在附注表里，只在审计报告关键审计事项（27.05 亿）。
   美的 2025 年报还把商标使用权的摊销年限从 2024 年的「40 年」改成「30-40 年」——
   同一项目两年政策表述不同，不能只取一年。

自校验（stderr 报告）：
- 逐类别：原值 − 累计摊销 − 减值准备 = 账面价值
- 分类别账面价值相加 = 账面价值合计
- 变动表：期初 + 增加 − 减少 + 汇率变动 = 期末（原值、累计摊销、减值准备）
- 变动表明细相加 = 表内「本期增加 / 本期减少」小计（格力有该小计行）
- 附注「账面价值合计」= 资产负债表「无形资产」，或命中 `BOOK_GAP` 已登记口径差

未取到的项：美的/格力未披露使用寿命不确定的无形资产金额；美的未披露研发支出资本化
转入额；海尔未披露分类别摊销年限。CSV 中以「数据性质=未披露」单列，不填 0。

用法：
    uv run python3 scripts/extract_intangibles.py --all
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path("/tmp/fsr")
FIN = ROOT / "财务数据"
OUT = FIN / "无形资产明细.csv"


@dataclass(frozen=True)
class Report:
    pdf: str
    factor: int  # 报表单位 → 元
    note: str  # 合并报表附注编号
    policy: str  # 会计政策附注编号


SOURCES: dict[tuple[str, str], Report] = {
    ("美的集团", "2025"): Report("美的2025.pdf", 1_000, "附注四(20)", "附注二(17)"),
    ("美的集团", "2024"): Report("美的2024.pdf", 1_000, "附注四(21)", "附注二(17)"),
    ("海尔智家", "2025"): Report("海尔2025.pdf", 1, "附注七、20", "附注五、19"),
    ("海尔智家", "2024"): Report("海尔2024.pdf", 1, "附注七、20", "附注五、19"),
    ("格力电器", "2025"): Report("格力2025.pdf", 1, "附注五、24", "附注三、24"),
    ("格力电器", "2024"): Report("格力2024.pdf", 1, "附注五、24", "附注三、24"),
}
ORDER = ["美的集团", "海尔智家", "格力电器"]
YEARS = ["2025", "2024"]

# 无形资产按类别表的列布局。海尔的续表拆成两个 block，横向拼起来。
LAYOUT: dict[str, list[list[str]]] = {
    "美的集团": [["土地使用权", "专利权及非专利技术", "商标权", "商标使用权", "其他", "合计"]],
    "海尔智家": [
        ["专有技术", "特许使用权", "土地使用权"],
        ["商标权", "客户关系", "应用管理软件及其他", "合计"],
    ],
    "格力电器": [["土地使用权", "专利权及其他", "合计"]],
}
TITLE = r"(?:\(\d+\)|\d+、)\s*无形资产"
STOP = r"(?:\(\d+\)|\d+、)\s*商誉"

SEC_MIDEA = re.compile(r"^(原价|累计摊销|减值准备|账面价值)$")
SEC_OTHER = re.compile(r"^[一二三四]\s*[、.]\s*(账面原值|累计摊销|减值准备|账面价值)$")
DATE = re.compile(r"^\s*\d{4}\s*年(?:\s*\d{1,2}\s*月)?(?:\s*\d{1,2}\s*日)?")
LEAD = re.compile(r"^\s*(?:[（(]\s*\d+\s*[）)]|\d+\s*[、.])")
PAREN_NO = re.compile(r"[（(]\s*\d+\s*[）)](?=\s*[\u4e00-\u9fa5A-Za-z])")
NUM = re.compile(
    r"(?<![A-Za-z0-9.,])\(-?[\d,]+(?:\.\d+)?\)"
    r"|(?<![A-Za-z0-9.,])-?\d[\d,]*(?:\.\d+)?(?![A-Za-z0-9])"
    r"|(?<=\s)-(?=\s|$)"
)
PAGE = re.compile(r"^\s*(?:\d{1,4}\s*/\s*\d{1,4}|[-—–]\s*\d{1,4}\s*[-—–]|\d{1,4})\s*$")
# 附注正文起始标记：美的「(a) 2025 年度…」、格力「【注 1】…」、海尔「（2）期末无形资产中…」
NOTE_MARK = re.compile(r"^(?:\(\w\)|（[一二三四五六七八九十\d]+）|【注)")

# 能被金额劈成两段的完整项目名（前半截 → 后半截）。
FULL = (
    "非同一控制下企业合并",
    "投资性房地产转入",
    "转至投资性房地产",
    "转入投资性房地产",
    "处置及其他",
    "处置子公司",
    "汇率变动及其他",
    "外币报表折算差额",
    "企业合并增加",
)
# 本身完整的项目名：即使本年无发生额，也不能当作「待拼接的前半截」。
COMPLETE = (
    "期初余额",
    "期末余额",
    "期初账面价值",
    "期末账面价值",
    "本年增加",
    "本年减少",
    "本期增加",
    "本期减少",
    "本期增加金额",
    "本期减少金额",
    "购置",
    "外购",
    "内部研发",
    "企业合并增加",
    "非同一控制下企业合并",
    "计提",
    "摊销",
    "处置",
    "处置及其他",
    "处置子公司",
    "核销",
    "转入投资性房地产",
    "投资性房地产转入",
    "转至投资性房地产",
    "汇率变动及其他",
    "外币报表折算差额",
    "其他",
    "合计",
)
INCREASE_HEAD = ("本年增加", "本期增加", "本期增加金额")
DECREASE_HEAD = ("本年减少", "本期减少", "本期减少金额")
FX = ("汇率变动及其他", "外币报表折算差额")

# 变动表标签 → 统一项目名
CANON = {
    "外购": "购置",
    "摊销": "计提",
    "非同一控制下企业合并": "企业合并增加",
    "处置及其他": "处置",
    "外币报表折算差额": "汇率变动",
    "汇率变动及其他": "汇率变动",
    "其他": "其他增加",
    "转入投资性房地产": "转至投资性房地产",
}
DISPLAY = {"内部研发": "内部研发（研发支出资本化转入）"}
FLOW_ORDER = (
    "期初余额",
    "购置",
    "内部研发",
    "企业合并增加",
    "投资性房地产转入",
    "计提",
    "其他增加",
    "处置",
    "核销",
    "转至投资性房地产",
    "处置子公司",
    "汇率变动",
    "期末余额",
)
# 增加项 / 减少项在 FLOW_ORDER 里的下标区间（左闭右开）
INCREASE_SLICE = slice(1, 7)
DECREASE_SLICE = slice(7, 11)

# 附注「账面价值合计」与资产负债表「无形资产」的已登记口径差。
BOOK_GAP: dict[tuple[str, str], tuple[float, str]] = {
    ("海尔智家", "2024"): (
        -0.08,
        "追溯重述：2025 年报因同一控制下企业合并（卡奥斯模具（青岛）有限公司，2025 年 3 月"
        "合并）重述 2024 年可比数——2024 年报无形资产 14,034,674,912.54 + 卡奥斯模具合并日"
        "上期期末无形资产 8,265,155.63 = 14,042,940,068.17，正是 2025 年报期初数。"
        "本表分类别明细取自 2024 年报，资产负债表为 2025 年报可比数，故差 0.08 亿",
    ),
}


def text_of(pdf: str) -> str:
    """优先用 /tmp/fsr 的 pdftotext -layout 缓存，缺了才重新转 PDF。"""
    cached = CACHE / f"{Path(pdf).stem}.txt"
    if cached.exists():
        return cached.read_text(encoding="utf-8")
    import subprocess

    result = subprocess.run(
        ["pdftotext", "-layout", str(ROOT / "年度报告" / pdf), "-"],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    return result.stdout


def number(token: str) -> float:
    token = token.strip()
    if token == "-":
        return 0.0
    if token.startswith("(") and token.endswith(")"):
        return -float(token[1:-1].replace(",", ""))
    return float(token.replace(",", ""))


def flat(text: str) -> str:
    return re.sub(r"\s+", "", text)


def boundary(stripped: str) -> bool:
    """页码 / 页眉 / 「- 224 -」：跨页处列宽会重排，必须在这里切页。"""
    if PAGE.match(stripped):
        return True
    if "股份有限公司" in stripped and ("年度报告" in stripped or "财务报表附注" in stripped):
        return True
    return "年度财务报表附注" in stripped or "年度报告全文" in stripped


def note_block(lines: list[str], company: str) -> list[str]:
    """截取合并报表项目附注里的无形资产表（不是会计政策章节那一节）。"""
    title = re.compile(r"^\s*" + TITLE + r"\s*$")
    start = None
    for index, line in enumerate(lines):
        if not title.match(line):
            continue
        window = [flat(item) for item in lines[index : index + 40]]
        if any(item == "原价" or item.startswith("一、账面原值") for item in window):
            start = index
            break
    if start is None:
        raise ValueError(f"{company} 找不到无形资产附注表")
    for index in range(start + 1, len(lines)):
        if re.match(r"^\s*" + STOP + r"\s*$", lines[index]):
            return lines[start:index]
    return lines[start : start + 500]


def is_prefix(text: str) -> bool:
    return bool(text) and any(item.startswith(text) and len(text) < len(item) for item in FULL)


def joins(head: str, tail: str) -> bool:
    """head 是不是某个完整项目名被金额劈断的前半截。"""
    if not head or not tail or len(tail) > 6 or re.match(r"^[（(]", tail):
        return False
    merged = head + tail
    return is_prefix(head) and any(merged == item or item.startswith(merged) for item in FULL)


@dataclass
class Row:
    section: str
    block: int
    page: int
    label: str
    values: list[float]
    ends: list[int]
    direction: str


def parse_rows(block: list[str], company: str) -> list[Row]:
    """一行 → (段, block, 页, 标签, 数字, 右边界)。"""
    rows: list[Row] = []
    page = 0
    section = ""
    seen: dict[str, int] = {}
    index = 0
    direction = ""
    carry = ""
    open_tail = False

    for raw in block:
        stripped = raw.strip()
        if boundary(stripped):
            page += 1
            continue
        key = flat(stripped)
        if not key:
            continue
        if NOTE_MARK.match(stripped) and section == "账面价值":
            # 附注正文（「(a) 2025 年度，无形资产计提的摊销金额为…」「【注 1】…」
            # 「（2）期末无形资产中…」）：账面价值表之后就是正文，继续解析会把
            # 正文里的数字当成表格行。
            break
        match = SEC_MIDEA.match(key) if company == "美的集团" else SEC_OTHER.match(key)
        if match:
            name = match.group(1)
            section = "原值" if name in ("原价", "账面原值") else name
            index = seen.get(section, 0)
            seen[section] = index + 1
            direction, carry, open_tail = "", "", False
            continue
        if not section:
            continue

        masked = DATE.sub(lambda m: " " * len(m.group()), raw.rstrip())
        masked = re.sub(r"其中[：:]", lambda m: " " * len(m.group()), masked)
        masked = PAREN_NO.sub(lambda m: " " * len(m.group()), masked)
        masked = LEAD.sub(lambda m: " " * len(m.group()), masked)
        found = [(m.group(), m.end()) for m in NUM.finditer(masked)]
        stamp = DATE.search(raw)
        label = flat(masked[: found[0][1] - len(found[0][0])] if found else masked)

        if not found:
            if open_tail and rows and joins(rows[-1].label, label):
                rows[-1].label += label
                open_tail = False
            elif label in COMPLETE:
                carry = ""
            elif is_prefix(label):
                carry = label
            else:
                carry = ""
            if label in INCREASE_HEAD:
                direction = "+"
            elif label in DECREASE_HEAD:
                direction = "-"
            continue

        if stamp:
            year = re.search(r"\d{4}", stamp.group())
            head = "期末" if year and year.group() == current_year else "期初"
            label = head + ("账面价值" if section == "账面价值" else "余额")
        elif carry:
            label, carry = carry + label, ""

        if not label:
            continue
        if label in FX:
            direction = ""
        open_tail = is_prefix(label)
        rows.append(
            Row(
                section,
                index,
                page,
                label,
                [number(value) for value, _ in found],
                [end for _, end in found],
                direction,
            )
        )
    return rows


current_year = ""


def cluster(ends: list[int], count: int) -> list[float]:
    """数字右边界聚类：同列结尾相差 ≤2 字符。簇多于目标数时合并最近的两个。"""
    groups: list[list[int]] = []
    for end in sorted(set(ends)):
        if groups and end - groups[-1][-1] <= 2:
            groups[-1].append(end)
        else:
            groups.append([end])
    while len(groups) > count:
        gaps = [groups[i + 1][0] - groups[i][-1] for i in range(len(groups) - 1)]
        slot = gaps.index(min(gaps))
        groups[slot] = groups[slot] + groups.pop(slot + 1)
    if len(groups) != count:
        raise ValueError(f"只识别到 {len(groups)} 列，期望 {count}")
    return [sum(group) / len(group) for group in groups]


def page_edges(rows: list[Row], count: int) -> list[float] | None:
    """用**列数正好等于目标列数**的行定位列边界。

    附注正文的折行（「(a) 2025 年度，无形资产计提的摊销金额为 1,501,257,000 元」）
    也会解析出数字，右边界散落在 11/23/41，混进来会把列边界拉偏。所以只用整行
    数字个数与表头列数一致的行；这类行一定是表格行。
    """
    full = [row for row in rows if len(row.ends) == count]
    if not full:
        return None
    try:
        return cluster([end for row in full for end in row.ends], count)
    except ValueError:
        return None


def assign(rows: list[Row], company: str, hint: str) -> dict[tuple[str, int], list[Row]]:
    """按页聚类列边界后把数字摊到列上；页内数字不足时回退到上一页的边界。"""
    layout = LAYOUT[company]
    pages: dict[tuple[int, int], list[Row]] = {}
    for row in rows:
        pages.setdefault((row.block, row.page), []).append(row)

    edges: dict[tuple[int, int], list[float]] = {}
    last: dict[int, list[float]] = {}
    for key in sorted(pages):
        found = page_edges(pages[key], len(layout[key[0]]))
        if found is None:
            found = last.get(key[0])
        if found is None:
            raise ValueError(f"{hint} 第 {key[1]} 页无法定位列边界")
        edges[key] = found
        last[key[0]] = found

    out: dict[tuple[str, int], list[Row]] = {}
    for key, group in pages.items():
        edge = edges[key]
        for row in group:
            cells = [0.0] * len(edge)
            for value, end in zip(row.values, row.ends, strict=True):
                slot = min(range(len(edge)), key=lambda i: abs(edge[i] - end))
                if abs(edge[slot] - end) > 10:
                    print(
                        f"  ! {hint} 「{row.label}」{value}@{end} 离列 {slot}@{edge[slot]:.0f} 太远",
                        file=sys.stderr,
                    )
                cells[slot] += value
            out.setdefault((row.section, row.block), []).append(
                Row(row.section, row.block, row.page, row.label, cells, [], row.direction)
            )
    return out


def merge(
    assigned: dict[tuple[str, int], list[Row]], company: str
) -> dict[tuple[str, str], list[float]]:
    """把海尔的续表按列偏移拼成一张宽表。"""
    layout = LAYOUT[company]
    width = sum(len(block) for block in layout)
    out: dict[tuple[str, str], list[float | None]] = {}
    for (section, block), rows in assigned.items():
        offset = sum(len(part) for part in layout[:block])
        for row in rows:
            bucket = out.setdefault((section, row.label), [None] * width)
            for index, value in enumerate(row.values):
                bucket[offset + index] = value
    return {
        key: [value if value is not None else 0.0 for value in cells] for key, cells in out.items()
    }


def policy_rows(company: str, year: str, text: str, report: Report) -> list[tuple[str, str, str]]:
    """分类别摊销年限 → (类别, 年限, 数据性质)。海尔只有通用政策，没有分类别年限。"""
    body = flat(text)
    rows: list[tuple[str, str, str]] = []
    if company == "美的集团":
        for label, pattern in (
            ("土地使用权", r"土地使用权按使用年限([\d\-–~]+)年平均摊销"),
            ("专利权及非专利技术", r"或收益年限([\d\-–~]+)年平均摊销"),
            ("商标权", r"外购的商标权以取得时的成本计量，按预计使用年限([\d\-–~]+)年平均摊销"),
            ("商标使用权", r"商标使用权按预计使用年限([\d\-–~]+)年平均摊销"),
            ("其他（客户关系、特许经营权、软件）", r"按预计使用寿命在([\d\-–~]+)年平均摊销"),
        ):
            match = re.search(pattern, body)
            value = f"{match.group(1)} 年" if match else "未披露"
            rows.append((label, value, "披露值" if match else "未披露"))
        if "可使用年限无限的商标" in body or "无限可使用年限" in body:
            rows.append(
                (
                    "商标权（使用寿命不确定部分）",
                    "部分商标拥有无限可使用年限，不摊销，仅每年做减值测试",
                    "披露值",
                )
            )
    elif company == "格力电器":
        for label, pattern in (
            ("土地使用权", r"土地使用权按使用年限([\d\-–~]+)年平均摊销"),
            ("专利权及其他", r"专利权及其他按预计使用年限([\d\-–~]+)年平均摊销"),
        ):
            match = re.search(pattern, body)
            value = f"{match.group(1)} 年" if match else "未披露"
            rows.append((label, value, "披露值" if match else "未披露"))
    else:
        rows.append(
            (
                "全部类别",
                "未披露分类别摊销年限；仅披露「使用寿命有限的无形资产采用直线法摊销」",
                "未披露",
            )
        )
    return rows


def indefinite(
    company: str, year: str, text: str, report: Report
) -> list[tuple[str, float | None, str, str]]:
    """使用寿命不确定的无形资产（不摊销）：(项目, 金额(元), 数据性质, 来源)。"""
    if company == "海尔智家":
        # 双栏排版把「账面价值 27.05 亿元」拦腰截断：左栏「账面价」+ 右栏整段审计程序
        # +「值 27.05 亿元」，连「面价」二字都不在左栏。所以只锚定「账」，取其后第一个
        # 「X.XX 亿元」——右栏那段不含「亿元」，不会抢先命中。
        match = re.search(r"使用寿命不确定无形资产的账.{0,200}?([\d.]+)\s*亿元", flat(text))
        if match:
            return [
                (
                    "商标权（使用寿命不确定，不摊销）",
                    float(match.group(1)) * 1e8,
                    "披露值",
                    f"审计报告 关键审计事项（{report.note}）",
                )
            ]
        return [("商标权（使用寿命不确定，不摊销）", None, "未披露", report.note)]
    if company == "美的集团":
        if "无限可使用年限" in flat(text):
            return [
                (
                    "商标权（存在无限可使用年限部分，金额未披露）",
                    None,
                    "未披露",
                    f"{report.policy}(c)",
                )
            ]
        return [("商标权（存在无限可使用年限部分，金额未披露）", None, "未披露", report.policy)]
    return [
        ("未披露使用寿命不确定的无形资产金额（政策提及但不摊销）", None, "未披露", report.policy)
    ]


def research_capitalised(
    company: str, year: str, flow: dict[str, float], text: str
) -> tuple[float | None, str]:
    """研发支出资本化后转入无形资产的金额。"""
    if "内部研发" in flow:
        return flow["内部研发"], "披露值"
    if company == "格力电器" and "本期无通过公司内部研发形成的无形资产" in flat(text):
        return 0.0, "披露值"
    return None, "未披露"


def build(company: str, year: str) -> tuple[list[list[str]], dict[str, object]]:
    global current_year
    current_year = year
    report = SOURCES[(company, year)]
    text = text_of(report.pdf)
    lines = text.split("\n")
    block = note_block(lines, company)
    assigned = assign(parse_rows(block, company), company, f"{company}{year}")
    merged = merge(assigned, company)
    names = [name for part in LAYOUT[company] for name in part]
    to_yi = lambda value: value * report.factor / 1e8  # noqa: E731

    rows: list[list[str]] = []
    total = names[-1]

    def cell(section: str, label: str, name: str) -> float | None:
        cells = merged.get((section, label))
        if cells is None:
            return None
        index = names.index(name)
        return cells[index] if index < len(cells) else None

    # A. 按类别：原值 / 累计摊销 / 减值准备 / 账面价值
    for section, label, prefix in (
        ("原值", "期末余额", "无形资产-原值"),
        ("累计摊销", "期末余额", "无形资产-累计摊销"),
        ("减值准备", "期末余额", "无形资产-减值准备"),
        ("账面价值", "期末账面价值", "无形资产-账面价值"),
    ):
        for name in names:
            value = cell(section, label, name)
            if value is None:
                continue
            rows.append([company, year, prefix, name, f"{to_yi(value):.2f}", "披露值", report.note])

    # B/C. 变动表（原值、累计摊销、减值准备各一套，按合计列）
    # 三家的正负号约定不同：美的把减少项写成 (238,384)，格力/海尔写正数。统一成
    # 「减少项为负」，否则格力 2025 原值变动表会算成 144.87+0.56+2.13=147.56。
    flows: dict[str, dict[str, float]] = {}
    for section in ("原值", "累计摊销", "减值准备"):
        values: dict[str, float] = {}
        for (sec, label), cells in merged.items():
            if sec != section:
                continue
            name = CANON.get(label, label)
            if name in ("期初余额", "期末余额") or name in FLOW_ORDER:
                value = cells[names.index(total)]
                if name in FLOW_ORDER[DECREASE_SLICE]:
                    value = -abs(value)
                values[name] = value
        flows[section] = values

    for section, prefix in (("原值", "原值变动表"), ("累计摊销", "累计摊销变动表")):
        values = flows[section]
        for name in FLOW_ORDER:
            if name not in values:
                continue
            rows.append(
                [
                    company,
                    year,
                    prefix,
                    DISPLAY.get(name, name),
                    f"{to_yi(values[name]):.2f}",
                    "披露值",
                    report.note,
                ]
            )
        opening = values.get("期初余额")
        closing = values.get("期末余额")
        if opening is not None and closing is not None:
            added = sum(value for key, value in values.items() if key in FLOW_ORDER[INCREASE_SLICE])
            removed = sum(
                value for key, value in values.items() if key in FLOW_ORDER[DECREASE_SLICE]
            )
            fx = values.get("汇率变动", 0.0)
            rows.append(
                [
                    company,
                    year,
                    prefix,
                    "本期增加合计",
                    f"{to_yi(added):.2f}",
                    "计算值",
                    report.note,
                ]
            )
            rows.append(
                [
                    company,
                    year,
                    prefix,
                    "本期减少合计",
                    f"{to_yi(removed):.2f}",
                    "计算值",
                    report.note,
                ]
            )
            rows.append(
                [
                    company,
                    year,
                    prefix,
                    "变动净额（期初+增加+减少+汇率）",
                    f"{to_yi(added + removed + fx):.2f}",
                    "计算值",
                    report.note,
                ]
            )

    # 减值准备变动挂在「原值变动表」类别下，项目名加前缀，避免与静态余额混淆
    for name in FLOW_ORDER:
        if name not in flows["减值准备"]:
            continue
        rows.append(
            [
                company,
                year,
                "原值变动表",
                f"减值准备变动-{name}",
                f"{to_yi(flows['减值准备'][name]):.2f}",
                "披露值",
                report.note,
            ]
        )

    # D. 摊销政策
    for label, value, nature in policy_rows(company, year, text, report):
        rows.append([company, year, "摊销政策", f"{label}：{value}", "", nature, report.policy])

    # 使用寿命不确定
    for label, value, nature, source in indefinite(company, year, text, report):
        rows.append(
            [
                company,
                year,
                "使用寿命不确定",
                label,
                "" if value is None else f"{value / 1e8:.2f}",
                nature,
                source,
            ]
        )

    # E. 研发支出资本化转入：原值变动表里的「内部研发」行就是它，已在上面落库；
    # 没有该行时补一行，标明未披露 / 本期为零。
    if "内部研发" not in flows["原值"]:
        value, nature = research_capitalised(company, year, flows["原值"], text)
        rows.append(
            [
                company,
                year,
                "原值变动表",
                "内部研发（研发支出资本化转入）",
                "" if value is None else f"{to_yi(value):.2f}",
                nature,
                f"{report.note}【注】" if value == 0.0 else report.note,
            ]
        )

    checks = {
        "names": names,
        "merged": merged,
        "total": total,
        "to_yi": to_yi,
        "flows": flows,
        "note": report.note,
    }
    return rows, checks


def check(company: str, year: str, data: dict[str, object]) -> list[str]:
    problems: list[str] = []
    names = data["names"]
    merged = data["merged"]
    to_yi = data["to_yi"]
    flows = data["flows"]

    def get(section: str, label: str, name: str) -> float | None:
        cells = merged.get((section, label))
        if cells is None:
            return None
        index = names.index(name)
        return cells[index] if index < len(cells) else None

    # 1. 逐类别：原值 − 累计摊销 − 减值准备 = 账面价值
    for name in names:
        gross = get("原值", "期末余额", name)
        amort = get("累计摊销", "期末余额", name)
        impair = get("减值准备", "期末余额", name)
        net = get("账面价值", "期末账面价值", name)
        if gross is None or net is None:
            problems.append(f"{company} {year} {name} 缺原值或账面价值")
            continue
        diff = to_yi(gross - (amort or 0.0) - (impair or 0.0) - net)
        if abs(diff) > 0.02:
            problems.append(f"{company} {year} {name} 原值−摊销−减值−净值 = {diff:+.2f} 亿")

    # 2. 分类别账面价值相加 = 合计
    items = [name for name in names if name != "合计"]
    total = get("账面价值", "期末账面价值", "合计")
    subtotal = sum(get("账面价值", "期末账面价值", name) or 0.0 for name in items)
    if total is not None and abs(to_yi(subtotal - total)) > 0.02:
        problems.append(
            f"{company} {year} 分类别账面价值相加 {to_yi(subtotal):.2f} ≠ 合计 {to_yi(total):.2f}"
        )

    # 3. 变动表：期初 + 增加 + 减少 + 汇率 = 期末
    for section in ("原值", "累计摊销", "减值准备"):
        values = flows[section]
        opening = values.get("期初余额")
        closing = values.get("期末余额")
        if opening is None or closing is None:
            problems.append(f"{company} {year} {section} 变动表缺期初或期末")
            continue
        added = sum(value for key, value in values.items() if key in FLOW_ORDER[INCREASE_SLICE])
        removed = sum(value for key, value in values.items() if key in FLOW_ORDER[DECREASE_SLICE])
        fx = values.get("汇率变动", 0.0)
        diff = to_yi(opening + added + removed + fx - closing)
        if abs(diff) > 0.02:
            problems.append(
                f"{company} {year} {section} 变动表 期初{to_yi(opening):.2f}"
                f"+增{to_yi(added):.2f}+减{to_yi(removed):.2f}+汇{to_yi(fx):.2f}"
                f"−期末{to_yi(closing):.2f} = {diff:+.2f} 亿"
            )

    # 4. 附注账面价值合计 = 资产负债表「无形资产」
    book = book_value(company, year)
    total = get("账面价值", "期末账面价值", "合计")
    if book is not None and total is not None:
        diff = to_yi(total) - book
        gap = BOOK_GAP.get((company, year))
        if gap and abs(diff - gap[0]) <= 0.02:
            print(f"  · {company} {year} 附注与报表差 {diff:+.2f} 亿：{gap[1]}", file=sys.stderr)
        elif abs(diff) > 0.02:
            problems.append(
                f"{company} {year} 附注账面价值 {to_yi(total):.2f} ≠ 资产负债表 {book:.2f}"
                f"（差 {diff:+.2f} 亿）"
            )
    return problems


def book_value(company: str, year: str) -> float | None:
    path = FIN / "资产负债表.csv"
    if not path.exists():
        return None
    with path.open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["公司"] != company or row["科目"] != "无形资产":
                continue
            if row["报告期"] != f"{year}1231":
                continue
            try:
                return float(row["数值"]) / 1e8
            except ValueError:
                return None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="提取三家 2025 与 2024 的无形资产明细")
    args = parser.parse_args()
    if not args.all:
        parser.print_help()
        return 0

    rows: list[list[str]] = []
    problems: list[str] = []
    summary: list[tuple[str, str, float, str, float, str]] = []

    for company in ORDER:
        for year in YEARS:
            try:
                part, data = build(company, year)
            except ValueError as error:
                problems.append(f"{company} {year} 解析失败：{error}")
                continue
            rows.extend(part)
            problems.extend(check(company, year, data))
            names = data["names"]
            merged = data["merged"]
            to_yi = data["to_yi"]
            cells = merged.get(("账面价值", "期末账面价值"))
            total = cells[names.index("合计")] if cells else 0.0
            best, best_value = "", 0.0
            for name in names[:-1]:
                value = cells[names.index(name)] if cells else 0.0
                if value > best_value:
                    best, best_value = name, value
            summary.append((company, year, to_yi(total), best, to_yi(best_value), ""))
            print(f"  {company} {year}: {len(part)} 行，账面价值 {to_yi(total):.2f} 亿")

    fields = ["公司", "年度", "类别", "项目", "金额(亿元)", "数据性质", "来源"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    print(f"\n{'公司':<8}{'年度':<6}{'无形资产':>10}{'最大类别':>22}{'金额':>10}")
    print("-" * 60)
    for company, year, total, best, best_value, _ in summary:
        print(f"{company:<8}{year:<6}{total:>10.2f}{best:>22}{best_value:>10.2f}")

    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    for problem in problems:
        print(f"校验问题：{problem}", file=sys.stderr)
    if not problems:
        print("校验全部通过", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
