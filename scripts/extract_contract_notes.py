"""合同资产与合同负债附注：预收构成、结转率、预期信用损失率。

为什么重要
----------
报表级 `资产负债表.csv` 已有「合同资产」「合同负债」两行，但只有净额一个数。
附注补上三件报表看不到的事：

1. **合同负债的构成**。美的拆成「预收货款及劳务款」与「预收工程款」。
   2025 年 433.0 亿 vs 37.0 亿——98% 是卖家电预收的款。
   这决定「合同负债下降」该往哪解释：2025 年美的合同负债从 492.5 亿降到
   469.9 亿，减少全部来自预收货款，预收工程款反而在涨。
2. **结转率**（美的独有）。每年披露「包括在上年 12 月 31 日账面价值中的 X%
   以上合同负债已于本年度转入营业收入」。2020—2024 都是 90%，
   **2025 年报跳到 95%**。这是预收款变现速度的直接度量，
   比合同负债余额本身更能说明渠道打款意愿。
3. **合同资产的预期信用损失率**，且分单项计提／组合计提、组合再分境内／境外。
   美的 2024 年境内组合 12.34 亿按 0.91% 计提、境外 22.90 亿按 1.16% 计提，
   而单项计提部分账面余额只有 2,420.8 万却按 **46.11%** 计提
   （理由是「债务人财务困难等」）。组合部分基本不逾期，
   真正的风险集中在极小金额的单项部分——这个结构报表数完全看不出来。

只有美的披露金额明细
--------------------
| 公司 | 合同资产/合同负债附注 | 金额明细 |
|---|---|---|
| 美的 | (8)/(9) 合同资产、(30)/(31) 合同负债 | **有**，2020 年起逐年 |
| 海尔 | 13、合同资产 22、合同负债 | 无——两段都是纯会计政策文字 |
| 格力 | 15、合同资产 27、合同负债 | 无——同样是纯政策文字 |

所以本表的美的以外只有两条「未披露」说明行。这不是提取失败，是披露本身没有，
金额已在 `资产负债表.csv` 覆盖。

一个容易读错的句子
------------------
海尔与格力的「**重要性标准**」表里都有一行
「单项账龄超过 1 年的合同负债占合同负债（期末余额）的 10% 以上且金额大于 1 亿元」。
字面像账龄数据，实际是**判断什么才算重要**的门槛定义；
紧跟其后的「账龄超过一年的重要合同负债」小节下面是空的。
搜到这句就写「海尔约 10% 的合同负债账龄超一年」是错的——那是标准，不是结果。

2020 年是新收入准则切换首年，列数与之后不同
-------------------------------------------
美的 2020 年报表头有三列：「2020 年 12 月 31 日 / 2020 年 1 月 1 日 /
2019 年 12 月 31 日」，第三列**全是「——」**（当年不编制这两项）。
之后年份只有两列（期末 / 上年期末）。
本表**按表头日期给每列定语义**（期末 / 年初 / 期初），而不是按列的位置猜：
「取前两列」在 2020 年会把「2020 年 1 月 1 日」当成期初，
把首次确认数错当成上年末数。

四个坑
------
1. **表头日期被排版拆成两行**：「2025 年」+「12 月 31 日」。
   按行统计列数会把 2 列误判成 4 列。要按**列位**（起始字符位置）聚类。
2. **单位是千元，但正文夹带元单位的句子**。美的附注通篇
   「金额单位为人民币千元」，2020 年合同负债下面却有
   「增加合同负债金额 491,780,000 元」（元）。混着读差三个数量级。
   本表只取表体数字，正文数字一律不进表。
3. **净额那一行常常没有标签**。「减：合同资产减值准备 (77,754)」下面是
   空标签的 4,268,501；2020 年那版反而写了「合计」标签。
   规则：有「合计」用合计，没有就用空标签行，再没有才用原值 + 减值（减值已带负号）。
4. **项目名写法会变**。2020 写「预收货物及劳务款」，2021 起写「预收货款及劳务款」。
   归并成同一项目，否则时间序列在 2021 年断掉。

用法
----
    uv run python3 scripts/extract_contract_notes.py --all
"""

from __future__ import annotations

import argparse
import csv
import itertools
import re
import sys
from pathlib import Path

from pdf_util import pdf_text

