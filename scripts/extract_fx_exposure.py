"""外币货币性项目：分币种敞口与汇率敏感度。

为什么重要
----------
已有的 `汇兑损益.csv` 只有**结果**（这一年汇兑赚/亏多少），答不了「汇率再动 1%
会怎样」。本表补上**原因**：分币种的外币资产与负债余额、折算汇率。

有了它才能算：
- 人民币升值 1%，三家各损失多少（= 净敞口 × 1%，不用等损益发生）；
- 谁的敞口在资产端、谁在负债端（人民币升值时资产端受损、负债端受益）；
- 币种结构差异：美的（美元/日元/港元/欧元/巴西雷亚尔/越南盾）、
  海尔（美元/欧元/日元/港币/新西兰元）、格力（美元/港币/欧元/雷亚尔/泰铢）。

三家格式完全不同（本脚本复杂度的来源）
--------------------------------------
| 公司 | 表形 | 给了什么 | 单位 |
|---|---|---|---|
| 美的 | 竖排，只给本期 | 外币余额 + 折算汇率 + 人民币余额 | **千元** |
| 海尔 | 竖排，一行含期末与期初 | 上述三件套 ×2 | 元 |
| 格力 | **转置**：币种做列、科目做行 | **只有分币种的人民币额**，无外币余额 | 元 |

格力的表是转置的，且**不提供外币余额与折算汇率**（只在表头给一排期末汇率），
所以格力行的「外币余额」列必须留空，不能编。

六个坑
------
1. **海尔一行数字个数会缺，且缺哪一期不能猜**。满行 6 个（期末 3 + 期初 3）；
   只披露一期时 3 个；「其他」「小计」行只有人民币，2 个或 1 个。
   例：海尔「短期借款—日元」行只有 `1,952,854,108.54  0.046233  90,286,304.00`
   三个数，那是**期初**（期末日元短期借款已还清）。按「取前三个」会把它记进 2025。
   只能靠数字右边界落在哪一列判断。
2. **标签会被数字劈成三段**。海尔「新西兰」在数字行**上一行**、「元」在**下一行**。
   只拼前缀会得到空币种；只看本行标签会漏掉整个新西兰元敞口。
3. **「不适用」不是数字但占一格**。美的「其他货币」行的外币余额与折算汇率都印
   「不适用」，只有人民币余额。跳过它会少算一格、把人民币余额错插进外币余额槽。
4. **美的的表跨 4 个页块**：(65) 与三个 (65)(续)，依次是 2025 资产、2025 负债、
   2024 资产、2024 负债。块间夹页眉，且每块必须在下一个个附注小节（`五 合并范围
   的变更`）处截断，否则会把「商誉约人民币 1,136,203,000 元」这类正文数字吃进来。
5. **格力的表里有「总计」列**。它等于同行各币种之和。若把「总计」也当成一个币种
   收进来，资产会翻倍（实测格力 2025 资产 147.57 亿会被算成 295 亿）。
6. **净敞口要用「小计」而不是币种行加总**。美的「应付债券」只有美元一行、**没有
   小计行**；只用小计会漏掉它。规则：有「小计」用小计，没有才回退到币种行加总。

用法
----
    uv run python3 scripts/extract_fx_exposure.py --all
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
OUT = FIN / "外币敞口与汇率敏感性.csv"
CACHE = Path("/tmp/fsr")

ASSET_SUBJECTS = {
    "货币资金",
    "应收账款",
    "应收款项",
    "其他应收款",
    "其他非流动资产",
    "一年内到期的非流动资产",
    "交易性金融资产",
    "其他权益工具投资",
    "其他非流动金融资产",
    "长期应收款",
    "应收利息",
    "合同资产",
}
ASSET_PREFIX = ("其他债权投资", "其他流动资产—套期工具", "其他流动资产-套期工具")

CURRENCIES = (
    "美元",
    "日元",
    "港元",
    "港币",
    "欧元",
    "巴西雷亚尔",
    "雷亚尔",
    "越南盾",
    "新西兰元",
    "泰铢",
    "其他货币",
    "其他",
)
SUBTOTALS = ("小计", "合计", "总计")
# 表头「项目 / 外币余额 / 折算汇率 / 人民币余额 / 期末余额 / 期初余额」的全部用字
HEADER_CHARS = set("项目外币余额折算汇率人币期末初")
# 转置表里这一列是行合计，不能当币种
TOTAL_COLUMN = "总计"

NUMTOK = re.compile(r"^-?[\d,]+(?:\.\d+)?$")
BLANK = re.compile(r"^(?:不适用|-|—)$")
CELL = re.compile(r"\S+")
SPLIT = re.compile(r"\s{2,}")


def text_of(name: str) -> str:
    pdf = PDF_DIR / name
    cached = CACHE / f"{pdf.stem}.txt"
    if cached.exists():
        return cached.read_text(encoding="utf-8")
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    return result.stdout


def number(token: str) -> float | None:
    token = token.strip()
    if not BLANK.match(token):
        try:
            return float(token.strip("()").replace(",", ""))
        except ValueError:
            return None
    return None


def cells(raw: str) -> tuple[str, list[tuple[int, float | None]]]:
    """(标签, [(右边界, 值或 None)])。

    用 finditer 拿绝对列位置，不能用 raw.index()：标签里也可能出现与数字相同的
    子串，且行首缩进会让 strip 后的下标整体偏移。
    「不适用」「-」也占一个数字位（返回 None），否则「其他货币」行会少算一格。
    """
    labels: list[str] = []
    numbers: list[tuple[int, float | None]] = []
    for match in CELL.finditer(raw):
        token = match.group(0)
        if NUMTOK.match(token) or BLANK.match(token):
            numbers.append((match.end(), number(token)))
        else:
            labels.append(token)
    return "".join(labels).strip(), numbers


def is_page_row(label: str, nums: list[tuple[int, float | None]]) -> bool:
    """页脚「123 / 245」形态的行：标签只有斜杠，数字是 1–4 位纯整数。"""
    if label.strip(" /") or not nums:
        return False
    return all(v is not None and abs(v) < 10_000 and float(v).is_integer() for _, v in nums)


def anchors_of(rows: list[list[tuple[int, float | None]]], want: int) -> list[int]:
    """从满行（数字个数 == want）按右边界聚类出列锚点。"""
    ends = sorted({end for nums in rows if len(nums) == want for end, _ in nums})
    if not ends:
        return []
    groups = [[ends[0]]]
    for value in ends[1:]:
        if value - groups[-1][-1] <= 4:
            groups[-1].append(value)
        else:
            groups.append([value])
    return sorted(max(g) for g in groups)


def place(nums: list[tuple[int, float | None]], anchors: list[int]) -> list[float | None]:
    """按最近锚点归位；偏离 > 8 列的丢弃（避免把页码塞进敞口）。"""
    slots: list[float | None] = [None] * len(anchors)
    for end, value in nums:
        nearest = min(range(len(anchors)), key=lambda i: abs(anchors[i] - end))
        if abs(anchors[nearest] - end) > 8:
            continue
        slots[nearest] = value
    return slots


def classify_label(label: str) -> str:
    """无数字行的标签归类。

    竖排表里，科目行与币种行都不带数字，必须靠词表区分：
      currency —— 币种（含被数字劈成两段的「新西兰」）
      subject  —— 报表科目
      skip     —— 表头、页眉、说明文字
    """
    if not label:
        return "skip"
    # 必须精确匹配：科目「其他应收款／其他应付款」都以「其他」开头，
    # 用 startswith 会把它们当成币种行，导致侧别（资产/负债）与科目双双错位。
    if label in CURRENCIES or label == "新西兰":
        return "currency"
    # 表头碎片。跨页时表头会重印并被拆行，留下「率率」这类只由表头用字组成的尾巴。
    # 它只有两字、又不匹配任何词组，会被当成科目，进而把上一块（货币资金）的
    # 「小计」记到负债侧——实测海尔 2025 资产侧因此少 65.05 亿。
    # 判据用「字集合」而非词组：整串字都来自表头用字才算碎片（「货币资金」里的
    # 「币」虽在表头出现，但其余字不在，仍是科目）。
    if set(label) <= HEADER_CHARS:
        return "skip"
    if "年度报告" in label or "附注" in label or "货币性项目" in label:
        return "skip"
    if label.startswith(SUBTOTALS) or label.startswith("上述"):
        return "skip"
    if 2 <= len(label) <= 14:
        return "subject"
    return "skip"


# ---------------------------------------------------------------- 竖排表（美的、海尔）


def parse_vertical(
    company: str, block: list[str], periods: dict[str, int], unit: str
) -> list[dict]:
    """periods: {"2025": 0, "2024": 3} —— 每个年份在 6 列槽里的起始下标。"""
    pairs = [(label, nums) for label, nums in (cells(r) for r in block) if nums]
    want = max(len(p[1]) for p in pairs) if pairs else 0
    anchors = anchors_of([nums for _, nums in pairs], want)
    if not anchors:
        return []

    rows: list[dict] = []
    subject = ""
    pending_currency = ""
    for raw in block:
        label, nums = cells(raw)
        if is_page_row(label, nums):
            continue
        if not nums:
            kind = classify_label(label)
            if kind == "currency":
                pending_currency = label
            elif kind == "subject":
                subject = label
            continue
        own = label
        currency = own if own in CURRENCIES else ""
        if not currency:
            for cand in SUBTOTALS:
                if own.startswith(cand):
                    currency = cand
                    break
        if not currency and pending_currency:
            currency = "新西兰元" if pending_currency == "新西兰" else pending_currency
        if not currency:
            subject = own[:14]
            continue
        pending_currency = ""

        slots = place(nums, anchors) if want == 6 else _slots_simple(nums)
        for year, offset in periods.items():
            fcy = _get(slots, offset)
            rate = _get(slots, offset + 1)
            rmb = _get(slots, offset + 2)
            if rmb is None and want == 3:  # 只有本期三列的表（美的）
                fcy, rate, rmb = _get(slots, 0), _get(slots, 1), _get(slots, 2)
            if rmb is None and len(nums) == 1 and want == 6:
                # 「其他」行只有一个数：按锚点已归位，若为空说明落在期初
                rmb = _get(slots, offset + 2)
            if rmb is None:
                continue
            rows.append(
                {
                    "公司": company,
                    "年度": year,
                    "科目": subject,
                    "币种": currency,
                    "外币余额": fcy,
                    "折算汇率": rate,
                    "人民币余额": rmb,
                    "单位": unit,
                }
            )
    return rows


def _slots_simple(nums: list[tuple[int, float | None]]) -> list[float | None]:
    """三列表（美的）：位置即语义，不需锚点。"""
    values = [v for _, v in nums]
    if len(values) >= 3:
        return [values[0], values[1], values[-1]]
    if len(values) == 1:  # 「其他货币」只有人民币
        return [None, None, values[0]]
    return values + [None] * (3 - len(values))


def _get(slots: list[float | None], index: int) -> float | None:
    return slots[index] if 0 <= index < len(slots) else None


def parse_midea(text: str) -> list[dict]:
    lines = text.splitlines()
    starts = [
        i for i, line in enumerate(lines) if re.match(r"^\(65\)\s+外币货币性项目", line.strip())
    ]
    if not starts:
        return []
    out: list[dict] = []
    for index, start in enumerate(starts):
        if index + 1 < len(starts):
            # 块与块相邻，下一块的起点就是本块的终点。多扫几行找「五」会把
            # 下一块整块并进来，导致该块科目在两个块里各算一遍（实测美的 2024
            # 负债侧币种加总恰好等于小计的 2 倍）。
            stop = starts[index + 1]
        else:
            stop = start + 90
            for j in range(start + 1, min(start + 140, len(lines))):
                if re.match(r"^五\s|^六\s|^\(67\)", lines[j].strip()):
                    stop = j
                    break
        year = "2025" if index < 2 else "2024"
        out.extend(parse_vertical("美的集团", lines[start:stop], {year: 0}, "千元"))
    return out


HAIER_PERIODS = {"2025": 0, "2024": 3}


def parse_haier(text: str) -> list[dict]:
    lines = text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if re.match(r"^\s*66、\s*外币货币性项目", line)), None
    )
    if start is None:
        return []
    block = []
    for line in lines[start + 1 : start + 120]:
        if re.match(r"^\s*67、", line):
            break
        block.append(line)
    return parse_vertical("海尔智家", block, HAIER_PERIODS, "元")


# ---------------------------------------------------------------- 转置表（格力）


def parse_gree(text: str, year: str = "2025") -> list[dict]:
    """格力年报的表只有本期一栏，2024 年数据要回到 2024 年报取。"""
    lines = text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if re.match(r"^\s*73、\s*外币货币性项目", line)), None
    )
    if start is None:
        return []
    header: list[str] = []
    rates: dict[str, float] = {}
    out: list[dict] = []
    for raw in lines[start : start + 40]:
        if "境外经营实体" in raw or "折算为人民币" in raw:
            break
        label, nums = cells(raw)
        if "汇率" in label and nums:  # 表头下的「2025-12-31 汇率」行
            for name, value in zip(header, [v for _, v in nums], strict=False):
                if value is not None:
                    rates[name] = value
            continue
        parts = [p for p in SPLIT.split(raw.strip()) if p]
        if not parts:
            continue
        head = parts[0].strip()
        rest = parts[1:]
        if not rest:
            continue
        if head == "项目" or "折合人民币" in head:
            header = [re.sub(r"折合人民币$", "", v.strip()) for v in rest]
            continue
        if not header:
            continue
        values = [number(v) for v in rest]
        for index, name in enumerate(header):
            if name == TOTAL_COLUMN:  # 行合计，收了会翻倍
                continue
            amount = values[index] if index < len(values) else None
            if amount is None:
                continue
            out.append(
                {
                    "公司": "格力电器",
                    "年度": year,
                    "科目": head,
                    "币种": name or "其他",
                    "外币余额": None,
                    "折算汇率": rates.get(name),
                    "人民币余额": amount,
                    "单位": "元",
                }
            )
    return out


# ---------------------------------------------------------------- 汇总


def to_yi(value: float | None, unit: str) -> float | None:
    if value is None:
        return None
    return value * (1_000 if unit == "千元" else 1) / 1e8


def side_of(subject: str) -> str:
    return "资产" if (subject in ASSET_SUBJECTS or subject.startswith(ASSET_PREFIX)) else "负债"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    if not args.all:
        parser.print_help()
        return 0

    problems: list[str] = []
    parsed: list[dict] = []
    sources: list[tuple[str, object, str]] = [
        ("美的2025.pdf", parse_midea, ""),
        ("海尔2025.pdf", parse_haier, ""),
        ("格力2025.pdf", parse_gree, "2025"),
        # 格力的表没有期初列，2024 只能取上一年年报
        ("格力2024.pdf", parse_gree, "2024"),
    ]
    for name, fn, arg in sources:
        rows = fn(text_of(name), arg) if arg else fn(text_of(name))
        print(f"  {name.replace('2025.pdf', '')}: {len(rows)} 行")
        if not rows:
            problems.append(f"{name} 未解析到外币货币性项目")
        parsed.extend(rows)

    out_rows: list[list[str]] = []
    for r in parsed:
        rmb = to_yi(r["人民币余额"], r["单位"])
        if rmb is None:
            continue
        out_rows.append(
            [
                r["公司"],
                r["年度"],
                side_of(r["科目"]),
                r["科目"],
                r["币种"],
                "" if r["外币余额"] is None else f"{r['外币余额']:,.2f}",
                "" if r["折算汇率"] is None else f"{r['折算汇率']}",
                f"{rmb:.2f}",
                "披露值",
                f"{r['公司'][:2]}2025.pdf 附注 外币货币性项目（单位 {r['单位']}）",
            ]
        )

    # 每科目取「小计」，无小计则回退到币种行加总（应付债券只有美元行、无小计）
    by_subject: dict[tuple[str, str, str, str], dict[str, float | None]] = {}
    for row in out_rows:
        key = (row[0], row[1], row[2], row[3])
        bucket = by_subject.setdefault(key, {"subtotal": None, "currencies": 0.0})
        amount = float(row[7])
        if row[4] in SUBTOTALS:
            bucket["subtotal"] = amount
        else:
            bucket["currencies"] += amount

    print(f"\n{'公司':<8}{'年度':<6}{'外币资产':>10}{'外币负债':>10}{'净敞口':>11}{'升值1%':>10}")
    print("-" * 57)
    for company in ("美的集团", "海尔智家", "格力电器"):
        for year in ("2025", "2024"):
            totals = {"资产": 0.0, "负债": 0.0}
            for (co, yr, side, _subject), bucket in by_subject.items():
                if co != company or yr != year:
                    continue
                value = bucket["subtotal"]
                if value is None:
                    value = bucket["currencies"]
                totals[side] += value
            if not (totals["资产"] or totals["负债"]):
                continue
            net = totals["资产"] - totals["负债"]
            impact = -net * 0.01
            out_rows.append(
                [
                    company,
                    year,
                    "净敞口",
                    "外币货币性项目",
                    "全部",
                    "",
                    "",
                    f"{net:.2f}",
                    "计算值",
                    "有『小计』用科目小计，无小计回退币种加总",
                ]
            )
            out_rows.append(
                [
                    company,
                    year,
                    "敏感度",
                    "人民币升值 1% 的影响",
                    "全部",
                    "",
                    "",
                    f"{impact:.2f}",
                    "计算值",
                    "= −净敞口 × 1%，假设各币种同向变动",
                ]
            )
            print(
                f"{company:<8}{year:<6}{totals['资产']:>10.2f}{totals['负债']:>10.2f}"
                f"{net:>11.2f}{impact:>10.2f}"
            )

    # problems 要在写文件前汇总，自校验的告警才不会丢
    fields = [
        "公司",
        "年度",
        "侧",
        "科目",
        "币种",
        "外币余额",
        "折算汇率",
        "人民币金额(亿元)",
        "数据性质",
        "来源",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(out_rows)
    tail = OUT.relative_to(ROOT)
    # 自校验：逐科目「币种行加总」应当等于年报自己印的「小计 / 总计」。
    # 不等说明要么币种漏收、要么「率率」这类表头碎片把小计挂到了错科目——
    # 这两类错此前都真实发生过。
    print("\n[自校验] 逐科目：币种加总 vs 年报小计")
    checked = 0
    for (co, yr, _side, subject), bucket in sorted(by_subject.items()):
        subtotal, currencies = bucket["subtotal"], bucket["currencies"]
        if subtotal is None or not currencies:
            continue
        checked += 1
        gap = currencies - subtotal
        if abs(gap) > 0.05:
            problems.append(
                f"{co} {yr} {subject} 币种加总 {currencies:.2f}"
                f" ≠ 小计 {subtotal:.2f}（差 {gap:+.2f} 亿）"
            )
    print(f"  比对 {checked} 个科目")

    tail = OUT.relative_to(ROOT)
    print(f"\n写入 {tail}: {len(out_rows)} 行")

    for problem in problems:
        print(f"注意：{problem}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
