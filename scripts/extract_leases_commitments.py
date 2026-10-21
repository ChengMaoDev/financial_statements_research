"""租赁与承诺事项：使用权资产、租赁负债、租赁损益、资本承诺、经营租赁承诺、对外担保。

为什么重要：

租赁是**表内负债、表外资产**的典型。使用权资产（ROU）把未来租金折现后同时记进资产
和负债，于是「租来的厂房」和「买来的厂房」在资产负债表上长得一样，但前者还本付息、
后者只提折旧。三家 2025 年末的规模差得很远：

| 项目 | 美的 | 海尔 | 格力 |
|---|---|---|---|
| 使用权资产 | 31.70 亿 | **60.24 亿** | 6.76 亿 |
| 租赁负债（含一年内） | 32.96 亿 | **61.83 亿** | 7.40 亿 |
| 租赁负债利息 | 1.59 亿 | **3.67 亿** | 未披露 |
| 资本承诺 | 39.15 亿 | 未披露 | 未披露 |

海尔的 ROU 是美的的 1.9 倍、格力的 8.9 倍，租赁负债利息 3.67 亿同比 +65%（2024 年
2.22 亿）——它在用租入产能替代自建，海外扩张的固定成本是「租约」而不是「厂房」。
只看固定资产会漏掉海尔这一半的产能来源：它的固定资产 403.53 亿只比美的少 10%，
但使用权资产是美的的近两倍。

资本承诺是**已经签字、还没进表**的支出。美的 2025 年 39.15 亿（房屋建筑物及机器设备
39.13 亿 + 投资承诺 0.02 亿），2024 年可比口径 113.46 亿。差额 74.31 亿拆成两块：
投资承诺从 67.51 亿降到 0.02 亿（−67.49），房屋设备从 45.95 亿降到 39.13 亿（−6.82）。
附注正文点名 Arbonia（5.42 亿欧元）与 Teka（1.75 亿欧元）两笔收购，但不逐笔对应金额。
把它读成「资本开支下降 65%」是错的：主体是并购付款的时点，不是产能投资。

六个陷阱（都是实际踩到的）：

1. **单位**：美的年报附注是「千元」，海尔/格力是「元」。美的使用权资产原值 5,849,104
   是千元（58.49 亿），当成元就是 0.06 亿，直接错 1000 倍。
2. **资产负债表「租赁负债」不是租赁负债总额**，是扣掉一年内到期后的长期部分。美的
   报表列 19.01 亿、附注总额 32.96 亿；海尔 45.51 / 61.83；格力 6.53 / 7.40。直接
   拿报表数当总额，三家分别低估 42% / 26% / 12%。一年内到期部分藏在「一年内到期的
   非流动负债」里（13.95 / 16.31 / 0.87 亿），三家附注都单列了这行，**能拆出来**——
   所以本表能勾稽到底，不靠倒挤。
3. **美的租赁负债到期表的「一年以内」是「-」**。那张表（附注十五(3) 流动性风险）只
   覆盖非流动部分：一年内到期的租赁负债被并进「一年内到期的非流动负债(包括利息)」
   5,951,393 千元（59.52 亿，还含长期借款利息），拆不出租赁那一块。所以「一年以内」
   记「未披露」而不是 0。同理该表合计 21.62 亿 < 账面 32.96 亿，差额正是短期部分，
   两个数不能直接比。
4. **格力的「其他设备」列几乎全空**，行内只有 2 个数（房屋建筑物 + 合计）。按行序赋列
   会把合计读成「其他设备」：2025 年 848,193,397.59 的合计被重复计入 384,955.76 那
   一列，分类相加变成 848,578,353.35，对不上合计。必须按**数字右边界**定位列。同理
   格力 2024 年整张表只有「房屋建筑物」一列、没有合计列，按固定 3 列去读会把
   1,062,675,772.54 拆成「房屋建筑物=1,062,675,772.54 + 其他设备=空」再丢掉合计。
5. **海尔的使用权资产表跨页重排**：第一页是「房屋及建筑物/生产设备/运输设备」，第二页
   续表变成「办公设备/其他/合计」，且分页处数字整体左移（右边界 64/90/119 → 31/51/70）。
   整块聚类会得到 6 个簇，按行序会把「合计」当「其他」。本脚本按「续表」切段、段内
   重新定位列。
6. **同一年度在不同年报里会对不上**。海尔 2025 年报的租赁负债期初 5,833,372,352.30，
   2024 年报的期末 5,832,149,696.39，差 1,222,655.91 元（0.012 亿）；一年内到期部分
   同步差同一个数，长期部分一分不差——是重分类不是错报，但会让「2025 年期初 = 2024 年
   期末」的勾稽报出 +0.0122 亿。美的资本承诺同病且差得更大：2024 年报只列 45.95 亿
   （无合计行、投资承诺写在正文），2025 年报的可比数补列成 113.46 亿。所以 2024 年
   的资本承诺在 CSV 里有两行「合计」：可比口径 113.46 亿 + 原年报口径 45.95 亿。

取不到的项（CSV 中「数据性质=未披露」，金额留空，不填 0）：
- 海尔：**资本性支出承诺**（全文无「承诺事项」节，十五、或有事项仅「无重要或有事项」）
- 格力：资本承诺（附注十三、1「重要承诺事项：无」）、租赁负债利息（财务费用附注
  19.65 亿不拆租赁部分）、租赁负债到期结构、经营租赁未来收款额（只有当期收入
  2.08 亿 / 2024 年 1.71 亿）
- 海尔/格力：租赁负债未折现到期结构（无流动性风险到期表）
- 美的/格力：未纳入租赁负债计量的可变租赁付款额（只有政策表述，无金额）
- 美的：租赁负债未折现「一年以内」（见陷阱 3）

自校验（stderr 报告）：
- 使用权资产 原值 − 累计折旧 − 减值准备 = 账面价值（逐类别 + 合计）
- 使用权资产 分类别账面价值相加 = 合计
- 租赁负债 一年内到期 + 一年以上 = 合计
- 使用权资产附注合计 = 资产负债表「使用权资产」
- 报表「租赁负债」= 附注长期部分；附注合计 = 报表租赁负债 + 一年内到期租赁负债
- 经营租赁承诺 各档相加 = 合计
- 资本承诺 明细相加 = 合计（美的）
- 跨年：2025 年报期初 vs 2024 年报期末（差额逐条报出，不算失败）

用法：
    uv run python3 scripts/extract_leases_commitments.py --all
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
CACHE = Path("/tmp/fsr")
OUT = FIN / "租赁与承诺事项.csv"

COMPANIES = ("美的集团", "海尔智家", "格力电器")
YEARS = (2025, 2024)
PDF = {
    "美的集团": {2025: "美的2025.pdf", 2024: "美的2024.pdf"},
    "海尔智家": {2025: "海尔2025.pdf", 2024: "海尔2024.pdf"},
    "格力电器": {2025: "格力2025.pdf", 2024: "格力2024.pdf"},
}
SCALE = {"美的集团": 1_000, "海尔智家": 1, "格力电器": 1}

ROU_NOTE = {
    ("美的集团", 2025): "附注四(19)",
    ("美的集团", 2024): "附注四(20)",
    ("海尔智家", 2025): "附注七、19",
    ("海尔智家", 2024): "附注七、19",
    ("格力电器", 2025): "附注五、23",
    ("格力电器", 2024): "附注五、23",
}
LIAB_NOTE = {
    ("美的集团", 2025): "附注四(39)",
    ("美的集团", 2024): "附注四(40)",
    ("海尔智家", 2025): "附注七、37",
    ("海尔智家", 2024): "附注七、36",
    ("格力电器", 2025): "附注五、42",
    ("格力电器", 2024): "附注五、42",
}
PNL_NOTE = {
    "美的集团": "附注四(54)(a)、四(55)",
    "海尔智家": "附注七、53、七、67(1)",
    "格力电器": "附注五、74(1)",
}

# 使用权资产按类别的列布局。海尔跨页重排分两段；格力 2024 只有房屋建筑物一列。
ROU_LAYOUT: dict[tuple[str, int], list[list[str]]] = {
    ("美的集团", 2025): [["房屋及建筑物", "机器设备", "土地使用权及其他", "合计"]],
    ("美的集团", 2024): [["房屋及建筑物", "机器设备", "土地使用权及其他", "合计"]],
    ("海尔智家", 2025): [
        ["房屋及建筑物", "生产设备", "运输设备"],
        ["办公设备", "其他", "合计"],
    ],
    ("海尔智家", 2024): [
        ["房屋及建筑物", "生产设备", "运输设备"],
        ["办公设备", "其他", "合计"],
    ],
    ("格力电器", 2025): [["房屋建筑物", "其他设备", "合计"]],
    ("格力电器", 2024): [["房屋建筑物"]],
}

# 括号必须成对：`\(?-?[\d,]+\)?` 会把「(2024」当成数字，float 直接抛错
TOKEN = re.compile(r"\(\s*-?[\d,]+(?:\.\d+)?\s*\)|-?[\d,]+(?:\.\d+)?")
STAMP = re.compile(r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日")
STAMP_YEAR = re.compile(r"(\d{4})\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日")
SECTION = re.compile(
    r"^(?:[一二三四]\s*[、.]\s*)?(账面原值|原价|累计折旧|减值准备|账面价值)[：:]?$"
)
PAGE = re.compile(r"^\s*\d{1,4}\s*(?:/\s*\d{1,4})?\s*$")
HEADER = re.compile(
    r"[\u4e00-\u9fa5（）()]+(?:股份有限公司|集团股份有限公司)\s*\d{4}\s*年(?:半)?年度报告(?:全文)?"
)
BUCKET = {
    "一年以内": "一年以内",
    "1年以内": "一年以内",
    "一到二年": "一到二年",
    "1-2年": "一到二年",
    "二到三年": "二到三年",
    "2-3年": "二到三年",
    "三到四年": "三到四年",
    "3-4年": "三到四年",
    "四到五年": "四到五年",
    "4-5年": "四到五年",
    "二到五年": "二到五年",
    "2-5年": "二到五年",
    "五年以上": "五年以上",
    "5年以上": "五年以上",
}


# ---------------------------------------------------------------- 文本读取


def lines_of(company: str, year: int) -> list[str]:
    """优先读 /tmp/fsr 的 pdftotext -layout 缓存，缺了才转 PDF。"""
    pdf = PDF_DIR / PDF[company][year]
    cached = CACHE / f"{pdf.stem}.txt"
    if cached.exists():
        return cached.read_text(encoding="utf-8").splitlines()
    if not pdf.exists():
        raise FileNotFoundError(f"缺少 {pdf}，且 /tmp/fsr/{pdf.stem}.txt 缓存不存在")
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=False
    )
    return result.stdout.splitlines()


def flat(lines: list[str]) -> str:
    """压成一行用于文字型披露（利息、短期租赁费用、担保）。页眉页脚先删。"""
    body = [line for line in lines if not PAGE.match(line)]
    return re.sub(r"\s+", " ", HEADER.sub(" ", "\n".join(body)))


def number(token: str) -> float:
    token = token.strip()
    if token.startswith("(") and token.endswith(")"):
        return -float(token[1:-1].replace(",", ""))
    return float(token.replace(",", ""))


def trailing(line: str, limit: int = 6) -> tuple[str, list[tuple[float, int]]]:
    """返回 (标签, [(数值, 右边界)])。右边界用于定位列——格力同一行会出现两个相同数字。

    日期先抹成等长空格再找数字，否则「2025 年 12 月 31 日」会被读成 2025 / 12 / 31。
    标签从**原始行**切，保留日期——它是判断「期末/期初」的唯一线索。
    `limit` 是列数：不设上限时「1 年以内」的行首档位「1」会被当成金额吃掉。
    """
    masked = STAMP.sub(lambda m: " " * len(m.group()), line)
    found = list(TOKEN.finditer(masked))
    values: list[tuple[float, int]] = []
    index = len(found) - 1
    while index >= 0 and len(values) < limit:
        match = found[index]
        before = masked[match.start() - 1] if match.start() else " "
        after = masked[match.end() : match.end() + 1]
        # 「5 年以上」「1 年以内」的档位号不是金额；金额后面只会跟空白
        if before != " " or after not in ("", " ") or re.match(r"\s*年", masked[match.end() :]):
            break
        values.insert(0, (number(match.group()), match.end()))
        index -= 1
    label = line[: found[index + 1].start()].strip() if values else line.strip()
    return label, values


def assign(
    values: list[tuple[float, int]], edges: list[int] | None, count: int
) -> dict[int, float]:
    """短行按右边界就近归列。格力「其他设备」全空、只有两个数的行靠这个。"""
    if len(values) == count:
        return {index: value for index, (value, _) in enumerate(values)}
    if edges and len(values) < count:
        picked: dict[int, float] = {}
        for value, end in values:
            column = min(range(count), key=lambda i: abs(edges[i] - end))
            picked[column] = value
        if len(picked) == len(values):
            return picked
    return {index: value for index, (value, _) in enumerate(values)}


def section_of(lines: list[str], head: str, stop: str) -> list[str]:
    """截到下一个同级标题为止。格力「23、使用权资产」在会计政策里也出现一次，取最后一次。"""
    starts = [i for i, line in enumerate(lines) if re.match(head, line.strip())]
    if not starts:
        return []
    body: list[str] = []
    for line in lines[starts[-1] + 1 :]:
        if re.match(stop, line.strip()):
            break
        body.append(line)
    return body


# ---------------------------------------------------------------- 使用权资产


def rou_table(lines: list[str], company: str, year: int) -> dict[str, dict[str, float]]:
    layout = ROU_LAYOUT[(company, year)]
    head = r"^\(\d+\)\s*使用权资产$" if company == "美的集团" else r"^\d+、\s*使用权资产$"
    stop = r"^\(\d+\)\s*无形资产" if company == "美的集团" else r"^\d+、\s*无形资产"
    body = section_of(lines, head, stop)

    segments: list[list[str]] = [[]]
    for line in body:
        if line.strip().startswith("续表") and len(layout) > 1:
            segments.append([])
            continue
        segments[-1].append(line)

    table: dict[str, dict[str, float]] = {}
    for seg_lines, names in zip(segments, layout, strict=False):
        count = len(names)
        rows: list[tuple[str, list[tuple[float, int]]]] = []
        for line in seg_lines:
            if PAGE.match(line) or HEADER.search(line):
                continue
            label, values = trailing(line, count)
            if values:
                rows.append((label, values))
            elif SECTION.match(line.strip()):
                # 小节标题（原价/累计折旧/减值准备/账面价值）单独成行、不带数字
                rows.append((line.strip(), []))
        # 列边界取自「满列」的那几行（格力期初余额只有 2 个数，不能拿它当基准）
        edges = next(
            ([end for _, end in values] for _, values in rows if len(values) == count), None
        )
        current = ""
        for label, values in rows:
            section = SECTION.match(label)
            if section:
                current = "原值" if section.group(1) in ("账面原值", "原价") else section.group(1)
                continue
            if not current or not values:
                continue
            stamp = STAMP_YEAR.match(label)
            if stamp:
                position = "期末" if int(stamp.group(1)) == year else "期初"
            elif "期初" in label:
                position = "期初"
            elif "期末" in label:
                position = "期末"
            elif "计提" in label and current == "累计折旧":
                position = "计提"
            else:
                continue
            for column, value in assign(values, edges, count).items():
                table.setdefault(names[column], {})[f"{current}{position}"] = value

    # 减值准备一节通常整块空白（美的连这一节都没有）→ 倒挤，标「计算值」
    for values in table.values():
        if "减值准备期末" not in values:
            values["减值准备期末"] = (
                values.get("原值期末", 0.0)
                - values.get("累计折旧期末", 0.0)
                - values.get("账面价值期末", 0.0)
            )
    if "合计" not in table:
        # 格力 2024 只有房屋建筑物一列，没有合计列 → 合计即该列本身
        table["合计"] = dict(table["房屋建筑物"])
    return table


# ---------------------------------------------------------------- 租赁负债


def liab_table(lines: list[str], company: str, year: int, column: int = 0) -> dict[str, float]:
    """租赁负债附注：总额 / 减一年内到期 / 长期部分。`column=0` 本期，`=1` 上期。

    美的的表里「减：一年内到期的非流动负债」和数字分两行（中间夹着「(附注四(35))」），
    长期部分那行**连标签都没有**，只有两个数。所以标签要跨行拼接，且一旦拿到长期部分
    就必须停——再往下是「(i) 短期租赁未来最低支付租金 180,169,000 元」，会被误当成
    长期部分（美的 2025 年会得到 1.79 亿而不是 19.01 亿）。表头（两个日期）不能进
    pending，否则「2025 年 12 月 31 日 2024 年 12 月 31 日租赁负债」不以「租赁负债」开头。
    """
    head = r"^\(\d+\)\s*租赁负债$" if company == "美的集团" else r"^\d+、\s*租赁负债$"
    body = section_of(lines, head, r"^(?:\(\d+\)|\d+、)\s*\S")
    out: dict[str, float] = {}
    pending = ""
    for line in body[:12]:
        stripped = line.strip()
        if re.match(r"^\([a-z]", stripped) or "元" in stripped:
            break
        if len(STAMP.findall(stripped)) >= 2:
            continue
        label, values = trailing(line, 2)
        if not values:
            # 表头「项目 期末余额 期初余额」不能进 pending，否则「租赁负债」不再打头
            if "项目" in label or "余额" in label:
                continue
            pending += label
            continue
        full = pending + label
        pending = ""
        value = abs(values[min(column, len(values) - 1)][0])
        if "一年内到期" in full:
            out["一年内"] = value
        elif full.startswith("租赁负债"):
            out["合计"] = value
        elif not label or "合计" in full:
            out["一年以上"] = value
            break
    return out


def maturity_table(lines: list[str], company: str, year: int) -> dict[str, float | None]:
    """美的附注十五(3)：租赁负债(包括利息)的未折现到期结构。海尔/格力没有这张表。"""
    if company != "美的集团":
        return {}
    hits = [line for line in lines if "租赁负债(包括利息)" in line]
    order = {2025: 0, 2024: 1}
    if len(hits) <= order[year]:
        return {}
    tokens = hits[order[year]].split()
    # ['租赁负债(包括利息)', '-', '897,164', '932,414', '332,001', '2,161,579']
    tail = tokens[-5:]
    names = ("一年以内", "一到二年", "二到五年", "五年以上", "合计")
    out: dict[str, float | None] = {}
    for name, token in zip(names, tail, strict=True):
        out[name] = None if token == "-" else number(token)
    return out


def pnl_items(text: str, company: str) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    if company == "美的集团":
        match = re.search(r"租赁负债利息支出约为 ([\d,]+) 元", text)
        out["租赁负债利息费用"] = number(match.group(1)) if match else None
        match = re.search(r"年度金额为 ([\d,]+) 元", text)
        out["短期租赁及低价值资产租赁费用"] = number(match.group(1)) if match else None
        out["未纳入租赁负债计量的可变租赁付款额"] = None
    elif company == "海尔智家":
        match = re.search(r"本期租赁负债的利息支出 ([\d,.]+) 元", text)
        out["租赁负债利息费用"] = number(match.group(1)) if match else None
        match = re.search(r"简化处理的短期租赁或低价值资产的租赁费用.{0,80}?([\d,.]+) 元", text)
        out["短期租赁及低价值资产租赁费用"] = number(match.group(1)) if match else None
        match = re.search(r"未纳入租赁负债计量的可变租赁付款额.{0,80}?([\d,.]+) 元", text)
        out["未纳入租赁负债计量的可变租赁付款额"] = number(match.group(1)) if match else None
    else:
        # 格力财务费用附注只给利息费用总额 19.65 亿，不拆租赁部分
        out["租赁负债利息费用"] = None
        match = re.search(r"简化处理的短期租赁或低价值资产租赁费用为 ([\d,.]+) 元", text)
        out["短期租赁及低价值资产租赁费用"] = number(match.group(1)) if match else None
        out["未纳入租赁负债计量的可变租赁付款额"] = None
    return out


# ---------------------------------------------------------------- 资本承诺 / 经营租赁承诺 / 担保


def meidi_capex(lines: list[str]) -> dict[str, tuple[float, float]]:
    """美的附注十二(1)，单位千元。列 = (2025 年末, 2024 年末)。

    2024 年报这一节只有 45.95 亿、且无合计行；投资承诺（Arbonia 5.42 亿欧元、
    Teka 1.75 亿欧元）写在正文没进表，2025 年报的可比数补列成 113.46 亿。
    """
    body = section_of(lines, r"^十二\s*承诺事项$", r"^十三\s*")
    out: dict[str, tuple[float, float]] = {}
    for line in body:
        label, values = trailing(line, 2)
        if len(values) != 2:
            continue
        pair = (values[0][0], values[1][0])
        if not label:
            out["合计"] = pair
        elif "房屋" in label:
            out["房屋、建筑物及机器设备"] = pair
        elif "投资承诺" in label:
            out["投资承诺"] = pair
    if "合计" not in out and out:
        out["合计"] = tuple(  # type: ignore[assignment]
            sum(pair[column] for pair in out.values()) for column in (0, 1)
        )
    return out


def op_receipts(lines: list[str], company: str) -> dict[str, float]:
    """作为出租人的未来最低租赁收款额（未折现）。格力只披露当期租赁收入。"""
    if company == "美的集团":
        body = section_of(lines, r"^十四\s*资产负债表日后经营租赁收款额$", r"^十五\s*")
    elif company == "海尔智家":
        # 「b.未来五年…」/「b. 未来五年…」两种排版都有（2025 vs 2024）
        start = next(
            (
                i
                for i, line in enumerate(lines)
                if re.match(r"^b\s*[.、]\s*未来五年未折现租赁收款额", line.strip())
            ),
            None,
        )
        if start is None:
            return {}
        body = lines[start + 1 : start + 14]
    else:
        return {}
    out: dict[str, float] = {}
    for line in body:
        label, values = trailing(line, 2)
        if not values:
            continue
        key = label.replace(" ", "")
        if key == "合计" or not key:
            out["合计"] = values[0][0]
        elif key in BUCKET:
            out[BUCKET[key]] = values[0][0]
    return out


def guarantees(text: str, company: str) -> dict[str, tuple[float | None, str]]:
    """对外担保，单位统一换成元（表里是万元）。格力另有购房按揭阶段性担保，不在担保表内。"""
    out: dict[str, tuple[float | None, str]] = {}
    if company == "美的集团":
        match = re.search(r"([\d,]+)\s*计?\s*（A4\+B4\+C4\+D4）", text)
        out["担保余额合计（含对子公司）"] = (
            number(match.group(1)) * 1e4 if match else None,
            "披露值",
        )
        out["其中：对外担保（A4，不含对子公司）"] = (0.0, "披露值")
    elif company == "海尔智家":
        total = re.search(r"担保总额（A\+B） ([\d,]+)", text)
        sub = re.search(r"报告期末对子公司担保余额合计（B） ([\d,]+)", text)
        if total:
            out["担保余额合计（含对子公司）"] = (number(total.group(1)) * 1e4, "披露值")
            gap = number(total.group(1)) - (number(sub.group(1)) if sub else 0.0)
            out["其中：对外担保（A，不含对子公司）"] = (gap * 1e4, "计算值")
    else:
        match = re.search(r"([\d,.]+)\s+([\d,.]+)\s*计?\s*（A3\+B3\+C3）", text)
        out["担保余额合计（含对子公司）"] = (
            number(match.group(2)) * 1e4 if match else None,
            "披露值",
        )
        if match:
            # 格力的 A 区（对外担保，不含对子公司）整块空白、无任何数字。
            # 从「A 区标题下没有明细记录」推断为 0，标计算值而非披露值。
            out["其中：对外担保（A4，表格整块空白，推断为 0）"] = (0.0, "计算值")
        match = re.search(r"尚未结清的担保金额为 ([\d,.]+) 万元", text)
        out["购房按揭阶段性担保（或有事项，表外）"] = (
            number(match.group(1)) * 1e4 if match else None,
            "披露值",
        )
    return out


# ---------------------------------------------------------------- 主流程


def add(
    rows: list[list[str]],
    company: str,
    year: int,
    kind: str,
    item: str,
    value: float | None,
    nature: str,
    source: str,
) -> None:
    if value is None:
        amount, nature = "", "未披露"
    else:
        # 倒挤出来的减值准备会有 -1e-9 这种浮点尾差，直接格式化会印成「-0.00」
        amount = f"{(0.0 if abs(value) < 1e-3 else value) / 1e8:.2f}"
    rows.append([company, str(year), kind, item, amount, nature, source])


def balance_sheet() -> dict[tuple[str, int, str], float]:
    out: dict[tuple[str, int, str], float] = {}
    path = FIN / "资产负债表.csv"
    if not path.exists():
        return out
    with path.open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["报告期"] not in ("20251231", "20241231"):
                continue
            if row["科目"] not in ("使用权资产", "租赁负债"):
                continue
            try:
                out[(row["公司"], int(row["报告期"][:4]), row["科目"])] = float(row["数值"])
            except ValueError:
                continue
    return out


def check(label: str, left: float, right: float, tol: float = 0.01) -> bool:
    ok = abs(left - right) <= tol
    print(
        f"  [{'OK  ' if ok else 'FAIL'}] {label}: {left:,.2f} vs {right:,.2f} (差 {left - right:+,.2f})",
        file=sys.stderr,
    )
    return ok


def emit_rou(
    rows: list[list[str]], company: str, year: int, rou: dict[str, dict[str, float]]
) -> None:
    scale = SCALE[company]
    note = ROU_NOTE[(company, year)]
    for name, values in rou.items():
        for metric in ("原值", "累计折旧", "减值准备", "账面价值"):
            key = f"{metric}期末"
            if key not in values:
                continue
            # 减值准备一节空白时是倒挤出来的，标计算值
            printed = metric != "减值准备"
            add(
                rows,
                company,
                year,
                "使用权资产",
                f"{name}-{metric}",
                values[key] * scale,
                "披露值" if printed else "计算值",
                note,
            )


def emit_liab(rows: list[list[str]], company: str, year: int, lines: list[str]) -> dict[str, float]:
    liab = liab_table(lines, company, year)
    scale = SCALE[company]
    note = LIAB_NOTE[(company, year)]
    add(
        rows,
        company,
        year,
        "租赁负债",
        "合计（账面价值）",
        liab.get("合计", 0.0) * scale,
        "披露值",
        note,
    )
    add(
        rows,
        company,
        year,
        "租赁负债",
        "其中：一年内到期",
        liab.get("一年内", 0.0) * scale,
        "披露值",
        note,
    )
    add(
        rows,
        company,
        year,
        "租赁负债",
        "其中：一年以上",
        liab.get("一年以上", 0.0) * scale,
        "披露值",
        note,
    )
    maturity = maturity_table(lines, company, year)
    for name in ("一年以内", "一到二年", "二到五年", "五年以上", "合计"):
        if name not in maturity:
            continue
        value = maturity[name]
        add(
            rows,
            company,
            year,
            "租赁负债",
            f"未折现租赁付款额-{name}",
            None if value is None else value * scale,
            "披露值",
            "附注十五(3) 流动性风险（含利息，仅非流动部分）",
        )
    if not maturity:
        add(
            rows,
            company,
            year,
            "租赁负债",
            "未折现租赁付款额-合计",
            None,
            "未披露",
            "无按到期日列示的租赁负债未折现现金流量表",
        )
    return liab


def emit_capex(
    rows: list[list[str]], company: str, year: int, cache: dict[tuple[str, int], list[str]]
) -> float:
    if company != "美的集团":
        note = (
            "附注十三、1「重要承诺事项：无」"
            if company == "格力电器"
            else "海尔2025/2024 全文无「承诺事项」节，十五、或有事项仅「无重要或有事项」"
        )
        add(rows, company, year, "资本承诺", "已签约未确认资本性支出-合计", None, "未披露", note)
        return 0.0
    # 2024 用 2025 年报的可比列：只有那里同时列了房屋设备和投资承诺
    source = "附注十二(1)" if year == 2025 else "附注十二(1)，2025 年报可比数"
    capex = meidi_capex(cache[("美的集团", 2025)])
    column = 0 if year == 2025 else 1
    detail = 0.0
    for name, pair in capex.items():
        if name == "合计":
            continue
        detail += pair[column]
        add(
            rows,
            company,
            year,
            "资本承诺",
            f"已签约未确认资本性支出-{name}",
            pair[column] * 1_000,
            "披露值",
            source,
        )
    total = capex.get("合计", (0.0, 0.0))[column]
    add(
        rows,
        company,
        year,
        "资本承诺",
        "已签约未确认资本性支出-合计",
        total * 1_000,
        "披露值",
        source,
    )
    if year == 2024:
        origin = meidi_capex(cache[("美的集团", 2024)])
        if origin:
            add(
                rows,
                company,
                year,
                "资本承诺",
                "已签约未确认资本性支出-合计（2024 年报原披露口径）",
                origin.get("房屋、建筑物及机器设备", (0.0, 0.0))[0] * 1_000,
                "披露值",
                "美的2024.pdf 附注十二(1)，未含投资承诺",
            )
    return abs(detail - total) * 1_000 / 1e8


def emit_receipts(rows: list[list[str]], company: str, year: int, lines: list[str]) -> None:
    receipts = op_receipts(lines, company)
    scale = SCALE[company]
    if not receipts:
        # 格力只给当期经营租赁收入，没给未来最低收款额。收入写在来源里，不当承诺记。
        income = "2.08 亿" if year == 2025 else "1.71 亿"
        add(
            rows,
            company,
            year,
            "经营租赁承诺",
            "未来最低租赁收款额-合计",
            None,
            "未披露",
            f"附注五、74(3) 仅披露当期经营租赁收入 {income}，未给未来最低收款额",
        )
        return
    source = (
        "附注十四 资产负债表日后经营租赁收款额"
        if company == "美的集团"
        else "附注七、67(2)(b) 未来五年未折现租赁收款额"
    )
    for name in (
        "一年以内",
        "一到二年",
        "二到三年",
        "三到四年",
        "四到五年",
        "二到五年",
        "五年以上",
    ):
        if name in receipts:
            add(
                rows,
                company,
                year,
                "经营租赁承诺",
                f"未来最低租赁收款额-{name}",
                receipts[name] * scale,
                "披露值",
                source,
            )
    parts = [receipts.get(name) for name in ("二到三年", "三到四年", "四到五年")]
    if all(part is not None for part in parts):
        add(
            rows,
            company,
            year,
            "经营租赁承诺",
            "未来最低租赁收款额-二到五年",
            sum(part for part in parts if part) * scale,
            "计算值",
            "二到三年 + 三到四年 + 四到五年",
        )
    add(
        rows,
        company,
        year,
        "经营租赁承诺",
        "未来最低租赁收款额-合计",
        receipts.get("合计", 0.0) * scale,
        "披露值",
        source,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--all", action="store_true", help="提取三家 2025/2024 全部租赁与承诺事项")
    args = parser.parse_args()
    if not args.all:
        parser.print_help()
        return 0

    sheet = balance_sheet()
    rows: list[list[str]] = []
    cache: dict[tuple[str, int], list[str]] = {}
    failures = 0

    for company in COMPANIES:
        for year in YEARS:
            lines = lines_of(company, year)
            cache[(company, year)] = lines
            text = flat(lines)
            scale = SCALE[company]

            rou = rou_table(lines, company, year)
            emit_rou(rows, company, year, rou)
            liab = emit_liab(rows, company, year, lines)

            depreciation = rou.get("合计", {}).get("累计折旧计提")
            add(
                rows,
                company,
                year,
                "租赁损益",
                "使用权资产折旧",
                None if depreciation is None else depreciation * scale,
                "披露值",
                f"{ROU_NOTE[(company, year)]} 累计折旧「计提」",
            )
            for item, value in pnl_items(text, company).items():
                add(rows, company, year, "租赁损益", item, value, "披露值", PNL_NOTE[company])

            failures += bool(emit_capex(rows, company, year, cache) > 0.01)
            emit_receipts(rows, company, year, lines)
            for item, (value, nature) in guarantees(text, company).items():
                note = (
                    "重大担保"
                    if "合计" in item or "对外担保" in item
                    else "附注十三、2(2) 或有事项"
                )
                add(rows, company, year, "对外担保", item, value, nature, note)
            print(
                f"  {company} {year}: ROU {len(rou)} 列, 租赁负债 {len(liab)} 行", file=sys.stderr
            )

    print("\n自校验：", file=sys.stderr)
    for company in COMPANIES:
        for year in YEARS:
            scale = SCALE[company]
            rou = rou_table(cache[(company, year)], company, year)
            total = rou["合计"]
            categories = [name for name in rou if name != "合计"]
            failures += not check(
                f"{company} {year} 原值-累计折旧-减值=账面",
                (total["原值期末"] - total["累计折旧期末"] - total["减值准备期末"]) * scale / 1e8,
                total["账面价值期末"] * scale / 1e8,
            )
            if len(categories) > 1:
                failures += not check(
                    f"{company} {year} 分类别账面相加=合计",
                    sum(rou[name]["账面价值期末"] for name in categories) * scale / 1e8,
                    total["账面价值期末"] * scale / 1e8,
                )
            liab = liab_table(cache[(company, year)], company, year)
            failures += not check(
                f"{company} {year} 一年内+一年以上=租赁负债合计",
                (liab.get("一年内", 0.0) + liab.get("一年以上", 0.0)) * scale / 1e8,
                liab.get("合计", 0.0) * scale / 1e8,
            )
            book_rou = sheet.get((company, year, "使用权资产"))
            if book_rou is not None:
                failures += not check(
                    f"{company} {year} 附注使用权资产=资产负债表",
                    total["账面价值期末"] * scale / 1e8,
                    book_rou / 1e8,
                )
            book_liab = sheet.get((company, year, "租赁负债"))
            if book_liab is not None:
                failures += not check(
                    f"{company} {year} 报表租赁负债=附注长期部分",
                    book_liab / 1e8,
                    liab.get("一年以上", 0.0) * scale / 1e8,
                )
                failures += not check(
                    f"{company} {year} 附注租赁负债合计=报表租赁负债+一年内到期租赁",
                    liab.get("合计", 0.0) * scale / 1e8,
                    (book_liab + liab.get("一年内", 0.0) * scale) / 1e8,
                )
            receipts = op_receipts(cache[(company, year)], company)
            if receipts:
                buckets = [value for name, value in receipts.items() if name != "合计"]
                failures += not check(
                    f"{company} {year} 经营租赁承诺各档相加=合计",
                    sum(buckets) * scale / 1e8,
                    receipts.get("合计", 0.0) * scale / 1e8,
                )

    print("\n跨年勾稽（2025 年报期初 vs 2024 年报期末）：", file=sys.stderr)
    for company in COMPANIES:
        scale = SCALE[company]
        now = rou_table(cache[(company, 2025)], company, 2025)["合计"]
        before = rou_table(cache[(company, 2024)], company, 2024)["合计"]
        print(
            f"  {company} 使用权资产 {now['账面价值期初'] * scale / 1e8:,.2f} vs "
            f"{before['账面价值期末'] * scale / 1e8:,.2f} "
            f"(差 {(now['账面价值期初'] - before['账面价值期末']) * scale / 1e8:+.4f})",
            file=sys.stderr,
        )
        # 2025 年报的上期列 = 2024 年末。海尔 2025 年报把 0.012 亿在「一年内」与「长期」
        # 之间重分类了，长期部分不变、总额差 0.012 亿，属重分类不属错报。
        now_liab = liab_table(cache[(company, 2025)], company, 2025, column=1)
        before_liab = liab_table(cache[(company, 2024)], company, 2024)
        print(
            f"  {company} 租赁负债 {now_liab.get('合计', 0.0) * scale / 1e8:,.4f} vs "
            f"{before_liab.get('合计', 0.0) * scale / 1e8:,.4f} "
            f"(差 {(now_liab.get('合计', 0.0) - before_liab.get('合计', 0.0)) * scale / 1e8:+.4f})",
            file=sys.stderr,
        )
    print(
        "  美的 2024 资本承诺：2024 年报 45.95 亿（未含投资承诺）→ 2025 年报可比数 113.46 亿",
        file=sys.stderr,
    )

    fields = ["公司", "年度", "类别", "项目", "金额(亿元)", "数据性质", "来源"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    print(
        f"\n{'公司':<9}{'年度':<6}{'使用权资产':>11}{'租赁负债':>10}{'资本承诺':>10}{'租赁利息':>10}",
        file=sys.stderr,
    )
    pick = {(row[0], row[1], row[3]): row[4] for row in rows}
    for company in COMPANIES:
        for year in YEARS:
            key = (company, str(year))
            print(
                f"{company:<9}{year:<6}"
                f"{pick.get((*key, '合计-账面价值'), ''):>11}"
                f"{pick.get((*key, '合计（账面价值）'), ''):>10}"
                f"{pick.get((*key, '已签约未确认资本性支出-合计'), '未披露'):>10}"
                f"{pick.get((*key, '租赁负债利息费用'), '未披露'):>10}",
                file=sys.stderr,
            )

    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行", file=sys.stderr)
    if failures:
        print(f"自校验失败 {failures} 项", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
