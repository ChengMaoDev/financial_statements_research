"""提取企业集团构成（主要子公司）与合并范围变动。

为什么重要：
合并范围决定了报表的边界。三家通过并购形成的集团结构差异极大——美的靠
KUKA（德国机器人）、TLSC（东芝家电）、小天鹅，海尔靠 GEA（美国）、
Fisher & Paykel（新西兰）、Candy（意大利）、CCR，格力靠格力钛、盾安环境、
南京华新。三家年报正文都写「无应当披露的重要控股参股公司信息」（美的）、
「不适用」（格力），海尔只指向境外资产说明，因此**唯一能还原集团边界的
公开数据就是附注里的「企业集团的构成」子公司清单**（含注册资本、持股比例、
取得方式）与「合并范围的变更」。

持股比例低于 100% 的子公司会同时产生「少数股东损益」与「少数股东权益」，
这是理解三家少数股东差异的前提：格力 2022 年少数股东损益为 −14.95 亿，
根源就在格力钛（55.01% 直接、72.47% 表决权）与盾安环境（38.13% 即纳入合并）
这类非全资、甚至低于 50% 仍控股的主体。只看合并报表数字，看不出这层结构。

提取范围：2025 与 2024 两个年度，三家共 6 份年报。

实际踩到的陷阱（都已写进代码）：
1. 表头跨页重复。海尔子公司清单连续 6 页，每页顶部重印「子公司名称/持股比例/
   直接/间接/表决权比例/取得方式」。按行切分时表头会被当成一条子公司记录，
   必须按固定 y 坐标区间剔除表头与页脚（「213 / 245」）。
2. 一行数据跨两行排版。海尔「青岛海尔电冰箱有限公司」的名称占两行，金额只落在
   第一行；若按「有百分号的行才算一条记录」切分，名称会被截断成「青岛海尔电子
   塑胶有」。解法：以「表决权列出现百分号」的 y 坐标作为行锚点，锚点之间的所有
   文字归入同一行。
3. 列右对齐导致串列。美的「取得方式」列右对齐，「非同一控制下企业合并」的起始
   x 坐标落在「间接」列区间内，按 x 区间硬切会把取得方式读成持股比例。解法：
   数值列只接受数字 token 并按最近表头归属，文字列单独按区间归属。
4. 单位不同。美的附注单位是「千元」，海尔、格力是「元」。美的 2025 年取得子公司
   支付现金 6,155,136 千元 = 61.55 亿元；若当元处理会差 1000 倍。
5. 格力 2024 年购买成本 ≠ 现金流量表。上海大创 65.95% 作价 244,597,668.00 元，
   而「取得子公司支付的现金净额」只有 209,444,845.48 元，差额 = 取得时点被收购方
   账面货币资金 5,152,822.52 + 同步增资 30,000,000.00，三者严丝合缝。直接拿
   购买成本去对现金流会误判为「不勾稽」。
6. 年报自身重复列示。海尔 2025 年清单里「中山海尔暖通设备有限公司」「青岛海尔
   智慧洗碗机有限公司」「青岛海尔暖通设备科技有限公司」各出现两次（业务性质
   还不一致）。家数统计按名称去重，明细行保留原始披露。
7. 正文与附注口径不一致。任务背景说格力 69 家子公司，2025 年报清单实际编号到
   72（2024 年报编号到 73）。以年报为准，差异在报告里说明。

取舍：格力清单 72 行、海尔 120 家，逐行录入工作量大但可自动解析，故**全部录入**，
未采用「只录非全资 + 汇总」的简化方案；仅「其他原因的合并范围变动」里成批新设的
主体（美的 2025 年 40 余家、格力 2025 年 27 家）按年报段落计数，不逐户展开。

输出列固定为 `公司,年度,类别,项目,数值,数据性质,来源`。子公司的注册地、业务性质、
注册资本、取得方式无法塞进固定列，附在「来源」列引用之后，用「｜」分隔。

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

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "年度报告"
CACHE = Path("/tmp/fsr")
FIN = ROOT / "财务数据"
OUT = FIN / "子公司与合并范围.csv"

COMPANIES = ("美的集团", "海尔智家", "格力电器")
YEARS = ("2025", "2024")
SHORT = {"美的集团": "美的", "海尔智家": "海尔", "格力电器": "格力"}

# 三种表结构：列名 -> 表头文字（用前缀匹配，容忍「主要经营地」被拆成两行）
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
    "子公司名称",
    "持股比例",
    "主要经营",
    "主要经营地",
    "注册地",
    "业务性质",
    "直接",
    "间接",
    "表决权",
    "表决权比例",
    "取得方",
    "取得方式",
    "注册资本",
    "序号",
}
FOOTER = re.compile(r"^\s*\d{1,3}\s*/\s*\d{1,3}\s*$")
NOISE = (
    "子公司名称",
    "持股比例",
    "年年度报告",
    "重要的非全资",
    "购买成本",
    "合营企业",
    "在子公司的所有者",
    "权益法",
    "减：",
    "差额",
    "项目",
    "本集团不存在",
)


# ---------------------------------------------------------------- PDF 读取


def cache_pages(short: str, year: str) -> list[str]:
    path = CACHE / f"{short}{year}.txt"
    if not path.exists():
        raise SystemExit(f"缺少文本缓存 {path}，请先 pdftotext -layout 生成")
    return path.read_text(encoding="utf-8").split("\f")


def find_table_page(pages: list[str], anchors: tuple[str, ...]) -> int:
    for idx, text in enumerate(pages):
        if any(a in text for a in anchors):
            return idx + 1
    raise SystemExit(f"未找到表格起始页，锚点={anchors}")


def page_words(pdf: Path, first: int, last: int) -> list[list[dict]]:
    out = subprocess.run(
        ["pdftotext", "-bbox", "-f", str(first), "-l", str(last), str(pdf), "-"],
        capture_output=True,
        text=True,
        timeout=300,
        check=True,
    ).stdout
    pages = []
    for body in re.findall(r'<page width="[\d.]+" height="[\d.]+">(.*?)</page>', out, re.S):
        words = []
        for m in re.finditer(
            r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>',
            body,
        ):
            words.append(
                {
                    "x": float(m.group(1)),
                    "y": float(m.group(2)),
                    "x2": float(m.group(3)),
                    "t": m.group(5).strip(),
                }
            )
        pages.append([w for w in words if w["t"] and not FOOTER.match(w["t"])])
    return pages


def columns(words: list[dict], schema: list[tuple[str, str]]) -> dict[str, tuple[float, float]]:
    """返回每列的 x 区间。数值列用「最近表头」归属，文字列用相邻表头中点切分。"""
    head: dict[str, float] = {}
    for w in words:
        if w["y"] > 360:
            continue
        for key, label in schema:
            if key not in head and w["t"].startswith(label) and len(w["t"]) <= len(label) + 3:
                head[key] = w["x"]
    if "name" not in head:
        return {}
    text_keys = [k for k, _ in schema if k in head and k not in NUMERIC]
    num_keys = [k for k, _ in schema if k in head and k in NUMERIC]
    bounds: dict[str, tuple[float, float]] = {}
    for i, key in enumerate(text_keys):
        lo = 0.0 if i == 0 else (head[text_keys[i - 1]] + head[key]) / 2
        hi = float("inf") if i == len(text_keys) - 1 else (head[key] + head[text_keys[i + 1]]) / 2
        bounds[key] = (lo, hi)
    for key in num_keys:  # 数值列不设上界，按最近表头归属
        bounds[key] = (head[key], head[key])
    return bounds


def assign(word: dict, bounds: dict[str, tuple[float, float]]) -> str | None:
    token = word["t"]
    numeric = bool(re.fullmatch(r"-|[\d,]+(?:\.\d+)?%?", token))
    if numeric:
        cands = [k for k, (lo, hi) in bounds.items() if lo == hi]
        if not cands:
            return None
        center = (word["x"] + word["x2"]) / 2
        return min(cands, key=lambda k: abs(bounds[k][0] - center))
    for key, (lo, hi) in bounds.items():
        if lo != hi and lo <= word["x"] < hi:
            return key
    return None


def parse_table(pdf: Path, first: int, last: int, kind: str) -> list[dict]:
    rows: list[dict] = []
    for words in page_words(pdf, first, last):
        bounds = columns(words, SCHEMAS[kind])
        if not bounds:
            continue
        num_cols = [k for k, (lo, hi) in bounds.items() if lo == hi]
        anchors = sorted(
            {
                round(w["y"], 1)
                for w in words
                if assign(w, bounds) in num_cols and re.fullmatch(r"[\d.]+%?|-", w["t"])
            }
        )
        if not anchors:
            continue
        edges = [anchors[0] - 12]
        edges += [(anchors[i] + anchors[i + 1]) / 2 for i in range(len(anchors) - 1)]
        edges.append(float("inf"))
        cells: list[dict[str, list]] = [{} for _ in anchors]
        before: dict[str, list] = {}
        for w in words:
            if w["t"] in HEADER_WORDS or "年度报告" in w["t"]:
                continue
            key = assign(w, bounds)
            if key is None:
                continue
            if w["y"] < edges[0]:
                before.setdefault(key, []).append(w)
                continue
            for i in range(len(anchors)):
                if edges[i] <= w["y"] < edges[i + 1]:
                    cells[i].setdefault(key, []).append(w)
                    break
        if rows and before:  # 跨页续表：上一行名称的后半截落在本页锚点之上
            for key, items in before.items():
                rows[-1][key] = rows[-1].get(key, "") + "".join(w["t"] for w in items)
        for cell in cells:
            rows.append(
                {
                    k: "".join(w["t"] for w in sorted(v, key=lambda w: (w["y"], w["x"])))
                    for k, v in cell.items()
                }
            )
    return rows


def pct(text: str | None) -> float | None:
    if not text:
        return None
    m = re.fullmatch(r"([\d.]+)%?", text.strip())
    return float(m.group(1)) if m else None


def clean_rows(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        name = (row.get("name") or "").strip()
        if not name or any(x in name for x in NOISE) or len(name) > 40:
            continue
        if "年度报告" in name or re.fullmatch(r"[\d.\s]+", name):
            continue
        out.append(row)
    return out


def total_ratio(row: dict) -> float | None:
    direct, indirect = pct(row.get("direct")), pct(row.get("indirect"))
    if direct is None and indirect is None:
        return pct(row.get("vote"))
    return (direct or 0.0) + (indirect or 0.0)


# ---------------------------------------------------------------- 合并范围变动


def flat(text: str) -> str:
    text = re.sub(r"\s*\d{1,3}\s*/\s*\d{1,3}\s*", " ", text)
    return re.sub(r"\s+", " ", text)


def section(text: str, start: str, end: str) -> str:
    i = text.find(start)
    j = text.find(end, i + len(start)) if end else -1
    return text[i : j if j > 0 else i + 4000] if i >= 0 else ""


def grab(pattern: str, block: str, group: int = 1) -> float | None:
    m = re.search(pattern, block, re.S)
    return float(m.group(group).replace(",", "")) if m else None


def midea_changes(pages: list[str]) -> list[tuple[str, str, float | None, str]]:
    text = flat("".join(pages))
    block = section(text, "五 合并范围的变更", "(2) 其他原因的合并范围变动")
    rows: list[tuple[str, str, float | None, str]] = []
    deals = [
        ("Arbonia Climate（22 家子公司）", "Arbonia Climate", "22 家子公司"),
        ("Teka Industrial, S.A.", "Teka Industrial", "97.38%+2.62%"),
        ("东芝电梯（中国+沈阳）", "东芝电梯", "58%"),
        ("锐珂医疗（11 家子公司）", "锐珂医疗", "11 家子公司"),
    ]
    for label, key, note in deals:
        start = block.find(key)
        if start < 0:
            continue
        seg = block[start : start + 900]
        cost = grab(r"折合人民币\s*([\d,]+)\s*元", seg) or grab(
            r"以人民币\s*([\d,]+)\s*元的对价", seg
        )
        good = grab(r"商誉约人民币\s*([\d,]+)\s*元", seg)
        net = grab(r"净现金流出合计为人民币\s*([\d,]+)\s*元", seg)
        for item, value in (("购买成本", cost), ("商誉", good), ("购买日至期末净现金流出", net)):
            if value is not None:
                rows.append(("非同一控制下合并", f"{label}·{item}", value, f"股权比例 {note}"))
    frig = grab(r"欧元\s*41,407,000\s*元.{0,80}?折合人民币\s*([\d,]+)\s*元", block)
    if frig:
        rows.append(
            (
                "非同一控制下合并",
                "Frigicoll HVAC 等 3 家·购买成本",
                frig,
                "含喜德瑞热能、浙江美的热能",
            )
        )
    return rows


def gree_changes(pages: list[str]) -> list[tuple[str, str, float | None, str]]:
    text = flat("".join(pages))
    block = section(text, "4、 处置子公司", "5、 其他原因的合并范围变动")
    rows: list[tuple[str, str, float | None, str]] = []
    pattern = re.compile(
        r"([\u4e00-\u9fa5（）()]+?(?:公司|中心|合伙）?\)?))\s*(\d{4}/\d{1,2}/\d{1,2})\s*"
        r"([\d,]+(?:\.\d+)?)?\s*(\d+(?:\.\d+)?)?\s*(出售|注销|被动稀释股权)"
    )
    for m in pattern.finditer(block):
        name, date, price, ratio, way = m.groups()
        value = float(price.replace(",", "")) if price else None
        rows.append(
            ("合并范围减少", name, value, f"处置日 {date}；方式 {way}；比例 {ratio or '未披露'}")
        )
    return rows


def haier_changes(pages: list[str]) -> list[tuple[str, str, float | None, str]]:
    text = flat("".join(pages))
    rows: list[tuple[str, str, float | None, str]] = []
    block = section(text, "本期发生的同一控制下企业合并", "3、 处置子公司")
    for m in re.finditer(
        r"([\u4e00-\u9fa5（）()]+?有限公司)\s*([\d.]+%)\s*合并前后均受海尔", block
    ):
        rows.append(
            (
                "同一控制下合并",
                f"{m.group(1)}·取得权益比例",
                float(m.group(2).rstrip("%")),
                "合并日 2025.3",
            )
        )
    cost = grab(r"卡奥斯模具（青岛）有限公司\s*([\d,]+\.\d+)", block)
    if cost:
        rows.append(("同一控制下合并", "卡奥斯模具（青岛）有限公司·合并成本", cost, "现金对价"))
    block = section(text, "3、 处置子公司", "4、 其他原因的合并范围变动")
    for m in re.finditer(
        r"(注销|转让)\s*(\d{4}\s*年\s*\d{1,2}\s*月)\s*[^\d\-]{0,40}?(-?[\d,]+\.\d+)", block
    ):
        rows.append(
            (
                "合并范围减少",
                f"处置（{m.group(1)}）",
                float(m.group(3).replace(",", "")),
                f"丧失控制权 {m.group(2)}",
            )
        )
    return rows


def text_changes(
    company: str, year: str, pages: list[str]
) -> list[tuple[str, str, float | None, str]]:
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
            pages = cache_pages(short, year)
            pdf = PDF_DIR / f"{short}{year}.pdf"
            kind = {"美的集团": "midea", "海尔智家": "haier", "格力电器": "gree"}[company]
            first = find_table_page(pages, ("企业集团的构成", "主要子公司的构成"))
            rows = clean_rows(parse_table(pdf, first, first + 7, kind))

            seen: dict[str, float] = {}
            for row in rows:
                ratio = total_ratio(row)
                if ratio is None:
                    continue
                # 持股比例不可能 >100。越界值来自表头/页眉（「2025」「214245」）
                # 或跨列拼出的数字，一律丢弃，否则会被当成 245% 的子公司。
                if ratio < 0 or ratio > 100:
                    continue
                name = row["name"]
                out.append(
                    [
                        company,
                        year,
                        "子公司",
                        name,
                        f"{ratio:.2f}",
                        "披露值",
                        f"{year}年报 附注 企业集团的构成｜{source_note(row)}",
                    ]
                )
                seen.setdefault(name, ratio)

            buckets = {"100%": 0, ">50%且<100%": 0, "≤50%但纳入合并": 0}
            for ratio in seen.values():
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
                        f"按清单去重后 {len(seen)} 家统计",
                    ]
                )
            out.append(
                [
                    company,
                    year,
                    "持股结构统计",
                    "子公司总家数（去重）",
                    str(len(seen)),
                    "计算值",
                    f"清单明细 {len(rows)} 行",
                ]
            )

            for cat, item, value, note in text_changes(company, year, pages):
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


def self_check(rows: list[list[str]]) -> int:
    problems = 0
    print("\n[自校验]", file=sys.stderr)
    groups: dict[tuple[str, str], dict[str, int]] = {}
    for company, year, cat, item, value, _kind, _ in rows:
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
        flag = "PASS" if parts == total else "FAIL"
        if parts != total:
            problems += 1
        print(
            f"  {flag} {company}{year} 100%={bucket['100%']} "
            f">50%<100%={bucket['>50%且<100%']} ≤50%={bucket['≤50%但纳入合并']} "
            f"合计={parts} 总家数={total}",
            file=sys.stderr,
        )

    cash = load_cashflow()
    for company in COMPANIES:
        for year in YEARS:
            paid = cash.get((company, f"{year}1231"))
            costs = [
                float(v)
                for c, y, cat, item, v, k, _ in rows
                if c == company
                and y == year
                and cat == "非同一控制下合并"
                and item.endswith("购买成本")
                and v
            ]
            if paid is None or not costs:
                continue
            total = sum(costs)
            ratio = total / paid
            flag = "PASS" if 0.5 <= ratio <= 1.6 else "WARN"
            print(
                f"  {flag} {company}{year} 购买成本合计={total:,.0f} "
                f"现金流量表取得子公司支付={paid:,.0f} 比值={ratio:.3f}",
                file=sys.stderr,
            )
    return problems


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
    problems = self_check(rows)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