ROOT = Path(__file__).resolve().parent.parent
FIN = ROOT / "财务数据"
OUT = FIN / "合同资产与合同负债附注.csv"

YEARS = [str(y) for y in range(2023, 2026)]

# 「预收货物及劳务款」(2020) 与「预收货款及劳务款」(2021 起) 是同一项目
ALIASES = {"预收货物及劳务款": "预收货款及劳务款"}
# 表体里认得的项目标签；空标签行是净额/合计
ITEM_LABELS = (
    "合同资产",
    "减：合同资产减值准备",
    "合计",
    "预收货款及劳务款",
    "预收货物及劳务款",
    "预收工程款",
)
NOISE = (
    "年度财务报表附注",
    "除特别注明外",
    "合并财务报表项目附注",
    "集团股份有限公司",
    "- 2",
    "报告全文",
)
# 正文起点（表体到此为止）
PROSE = (
    "合同资产无论",
    "年度本集团不存在",
    "包括在",
    "如附注",
    "单项计提坏账准备",
    "组合计提坏账准备",
    "于 20",
)

DATE_YEAR = re.compile(r"\d{4}\s*年")
DATE_MD = re.compile(r"\d{1,2}\s*月\s*\d{1,2}\s*日")
NUM = re.compile(r"^-?[\d,]+(?:\.\d+)?$")
SPLIT = re.compile(r"\s{2,}")
CELL = re.compile(r"\S+")


def text_of(year: str) -> str:
    return pdf_text(ROOT / "年度报告" / f"美的{year}.pdf")


def number(token: str) -> float | None:
    """支持括号负数（报表里减值准备写成 (77,754)）。"""
    token = token.strip()
    neg = token.startswith("(") and token.endswith(")")
    body = token.strip("()")
    if NUM.match(body):
        return -float(body.replace(",", "")) if neg else float(body.replace(",", ""))
    return None


PLACEHOLDER = re.compile(r"^(?:-|—+|/|不适用)$")
PERCENT = re.compile(r"^(\d+(?:\.\d+)?)%$")


def row_slots(raw: str) -> tuple[str, list[float | None], list[str]]:
    """(标签, 按列顺序的值槽位, 百分数列表)。

    **按顺序而不是按列位映射**：这类窄表里数字并不真的右对齐到同一列边界
    （实测美的 2020 减值行的 (52,935) 落在第二列的表头区间内），
    用「最近锚点」会把期末读成年初。
    占位符（——、-、不适用）必须占一个槽位，否则后面的列会整体左移。
    百分号单独收集，不进标签——否则「境内业务组合 0.91%」会被粘成
    「境内业务组合0.91%」，项目名匹配全部落空。
    """
    tokens = [m.group(0) for m in CELL.finditer(raw)]
    if not tokens:
        return "", [], []
    labels: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if number(token) is not None or PLACEHOLDER.match(token) or PERCENT.match(token):
            break
        labels.append(token)
        index += 1
    slots: list[float | None] = []
    percents: list[str] = []
    for token in tokens[index:]:
        if PLACEHOLDER.match(token):
            slots.append(None)
            continue
        percent = PERCENT.match(token)
        if percent:
            percents.append(percent.group(1))
            slots.append(float(percent.group(1)))
            continue
        slots.append(number(token))
    label = "".join(labels).strip()
    if re.match(r"^\(\d+\)$", label):
        label = ""
    return label, slots, percents


def header_columns(lines: list[str], report_year: str) -> list[str]:
    """表头 → 从左到右的期别标签列表。

    美的是竖排表头，一个列名常被拆成两半：「2025 年」在一行、
    「12 月 31 日」在下一行，也可能同行写完。所以分别收集
    「YYYY 年」与「M 月 D 日」两类碎片，**按出现顺序配对**。

    不要按横向距离聚类：实测 2020 合同负债表头
    「2020 年 12 月 31 日   2020 年 1 月 1 日  2019 年 12 月 31 日」
    第二、三列的碎片只隔 3 个字符宽，按距离聚类会把两列并成一列，
    少识别一整列（本表当年就是这么丢的）。

    返回值是**列表**而不是位置字典：数据行改用「第 k 个槽位 ↔ 第 k 列」
    的顺序映射，列的横向坐标因此不再参与判断，也就不需要算锚点。
    """
    years = _collect(lines, DATE_YEAR)
    months = _collect(lines, DATE_MD)
    if not years or len(years) != len(months):
        return []
    labels = [
        classify_period(year_text + month_text, report_year)
        for (_yl, _ys, _ye, year_text), (_ml, _ms, _me, month_text) in zip(
            years, months, strict=True
        )
    ]
    if len(set(labels)) != len(labels):
        return []  # 有列判不出唯一期别，宁可不用这张表头
    return labels


