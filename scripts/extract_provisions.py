"""预计负债（售后三包、安装费、未决诉讼）：售后义务规模与计提充分性。

为什么重要
----------
「预计负债」是**售后义务的账面体现**——产品卖出去以后还要花的钱（三包、安装、
维修）在销售当期就估出来挂账。它回答两个分析问题：

1. **售后承诺有多重**。海尔 2025 年「预计三包安装费」19.68 亿，占预计负债合计
   （24.90 亿）的 79%；这笔钱是「已销售但尚未履行」的义务，与当期已经发生的
   销售费用不是一回事。
2. **计提是否充分、口径是否可比**。三家差别极大：海尔单独计提三包安装费并披露
   明细与计提依据；美的只挂一个总数、附注不拆项目；格力**合并与母公司资产负债
   表该行整列空白**。
   「格力没有售后义务」是错的——它未确认预计负债，维修支出直接进当期销售费用。
   这直接决定三家销售费用率不可不加调整地横向比较。

顺带解释美的一个反直觉数字
--------------------------
美的 2025 年「其他流动负债」925.37 亿里，**529.53 亿是预提销售返利**
（附注四(36)）。经销商返利按合同对价扣除预计返利后的净额确认收入，这部分是
「已收经销商的钱但尚未结返利」，属于对下游的占用，已由 `渠道返利与占款.csv`
覆盖，本表不重复记录。

四个坑
------
1. **海尔 2019 与 2025 的表头列序是反的**。2019/2020 年报表头为
   「项目 | 期初余额 | 期末余额」，2025 年报为「项目 | 期末余额 | 期初余额」。
   写死列序会把「当年期末」取成「上年期末」，整条时间序列平移一年而看不出异常。
   **必须读表头判定**，本脚本按「期末」与「期初」谁先出现来取值，并在输出里
   把列序写进口径说明。找不到表头时抛错而不是猜。
2. **报表上的「预计负债」只是非流动那一半**。一年内到期的部分列示在
   「一年内到期的非流动负债」里（海尔 2019 年附注明确列了
   「1 年内到期的预计负债 1,992,138,260.62 元」）。美的会计政策同样写明
   「预期在资产负债表日起一年内需支付的预计负债，列报为流动负债」。
   海尔 2019 年审计报告把两者并列为关键审计事项：「预计负债及一年内到期非流动
   负债中与产品质量保证相关的余额为 30.58 亿元」，而当年附注「预计负债」合计
   只有 13.99 亿——**只看附注合计会显著低估售后义务**。
3. **akshare 的期中数与年报数不是同一口径**。实测海尔：
   2019-03/06/09 三季末分别 27.65/28.62/28.13 亿，而 2019-12-31 掉到 13.99 亿
   （与年报附注合计逐位一致）；2018-09 29.84 亿、2018-12-31 12.07 亿。
   即**期中把两半加在一起、1231 只给非流动部分**。画趋势时必须只用年报口径。
4. **格力的行是空的，不是 0**。合并与母公司资产负债表「预计负债」后面不跟数字，
   2019 年后 akshare 也不再返回该科目（只有 2017/2018 的 0.0 与 2006/2007 的数）。
   **空 ≠ 零计提**，本表记为「未披露（报表行为空）」而不是 0。

用法
----
    uv run python3 scripts/extract_provisions.py --all
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

from pdf_util import pdf_text, report_pdf

ROOT = Path(__file__).resolve().parent.parent
FIN = ROOT / "财务数据"
OUT = FIN / "预计负债与售后义务.csv"

YEARS = [str(y) for y in range(2019, 2026)]

# 海尔附注里的项目名（保留原文名，不强行归并）
HAIER_ITEMS = ("预计三包安装费", "未决诉讼", "其他")
# 同一行在不同年报里写法有三种：2019/2020/2021/2023 写「1 年内到期的预计负债」，
# 2022 写「一年内到期的预计负债」（中文「一」，不是「1 」）。
# 只匹配「1 」前缀会整年漏掉 2022 的 25.37 亿流动部分。
HAIER_DUE = r"(?:1 |一)?年内到期的预计负债"
UNIT_TO_YI = {"元": 1e8, "千元": 1e5}

SPLIT = re.compile(r"\s{2,}")
NUM = re.compile(r"^-?[\d,]+(?:\.\d+)?$")


def text_of(company: str, year: str) -> str:
    stem = f"{company[:2]}{year}"
    return pdf_text(report_pdf(ROOT, stem))


def number(token: str) -> float | None:
    token = token.strip()
    return float(token.replace(",", "")) if NUM.match(token) else None


def cells(raw: str) -> tuple[str, list[float | None]]:
    """(行首标签, 其余列的数值)。「-」与空白解析为 None。"""
    parts = [p for p in SPLIT.split(raw.strip()) if p]
    if not parts:
        return "", []
    return parts[0].strip(), [number(p) for p in parts[1:]]


def period_slot(line: str) -> int:
    """表头行里「期末」是第几个数值列：0=期末在前，1=期末在后（期初在前）。

    海尔 2019 是 1、2025 是 0。两词都在才判，缺一律抛错——猜错的后果是
    整条序列平移一年，比直接失败更糟。
    """
    end_pos, opening_pos = line.find("期末"), line.find("期初")
    if end_pos == -1 or opening_pos == -1:
        raise LookupError(f"表头不完整（缺期末或期初）：{line.strip()[:70]!r}")
    return 0 if end_pos < opening_pos else 1


def find_header(lines: list[str], within: int = 12) -> tuple[int, int]:
    """在数据行之前找到表头，返回 (表头行下标, 期末槽位)。"""
    for i, raw in enumerate(lines[:within]):
        if "期末" in raw and "期初" in raw:
            return i, period_slot(raw)
    raise LookupError(f"{within} 行内没有找到同时含期初/期末的表头")


# ------------------------------------------------------------------ 海尔附注


def parse_haier_note(text: str) -> dict[str, object]:
    """取「N、预计负债」中**带期初/期末表头**的那一个小节。

    同一份年报里这个标题出现两次：政策部分（如 2025 年报的「24、预计负债」，
    只有文字）与附注部分（「40、预计负债」，才是金额表）。
    实测只按第一次命中去解析，海尔 2024/2025 会抓到政策小节而报「找不到表头」，
    而 2019—2023 恰好政策小节编号写法不同才蒙对。必须逐个候选试。
    """
    candidates = list(re.finditer(r"^\s*\d+、\s*预计负债\s*$", text, re.M))
    if not candidates:
        raise LookupError("找不到「N、预计负债」小节")
    last_error: Exception | None = None
    for m in candidates:
        try:
            return _parse_haier_block(text[m.end() : m.end() + 2600])
        except LookupError as exc:
            last_error = exc
    raise LookupError(f"两个候选小节都没有金额表：{last_error}")


def _parse_haier_block(block: str) -> dict[str, object]:
    lines = block.splitlines()
    header_at, slot = find_header(lines)

    items: dict[str, float] = {}
    total: float | None = None
    prior: float | None = None
    for raw in lines[header_at + 1 :]:
        label, nums = cells(raw)
        if not nums:
            if label.startswith("预计负债") or "作为承租人" in raw:
                break  # 到了下一个小节
            continue
        if len(nums) <= slot:
            continue
        value = nums[slot]
        if label == "合计":
            total = value
            prior = nums[1 - slot] if len(nums) > 1 - slot else None
            break
        if label in HAIER_ITEMS and value is not None:
            items[label] = value
    order = "期末在前" if slot == 0 else "期初在前"
    return {"合计": total, "期初": prior, "明细": items, "列序": order}


def parse_haier_due_within_year(text: str) -> tuple[float | None, float | None]:
    """「一年内到期的预计负债」在「一年内到期的非流动负债」附注里。

    返回 (期末, 期初)。
    """
    m = re.search(rf"^\s*{HAIER_DUE}", text, re.M)
    if not m:
        return None, None
    # 同一小节的表头可能在上方几行，也可能被换行拆断；取该小节内最近的一条
    above = text[max(0, m.start() - 700) : m.start()]
    header_lines = [x for x in above.splitlines() if "期末" in x and "期初" in x]
    slot = period_slot(header_lines[-1]) if header_lines else 0
    _label, nums = cells(text[m.start() : text.index("\n", m.start())])
    live = [i for i, v in enumerate(nums) if v is not None]
    if not live:
        return None, None
    end_idx = slot if slot in live else live[0]
    other = [i for i in live if i != end_idx]
    return nums[end_idx], (nums[other[0]] if other else None)


# ------------------------------------------------------------------ 资产负债表行


def parse_balance_line(text: str) -> float | None:
    """合并资产负债表「预计负债」行的第一个数值（合并口径期末数）。

    美的该行形如「预计负债  853,874  781,733  -  -」：合并期末/合并期初/母期末/母期初。
    格力该行后面不跟数字，返回 None（由调用方记「未披露」，不填 0）。
    """
    for raw in text.splitlines():
        label, nums = cells(raw)
        if label.strip() == "预计负债":
            values = [v for v in nums if v is not None]
            return values[0] if values else None
    return None


# ------------------------------------------------------------------ 交叉校验


def akshare_provisions() -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    with (FIN / "资产负债表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["科目"] != "预计非流动负债" or not row["报告期"].endswith("1231"):
                continue
            if row["数值"] in ("", "nan"):
                continue
            out[(row["公司"], row["报告期"][:4])] = float(row["数值"])
    return out


# ------------------------------------------------------------------ 主流程


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    if not args.all:
        parser.print_help()
        return 0

    problems: list[str] = []
    rows: list[list[str]] = []
    haier_detail: dict[str, dict[str, object]] = {}
    # 用于「本年报期初 == 上年年报期末」的链条验证
    chain: dict[str, list[tuple[str, float | None, float | None]]] = {
        "合计": [],
        "一年内到期": [],
    }

    def add(
        company: str, year: str, item: str, value: float | None, unit: str, nature: str, note: str
    ) -> None:
        rows.append(
            [
                company,
                year,
                item,
                "" if value is None else f"{value / UNIT_TO_YI[unit]:.2f}",
                nature,
                note,
            ]
        )

    for year in YEARS:
        # ---------------- 海尔：附注明细 + 一年内到期（元）
        haier = text_of("海尔智家", year)
        try:
            got = parse_haier_note(haier)
        except LookupError as exc:
            problems.append(f"海尔 {year} 预计负债附注解析失败：{exc}")
            got = {}
        if got:
            haier_detail[year] = got
            add(
                "海尔智家",
                year,
                "预计负债合计（附注，非流动口径）",
                got["合计"],
                "元",
                "披露值",
                f"表头列序 {got['列序']}",
            )
            for item, value in got["明细"].items():
                add("海尔智家", year, f"其中：{item}", value, "元", "披露值", "附注 预计负债")
            due, due_prior = parse_haier_due_within_year(haier)
            if due:
                add(
                    "海尔智家",
                    year,
                    "一年内到期的预计负债（流动部分）",
                    due,
                    "元",
                    "披露值",
                    "列示在「一年内到期的非流动负债」附注内，不在上表合计里",
                )
            chain["合计"].append((year, got["合计"], got.get("期初")))
            chain["一年内到期"].append((year, due, due_prior))

        # ---------------- 美的：报表总数（千元），附注不拆项目
        midea = text_of("美的集团", year)
        value = parse_balance_line(midea)
        if value is None:
            problems.append(f"美的 {year} 未解析到预计负债")
        else:
            add(
                "美的集团",
                year,
                "预计负债（合并资产负债表）",
                value,
                "千元",
                "披露值",
                "附注二(23) 仅给会计政策；二(26) 说明产品质量保证不构成单独履约"
                "义务、确认营业成本与预计负债；未拆项目",
            )

        # ---------------- 格力：报表行为空 → 未披露
        gree = text_of("格力电器", year)
        value = parse_balance_line(gree)
        if value is None:
            add(
                "格力电器",
                year,
                "预计负债（合并资产负债表）",
                None,
                "元",
                "未披露",
                "合并与母公司资产负债表「预计负债」行均无金额；"
                "**不等于无售后义务**，维修支出直接进当期销售费用",
            )
        else:
            add(
                "格力电器",
                year,
                "预计负债（合并资产负债表）",
                value,
                "元",
                "披露值",
                "报表列示金额",
            )

    # ---------------- 链条验证：本年报的期初必须等于上一份年报的期末。
    # 这一条能同时抓住两类错：列序判反（期初/期末互换）与年份错位。
    # 实测 2019—2025 两条链各 6 环全部闭合。
    print("[链条] 本年报期初 == 上年年报期末（能同时抓住列序判反与年份错位）")
    for label, series in chain.items():
        rings = 0
        broken = 0
        # series[1:] 与 series[:-1] 等长，strict=True 是结构保证而非兜底
        for (year, _end, prior), (pyear, pend, _p) in zip(series[1:], series[:-1], strict=True):
            if prior is None or pend is None:
                continue
            if int(year) != int(pyear) + 1:
                continue  # 中间有年份缺失，不构成可验证的相邻环
            rings += 1
            if abs(prior - pend) > 1:
                broken += 1
                problems.append(
                    f"海尔 {label} {year} 期初 {prior / 1e8:.2f} 亿"
                    f" ≠ {pyear} 期末 {pend / 1e8:.2f} 亿（列序或年份错位）"
                )
        # 必须把断环数说出口：早先这里只打印环数，即使全断也照样显示
        # 「6 环全部闭合」，等于一句没有依据的断言。
        verdict = "全部闭合" if not broken else f"**{broken} 环断开**"
        print(f"    {label}：{rings} 环，{verdict}" if rings else f"    {label}：无可验证环")

    # ---------------- 明细加总 == 合计（用原始元值比，不用四舍五入后的亿元）
    # CSV 里的亿元是保留两位的展示值，若拿它相加再比合计，海尔 2020/2023 会出现
    # 0.01 亿的**舍入累积假差异**。必须用解析到的元级原值判。
    for row in rows:
        if row[0] != "海尔智家" or not row[2].startswith("预计负债合计"):
            continue
        parsed = haier_detail.get(row[1])
        if not parsed:
            continue
        total = parsed["合计"]
        detail = sum(v for v in parsed["明细"].values() if v is not None)
        if total is None:
            continue
        ok = abs(detail - total) <= 1  # 元级容差
        print(
            f"[加总] 海尔 {row[1]} 明细相加 {detail / 1e8:.2f} vs "
            f"合计 {total / 1e8:.2f}  {'OK' if ok else '差异'}"
        )
        if not ok:
            problems.append(
                f"海尔 {row[1]} 预计负债明细相加 {detail:,.2f} 元 与"
                f"合计 {total:,.2f} 元 差 {detail - total:+,.2f} 元"
            )

    # ---------------- 与 akshare 交叉校验（年报口径应对平）
    bs = akshare_provisions()
    print("[交叉校验] 提取值 vs akshare「预计非流动负债」（均取年报 1231）")
    for row in rows:
        company, year, item = row[0], row[1], row[2]
        if not (item.startswith("预计负债合计") or "合并资产负债表" in item):
            continue
        theirs = bs.get((company, year))
        if theirs is None and not row[3]:
            print(f"    {company} {year}：两边都无数据（格力不列示）OK")
            continue
        if theirs is None or not row[3]:
            problems.append(f"{company} {year} 一边有一边无，口径需人工确认")
            continue
        gap = float(row[3]) * 1e8 - theirs
        ok = abs(gap) <= 0.01e8
        print(
            f"    {company} {year}：提取 {row[3]} vs akshare {theirs / 1e8:.2f} "
            f"{'OK' if ok else f'差 {gap / 1e8:+.2f} 亿'}"
        )
        if not ok:
            problems.append(f"{company} {year} 与 akshare 差 {gap / 1e8:+.2f} 亿")

    fields = ["公司", "年度", "项目", "金额(亿元)", "数据性质", "口径说明"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    print(f"\n{'公司':<8}{'年度':<6}{'项目':<32}{'金额':>9}  性质")
    print("-" * 70)
    for row in rows:
        if row[2].startswith(("预计负债合计", "预计负债（", "一年内到期")):
            print(f"{row[0]:<8}{row[1]:<6}{row[2][:30]:<32}{row[3] or '—':>9}  {row[4]}")

    tail = OUT.relative_to(ROOT)
    print(f"\n写入 {tail}: {len(rows)} 行")
    for problem in problems:
        print(f"注意：{problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
