"""净利润 → 经营现金流的调节表：利润里有多少是真现金。

为什么重要：
三家 2025 年经营现金流都高于净利润，但**来源完全不同**：

| 公司 | 净利润 | 经营现金流 | 差额 | 差额主因 |
|---|---|---|---|---|
| 美的 | 445.20 亿 | 533.46 亿 | +88.26 亿 | 经营性应付 +113.17 亿（占款） |
| 海尔 | 201.63 亿 | 260.03 亿 | +58.40 亿 | 折旧摊销 87.50 亿 |
| 格力 | 288.63 亿 | 463.83 亿 | +175.20 亿 | **「其他」+170.92 亿** |

格力的「其他」170.92 亿，年报注明其中**票据保证金净减少 156.67 亿**。这是客户
承兑汇票保证金到期释放，属于**一次性**的营运资金回流，不是经营改善。剔除后格力
经营现金流约 307 亿，仍高于净利润，但差额从 175 亿降到 19 亿。

三个陷阱：

1. **美的是「千元」，海尔/格力是「元」**，且美的这张表在附注四(64)(h)，
   标题写作「将净利润调节为经营活动现金流量如下」，不带编号。
2. **符号约定相同但方向词相反**：三家都印成「加：XXX」，数字直接相加即可。
   但海尔/格力在标签里写「损失（收益以"－"号填列）」，美的写「资产处置损失/(收益)」，
   同一含义三种写法。**不要按标签猜正负，直接按印刷值相加**。
3. **格力的调节表「其他」是最大单项**（170.92 亿），且年报只在表格下方用一行
   小字注释拆出「法定存款准备金净增加 0.35 亿、票据保证金等净减少 156.67 亿、
   股份支付 14.60 亿」。不读注释会误以为这是经营现金流的质量。

**折旧摊销口径也不同**：美的把折旧、无形资产摊销、长期待摊费用合成一行
「折旧和摊销」93.40 亿；海尔拆成四行（固定资产 53.02、使用权 17.81、
无形 14.13、长期待摊 2.54）合计 87.50 亿；格力合成两行（固定资产+投资性房地产+
使用权 46.07、无形 4.48）合计 50.55 亿。

用法：
    uv run python3 scripts/extract_cash_reconciliation.py --all
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
OUT = FIN / "净利润调节经营现金流.csv"

COMPANY_OF = {
    "美的集团": ("美的2025.pdf", 1_000, "将净利润调节为经营活动现金流量如下"),
    "海尔智家": ("海尔2025.pdf", 1, "将净利润调节为经营活动现金流量"),
    "格力电器": ("格力2025.pdf", 1, "将净利润调节为经营活动现金"),
}

# 统一项目名。顺序即输出顺序，与报表顺序一致。
NORMALIZE = [
    ("净利润", "净利润"),
    ("资产减值", "资产及信用减值"),
    ("信用减值", "资产及信用减值"),
    ("折旧", "折旧与摊销"),
    ("使用权资产摊销", "折旧与摊销"),
    ("无形资产摊销", "折旧与摊销"),
    ("长期待摊费用摊销", "折旧与摊销"),
    # 「处置固定资产」不含「资产处置」三个字，必须单列；否则会掉进「其他」
    ("处置固定资产", "资产处置与报废"),
    ("资产处置", "资产处置与报废"),
    ("非流动资产报废", "资产处置与报废"),
    ("公允价值变动", "公允价值变动"),
    ("财务收入", "财务费用/收入"),
    ("财务费用", "财务费用/收入"),
    ("投资收益", "投资收益"),
    ("投资损失", "投资收益"),
    ("递延所得税资产", "递延所得税"),
    ("递延所得税负债", "递延所得税"),
    ("存货的减少", "存货变动"),
    ("经营性应收", "经营性应收变动"),
    ("经营性应付", "经营性应付变动"),
    ("股份支付", "股份支付及其他"),
    ("其他", "股份支付及其他"),
    ("经营活动产生的现金流量净额", "STOP"),
]

# 这些行需要累加（折旧四行、减值两行、递延税两行）
ACCUMULATE = {"资产及信用减值", "折旧与摊销", "递延所得税", "资产处置与报废"}

NUMBER = r"\(?-?[\d,]+(?:\.\d+)?\)?"
TOKEN = re.compile(rf"^{NUMBER}$")
SPLIT = re.compile(r"\s{2,}")


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


def block(text: str, title: str) -> list[str]:
    target = re.sub(r"\s+", "", title)
    lines = text.splitlines()
    # 标题带序号（`1．将净利润调节为…`）或折行，用包含匹配
    start = next(
        (i for i, line in enumerate(lines) if target in re.sub(r"\s+", "", line)),
        None,
    )
    return lines[start : start + 60] if start is not None else []


# 标签里的方向说明（`损失（收益以"－"号填列）`）和跨行残片（`列）`）要先清掉，
# 否则会粘到下一项开头，让两项都匹配不上。
NOISE = re.compile(r"[（(][^（()）]*(?:填列|号填)[^（()）]*[）)]|号填列[）)]?|[）)]$|列[）)]?$")


def clean(label: str) -> str:
    s = re.sub(r"\s+", "", label)
    s = re.sub(r"【[^】]*】", "", s)
    for _ in range(3):
        s = NOISE.sub("", s)
    return s


def unified(label: str) -> str | None:
    raw = re.sub(r"\s+", "", label)
    s = clean(raw)
    for key, name in NORMALIZE:
        if key == "其他":
            # 「其他」是兜底词，只认整行，否则会吞掉「处置固定资产、无形资产和其他长期资产」
            if s.endswith("其他"):
                return name
            continue
        if key in s:
            return name
    return None


def parse(lines: list[str], factor: float) -> tuple[dict[str, tuple[float, float]], float | None]:
    """返回 ({项目: (本期, 上期)}, 表内经营现金流净额)，单位元。"""
    out: dict[str, tuple[float, float]] = {}
    pending = ""
    stated: float | None = None
    for raw in lines:
        parts = [p for p in SPLIT.split(raw.strip()) if p]
        if not parts:
            continue
        values: list[str] = []
        while parts and TOKEN.match(parts[-1]):
            values.insert(0, parts.pop())
        label = "".join(parts)
        if label:
            pending += label
        if not values:
            continue
        if len(values) == 1 and len(values[0]) <= 3:
            continue

        name = unified(pending)
        pending = ""
        if name is None:
            continue
        if name == "STOP":
            stated = number(values[0]) * factor
            break
        current = number(values[0]) * factor
        previous = number(values[1]) * factor if len(values) > 1 else 0.0
        if name in ACCUMULATE and name in out:
            before = out[name]
            out[name] = (before[0] + current, before[1] + previous)
        else:
            out.setdefault(name, (current, previous))
    return out, stated


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
    problems: list[str] = []
    summary: list[list[str]] = []

    for company, (filename, factor, title) in COMPANY_OF.items():
        data, stated = parse(block(pdf_text(PDF_DIR / filename), title), factor)
        if not data:
            problems.append(f"{company} 未匹配")
            continue

        notes: list[list[str]] = []
        for year_index, year in enumerate(("2025", "2024")):
            net = data.get("净利润", (0.0, 0.0))[year_index]
            items = {k: v[year_index] for k, v in data.items() if k != "净利润"}
            total = sum(items.values())
            recomputed = net + total
            if stated is not None and year_index == 0:
                gap = recomputed - stated
                if abs(gap) > 1e5:
                    problems.append(
                        f"{company} 2025 调节合计 {recomputed / 1e8:.2f} ≠ 表内 {stated / 1e8:.2f}"
                    )
            rows.append(
                [
                    company,
                    year,
                    "净利润",
                    f"{net / 1e8:.2f}",
                    f"{net / net * 100:.2f}",
                    "起点",
                    "披露值",
                ]
            )
            for name, value in items.items():
                rows.append(
                    [
                        company,
                        year,
                        name,
                        f"{value / 1e8:.2f}",
                        f"{value / net * 100:.2f}" if net else "",
                        "加项" if value >= 0 else "减项",
                        "披露值",
                    ]
                )
            rows.append(
                [
                    company,
                    year,
                    "经营活动现金流量净额",
                    f"{recomputed / 1e8:.2f}",
                    f"{recomputed / net * 100:.2f}" if net else "",
                    "合计",
                    "计算值",
                ]
            )
            if year_index == 0:
                summary.append([company, net / 1e8, items, recomputed / 1e8])

            if company == "格力电器" and year == "2025":
                # 「其他」170.92 亿的构成只在表下注释里（格力 2025 年报第 178 页）
                notes = [
                    [
                        company,
                        year,
                        "其中：票据保证金等净减少",
                        "156.67",
                        "54.28",
                        "加项",
                        "披露值",
                    ],
                    [
                        company,
                        year,
                        "其中：股份支付费用",
                        "14.60",
                        "5.06",
                        "加项",
                        "披露值",
                    ],
                    [
                        company,
                        year,
                        "其中：法定存款准备金净增加",
                        "0.35",
                        "0.12",
                        "加项",
                        "披露值",
                    ],
                    [
                        company,
                        year,
                        "注释未解释的差额",
                        "-0.70",
                        "-0.24",
                        "减项",
                        "计算值",
                    ],
                    [
                        company,
                        year,
                        "剔除票据保证金后的经营现金流",
                        "307.16",
                        "106.42",
                        "计算值",
                        "计算值",
                    ],
                ]
            # 注释行插在 2025 年区块的末尾、2024 年区块之前。
            # 写入后必须清空，否则下一轮（2024）会把这批注释放进 2025 区块，
            # 造成 5 个键重复出现两次（曾实际发生）。
            if notes:
                rows.extend(notes)
                notes = []

    fields = ["公司", "年度", "项目", "金额(亿元)", "占净利润%", "方向", "数据性质"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    print(
        f"\n{'公司':<8}{'净利润':>10}{'折旧摊销':>10}{'应付变动':>10}{'其他':>10}{'经营现金流':>12}{'现金/利润':>10}"
    )
    print("-" * 74)
    for company, net, items, total in summary:
        print(
            f"{company:<8}{net:>10.2f}{items.get('折旧与摊销', 0) / 1e8:>10.2f}"
            f"{items.get('经营性应付变动', 0) / 1e8:>10.2f}"
            f"{items.get('股份支付及其他', 0) / 1e8:>10.2f}"
            f"{total:>12.2f}{total / net:>10.2f}"
        )

    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    for problem in problems:
        print(f"注意：{problem}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
