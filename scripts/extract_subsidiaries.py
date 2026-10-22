"""提取企业集团构成（主要子公司）与合并范围变动。

为什么重要：
合并范围决定了报表的边界。三家通过并购形成的集团结构差异极大——美的靠
KUKA（德国机器人）、TLSC（东芝家电）、小天鹅；海尔靠 GEA（美国）、
Fisher & Paykel（新西兰）、Candy（意大利）、CCR；格力靠格力钛、盾安环境、
南京华新。三家年报正文都写「无应当披露的重要控股参股公司信息」（美的）、
「不适用」（格力），海尔只指向境外资产说明，因此**唯一能还原集团边界的公开
数据就是附注里的「企业集团的构成」子公司清单**（含注册资本、持股比例、取得
方式）与「合并范围的变更」。

持股比例低于 100% 的子公司会同时产生「少数股东损益」与「少数股东权益」，这
是理解三家少数股东差异的前提：格力 2022 年少数股东损益 −14.95 亿，根源就在
格力钛（直接 55.01%、表决权 72.47%）与盾安环境（直接 38.13% 即纳入合并）这
类非全资、甚至低于 50% 仍控股的主体。只看合并报表数字看不出这层结构。

提取范围：2025 与 2024 两个年度，三家共 6 份年报。

实际踩到的陷阱（都已写进代码）：
1. 表头跨页重复。海尔子公司清单连续 6 页，每页顶部重印「子公司名称/持股比例/
   直接/间接/表决权比例/取得方式」。按行切分时表头会变成一条子公司记录，必须
   先定位「子公司名称」表头的 y 坐标，只取该 y 以下的数据区。
2. 一行数据跨两行排版。海尔「青岛海尔电子塑胶有限公司」的名称占两行、金额只落
   在第一行；若按「有百分号的行才算一条记录」切分，名称会被截断成「青岛海尔电
   子塑胶有」。解法：以数值列出现百分号的 y 坐标做行锚点，锚点之间的文字归入
   同一行；跨页续表则把上一行名称与本页锚点之上的残片拼接。
3. 列右对齐导致串列。美的「取得方式」列右对齐，「非同一控制下企业合并」的起始
   x 落在「间接」列区间内，按 x 区间硬切会把取得方式读成持股比例（34 行里错 20
   行）。解法：数值列只接受数字 token 并按最近表头归属，文字列按左边界归属。
4. 单位不同。美的附注单位是「千元」，海尔、格力是「元」。美的 2025 年取得子公司
   支付现金 6,155,136 千元 = 61.55 亿元；当元处理会差 1000 倍。
5. 格力 2024 年购买成本 ≠ 现金流量表。上海大创 65.95% 作价 244,597,668.00 元，
   而「取得子公司支付的现金净额」只有 209,444,845.48 元。差额 35,152,822.52 元
   = 被收购方购买日账面货币资金 5,152,822.52 + 同步增资 30,000,000.00，三者严
   丝合缝。直接拿购买成本去对现金流会误判成「不勾稽」。
6. 年报自身重复列示。海尔 2025 年清单里「中山海尔暖通设备有限公司」「青岛海尔智
   慧洗碗机有限公司」「青岛海尔暖通设备科技有限公司」各出现两次，业务性质还不
   一致。家数统计按名称去重，明细行保留原始披露。
7. 编号与家数不一致。任务背景说格力 69 家，2025 年报清单实际编号到 72、2024 年
   到 73。以年报为准；差异来自 2025 年注销的珠海格力信息科技（2024 年第 40 号）
   与新增主体。

取舍：格力清单 72/73 行、海尔 120 余家，逐行录入工作量大但可自动解析，故**全部
录入**，未采用「只录非全资 + 汇总」的简化方案；只有「其他原因的合并范围变动」里
成批新设的主体（美的 2025 年 40 余家、格力 2025 年 27 家）按年报段落计数，不逐户
展开——这些主体当年即并表、无购买成本，逐户列示对分析集团边界没有增量信息。

输出列固定为 `公司,年度,类别,项目,数值,数据性质,来源`。子公司的注册地、业务性质、
注册资本、取得方式塞不进固定列，附在「来源」列里用「｜」分隔。

用法：
    uv run python3 scripts/extract_subsidiaries.py --all
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path

from pdf_util import pdf_text

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "年度报告"
FIN = ROOT / "财务数据"
OUT = FIN / "子公司与合并范围.csv"

COMPANIES = ("美的集团", "海尔智家", "格力电器")
YEARS = ("2025", "2024")
SHORT = {"美的集团": "美的", "海尔智家": "海尔", "格力电器": "格力"}
KIND = {"美的集团": "midea", "海尔智家": "haier", "格力电器": "gree"}

# 三种表结构：内部列名 -> 表头文字（前缀匹配，容忍「主要经营地」被拆成两行）
SCHEMAS = {
    "midea": [
        ("name", "子公司名称"),
        ("biz", "主要经营地"),
        ("reg", "注册地"),
        ("nature", "业务性质"),
        ("direct", "直接"),
        ("indirect", "间接"),
        ("acq", "取得方式"),
    ],
    "haier": [
        ("name", "子公司名称"),
        ("biz", "主要经营"),
        ("reg", "注册地"),
        ("nature", "业务性质"),
        ("direct", "直接"),
        ("indirect", "间接"),
        ("vote", "表决权"),
        ("acq", "取得方"),
    ],
    "gree": [
        ("seq", "序号"),
        ("name", "子公司名称"),
        ("capital", "注册资本"),
        ("biz", "主要经营地"),
        ("reg", "注册地"),
        ("nature", "业务性质"),
        ("direct", "直接"),
        ("indirect", "间接"),
        ("vote", "表决权"),
        ("acq", "取得方式"),
    ],
}
NUMERIC = {"direct", "indirect", "vote", "capital", "seq"}
HEADER_WORDS = {
    "持股比例",
    "表决权比例",
    "子公司名称",
    "序号",
    "注册资本",
    "注册地",
    "业务性质",
    "取得方式",
    "取得方",
    "直接",
    "间接",
    "表决权",
    "主要经营地",
    "主要经营",
    "比例",
    "（%）",
    "(%)",
}
NOISE = (
    "主体中的权益",
    "子公司的构成",
    "合并范围的变更",
    "年度报告",
    "财务报表附注",
    "重要的非全资",
    "人民币千元",
    "金额单位",
    "【注】",
    "本公司",
    "合并范围",
    "在子公司",
)
STOP_PHRASES = ("重要的非全资", "合营或联营企业", "购买成本/处置对价")
NOT_A_SUB = ("权益法",)


def is_noise(text: str) -> bool:
    return text in HEADER_WORDS or any(n in text for n in NOISE)


# ---------------------------------------------------------------- PDF 表格


def page_words(pdf: Path, first: int, last: int) -> list[tuple[float, list[dict]]]:
    """逐页返回 (页高, 词表)。用 -bbox 拿坐标，因为纯文本已经串列。"""
    out = subprocess.run(
        ["pdftotext", "-bbox", "-f", str(first), "-l", str(last), str(pdf), "-"],
        capture_output=True,
        text=True,
        timeout=300,
        check=True,
    ).stdout
    pages = []
    for m in re.finditer(r'<page width="[\d.]+" height="([\d.]+)">(.*?)</page>', out, re.S):
        height, body = float(m.group(1)), m.group(2)
        words = []
        for w in re.finditer(
            r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>',
            body,
        ):
            text = w.group(5).strip()
            if text:
                words.append(
                    {
                        "x": float(w.group(1)),
                        "y": float(w.group(2)),
                        "x2": float(w.group(3)),
                        "t": text,
                    }
                )
        pages.append((height, words))
    return pages


def header_positions(words: list[dict], schema: list[tuple[str, str]]) -> dict[str, float]:
    """以「子公司名称」表头的 y 为锚，取 ±40pt 内的列名 x 坐标。

    返回 (列名 → x 坐标, 表头行的 y 坐标)。表头的 y 必须单独返回：
    页面是横向的（美的 841.92 × 595.32），列名 x 最大到 729，
    若拿 max(列 x) 当表头 y，会得到 731 > 页高，整页被判定为「表头之上的内容」。
    """
    anchors = [w["y"] for w in words if w["t"] == "子公司名称"]
    if not anchors:
        return {}, None
    y0 = min(anchors)
    pos: dict[str, float] = {}
    for w in words:
        if not y0 - 40 <= w["y"] <= y0 + 40:
            continue
        for key, label in schema:
            if key not in pos and w["t"].startswith(label) and len(w["t"]) <= len(label) + 3:
                pos[key] = w["x"]
    return pos, y0


def assign(word: dict, pos: dict[str, float]) -> str | None:
    """数字按最近表头（右对齐）归属，文字按最近左边界归属。"""
    center = (word["x"] + word["x2"]) / 2
    numbers = {k: v for k, v in pos.items() if k in NUMERIC}
    texts = {k: v for k, v in pos.items() if k not in NUMERIC}
    if re.fullmatch(r"-|[\d,]+(?:\.\d+)?%?", word["t"]):
        return min(numbers, key=lambda k: abs(numbers[k] - center)) if numbers else None
    return min(texts, key=lambda k: abs(texts[k] - word["x"])) if texts else None


def join(words: list[dict]) -> str:
    out = ""
    for w in sorted(words, key=lambda w: (w["y"], w["x"])):
        if out and re.search(r"[A-Za-z0-9]$", out) and re.match(r"[A-Za-z0-9(]", w["t"]):
            out += " "
        out += w["t"]
    return out


def parse_table(pdf: Path, first: int, last: int, kind: str) -> list[dict]:
    schema = SCHEMAS[kind]
    rows: list[dict] = []
    for height, words in page_words(pdf, first, last):
        pos, header_y = header_positions(words, schema)
        if "name" not in pos or header_y is None:
            continue
        top = header_y + 2
        body = [w for w in words if top < w["y"] < height - 40 and not is_noise(w["t"])]
        if "seq" in pos:
            raw = [
                w["y"]
                for w in body
                if abs(w["x"] - pos["seq"]) < 10 and re.fullmatch(r"\d{1,2}", w["t"])
            ]
        else:
            raw = [
                w["y"]
                for w in body
                if re.fullmatch(r"[\d.]+%", w["t"]) and assign(w, pos) in NUMERIC
            ]
        anchors: list[float] = []
        for y in sorted(raw):
            if not anchors or y - anchors[-1] > 3:  # 同一行的「直接/间接」共用一个锚点
                anchors.append(y)
        if not anchors:
            continue
        edges = [anchors[0] - 11]
        edges += [(anchors[i] + anchors[i + 1]) / 2 for i in range(len(anchors) - 1)]
        edges.append(anchors[-1] + 9)
        cells: list[dict[str, list[dict]]] = [{} for _ in anchors]
        before: dict[str, list[dict]] = {}
        for w in body:
            key = assign(w, pos)
            if key is None:
                continue
            if w["y"] < edges[0]:
                before.setdefault(key, []).append(w)
                continue
            if w["y"] >= edges[-1]:
                continue
            for i in range(len(anchors)):
                if edges[i] <= w["y"] < edges[i + 1]:
                    cells[i].setdefault(key, []).append(w)
                    break
        if rows and before.get("name"):  # 跨页续表：接上被切断的名称
            rows[-1]["name"] = rows[-1].get("name", "") + join(before.pop("name"))
        for key, items in before.items():
            cells[0].setdefault(key, []).extend(items)
        for cell in cells:
            rows.append({k: join(v) for k, v in cell.items()})
    return rows


# ---------------------------------------------------------------- 数值清洗


def pct(text: str | None) -> float | None:
    if not text:
        return None
    m = re.fullmatch(r"([\d.]+)%?", text.strip())
    return float(m.group(1)) if m else None


def total_ratio(row: dict) -> float | None:
    """直接+间接。表格里用「-」表示该栏无持股，不能用 0 兜底（会变成「0%」）。"""
    direct, indirect = pct(row.get("direct")), pct(row.get("indirect"))
    if direct is None and indirect is None:
        return pct(row.get("vote"))
    return (direct or 0.0) + (indirect or 0.0)


def clean_rows(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        name = (row.get("name") or "").strip()
        if not name or len(name) > 40 or any(x in name for x in NOISE):
            continue
        if not re.search(r"[\u4e00-\u9fa5A-Za-z]", name):
            continue
        if any(x in (row.get("acq") or "") for x in NOT_A_SUB):  # 联营/合营企业不是子公司
            continue
        out.append(row)
    return out


def find_pages(short: str, year: str) -> tuple[int, int]:
    """定位「企业集团的构成」所在页，向后多取 6 页以覆盖跨页长表。"""
    for idx, page in enumerate(pdf_text(PDF_DIR / f"{short}{year}.pdf").split("\f")):
        if "企业集团的构成" in page or "主要子公司的构成" in page:
            return idx + 1, idx + 7
    raise SystemExit(f"{short}{year} 未找到「企业集团的构成」")


# ---------------------------------------------------------------- 合并范围变动


def flat(text: str) -> str:
    text = re.sub(r"\s*\d{1,3}\s*/\s*\d{1,3}\s*", " ", text)
    return re.sub(r"\s+", " ", text)


def between(text: str, start: str, end: str) -> str:
    i = text.find(start)
    if i < 0:
        return ""
    j = text.find(end, i + len(start))
    return text[i : j if j > 0 else i + 3000]


def money(pattern: str, block: str) -> float | None:
    m = re.search(pattern, block, re.S)
    return float(m.group(1).replace(",", "")) if m else None


def midea_changes(pages: list[str]) -> list[tuple[str, str, float | None, str]]:
    """美的：非同一控制下企业合并 4 笔 + 1 笔小收购，金额单位千元。"""
    text = flat("".join(pages))
    block = between(text, "五 合并范围的变更", "(2) 其他原因的合并范围变动")
    deals = [
        ("Arbonia Climate（22 家子公司）", "Arbonia Climate", "22 家子公司全部股权"),
        ("Teka Industrial, S.A.", "Teka Industrial", "97.38%+2.62%"),
        ("东芝电梯（中国+沈阳）", "东芝电梯", "58%"),
        ("锐珂医疗（11 家子公司）", "锐珂医疗", "11 家子公司全部股权"),
    ]
    rows: list[tuple[str, str, float | None, str]] = []
    for label, key, note in deals:
        seg = block[block.find(key) : block.find(key) + 900] if key in block else ""
        if not seg:
            continue
        cost = money(r"折合人民币\s*([\d,]+)\s*元", seg) or money(
            r"以人民币\s*([\d,]+)\s*元的对价", seg
        )
        rows.append(("非同一控制下合并", f"{label}·购买成本", cost, f"股权比例 {note}；单位千元"))
        good = money(r"商誉约人民币\s*([\d,]+)\s*元", seg)
        rows.append(("非同一控制下合并", f"{label}·商誉", good, "单位千元"))
        net = money(r"净现金流出合计为人民币\s*([\d,]+)\s*元", seg)
        rows.append(("非同一控制下合并", f"{label}·购买日至期末净现金流出", net, "单位千元"))
    small = money(r"欧元\s*41,407,000\s*元.{0,80}?折合人民币\s*([\d,]+)\s*元", block)
    rows.append(
        (
            "非同一控制下合并",
            "Frigicoll HVAC 等 3 家·购买成本",
            small,
            "含喜德瑞热能技术(浙江)、浙江美的热能技术；单位千元",
        )
    )
    return rows


def gree_changes(pages: list[str]) -> list[tuple[str, str, float | None, str]]:
    """格力：2025 年无非同一控制/同一控制合并；处置 3 家；新设 27 家。"""
    text = flat("".join(pages))
    rows: list[tuple[str, str, float | None, str]] = []
    for label, key in (
        ("非同一控制下合并", "1、 非同一控制下企业合并"),
        ("同一控制下合并", "2、 同一控制下企业合并"),
    ):
        seg = between(text, key, "3、 反向购买")
        rows.append(
            (
                label,
                "本期是否发生",
                0.0 if re.search(r"^\s*无。", seg) else None,
                "年报原文「无」" if re.search(r"^\s*无。", seg) else "未披露",
            )
        )
    block = between(text, "4、 处置子公司", "5、 其他原因的合并范围变动")
    for m in re.finditer(
        r"([\u4e00-\u9fa5（）()]+?(?:有限公司|股份有限公司))\s*(\d{4}/\d{1,2}/\d{1,2})\s*"
        r"([\d,]+(?:\.\d+)?)?\s*(\d+(?:\.\d+)?)?\s*(出售|注销|被动稀释股权)",
        block,
    ):
        name, date, price, ratio, way = m.groups()
        value = float(price.replace(",", "")) if price else None
        rows.append(
            (
                "合并范围减少",
                name,
                value,
                f"处置日 {date}；方式 {way}；比例 {ratio or '未披露'}%；金额单位元",
            )
        )
    return rows


def haier_changes(pages: list[str]) -> list[tuple[str, str, float | None, str]]:
    """海尔：2025 年同一控制下合并卡奥斯模具，处置 2 家注销主体。"""
    text = flat("".join(pages))
    rows: list[tuple[str, str, float | None, str]] = []
    block = between(text, "本期发生的同一控制下企业合并", "3、 处置子公司")
    for m in re.finditer(
        r"([\u4e00-\u9fa5（）()]+?有限公司)\s*([\d.]+)%\s*合并前后均受海尔", block
    ):
        rows.append(
            (
                "同一控制下合并",
                f"{m.group(1)}·取得权益比例",
                float(m.group(2)),
                "合并日 2025.3；表决权转让",
            )
        )
    cost = money(r"卡奥斯模具（青岛）有限公司\s*([\d,]+\.\d+)", block)
    rows.append(("同一控制下合并", "卡奥斯模具（青岛）有限公司·合并成本", cost, "现金对价；单位元"))
    block = between(text, "3、 处置子公司", "4、 其他原因的合并范围变动")
    for m in re.finditer(
        r"注销\s*(\d{4}\s*年\s*\d{1,2}\s*月)\s*[^\d\-]{0,30}?(-?[\d,]+\.\d+)", block
    ):
        rows.append(
            (
                "合并范围减少",
                "处置（注销）",
                float(m.group(2).replace(",", "")),
                f"丧失控制权 {m.group(1)}；金额为处置价款与净资产份额差额",
            )
        )
    return rows


def change_rows(company: str, pages: list[str]) -> list[tuple[str, str, float | None, str]]:
    if company == "美的集团":
        return midea_changes(pages)
    if company == "格力电器":
        return gree_changes(pages)
    return haier_changes(pages)


# ---------------------------------------------------------------- 主流程


def source_note(row: dict) -> str:
    parts = []
    for key, label in (
        ("reg", "注册地"),
        ("nature", "业务性质"),
        ("capital", "注册资本"),
        ("acq", "取得方式"),
    ):
        if row.get(key):
            parts.append(f"{label}={row[key]}")
    return "｜".join(parts)


def build() -> list[list[str]]:
    out: list[list[str]] = []
    for company in COMPANIES:
        short = SHORT[company]
        for year in YEARS:
            first, last = find_pages(short, year)
            pages = pdf_text(PDF_DIR / f"{short}{year}.pdf").split("\f")
            rows = clean_rows(
                parse_table(PDF_DIR / f"{short}{year}.pdf", first, last, KIND[company])
            )

            ratios: dict[str, float] = {}
            for row in rows:
                ratio = total_ratio(row)
                if ratio is None:
                    continue
                out.append(
                    [
                        company,
                        year,
                        "子公司",
                        row["name"],
                        f"{ratio:.2f}",
                        "披露值",
                        f"{year}年报 附注 企业集团的构成｜{source_note(row)}",
                    ]
                )
                ratios.setdefault(row["name"], ratio)

            buckets = {"100%": 0, ">50%且<100%": 0, "≤50%但纳入合并": 0}
            for ratio in ratios.values():
                if ratio >= 99.995:
                    buckets["100%"] += 1
                elif ratio > 50:
                    buckets[">50%且<100%"] += 1
                else:
                    buckets["≤50%但纳入合并"] += 1
            for label, count in buckets.items():
                out.append(
                    [
                        company,
                        year,
                        "持股结构统计",
                        label,
                        str(count),
                        "计算值",
                        f"清单 {len(rows)} 行去重后 {len(ratios)} 家",
                    ]
                )
            out.append(
                [
                    company,
                    year,
                    "持股结构统计",
                    "子公司总家数（去重）",
                    str(len(ratios)),
                    "计算值",
                    f"清单明细 {len(rows)} 行（含重复列示）",
                ]
            )

            for cat, item, value, note in change_rows(company, pages[first - 1 : last]):
                out.append(
                    [
                        company,
                        year,
                        cat,
                        item,
                        "" if value is None else f"{value:.2f}",
                        "披露值",
                        note,
                    ]
                )
    return out


def load_cashflow() -> dict[tuple[str, str], float]:
    path = FIN / "现金流量表.csv"
    result: dict[tuple[str, str], float] = {}
    if not path.exists():
        return result
    with path.open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["科目"] == "取得子公司及其他营业单位支付的现金净额":
                result[(row["公司"], row["报告期"])] = float(row["数值"])
    return result


def self_check(rows: list[list[str]]) -> int:
    problems = 0
    print("\n[自校验] 1) 持股区间家数相加 = 子公司总家数", file=sys.stderr)
    groups: dict[tuple[str, str], dict[str, int]] = {}
    for company, year, cat, item, value, _, _ in rows:
        if cat == "持股结构统计":
            groups.setdefault((company, year), {})[item] = int(value)
        if cat == "子公司":
            ratio = float(value)
            if not 0 <= ratio <= 100:
                print(f"  FAIL 持股比例越界 {company}{year} {item} {ratio}", file=sys.stderr)
                problems += 1
    for (company, year), bucket in sorted(groups.items()):
        total = bucket["子公司总家数（去重）"]
        parts = bucket["100%"] + bucket[">50%且<100%"] + bucket["≤50%但纳入合并"]
        ok = parts == total
        problems += 0 if ok else 1
        # 桶名含引号，f-string 里不能复用外层引号（py3.11 限制），先取出来
        full = bucket["100%"]
        partial = bucket[">50%且<100%"]
        control = bucket["≤50%但纳入合并"]
        flag = "PASS" if ok else "FAIL"
        print(
            f"  {flag} {company}{year} 100%={full} >50%<100%={partial} "
            f"≤50%={control} 合计={parts} 总家数={total}",
            file=sys.stderr,
        )

    print("  [2) 持股比例均在 0–100] 上面已逐行检查", file=sys.stderr)
    print("\n[自校验] 3) 购买成本 vs 现金流量表「取得子公司支付的现金净额」", file=sys.stderr)
    cash = load_cashflow()
    for company in COMPANIES:
        for year in YEARS:
            paid = cash.get((company, f"{year}1231"))
            costs = [
                float(v)
                for c, y, cat, item, v, _, _ in rows
                if c == company
                and y == year
                and cat == "非同一控制下合并"
                and item.endswith("购买成本")
                and v
            ]
            if paid is None or not costs:
                print(f"  SKIP {company}{year} 现金流量表无该项目或本期无收购", file=sys.stderr)
                continue
            total = sum(costs)
            ratio = total / paid
            ok = 0.5 <= ratio <= 1.6
            print(
                f"  {'PASS' if ok else 'WARN'} {company}{year} 购买成本合计={total:,.0f} "
                f"现金净额={paid:,.0f} 比值={ratio:.3f}",
                file=sys.stderr,
            )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="提取三家 2025/2024 全部数据")
    args = parser.parse_args()
    if not args.all:
        parser.print_help()
        return 0

    rows = build()
    fields = ["公司", "年度", "类别", "项目", "数值", "数据性质", "来源"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)
    print(f"写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    return 1 if self_check(rows) else 0


if __name__ == "__main__":
    sys.exit(main())
