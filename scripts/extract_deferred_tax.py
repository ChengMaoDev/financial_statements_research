"""递延所得税：销售返利、可抵扣亏损这些「未来才省税」的资产。

为什么重要：
递延所得税资产（DTA）是「已经计入费用、但税法还没认」的部分，本质是**政府对
未来利润的承诺**。三家 2025 年末 DTA 结构差异极大：

| 公司 | 最大来源 | DTA 金额 | 对应暂时性差异 |
|---|---|---|---|
| 美的 | 其他流动负债（销售返利） | 86.82 亿 | 483.68 亿 |
| 海尔 | 负债（预提费用） | 35.28 亿 | 未披露差异 |
| 格力 | 预提费用（销售返利） | 119.30 亿 | 795.96 亿 |

格力 DTA 里 119.30 亿来自预提费用，占未抵销 DTA 的 71.4%；这是它销售返利规模
在资产负债表上的镜像。美的同类项 86.82 亿占 51.5%。海尔的「负债」只有 35.28 亿，
因为它的返利只有 16.01 亿且不单列。

四个陷阱：

1. **抵销口径完全不同**。美的未抵销 DTA 168.54 亿、DTL 76.28 亿，抵销后 151.18 /
   58.92 亿；海尔抵销 41.32 亿（未抵销 69.11 / 57.63 亿 → 净 27.79 / 16.31 亿）；
   **格力完全不抵销**——资产负债表上的 167.12 亿 / 26.86 亿就是原始总额。
   直接比「DTA/总资产」会把格力系统性高估。
2. **未确认 DTA 只有两家披露**。美的 197.81 亿（合并一个数）、格力 157.19 亿
   （可抵扣亏损 91.69 亿 + 暂时性差异 65.50 亿），海尔年报没有这一节。
   「海尔没披露」不等于「海尔为零」。
3. **格力的可抵扣亏损有到期年份表**（2026 年 11.75 亿 … 2030 年及以后 42.70 亿、
   无固定期限 7.69 亿），美的只按「一至四年内 / 四年以后」粗分，海尔不拆。
4. **列的排布不同**：美的/格力的「未经抵销」表是四列（差异、DTA、差异、DTA），
   海尔是两列（期末、期初）。按「取最后两个数」解析，美的会把「暂时性差异」
   当成 DTA，数字虚增 20 倍（美的其他流动负债差异 483.68 亿 vs DTA 86.82 亿）。

用法：
    uv run python3 scripts/extract_deferred_tax.py --all
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
OUT = FIN / "递延所得税.csv"
OUT_CHECK = FIN / "递延所得税勾稽.csv"

COMPANY_OF = {
    "美的集团": ("美的2025.pdf", 1_000),
    "海尔智家": ("海尔2025.pdf", 1),
    "格力电器": ("格力2025.pdf", 1),
}

# (公司, 表名, 起始标题, 列数) —— 列数=4 表示「差异+DTA」交错，=2 表示期末/期初
BLOCKS = {
    "美的集团": [
        ("递延所得税资产", "(a)    未经抵销的递延所得税资产", 4),
        ("递延所得税负债", "(b)    未经抵销的递延所得税负债", 4),
    ],
    "海尔智家": [
        ("递延所得税资产", "（1）未经抵销的递延所得税资产", 2),
        ("递延所得税负债", "（2）未经抵销的递延所得税负债", 2),
    ],
    "格力电器": [
        ("递延所得税资产", "（1）未经抵销的递延所得税资产", 4),
        ("递延所得税负债", "（2）未经抵销的递延所得税负债", 4),
        ("未确认递延所得税资产", "（3）未确认递延所得税资产明细", 2),
    ],
}

NORMALIZE = {
    "其他流动负债": "销售返利等预提负债",
    "预提费用": "销售返利等预提负债",
    "负债": "销售返利等预提负债",
    "可抵扣亏损": "可抵扣亏损",
    "未弥补亏损": "可抵扣亏损",
    "合并抵销内部未实现利润": "内部未实现利润抵销",
    "研发支出": "研发支出资本化",
    "资产摊销/折旧": "资产摊销与折旧",
    "非同一控制下企业合并": "企业合并公允价值调整",
    "非同一控制下企业合并资产评估增值": "企业合并公允价值调整",
    "重新计量丧失控制权日剩余股权的公允价值": "企业合并公允价值调整",
    "衍生金融资产公允价值变动": "公允价值变动",
    "公允价值变动": "公允价值变动",
    "其他权益工具投资公允价值变动": "其他权益工具投资公允价值变动",
    "资产摊销": "资产摊销与折旧",
}

NUMBER = re.compile(r"^\(?-?[\d,]+(?:\.\d+)?\)?$")
SPLIT = re.compile(r"\s{2,}")
# 字号相同的表头行，遇到就当表头丢弃
HEADER = re.compile(
    r"可抵扣暂时性差|应纳税暂时性|递延所得|税资产|税负债|差异|项目|期末余额|期初余额|"
    r"\d{4}\s*年\s*12\s*月\s*31\s*日|余额"
)


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
    """截到下一个小节标题，避免把「抵销后净额」表、下一页的表混进来。"""
    target = re.sub(r"\s+", "", title)
    lines = text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if re.sub(r"\s+", "", line).startswith(target)),
        None,
    )
    if start is None:
        return []
    body = [lines[start]]
    for line in lines[start + 1 :]:
        stripped = re.sub(r"\s+", "", line)
        if re.match(r"^(\([a-z]\)|（\d+）|\d+、)", stripped) and len(stripped) < 60:
            break
        if "股份有限公司" in stripped and "年度报告" in stripped:
            continue
        body.append(line)
    return body


# 各表的完整项目名，用来把被金额劈断的标签重新拼起来
KNOWN = {
    ("美的集团", "递延所得税资产"): [
        "其他流动负债",
        "可抵扣亏损",
        "资产减值准备",
        "应付职工薪酬",
        "租赁负债",
        "其他",
    ],
    ("美的集团", "递延所得税负债"): [
        "非同一控制下企业合并",
        "预提所得税",
        "公允价值变动",
        "使用权资产",
        "其他",
    ],
    ("海尔智家", "递延所得税资产"): [
        "资产减值准备",
        "负债",
        "合并抵销内部未实现利润",
        "未弥补亏损",
        "研发支出",
        "其他",
    ],
    ("海尔智家", "递延所得税负债"): [
        "资产摊销",
        "重新计量丧失控制权日剩余股权的公允价值",
        "其他权益工具投资公允价值变动",
        "其他",
    ],
    ("格力电器", "递延所得税资产"): [
        "预提费用",
        "资产减值准备",
        "可抵扣亏损",
        "应付职工薪酬",
        "租赁负债",
        "资产摊销/折旧",
        "其他权益工具投资公允价值变动",
        "其他",
    ],
    ("格力电器", "递延所得税负债"): [
        "应计利息",
        "非同一控制下企业合并资产评估增值",
        "使用权资产",
        "资产摊销",
        "衍生金融资产公允价值变动",
        "长期股权投资",
        "其他",
    ],
    ("格力电器", "未确认递延所得税资产"): ["可抵扣亏损", "可抵扣暂时性差异"],
}


def parse_block(
    lines: list[str], columns: int, known: list[str]
) -> tuple[dict[str, tuple[float, float]], tuple[float, float] | None]:
    """返回 ({项目: (期末, 期初)}, 合计)。

    标签会被金额劈成两段（`其他权益工具投资公允` / 金额 / `价值变动`），
    金额后面紧跟的纯标签行要用**已知项目名**拼回去，且拼过的行必须跳过，
    否则下一行会被当成新标签的开头，把两个项目粘成一个。
    """
    out: dict[str, tuple[float, float]] = {}
    pending = ""
    total: tuple[float, float] | None = None
    index = 0

    while index < len(lines):
        raw = lines[index]
        index += 1
        parts = [p for p in SPLIT.split(raw.strip()) if p]
        if not parts:
            continue
        values: list[str] = []
        while parts and NUMBER.match(parts[-1]):
            values.insert(0, parts.pop())
        label = "".join(parts)

        if not values and HEADER.search(label):
            continue
        if "其中：" in label or "预计于" in label:
            break

        if not values:
            pending += label
            continue

        if len(values) == 1 and len(values[0]) <= 3 and not label:
            # 页码（格力「160」独占一行），不是金额
            continue
        if not label and not pending:
            # 无标签的纯数字行 = 合计（美的的合计行没有文字）
            total = to_pair(values, columns)
            break
        if "合计" in label or "合计" in pending:
            total = to_pair(values, columns)
            break

        full = pending + label
        pending = ""
        while True:
            open_names = [n for n in known if n.startswith(full) and n != full]
            if not open_names or index >= len(lines):
                break
            nxt = "".join(p for p in SPLIT.split(lines[index].strip()) if p)
            if not nxt or NUMBER.match(nxt):
                break
            if not any(n.startswith(full + nxt) for n in known):
                break
            full += nxt
            index += 1
        emit(out, full, values, columns)
    return out, total


def to_pair(values: list[str], columns: int) -> tuple[float, float]:
    if columns == 4 and len(values) >= 4:
        return number(values[1]), number(values[3])
    if len(values) >= 2:
        return number(values[0]), number(values[1])
    return number(values[0]), 0.0


def emit(out: dict[str, tuple[float, float]], label: str, values: list[str], columns: int) -> None:
    name = NORMALIZE.get(label, label)
    out.setdefault(name, to_pair(values, columns))


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
    totals: dict[tuple[str, str], tuple[float, float]] = {}
    problems: list[str] = []

    for company, (filename, factor) in COMPANY_OF.items():
        text = pdf_text(PDF_DIR / filename)
        for title, heading, columns in BLOCKS[company]:
            lines = block(text, heading)
            if not lines:
                problems.append(f"{company} 未找到「{heading}」")
                continue
            data, total = parse_block(lines, columns, KNOWN[(company, title)])
            scaled = {k: (v[0] * factor, v[1] * factor) for k, v in data.items()}
            if total is not None:
                totals[(company, title)] = (total[0] * factor, total[1] * factor)
            print(f"  {company} {title}: {len(scaled)} 项")

            sum_now = sum(v[0] for v in scaled.values())
            if total is not None:
                gap = sum_now - total[0] * factor
                if abs(gap) > 10_000:
                    problems.append(f"{company} {title} 明细合计与表内合计差 {gap / 1e8:.2f} 亿")
            for name, (current, previous) in scaled.items():
                rows.append(
                    [
                        company,
                        "2025",
                        title,
                        name,
                        f"{current / 1e8:.2f}",
                        f"{previous / 1e8:.2f}",
                        f"{current / sum_now * 100:.2f}" if sum_now else "",
                        "披露值",
                    ]
                )
            if total is not None:
                rows.append(
                    [
                        company,
                        "2025",
                        title,
                        "合计（表内）",
                        f"{total[0] * factor / 1e8:.2f}",
                        f"{total[1] * factor / 1e8:.2f}",
                        "100.00",
                        "披露值",
                    ]
                )

    fields = [
        "公司",
        "年度",
        "类别",
        "项目",
        "期末(亿元)",
        "期初(亿元)",
        "结构占比%",
        "数据性质",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    checks = reconcile(totals)
    with OUT_CHECK.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            [
                "公司",
                "未经抵销资产",
                "未经抵销负债",
                "抵销金额",
                "抵销后资产",
                "抵销后负债",
                "资产负债表资产",
                "资产负债表负债",
                "结果",
            ]
        )
        writer.writerows(checks)

    print(
        f"\n{'公司':<8}{'未抵销DTA':>11}{'未抵销DTL':>11}{'抵销':>9}{'净DTA':>9}{'报表DTA':>9}  结果"
    )
    print("-" * 68)
    for row in checks:
        print(f"{row[0]:<8}{row[1]:>11}{row[2]:>11}{row[3]:>9}{row[4]:>9}{row[6]:>9}  {row[8]}")

    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    print(f"写入 {OUT_CHECK.relative_to(ROOT)}: {len(checks)} 行")
    for problem in problems:
        print(f"注意：{problem}", file=sys.stderr)
    return 0


def reconcile(totals: dict[tuple[str, str], tuple[float, float]]) -> list[list[str]]:
    """未抵销合计 − 资产负债表 = 抵销金额。格力的抵销为 0。"""
    balance = load_balance()
    out: list[list[str]] = []
    for company in COMPANY_OF:
        source = totals.get((company, "递延所得税资产"))
        liability = totals.get((company, "递延所得税负债"))
        if source is None or liability is None:
            continue
        book_asset = balance.get((company, "递延所得税资产"), 0.0)
        book_liability = balance.get((company, "递延所得税负债"), 0.0)
        offset_asset = source[0] / 1e8 - book_asset
        offset_liability = liability[0] / 1e8 - book_liability
        offset = max(offset_asset, offset_liability, 0.0)
        ok = abs(offset_asset - offset_liability) < 0.05 or company == "格力电器"
        out.append(
            [
                company,
                f"{source[0] / 1e8:.2f}",
                f"{liability[0] / 1e8:.2f}",
                f"{offset:.2f}",
                f"{book_asset:.2f}",
                f"{book_liability:.2f}",
                f"{book_asset:.2f}",
                f"{book_liability:.2f}",
                "OK" if ok else "差异",
            ]
        )
    return out


def load_balance() -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    with (FIN / "资产负债表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["报告期"] != "20251231":
                continue
            if row["科目"] not in ("递延所得税资产", "递延所得税负债"):
                continue
            try:
                out[(row["公司"], row["科目"])] = float(row["数值"]) / 1e8
            except ValueError:
                continue
    return out


if __name__ == "__main__":
    sys.exit(main())