def _collect(lines: list[str], regex: re.Pattern) -> list[tuple[int, int, int, str]]:
    out: list[tuple[int, int, int, str]] = []
    for li, line in enumerate(lines[:4]):
        for m in regex.finditer(line):
            out.append((li, m.start(), m.end(), re.sub(r"\s+", "", m.group(0))))
    out.sort(key=lambda f: (f[0], f[1]))
    return out


def classify_period(date_text: str, report_year: str) -> str:
    """按报告年判定这一列是什么期别。

    年报里两列都是「YYYY 年 12 月 31 日」，靠**年份是不是报告年**区分：
    本年是「期末」，上一年是「期初」。若不这样分，上年比较数会被写成
    「期末(上年)」，与上年自己那份年报的「期末(上年)」**重复入库**，
    两条还可能因重述而不一致。
    """
    year = date_text[:4]
    if "1月1日" in date_text:
        return "年初" if year == report_year else f"其他({date_text})"
    if date_text.endswith("12月31日"):
        if year == report_year:
            return "期末"
        if int(year) == int(report_year) - 1:
            return "期初"
    return f"其他({date_text})"


def note_window(text: str, subject: str) -> list[str] | None:
    """取「(N) 合同资产 / 合同负债」小节里**表体**那几行，遇正文即止。"""
    m = re.search(rf"^\((\d+)\)\s+{subject}\s*$", text, re.M)
    if not m:
        return None
    out: list[str] = []
    for raw in text[m.end() : m.end() + 1200].splitlines():
        flat = raw.strip()
        if not flat:
            continue
        if any(n in flat for n in NOISE):
            continue
        if any(flat.startswith(p) or p in flat[:12] for p in PROSE):
            break
        # 下一个小节标题
        if re.match(r"^\(\d+\)\s+\S", flat) and subject not in flat:
            break
        if re.match(r"^[四五六七八九十]\s", flat):
            break
        out.append(raw)
        if len(out) > 12:
            break
    return out or None


def parse_block(lines: list[str], report_year: str, subject: str) -> list[dict[str, object]]:
    labels = header_columns(lines, report_year)
    if not labels:
        return []

    rows: list[dict[str, object]] = []
    for raw in lines:
        # 表头行本身会被当成数据（「2020 年」里的 2020 是数字），先排除
        if DATE_YEAR.search(raw) or DATE_MD.search(raw):
            continue
        label, slots, _percents = row_slots(raw)
        values = [v for v in slots if v is not None]
        if not values:
            continue
        # 槽位数必须等于列数；不等说明版式不是预期的两/三列窄表，宁可报错
        if len(slots) != len(labels):
            raise ValueError(
                f"{report_year} 行「{label}」有 {len(slots)} 个槽位，"
                f"表头却是 {len(labels)} 列：{' | '.join(labels)}"
            )
        mapped = dict(zip(labels, slots, strict=True))
        mapped = {k: v for k, v in mapped.items() if v is not None}
        if not mapped:
            continue
        key = ALIASES.get(label, label)
        if key == "合同资产":
            key = "合同资产原值"
        if key and key not in (*ITEM_LABELS, "合同资产原值"):
            continue
        if not key:
            # 空标签行 = 该小计的合计数：合同资产交给 merge_net 处理，合同负债就地命名
            key = "__NET__" if subject == "合同资产" else "合同负债合计（附注）"
        rows.append({"项目": key, "值": mapped})
    return rows


