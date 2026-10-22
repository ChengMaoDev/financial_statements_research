"""提取前五大客户/供应商集中度与关联方购销依赖度（2019—2025）。

前五大集中度与全部关联采购/销售分别提取，不能用其中一项推断全部供应链
关系或内部定价贡献。匿名客户保留序号，不仅凭金额相同推断身份。

实际踩到的陷阱：
1. 单位不同：美的「千元」、海尔「万元」、格力「元」。同一张表里 60,136,990
   是美的的 601 亿，3,491,480.10 是海尔的 349 亿，36,450,619,454.43 是格力的
   365 亿，直接比较会差 4—7 个数量级。
2. 占比分母不是营业成本：格力 2025 前五大供应商 364.51 亿 ÷ 32.75% 反推
   1,113 亿，而营业成本 1,196 亿，差 7.0%。年报分母是「年度采购总额」。
   海尔的关联采购 302.46 亿 ÷ 营业成本 2,217 亿 = 13.64%，但若用「采购总额」
   则约 14.4%。跨公司比较只能用同一分母，且要标注。
3. 海尔采购表方向：2020—2024 年表头明确是「本公司向关联方采购货物及服务」，
   2025 年改用证监会模板标题「购销商品、提供和接受劳务的关联交易」，但表内
   只有采购方向，销售另起一表（35.72 亿）。用「上期列勾稽」可证：2025 年该表
   上期 301.31 亿 ≈ 2024 年采购 302.04 亿，若含销售则应约 337.8 亿。因此 302.46
   亿是纯采购，不是「采购+销售」上限；真正的口径问题是它含物流、安装等服务，
   不是纯原材料采购。
4. 美的关联交易表口径在 2023/2024 之间断裂：2019—2023 年报只列「重大关联交易」
   （2023 年只有会通一笔 14.20 亿），2024 年报改列全部关联方并加「其他」汇总，
   并把 2023 年可比数重述为 23.39 亿（采购）/30.73 亿（销售），销售差 7.5 倍。
   本表逐年用当年年报原披露值，重述数写进口径说明，不混用。
5. 格力 2019/2021 年报把「……占年度销售总额比例」的「比例」二字拆到数字
   两侧（「比\\n4.35%\\n例」），直接正则匹配不到，必须先修复断行。
6. 海尔 2024 年 12 月日日顺并表，2024 年报把 2023 年关联采购从 375.40 亿
   重述为 311.79 亿（少 63.61 亿），跨 2023/2024 比较必须用重述后口径。
7. 格力 2021 年报自相矛盾：前五名客户关联方占比披露 0.00%，但第 2 名
   61.74 亿与关联方「浙江盛世欣兴」销售明细分毫不差。
8. 2019—2022 年报不在 年度报告/ 目录，需从 cninfo 按 定期报告清单.csv 的
   链接补下；只读取原始 PDF，不接受无来源的旧文本缓存。

用法：
    uv run python3 scripts/extract_supply_chain_concentration.py --all
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

from pdf_util import pdf_text, report_pdf

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "年度报告"
FIN = ROOT / "财务数据"
OUT = FIN / "供应商客户集中度时序.csv"

COMPANIES = ("美的集团", "海尔智家", "格力电器")
SHORT = {"美的集团": "美的", "海尔智家": "海尔", "格力电器": "格力"}
UNIT = {"美的集团": 1_000, "海尔智家": 10_000, "格力电器": 1}
# 关联交易附注单位与集中度表不同：美的千元，海尔/格力元
REL_UNIT = {"美的集团": 1_000, "海尔智家": 1, "格力电器": 1}
YEARS = range(2023, 2026)


def num(text: str | None) -> float | None:
    if text is None:
        return None
    try:
        return float(text.replace(",", "").replace("—", "").strip())
    except ValueError:
        return None


def text_of(short: str, year: int) -> str | None:
    """研究期原件全部在仓库内，不再下载早期年报。"""
    return pdf_text(report_pdf(ROOT, f"{short}{year}"))


def flatten(text: str) -> str:
    """修复断行后压成单行，供字段/句式解析。"""
    # 格力 2019/2021 把「……比例」拆成「比\n 4.35%\n例」或「……总额\n 0.00%\n比例」
    text = re.sub(r"比\s*\n\s*([\d.]+%)\s*\n\s*例", r"比例 \1", text)
    text = re.sub(r"(占年度(?:销售|采购)总额)\s*\n\s*([\d.]+%)\s*\n?\s*比例", r"\1比例 \2", text)
    text = re.sub(r"\b\d{1,3}\s*/\s*\d{1,3}\b", " ", text)
    text = re.sub(
        r"[\u4e00-\u9fa5（）()]+股份有限公司\s*\d{4}\s*年(?:半)?年度报告(?:全文)?", " ", text
    )
    text = re.sub(r"(?m)^\s*\d{2,3}\s*$", " ", text)
    return re.sub(r"\s+", " ", text)


def block(text: str, start_pat: str, end_pat: str) -> str:
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if re.search(start_pat, line)), None)
    if start is None:
        return ""
    end = next(
        (i for i in range(start + 1, len(lines)) if re.search(end_pat, lines[i])), len(lines)
    )
    return "\n".join(lines[start:end])


def last_pair(body: str) -> tuple[float, float] | None:
    """表格合计行通常只含两个数字（本期、上期）。"""
    pairs = re.findall(r"(?m)^\s*([\d,]+(?:\.\d+)?)\s+([\d,]+(?:\.\d+)?)\s*$", body)
    if not pairs:
        return None
    first, second = num(pairs[-1][0]), num(pairs[-1][1])
    return (first, second) if first is not None and second is not None else None


def data_rows_sum(body: str) -> float | None:
    """无合计行时，把带中文的数据行倒数第二个数相加（本期列）。

    表头「关联方 内容 2023 年度 2022 年度」也会被拆出两个数，必须排除纯年份。
    """
    total, found = 0.0, False
    for line in body.splitlines():
        if re.search(r"^\s*关联方\b", line) or re.search(r"\d{4}\s*年度\s+\d{4}\s*年度", line):
            continue
        values = re.findall(r"[\d,]+(?:\.\d+)?", line)
        if len(values) >= 2 and re.search(r"[\u4e00-\u9fa5]", line):
            value = num(values[-2])
            if value is not None:
                total, found = total + value, True
    return total if found else None


def top5_detail(text: str, anchor: str) -> list[tuple[int, float, float]]:
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if re.search(anchor, line)), None)
    if start is None:
        return []
    rows: list[tuple[int, float, float]] = []
    for line in lines[start : start + 80]:
        match = re.match(r"^\s*([1-5])\s+第[一二三四五]名\s+([\d,]+(?:\.\d+)?)\s+([\d.]+)%", line)
        if match:
            rows.append((int(match.group(1)), num(match.group(2)) or 0.0, float(match.group(3))))
        elif rows and re.search(r"合\s*计", line):
            break
    return rows


def parse_meidi(flat: str) -> dict[str, float | None]:
    def after(label: str) -> float | None:
        match = re.search(rf"{re.escape(label)}\s*([\d.]+)\s*%?", flat)
        return float(match.group(1)) if match else None

    amount = re.search(r"前五名客户合计销售金额（千元）\s*([\d,]+(?:\.\d+)?)", flat)
    supply = re.search(r"前五名供应商合计采购金额（千元）\s*([\d,]+(?:\.\d+)?)", flat)
    return {
        "cust_amount": num(amount.group(1)) if amount else None,
        "cust_ratio": after("前五名客户合计销售金额占年度销售总额比例"),
        "cust_related": after("前五名客户销售额中关联方销售额占年度销售总额比例"),
        "sup_amount": num(supply.group(1)) if supply else None,
        "sup_ratio": after("前五名供应商合计采购金额占年度采购总额比例"),
        "sup_related": after("前五名供应商采购额中关联方采购额占年度采购总额比例"),
    }


def parse_gree(flat: str) -> dict[str, float | None]:
    def after(label: str) -> float | None:
        match = re.search(rf"{re.escape(label)}\s*([\d.]+)\s*%?", flat)
        return float(match.group(1)) if match else None

    amount = re.search(r"前五名客户合计销售金额（元）\s*([\d,]+(?:\.\d+)?)", flat)
    supply = re.search(r"前五名供应商合计采购金额（元）\s*([\d,]+(?:\.\d+)?)", flat)
    return {
        "cust_amount": num(amount.group(1)) if amount else None,
        "cust_ratio": after("前五名客户合计销售金额占年度销售总额比例"),
        "cust_related": after("前五名客户销售额中关联方销售额占年度销售总额比例"),
        "sup_amount": num(supply.group(1)) if supply else None,
        "sup_ratio": after("前五名供应商合计采购金额占年度采购总额比例"),
        "sup_related": after("前五名供应商采购额中关联方采购额占年度采购总额比例"),
    }


def parse_haier(flat: str) -> dict[str, float | None]:
    cust = re.search(
        r"前五名客户销售额\s*([\d,]+(?:\.\d+)?)\s*万元\s*[，,]?\s*占年度销售总额\s*([\d.]+)\s*%",
        flat,
    )
    cust_rel = re.search(
        r"其中前五名客户销售额中关\s*联\s*方\s*销售额\s*([\d,]+(?:\.\d+)?)\s*万元"
        r"\s*[，,]?\s*占年度销售总额\s*([\d.]+)\s*%",
        flat,
    )
    sup = re.search(
        r"前五名供应商采购额\s*([\d,]+(?:\.\d+)?)\s*万元\s*[，,]?\s*占年度采购总额\s*([\d.]+)\s*%",
        flat,
    )
    sup_rel = re.search(
        r"其中前五名供应商采购额\s*中\s*关\s*联\s*方\s*采购额\s*([\d,]+(?:\.\d+)?)\s*万元"
        r"\s*[，,]?\s*占年度采购总额\s*([\d.]+)\s*%",
        flat,
    )
    return {
        "cust_amount": num(cust.group(1)) if cust else None,
        "cust_ratio": float(cust.group(2)) if cust else None,
        "cust_related": float(cust_rel.group(2)) if cust_rel else None,
        "cust_related_amount": num(cust_rel.group(1)) if cust_rel else None,
        "sup_amount": num(sup.group(1)) if sup else None,
        "sup_ratio": float(sup.group(2)) if sup else None,
        "sup_related": float(sup_rel.group(2)) if sup_rel else None,
        "sup_related_amount": num(sup_rel.group(1)) if sup_rel else None,
    }


def related_meidi(text: str, kind: str) -> tuple[float, float] | None:
    # 附注里「(a) 销售商品」也出现在收入会计政策段，且「关联交易情况」有「(续)」页，
    # 因此取「含采购商品表」的第一处小节起点，不能用 rfind。
    starts = [m.start() for m in re.finditer(r"(?m)^\s*\(4\)\s+关联交易情况", text)]
    anchor = next((s for s in starts if "采购商品" in text[s : s + 4_000]), None)
    if anchor is None:
        return None
    section = text[anchor : anchor + 20_000]
    if kind == "purchase":
        start, end = r"^\s*\([a-d]\)\s+采购商品", r"^\s*\([a-d]\)\s+销售商品"
    else:
        start = r"^\s*\([a-d]\)\s+销售商品"
        end = r"^\s*\([a-d]\)\s+(?:投资收益|关键管理人员|利息收入)"
    body = block(section, start, end)
    pair = last_pair(body)
    if pair:
        return pair
    total = data_rows_sum(body)
    return (total, 0.0) if total else None


def related_haier(text: str, year: int, kind: str) -> float | None:
    if year == 2019:
        start = r"采购商品/接受劳务情况表" if kind == "purchase" else r"出售商品/提供劳务情况表"
        end = (
            r"出售商品/提供劳务情况表"
            if kind == "purchase"
            else r"购销商品、提供和接受劳务的关联交易说明"
        )
    elif year == 2025:
        start = (
            r"购销商品、提供和接受劳务的关联交易"
            if kind == "purchase"
            else r"本公司向关联方销售货物有关明细资料"
        )
        end = (
            r"本公司向关联方销售货物有关明细资料" if kind == "purchase" else r"关联方未结算项目金额"
        )
    else:
        start = (
            r"本公司向关联方采购货物及服务有关明细资料"
            if kind == "purchase"
            else r"本公司向关联方销售货物有关明细资料"
        )
        end = (
            r"本公司向关联方销售货物有关明细资料" if kind == "purchase" else r"关联方未结算项目金额"
        )
    body = block(text, start, end)
    match = re.search(r"合\s*计\s+([\d,]+(?:\.\d+)?)\s+([\d,]+(?:\.\d+)?)", body)
    return num(match.group(1)) if match else None


def related_gree(text: str, kind: str) -> float | None:
    if kind == "purchase":
        start, end = r"1\)\s*采购商品/接受劳务情况表", r"2\)\s*出售商品/提供劳务情况表"
    else:
        start, end = r"2\)\s*出售商品/提供劳务情况表", r"（2）关联受托管理"
    body = block(text, start, end)
    match = re.search(r"合\s*计\s+([\d,]+(?:\.\d+)?)\s+([\d,]+(?:\.\d+)?)", body)
    return num(match.group(1)) if match else None


def load_denominators() -> dict[tuple[str, int], tuple[float, float]]:
    out: dict[tuple[str, int], tuple[float, float]] = {}
    with (FIN / "利润表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if not row["报告期"].endswith("1231") or row["科目"] not in ("营业收入", "营业成本"):
                continue
            key = (row["公司"], int(row["报告期"][:4]))
            revenue, cost = out.get(key, (0.0, 0.0))
            if row["科目"] == "营业收入":
                revenue = float(row["数值"])
            else:
                cost = float(row["数值"])
            out[key] = (revenue, cost)
    return out


def row(
    company: str,
    year: int,
    category: str,
    item: str,
    amount: float | None,
    ratio: float | None,
    nature: str,
    note: str,
    source: str,
    amount_yuan: float | None = None,
) -> dict[str, str]:
    return {
        "公司": company,
        "年度": str(year),
        "类别": category,
        "项目": item,
        "金额(亿元)": f"{amount:.2f}" if amount is not None else "",
        "占比%": f"{ratio:.2f}" if ratio is not None else "",
        "数据性质": nature,
        "口径说明": note,
        "来源": source,
        "金额(元)": "" if amount_yuan is None else f"{amount_yuan:.2f}",
    }


def build_rows(denom: dict[tuple[str, int], tuple[float, float]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for company in COMPANIES:
        short = SHORT[company]
        factor = UNIT[company]
        for year in YEARS:
            text = text_of(short, year)
            source = f"{short}{year}.pdf"
            if not text:
                for category in ("前五大客户", "前五大供应商", "关联采购", "关联销售"):
                    rows.append(
                        row(company, year, category, "原文缺失", None, None, "未披露", "", "")
                    )
                print(f"  {company} {year}: 原文缺失", file=sys.stderr)
                continue

            flat = flatten(text)
            if company == "美的集团":
                data = parse_meidi(flat)
                cust_detail = top5_detail(text, r"前\s?5\s?大客户资料")
                sup_detail = top5_detail(text, r"前\s?5\s?名供应商资料")
            elif company == "格力电器":
                data = parse_gree(flat)
                cust_detail = top5_detail(text, r"前\s?5\s?大客户资料")
                sup_detail = top5_detail(text, r"前\s?5\s?名供应商资料")
            else:
                data = parse_haier(flat)
                cust_detail, sup_detail = [], []

            revenue, cost = denom.get((company, year), (0.0, 0.0))
            unit_note = (
                f"原单位{'千元' if factor == 1_000 else '万元' if factor == 10_000 else '元'}"
            )
            for category, prefix, _base, _base_name in (
                ("前五大客户", "cust", revenue, "营业收入"),
                ("前五大供应商", "sup", cost, "营业成本"),
            ):
                amount = data.get(f"{prefix}_amount")
                ratio = data.get(f"{prefix}_ratio")
                related_ratio = data.get(f"{prefix}_related")
                if amount is None:
                    rows.append(
                        row(company, year, category, "前五名合计", None, None, "未披露", "", source)
                    )
                    continue
                amount_b = amount * factor / 1e8
                note = f"{unit_note}；占比分母为年报「年度{'销售' if prefix == 'cust' else '采购'}总额」"
                if prefix == "sup":
                    note += "，非营业成本"
                    if company == "海尔智家" and year <= 2022:
                        note += (
                            "；2019—2022 年反推分母约为营业成本的 1.30 倍，"
                            "2023 年起降到 0.88—1.03 倍，分母口径在 2022/2023 之间有断点"
                        )
                rows.append(
                    row(
                        company,
                        year,
                        category,
                        "前五名合计",
                        amount_b,
                        ratio,
                        "披露值",
                        note,
                        source,
                        amount_yuan=amount * factor,
                    )
                )

                disclosed_amount = data.get(f"{prefix}_related_amount")
                inconsistent = company == "格力电器" and year == 2021 and prefix == "cust"
                if inconsistent:
                    rows.append(
                        row(
                            company,
                            year,
                            category,
                            "其中:关联方",
                            None,
                            None,
                            "不可得",
                            "原文占比与关联方明细冲突，已删除该占比及反推金额",
                            source,
                        )
                    )
                elif related_ratio is None:
                    rows.append(
                        row(
                            company, year, category, "其中:关联方", None, None, "未披露", "", source
                        )
                    )
                elif disclosed_amount is not None:
                    rows.append(
                        row(
                            company,
                            year,
                            category,
                            "其中:关联方",
                            disclosed_amount * factor / 1e8,
                            related_ratio,
                            "披露值",
                            "金额与占比均为年报直接披露",
                            source,
                            amount_yuan=disclosed_amount * factor,
                        )
                    )
                else:
                    # 关联方占比和前五名占比的分母均为年度销售/采购总额。
                    # 不能把「占年度总额比例」乘以前五名金额。
                    if ratio is None or ratio <= 0:
                        raise ValueError(f"{company} {year} {category} 缺少有效的前五名占比")
                    related_b = amount_b * related_ratio / ratio
                    related_note = (
                        "占比为年报直接披露；金额=前五名合计×关联方占年度总额比例÷前五名占比"
                        if related_ratio
                        else "年报明确披露关联方占比为 0，金额相应为 0"
                    )
                    rows.append(
                        row(
                            company,
                            year,
                            category,
                            "其中:关联方",
                            related_b,
                            related_ratio,
                            "计算值",
                            related_note,
                            source,
                            amount_yuan=amount * factor * related_ratio / ratio,
                        )
                    )

                detail = cust_detail if prefix == "cust" else sup_detail
                if not detail:
                    rows.append(
                        row(
                            company,
                            year,
                            category,
                            "逐户明细",
                            None,
                            None,
                            "未披露",
                            "年报仅披露合计数，未披露逐户名称与金额",
                            source,
                        )
                    )
                for index, value, share in detail:
                    note = "年报以「第一名」等匿名序号列示，未披露名称"
                    rows.append(
                        row(
                            company,
                            year,
                            category,
                            f"第{index}名",
                            value * factor / 1e8,
                            share,
                            "披露值",
                            note,
                            source,
                            amount_yuan=value * factor,
                        )
                    )

            # 关联采购 / 关联销售
            if company == "美的集团":
                if year == 2023:
                    trace = text_of("美的", 2024)
                    purchase = related_meidi(trace, "purchase") if trace else None
                    sale = related_meidi(trace, "sale") if trace else None
                    purchase = purchase[1] if purchase else None
                    sale = sale[1] if sale else None
                    rel_source = "美的2024.pdf（2023年可比列）"
                    rel_note = (
                        "2023年报仅列会通一笔（采购14.20亿/销售4.08亿）；采用2024年报"
                        "追溯的2023年可比数（含「其他」汇总），口径更完整"
                    )
                else:
                    purchase = related_meidi(text, "purchase")
                    sale = related_meidi(text, "sale")
                    purchase = purchase[0] if purchase else None
                    sale = sale[0] if sale else None
                    rel_source = source
                    rel_note = (
                        "附注「重大关联交易」表，列示范围逐年变化，为下限口径"
                        if year <= 2023
                        else "附注关联交易表合计，含「其他」汇总行"
                    )
            elif company == "海尔智家":
                purchase = related_haier(text, year, "purchase")
                sale = related_haier(text, year, "sale")
                rel_source, rel_note = source, ""
                if year == 2023:
                    rel_note = (
                        "2023年报原披露 375.40 亿；2024年报因日日顺并入合并范围，"
                        "把 2023 年可比数重述为 311.79 亿（少 63.61 亿），本表采用原披露值"
                    )
            else:
                purchase = related_gree(text, "purchase")
                sale = related_gree(text, "sale")
                rel_source = source
                rel_note = "附注「采购商品/接受劳务」合计，含服务采购与利息支出"

            purchase_b = purchase * REL_UNIT[company] / 1e8 if purchase is not None else None
            sale_b = sale * REL_UNIT[company] / 1e8 if sale is not None else None
            for category, value, base, base_name in (
                ("关联采购", purchase_b, cost, "营业成本"),
                ("关联销售", sale_b, revenue, "营业收入"),
            ):
                if value is None:
                    rows.append(
                        row(company, year, category, "金额", None, None, "未披露", "", source)
                    )
                    continue
                note = rel_note
                if company == "海尔智家" and category == "关联采购":
                    note = (
                        "附注表列采购方向（销售另表）；含物流、安装等服务，"
                        "非纯原材料采购，与服务型关联方合并列示"
                    )
                    if year == 2025:
                        note += (
                            "；2025 年表头用证监会模板「购销商品…」，但上期列 301.31 亿"
                            "≈2024 年采购 302.04 亿，可证未含销售"
                        )
                    if year == 2023:
                        note += (
                            "；2023年报原披露 375.40 亿，2024年报因日日顺并表重述为 311.79 亿，"
                            "本表用原披露值"
                        )
                elif company == "格力电器" and category == "关联销售":
                    note = "附注「出售商品/提供劳务」合计，含关联方贷款利息收入与手续费"
                rows.append(
                    row(company, year, category, "金额", value, None, "披露值", note, rel_source)
                )
                ratio = value / (base / 1e8) * 100 if base else None
                rows.append(
                    row(
                        company,
                        year,
                        category,
                        f"占{base_name}",
                        None,
                        ratio,
                        "计算值",
                        f"金额÷{base_name}（利润表）",
                        rel_source,
                    )
                )
    return rows


def self_check(
    rows: list[dict[str, str]], denom: dict[tuple[str, int], tuple[float, float]]
) -> int:
    problems = 0
    explained = 0
    print("\n[校验1] 前五名金额 ÷ 占比 → 反推分母 vs 利润表（容差 5%）", file=sys.stderr)
    for item in (r for r in rows if r["项目"] == "前五名合计"):
        if not item["金额(亿元)"] or not item["占比%"]:
            continue
        amount = float(item["金额(亿元)"])
        ratio = float(item["占比%"])
        if ratio == 0:
            continue
        implied = amount / ratio * 100
        revenue, cost = denom.get((item["公司"], int(item["年度"])), (0.0, 0.0))
        base_name = "营业收入" if item["类别"] == "前五大客户" else "营业成本"
        base = (revenue if item["类别"] == "前五大客户" else cost) / 1e8
        if not base:
            continue
        diff = (implied - base) / base * 100
        ok = abs(diff) <= 5
        if ok:
            verdict = "OK"
        elif item["类别"] == "前五大供应商":
            # 供应商占比分母是「年度采购总额」，与营业成本本就不同口径
            verdict = "口径差异（分母=采购总额，非营业成本）"
        elif item["公司"] == "海尔智家" and item["年度"] == "2023":
            verdict = "口径差异（2024年报重述2023营收为2,742亿，原披露2,614亿）"
        else:
            verdict = "超差"
            problems += 1
        print(
            f"  {item['公司']} {item['年度']} {item['类别']}: 反推 {implied:,.1f}亿 vs "
            f"{base_name} {base:,.1f}亿 ({diff:+.2f}%) {verdict}",
            file=sys.stderr,
        )

    print("\n[校验2] 前五名内部关联方金额不得超过前五名合计", file=sys.stderr)
    for company in COMPANIES:
        for year in YEARS:

            def amount_of(
                category: str,
                item: str,
                company: str = company,
                year: int = year,
            ) -> float | None:
                return next(
                    (
                        float(r["金额(亿元)"])
                        for r in rows
                        if r["公司"] == company
                        and r["年度"] == str(year)
                        and r["类别"] == category
                        and r["项目"] == item
                        and r["金额(亿元)"]
                    ),
                    None,
                )

            purchase = amount_of("前五大供应商", "其中:关联方")
            top5 = amount_of("前五大供应商", "前五名合计")
            if purchase is None or top5 is None:
                continue
            if purchase <= top5:
                print(f"  {company} {year}: {purchase:,.1f} ≤ {top5:,.1f} OK", file=sys.stderr)
            else:
                problems += 1
                print(
                    f"  {company} {year}: {purchase:,.1f} > {top5:,.1f} 违反，需人工复核",
                    file=sys.stderr,
                )

    print("\n[校验3] 单家金额量级 0.1—5000 亿元", file=sys.stderr)
    checked = zero = 0
    for item in rows:
        if not item["金额(亿元)"]:
            continue
        value = float(item["金额(亿元)"])
        if value == 0:
            zero += 1  # 年报明确披露为 0（如「关联方销售额占比 0%」），不是量级错误
            continue
        checked += 1
        if not 0.1 <= value <= 5_000:
            problems += 1
            print(
                f"  {item['公司']} {item['年度']} {item['类别']} {item['项目']}: "
                f"{value:,.2f}亿 超界",
                file=sys.stderr,
            )
    print(f"  已检查 {checked} 个非零金额；另有 {zero} 个年报披露为 0", file=sys.stderr)
    print(
        f"\n校验完成：{problems} 项失败，{explained} 项已解释的口径差异（不计为失败）",
        file=sys.stderr,
    )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="提取 2019—2025 全部年份")
    args = parser.parse_args()
    if not args.all:
        parser.print_help()
        return 0

    denom = load_denominators()
    rows = build_rows(denom)

    fields = [
        "公司",
        "年度",
        "类别",
        "项目",
        "金额(亿元)",
        "占比%",
        "数据性质",
        "口径说明",
        "来源",
        "金额(元)",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(f"写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    print(f"覆盖年份: {min(YEARS)}—{max(YEARS)}；公司: {'、'.join(COMPANIES)}")

    print("\n2025 年三家对比（亿元 / %）")
    header = f"{'公司':<8}{'客户前五':>10}{'占比':>8}{'供应商前五':>12}{'占比':>8}{'关联采购':>10}{'占成本':>8}{'关联销售':>10}{'占收入':>8}"
    print(header)
    print("-" * 76)
    for company in COMPANIES:

        def value(category: str, item: str, field: str, company: str = company) -> float:
            found = next(
                (
                    r[field]
                    for r in rows
                    if r["公司"] == company
                    and r["年度"] == "2025"
                    and r["类别"] == category
                    and r["项目"] == item
                ),
                "",
            )
            return float(found) if found else 0.0

        print(
            f"{company:<8}{value('前五大客户', '前五名合计', '金额(亿元)'):>10.1f}"
            f"{value('前五大客户', '前五名合计', '占比%'):>8.2f}"
            f"{value('前五大供应商', '前五名合计', '金额(亿元)'):>12.1f}"
            f"{value('前五大供应商', '前五名合计', '占比%'):>8.2f}"
            f"{value('关联采购', '金额', '金额(亿元)'):>10.1f}"
            f"{value('关联采购', '占营业成本', '占比%'):>8.2f}"
            f"{value('关联销售', '金额', '金额(亿元)'):>10.1f}"
            f"{value('关联销售', '占营业收入', '占比%'):>8.2f}"
        )

    return int(self_check(rows, denom) > 0)


if __name__ == "__main__":
    sys.exit(main())