def merge_net(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """净额：有「合计」用合计；有 __NET__（空标签行）用它；否则原值 + 减值。"""
    gross = next((r for r in rows if r["项目"] == "合同资产原值"), None)
    allow = next((r for r in rows if r["项目"] == "减：合同资产减值准备"), None)
    total = next((r for r in rows if r["项目"] == "合计"), None)
    blank = next((r for r in rows if r["项目"] == "__NET__"), None)
    out = [r for r in rows if r["项目"] not in ("合计", "__NET__")]
    if total:
        out.append({"项目": "合同资产净额", "值": total["值"]})
    elif blank:
        out.append({"项目": "合同资产净额", "值": blank["值"]})
    elif gross and allow:
        merged = {}
        for period in gross["值"]:
            if period in allow["值"]:
                merged[period] = gross["值"][period] + allow["值"][period]
        out.append({"项目": "合同资产净额", "值": merged})
    return out


def ecl_detail(text: str) -> list[dict[str, str]]:
    """「(N) 合同资产(续)」里的预期信用损失率：单项计提 + 组合计提（境内/境外）。"""
    flat_zone = re.findall(
        r"于 (\d{4}) 年 \d{1,2} 月 \d{1,2} 日，(单项|组合)计提坏账准备的合同资产分析如下：",
        text,
    )
    out: list[dict[str, str]] = []
    for year, kind in flat_zone:
        m = re.search(
            rf"于 {year} 年 \d{{1,2}} 月 \d{{1,2}} 日，{kind}计提坏账准备的合同资产分析如下：",
            text,
        )
        if not m:
            continue
        seg = text[m.end() : m.end() + 900]
        # 同类小节在正文里连着排（单项 → 组合 → 又一年），窗口必须在本小节结束处切断。
        # 早先固定 900 字直接扫过去，把「组合计提」的境内/境外行也收进
        # 「单项计提」，同一条目每年入库两遍且其中一遍归属是错的。
        nxt = re.search(r"于 \d{4} 年 \d{1,2} 月 \d{1,2} 日，(?:单项|组合)计提", seg)
        if nxt:
            seg = seg[: nxt.start()]
        for raw in seg.splitlines():
            label, slots, percents = row_slots(raw)
            if not label or not percents:
                continue
            clean = re.sub(r"\s+", "", label)
            is_combo = clean.endswith("组合")
            if clean not in ("境内业务", "境外业务") and not is_combo:
                continue
            values = [v for v in slots if v is not None]
            rates = percents
            if len(values) < 2:
                continue
            out.append(
                {
                    "截至": year,
                    "类型": f"{kind}计提",
                    "范围": "境内" if "境内" in clean else "境外",
                    "账面余额": values[0],
                    "预期信用损失率": rates[0] if rates else "",
                    "减值准备": values[-1],
                }
            )
            if len(out) > 40:
                return out
    return out


def carryover_rate(text: str) -> tuple[str, str, str]:
    """结转率。原文跨行，先压平空白再匹配。"""
    flat = re.sub(r"\s+", "", text)
    m = re.search(
        r"包括在(\d{4})年\d{1,2}月\d{1,2}日账面价值中的(\d+)%以上合同负债已于(\d{4})年度转入营业收入",
        flat,
    )
    return (m.group(1), m.group(2), m.group(3)) if m else ("", "", "")


def balance_sheet() -> dict[tuple[str, str], dict[str, float]]:
    out: dict[tuple[str, str], dict[str, float]] = {}
    with (FIN / "资产负债表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["科目"] not in ("合同资产", "合同负债") or row["数值"] in ("", "nan"):
                continue
            if not row["报告期"].endswith("1231"):
                continue
            out.setdefault((row["公司"], row["报告期"][:4]), {})[row["科目"]] = float(row["数值"])
    return out


def yi(value: float) -> str:
    """附注单位是千元 → 亿元。"""
    return f"{value / 1e5:.2f}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    if not args.all:
        parser.print_help()
        return 0

    problems: list[str] = []
    rows: list[list[str]] = []
    ending: dict[str, dict[str, float]] = {}
    opening: dict[str, dict[str, float]] = {}
    # ECL 明细的**元级原值** {(年度, 类型, 范围): (账面余额, 减值准备, 披露率)}
    ecl_raw: dict[tuple[str, str, str], tuple[float, float, str]] = {}
    # 表体元级原值 {(年度, 项目): [值,…]}，勾稽 5 用它
    note_totals: dict[tuple[str, str], list[float]] = {}

    for year in YEARS:
        text = text_of(year)
        if not text.strip():
            problems.append(f"美的 {year} 年报文本缺失")
            continue

        for subject in ("合同资产", "合同负债"):
            block = note_window(text, subject)
            if block is None:
                problems.append(f"美的 {year} 未找到「{subject}」附注小节")
                continue
            parsed = parse_block(block, year, subject)
            if subject == "合同资产":
                parsed = merge_net(parsed)
            if not parsed:
                problems.append(f"美的 {year} 「{subject}」小节没解析出对齐表头的数字")
                continue
            for item in parsed:
                for period, value in item["值"].items():
                    rows.append(
                        [
                            "美的集团",
                            year,
                            period,
                            subject,
                            item["项目"],
                            yi(value),
                            f"{value:.0f}",
                            "披露值",
                            f"美的{year}.pdf 附注 {subject}（单位千元）",
                        ]
                    )
                    if period == "期末":
                        ending.setdefault(year, {})[item["项目"]] = value
                        # 同时留元级原值，勾稽用它而不是亿元展示值
                        note_totals.setdefault((year, item["项目"]), []).append(value)
                    elif period == "期初":
                        opening.setdefault(year, {})[item["项目"]] = value

        # 预期信用损失率（合同资产附注续）
        # 2022 年报原文「于 2022 年 12 月 31 日，无单项计提坏账准备的合同资产」。
        # 这是**披露为无**，与「没解析到」不同，必须记一行，否则读者只能看到空白。
        if re.search(
            rf"于 {year} 年 \d{{1,2}} 月 \d{{1,2}} 日，无单项计提坏账准备的合同资产", text
        ):
            rows.append(
                [
                    "美的集团",
                    year,
                    "期末",
                    "合同资产",
                    "单项计提·境内业务 账面余额",
                    "0.00",
                    "0",
                    "披露值",
                    f"美的{year}.pdf 附注 (续)：原文「无单项计提坏账准备的合同资产」",
                ]
            )
        for d in ecl_detail(text):
            if d["截至"] != year:
                continue  # 只收本年数，比较数会与上一年那份年报重复入库
            balance = float(d["账面余额"])
            allowance = abs(float(d["减值准备"]))
            stated = d["预期信用损失率"]
            prefix = f"{d['类型']}·{d['范围']}业务"
            source = f"美的{year}.pdf 附注 (续) {d['类型']}坏账准备分析"
            rows.append(
                [
                    "美的集团",
                    year,
                    "期末",
                    "合同资产",
                    f"{prefix} 账面余额",
                    yi(balance),
                    f"{balance:.0f}",
                    "披露值",
                    source,
                ]
            )
            if stated:
                rows.append(
                    [
                        "美的集团",
                        year,
                        "期末",
                        "合同资产",
                        f"{prefix} 预期信用损失率",
                        f"{stated}%",
                        "",
                        "披露值",
                        source,
                    ]
                )
                ecl_raw[(year, d["类型"], d["范围"])] = (balance, allowance, stated)
            rows.append(
                [
                    "美的集团",
                    year,
                    "期末",
                    "合同资产",
                    f"{prefix} 减值准备",
                    yi(allowance),
                    f"{allowance:.0f}",
                    "披露值",
                    source,
                ]
            )

        base, rate, applied = carryover_rate(text)
        if base:
            rows.append(
                [
                    "美的集团",
                    year,
                    "本年",
                    "合同负债",
                    "结转率：上年末合同负债本年转入营业收入比例",
                    f"{rate}%",
                    "",
                    "披露值",
                    f"美的{year}.pdf：包括在 {base} 年 12 月 31 日账面价值中的 {rate}% 以上"
                    f"合同负债已于 {applied} 年度转入营业收入",
                ]
            )

    # ---------------- 海尔 / 格力：附注只有政策文字
    for company, short in (("海尔智家", "海尔"), ("格力电器", "格力")):
        rows.append(
            [
                company,
                "2025",
                "期末",
                "合同资产/合同负债",
                "附注金额明细",
                "",
                "",
                "未披露",
                f"{short}2025.pdf 的「合同资产」「合同负债」小节是**纯会计政策文字**，未拆项目；"
                "金额见 资产负债表.csv 报表级两行。该文件「重要性标准」表里的"
                "「单项账龄超过 1 年的合同负债占合同负债 10% 以上且金额大于 1 亿元」"
                "是判断门槛而非账龄结果，不能读成「有 10% 账龄超一年」",
            ]
        )

    # ================= 自校验 =================
    print("[勾稽 1] 合同资产：原值 + 减值（带负号）= 净额")
    for year in YEARS:
        gross = next(
            (
                float(r[5])
                for r in rows
                if r[1] == year and r[4] == "合同资产原值" and r[2] == "期末"
            ),
            None,
        )
        allow = next(
            (
                float(r[5])
                for r in rows
                if r[1] == year and r[4] == "减：合同资产减值准备" and r[2] == "期末"
            ),
            None,
        )
        net = next(
            (
                float(r[5])
                for r in rows
                if r[1] == year and r[4] == "合同资产净额" and r[2] == "期末"
            ),
            None,
        )
        if gross is None or net is None:
            problems.append(f"{year} 合同资产原值或净额缺失")
            continue
        if allow is not None:
            ok = abs(gross - abs(allow) - net) <= 0.02
            print(
                f"    {year}: {gross:.2f} − {abs(allow):.2f} = {gross - abs(allow):.2f}"
                f" vs 净额 {net:.2f}  {'OK' if ok else '差异'}"
            )
            if not ok:
                problems.append(f"{year} 合同资产原值减减值与净额不符")

    print("[勾稽 2] 合同负债：预收货款 + 预收工程款 = 附注总额 = 报表数")
    bs = balance_sheet()
    for year in YEARS:
        goods = next(
            (
                float(r[5])
                for r in rows
                if r[1] == year and r[4] == "预收货款及劳务款" and r[2] == "期末"
            ),
            None,
        )
        eng = next(
            (float(r[5]) for r in rows if r[1] == year and r[4] == "预收工程款" and r[2] == "期末"),
            None,
        )
        if goods is None or eng is None:
            continue
        total = goods + eng
        theirs = bs.get(("美的集团", year), {}).get("合同负债")
        if theirs:
            ok = abs(total - theirs / 1e8) <= 0.02
            print(
                f"    {year}: {goods:.2f} + {eng:.2f} = {total:.2f}"
                f" vs 报表 {theirs / 1e8:.2f}  {'OK' if ok else '差异'}"
            )
            if not ok:
                problems.append(f"{year} 合同负债分项相加与报表数不符")

    print("[勾稽 3] 合同资产净额与报表数对平")
    for year in YEARS:
        net = next(
            (
                float(r[5])
                for r in rows
                if r[1] == year and r[4] == "合同资产净额" and r[2] == "期末"
            ),
            None,
        )
        theirs = bs.get(("美的集团", year), {}).get("合同资产")
        if net is None or not theirs:
            continue
        ok = abs(net - theirs / 1e8) <= 0.02
        print(f"    {year}: 附注 {net:.2f} vs 报表 {theirs / 1e8:.2f}  {'OK' if ok else '差异'}")
        if not ok:
            problems.append(f"{year} 合同资产附注净额与报表不符")

    print("[链条] 本年报期初 == 上年年报期末（2020 是三列结构，无期初）")
    rings = broken = 0
    for a, b in itertools.pairwise(YEARS):
        for item, prior in opening.get(b, {}).items():
            end_value = ending.get(a, {}).get(item)
            if end_value is None:
                continue
            rings += 1
            if abs(prior - end_value) > 0.02:
                broken += 1
                problems.append(f"{b} 期初「{item}」{prior:.2f} ≠ {a} 期末 {end_value:.2f}")
    print(f"    {rings} 环比对，断开 {broken} 环")

    print("[损失率] 减值准备 ÷ 账面余额 应等于披露的预期信用损失率")
    # 用**元级原值**判。拿表里保留两位的亿元（0.35 / 8.40）相除会得到 4.17%，
    # 与披露的 4.22% 差 0.05pp 而误报——原值 35,436 / 840,430 = 4.2165%，
    # 四舍五入正是 4.22%。同第 68 条记的舍入累积坑是一回事。
    rings = 0
    for (year, kind, scope), (balance, allowance, stated) in sorted(ecl_raw.items()):
        if not balance:
            continue
        implied = round(allowance / balance * 100, 2)
        rings += 1
        ok = abs(implied - float(stated)) <= 0.01
        print(
            f"    {year} {kind}·{scope}：{allowance:,.0f} / {balance:,.0f}"
            f" = {implied:.2f}% vs 披露 {stated}%  {'OK' if ok else '差异'}"
        )
        if not ok:
            problems.append(
                f"{year} {kind}·{scope} 隐含损失率 {implied:.2f}% 与披露 {stated}% 不符"
            )
    print(f"    比对 {rings} 组")

    print("[勾稽 5] 单项 + 组合(境内+境外) = 合同资产原值，减值准备同理")
    checked = 0
    # 全部用**元级原值**加总比对。拿表里保留两位的亿元相加会得到
    # 38.69 ≠ 38.70、0.46 ≠ 0.47 这类 0.01 的舍入累积假差异（同第 68 条）。
    # 美的只披露单项计提的**境内**一行（无境外单项），所以按实际存在的分项加总，
    # 不硬要求四格齐全——后者会让每年都不满足条件、勾稽悄悄不跑（实测就发生过）。
    # 某分项若解析失败，加总会短一截并在这里报差异，那正是要抓的东西。
    for year in YEARS:
        for label, want_balance in (("账面", True), ("减值", False)):
            item = "合同资产原值" if want_balance else "减：合同资产减值准备"
            parts = [
                hit[0] if want_balance else hit[1]
                for kind in ("单项计提", "组合计提")
                for scope in ("境内", "境外")
                if (hit := ecl_raw.get((year, kind, scope)))
            ]
            # 期末是表体第一列，note_totals 按解析顺序存，取第一个
            hits = note_totals.get((year, item), [])
            # 减值准备在报表里写成括号负数 (77,754)，解析后是 -77,754；
            # ECL 分项的减值是绝对值，比对前统一取正。
            target = abs(hits[0]) if hits else None
            if not target or len(parts) < 2:
                continue
            checked += 1
            total = sum(parts)
            ok = abs(total - target) <= 2  # 元级容差
            detail = " + ".join(f"{v:,.0f}" for v in parts)
            print(
                f"    {year} {label}：{detail} = {total:,.0f}"
                f" vs 附注 {target:,.0f}  {'OK' if ok else '差异'}"
            )
            if not ok:
                problems.append(
                    f"{year} 合同资产{label}分项相加 {total:,.0f} 元 ≠ 附注 {target:,.0f} 元"
                )

    print(f"    比对 {checked} 组")

    fields = [
        "公司",
        "年度",
        "期别",
        "附注小节",
        "项目",
        "金额或比例",
        "附注原值(千元)",
        "数据性质",
        "口径说明",
    ]
    short = [r for r in rows if len(r) != len(fields)]
    if short:
        for r in short[:5]:
            print(f"列数错位（{len(r)} 列，应为 {len(fields)}）：{r[:5]}", file=sys.stderr)
        raise SystemExit(f"{len(short)} 行列数不对，拒绝写出 {OUT.name}")

    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    print(f"\n{'年度':<6}{'合同资产净额':>10}{'合同负债':>10}{'减值率':>9}{'结转率':>8}")
    print("-" * 46)
    for year in YEARS:
        net = next(
            (r[5] for r in rows if r[1] == year and r[4] == "合同资产净额" and r[2] == "期末"),
            "—",
        )
        goods = next(
            (
                float(r[5])
                for r in rows
                if r[1] == year and r[4] == "预收货款及劳务款" and r[2] == "期末"
            ),
            None,
        )
        eng = next(
            (float(r[5]) for r in rows if r[1] == year and r[4] == "预收工程款" and r[2] == "期末"),
            None,
        )
        gross = next(
            (
                float(r[5])
                for r in rows
                if r[1] == year and r[4] == "合同资产原值" and r[2] == "期末"
            ),
            None,
        )
        allow = next(
            (
                float(r[5])
                for r in rows
                if r[1] == year and r[4] == "减：合同资产减值准备" and r[2] == "期末"
            ),
            None,
        )
        rate = f"{abs(allow) / gross * 100:.1f}%" if gross and allow is not None else "—"
        total = f"{(goods + eng):.1f}" if goods and eng else "—"
        carry = next((r[5] for r in rows if r[1] == year and "结转率" in r[4]), "—")
        print(f"{year:<6}{net:>10}{total:>10}{rate:>9}{carry:>8}")

    tail = OUT.relative_to(ROOT)
    print(f"\n写入 {tail}: {len(rows)} 行")
    for problem in problems:
        print(f"注意：{problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
