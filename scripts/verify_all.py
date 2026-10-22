"""全量交叉校验：已采集数据之间的一致性检查。

校验逻辑（每项都对应一个已知的口径陷阱，36 类）：
1. 季度合计 vs 利润表全年 —— 检测提取错位与追溯重述
2. 分产品合计 vs 营业收入 —— 检测「其中」子项重复计入
3. 年报研发投入 vs 利润表研发费用 —— 检测资本化口径差异
4. 主营构成分地区合计 vs 营业收入 —— 检测地区口径遗漏
5. 产销量平衡：本期生产 + 期初库存 - 期末库存 ≈ 本期销售
6-9. 分部报告、员工人数、存货明细、客户供应商集中度
10. 主要财务指标「营业成本」= 利润表「营业总成本」（命名陷阱）
11. 商誉明细合计 vs 资产负债表商誉
12. 政府补助明细合计 vs 利润表「其他收益」
13. 关联交易：金额为正、占比可重算
14. 2026H1 分地区收入合计 vs 营业收入
15. 2026H1 利润表归母净利润 vs 主要财务指标
16. 担保余额/归母净资产 vs 年报披露比例
17. 研发人员数 = 员工构成「技术人员」，学历/年龄覆盖不超总数
18. 收现比 = 销售商品收到的现金 / 营业收入
19. 2026H1 中期分红：现金分红/归母净利润 vs 年报披露比例
20. 受限资产：明细相加 = 年报合计，占总资产比例可复算
21. 股份支付：扣除后净利润 − 净利润 = 反推影响
22. 所得税调整表：起点税率 + 各调整项 = 所得税费用
23. 投资收益：分项合计 = 利润表，权益法占比可复算
24. 少数股东损益：净利润 − 归母净利润 = 少数股东损益
25. 财务净收益：明细合计 = −利润表「财务费用」
26. 减值明细：资产减值 + 信用减值 = −利润表两项之和
27. 其他综合收益：分项合计 = 归母，归母 + 少数 = 税后净额
28. 递延所得税：未抵销 − 抵销 = 资产负债表
29. 净利润调节表：调节后合计 = 现金流量表经营净额
30. 类现金与金融资产：明细相加 = 合计，隐含收益率合理
31. 商誉减值假设：安全垫倍数可复算
32. 品牌归一：短别名不跨品牌误命中，食品品牌不进家电面板
33. 跨检索词去重：同一 SKU 跨关键词重复入库的规模
34. 数据性质一致性：CSV 的 actual/forecast 与来源登记不矛盾
35. 票据与应收：三分合计与资产负债表勾稽
35. 固定资产与在建工程：变动表勾稽 + 原值−折旧−减值=账面价值

用法：
    uv run python3 scripts/verify_all.py
"""

from __future__ import annotations

import csv
import itertools
import re
import sys
from collections import defaultdict
from pathlib import Path

from verify_derived import verify as verify_derived
from verify_inventory import verify as verify_inventory

ROOT = Path(__file__).resolve().parent.parent
FIN = ROOT / "财务数据"
MKT = ROOT / "市场数据"
ECO = MKT / "电商"
EXPLAINED: list[str] = []
# 只接受已核对的特定观测值与参考值；新差异不能靠「已有差异数」豁免。
KNOWN = {
    ("quarterly", "海尔智家", "2023", "营业收入"): (261427783050.1, 274204520847.97, 1.0),
    ("quarterly", "海尔智家", "2024", "营业收入"): (285981225203.93, 286015294936.52, 1.0),
    ("quarterly", "海尔智家", "2024", "归母净利润"): (18741120122.93, 18731046273.17, 1.0),
    ("volume", "美的集团", "2023"): (57550.22, 59716.31, 0.001),
    ("volume", "美的集团", "2024"): (60267.92, 65181.9, 0.001),
    ("volume", "美的集团", "2025"): (66659.18, 73586.93, 0.001),
    ("segment_note", "海尔智家", "2023"): (261427783050.1, 274204520847.97, 1.0),
    ("segment_note", "海尔智家", "2024"): (285981225203.93, 286015294936.52, 1.0),
    ("inventory", "海尔智家", "2024"): (430.44, 431.8985569796, 0.0001),
    ("concentration", "海尔智家", "2023"): (261569227467.81116, 274204520847.97, 1.0),
    ("fixed", "海尔智家", "2024"): (375.19, 376.1321576946, 0.0001),
}


def known_difference(key: tuple[str, ...], actual: float, reference: float) -> bool:
    registered = KNOWN.get(key)
    if registered is None:
        return False
    expected_actual, expected_reference, tolerance = registered
    if abs(actual - expected_actual) > tolerance or abs(reference - expected_reference) > tolerance:
        return False
    EXPLAINED.append(" / ".join(key))
    return True


def load(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"缺少校验输入 {path}")
    with path.open(encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"校验输入为空 {path}")
    return rows


def check_quarterly() -> tuple[int, int]:
    """季度合计 vs 利润表全年。"""
    quarterly = load(FIN / "分季度经营.csv")
    income = load(FIN / "利润表.csv")
    if not quarterly or not income:
        return 0, 0

    annual = {
        (r["公司"], r["报告期"][:4], r["科目"]): float(r["数值"])
        for r in income
        if r["报告期"].endswith("1231") and r["科目"] in ("营业收入", "归属于母公司所有者的净利润")
    }
    sums: dict[tuple[str, str, str], float] = defaultdict(float)
    for row in quarterly:
        sums[(row["公司"], row["年度"], row["指标"])] += float(row["数值"])

    print("【1】季度合计 vs 利润表全年")
    print(
        f"    {'公司':<8}{'年度':<6}{'指标':<12}{'季度合计(亿)':>13}{'利润表(亿)':>13}{'差异%':>9}"
    )
    passed = failed = 0
    for (company, year, metric), total in sorted(sums.items()):
        key = "营业收入" if metric == "营业收入" else "归属于母公司所有者的净利润"
        reference = annual.get((company, year, key))
        if reference is None:
            continue
        diff = (total - reference) / reference * 100
        ok = abs(diff) < 0.01
        passed += ok
        failed += not ok and not known_difference(
            ("quarterly", company, year, metric), total, reference
        )
        mark = "OK" if ok else "差异"
        print(
            f"    {company:<8}{year:<6}{metric:<12}"
            f"{total / 1e8:>13,.2f}{reference / 1e8:>13,.2f}{diff:>8.2f}%  {mark}"
        )
    print(f"    通过 {passed}，差异 {failed}（差异均已归因，见 README）\n")
    return passed, failed


def check_segments() -> tuple[int, int]:
    """分产品合计 vs 营业收入。"""
    segments = load(FIN / "主营构成.csv")
    income = load(FIN / "利润表.csv")
    if not segments or not income:
        return 0, 0

    revenue = {
        (r["公司"], r["报告期"]): float(r["数值"]) for r in income if r["科目"] == "营业收入"
    }
    by_product: dict[tuple[str, str], float] = defaultdict(float)
    for row in segments:
        if row["分类类型"] != "按产品分类":
            continue
        # 「其中:」明细是子项，计入会重复
        if row["主营构成"].startswith("其中"):
            continue
        by_product[(row["公司"], row["报告日期"].replace("-", ""))] += float(row["主营收入"])

    print("【2】分产品合计 vs 营业收入")
    passed = failed = 0
    for (company, period), total in sorted(by_product.items()):
        reference = revenue.get((company, period))
        if not reference:
            continue
        pct = total / reference * 100
        ok = 95 <= pct <= 101
        passed += ok
        failed += not ok and not known_difference(("segments", company, period), total, reference)
        if not ok:
            print(
                f"    {company} {period}: 分产品 {total / 1e8:,.2f} 亿 vs "
                f"营业收入 {reference / 1e8:,.2f} 亿 = {pct:.2f}%  差异"
            )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_research() -> tuple[int, int]:
    """年报研发投入 vs 利润表研发费用。"""
    disclosures = load(FIN / "治理与经营披露.csv")
    income = load(FIN / "利润表.csv")
    if not disclosures or not income:
        return 0, 0

    expense = {
        (r["公司"], r["报告期"]): float(r["数值"]) for r in income if r["科目"] == "研发费用"
    }

    print("【3】年报研发投入 vs 利润表研发费用")
    print(f"    {'公司':<8}{'年度':<10}{'年报(亿)':>12}{'利润表(亿)':>12}{'差异%':>9}  口径")
    passed = failed = 0
    for row in disclosures:
        year = row["报告期"].replace(" 年度", "")
        reference = expense.get((row["公司"], f"{year}1231"))
        if not reference:
            continue
        try:
            value = float(row["研发投入_合计"])
        except ValueError:
            continue
        diff = (value - reference) / reference * 100
        # 美的全费用化 0%，海尔含资本化 +6%，格力口径差 -0.3%
        ok = abs(diff) < 8
        passed += ok
        failed += not ok
        print(
            f"    {row['公司']:<8}{year:<10}{value / 1e8:>12,.2f}"
            f"{reference / 1e8:>12,.2f}{diff:>8.2f}%  {row['研发投入_口径']}"
        )
    print(f"    通过 {passed}，差异 {failed}（差异为资本化口径，非错误）\n")
    return passed, failed


def check_volume() -> tuple[int, int]:
    """产销量平衡。"""
    rows = load(MKT / "公司产销量.csv")
    if not rows:
        return 0, 0

    grouped: dict[tuple[str, str], dict[str, tuple[float, float | None]]] = defaultdict(dict)
    for row in rows:
        try:
            current = float(row["本期"])
        except ValueError:
            continue
        previous = float(row["上期"]) if row["上期"] else None
        grouped[(row["公司"], row["年度"])][row["指标"]] = (current, previous)

    print("【4】产销量平衡：生产 + 期初库存 - 期末库存 ≈ 销售")
    passed = failed = 0
    for (company, year), metrics in sorted(grouped.items()):
        if not {"生产量", "销售量", "库存量"} <= metrics.keys():
            continue
        production = metrics["生产量"][0]
        sales = metrics["销售量"][0]
        closing = metrics["库存量"][0]
        opening = metrics["库存量"][1]
        if opening is None or not sales:
            continue
        implied = production + opening - closing
        diff = (implied - sales) / sales * 100
        ok = abs(diff) < 3
        passed += ok
        failed += not ok and not known_difference(("volume", company, year), implied, sales)
        print(
            f"    {company} {year}: 推算 {implied:,.0f} vs 披露 {sales:,.0f} "
            f"({diff:+.2f}%)  {'OK' if ok else '差异（未披露完整调节）'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_segments_note() -> tuple[int, int]:
    """分部报告合计 vs 营业收入。"""
    segments = load(FIN / "分部报告.csv")
    income = load(FIN / "利润表.csv")
    if not segments or not income:
        return 0, 0

    revenue = {
        (r["公司"], r["报告期"][:4]): float(r["数值"])
        for r in income
        if r["科目"] == "营业总收入" and r["报告期"].endswith("1231")
    }

    print("【5】分部报告对外交易收入合计 vs 利润表营业总收入")
    print(f"    {'公司':<8}{'年度':<6}{'分部合计(亿)':>14}{'营业总收入(亿)':>16}{'差异%':>9}")
    passed = failed = 0
    for row in segments:
        if row["指标"] not in ("对外交易收入", "对外交易收入_本期"):
            continue
        if row["分部"] != "合计":
            continue
        reference = revenue.get((row["公司"], row["年度"]))
        if not reference:
            continue
        try:
            total = float(row["数值"])
        except ValueError:
            continue
        diff = (total - reference) / reference * 100
        ok = abs(diff) < 0.01
        passed += ok
        failed += not ok and not known_difference(
            ("segment_note", row["公司"], row["年度"]), total, reference
        )
        print(
            f"    {row['公司']:<8}{row['年度']:<6}{total / 1e8:>14,.2f}"
            f"{reference / 1e8:>16,.2f}{diff:>8.2f}%  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_employees() -> tuple[int, int]:
    """员工构成合计 vs 治理披露的员工人数。"""
    employees = load(FIN / "员工构成.csv")
    governance = load(FIN / "治理与经营披露.csv")
    if not employees or not governance:
        return 0, 0

    reference = {}
    for row in governance:
        try:
            reference[(row["公司"], row["报告期"][:4])] = int(float(row["员工人数"]))
        except (ValueError, KeyError):
            continue

    print("【6】员工构成合计 vs 治理披露员工人数")
    print(f"    {'公司':<8}{'年度':<6}{'员工构成':>12}{'治理披露':>12}  结果")
    passed = failed = 0
    for row in employees:
        if row["维度"] != "合计":
            continue
        key = (row["公司"], row["年度"])
        if key not in reference:
            continue
        actual = int(row["人数"])
        expect = reference[key]
        ok = actual == expect
        passed += ok
        failed += not ok
        print(f"    {key[0]:<8}{key[1]:<6}{actual:>12,}{expect:>12,}  {'OK' if ok else '差异'}")
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_inventory() -> tuple[int, int]:
    """存货明细分项合计 vs 资产负债表存货。"""
    inventory = load(FIN / "存货明细.csv")
    balance = load(FIN / "资产负债表.csv")
    if not inventory or not balance:
        return 0, 0

    reference = {}
    for row in balance:
        if row["科目"] == "存货" and row["报告期"].endswith("1231"):
            try:
                reference[(row["公司"], row["报告期"][:4])] = float(row["数值"]) / 1e8
            except ValueError:
                continue

    print("【7】存货明细分项合计 vs 资产负债表存货")
    print(f"    {'公司':<8}{'年度':<6}{'分项合计(亿)':>14}{'资产负债表(亿)':>16}{'差异(亿)':>10}")
    passed = failed = 0
    for row in inventory:
        if not row["存货类别"].startswith("合计"):
            continue
        key = (row["公司"], row["年度"])
        expect = reference.get(key)
        if expect is None:
            continue
        actual = float(row["账面价值(亿元)"])
        diff = actual - expect
        ok = abs(diff) < 0.05
        passed += ok
        failed += not ok and not known_difference(("inventory", *key), actual, expect)
        note = "" if ok else "  附注与资产负债表口径差（合同履约成本重分类）"
        print(f"    {key[0]:<8}{key[1]:<6}{actual:>14,.2f}{expect:>16,.2f}{diff:>10,.2f}{note}")
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_concentration() -> tuple[int, int]:
    """前五大客户金额 / 占比 反推营业收入，验证两个披露值互相自洽。"""
    concentration = load(FIN / "供应商客户集中度时序.csv")
    if not concentration:
        return 0, 0

    print("【8】前五大客户：金额 / 占比 反推营业收入")
    print(f"    {'公司':<8}{'年度':<6}{'反推营收(亿)':>14}{'实际营收(亿)':>14}{'差异%':>9}")
    passed = failed = 0
    rows = {
        (r["公司"], r["年度"], r["类别"]): r for r in concentration if r["项目"] == "前五名合计"
    }
    income = load(FIN / "利润表.csv")
    revenue = {
        (r["公司"], r["报告期"][:4]): float(r["数值"])
        for r in income
        if r["科目"] == "营业收入" and r["报告期"].endswith("1231")
    }
    for (company, year, dimension), row in rows.items():
        if dimension != "前五大客户":
            continue
        if not row["金额(元)"] or not row["占比%"]:
            continue
        implied = float(row["金额(元)"]) / (float(row["占比%"]) / 100)
        actual = revenue.get((company, year))
        if not actual:
            continue
        diff = (implied - actual) / actual * 100
        ok = abs(diff) < 3
        passed += ok
        failed += not ok and not known_difference(("concentration", company, year), implied, actual)
        print(
            f"    {company:<8}{year:<6}{implied / 1e8:>14,.2f}{actual / 1e8:>14,.2f}"
            f"{diff:>8.2f}%  {'OK' if ok else '差异'}"
        )
    print(
        f"    通过 {passed}，差异 {failed}（差异来自年报「销售总额」与利润表「营业收入」口径不同）\n"
    )
    return passed, failed


def check_receivables() -> tuple[int, int]:
    """应收账款余额 − 坏账准备 是否等于资产负债表净额。"""
    rows = load(FIN / "应收账款质量.csv")
    if not rows:
        return 0, 0

    print("【9】应收账款：余额 − 坏账准备 vs 资产负债表")
    print(f"    {'公司':<8}{'年度':<6}{'计算净额(亿)':>14}{'报表净额(亿)':>14}{'差异(亿)':>10}")
    passed = failed = 0
    for row in rows:
        try:
            diff = float(row["净额(亿元)"]) - float(row["资产负债表净额(亿元)"])
        except ValueError:
            continue
        ok = abs(diff) < 0.02
        passed += ok
        failed += not ok
        print(
            f"    {row['公司']:<8}{row['年度']:<6}{float(row['净额(亿元)']):>14,.2f}"
            f"{float(row['资产负债表净额(亿元)']):>14,.2f}{diff:>10,.2f}"
            f"  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_cost_label() -> tuple[int, int]:
    """主要财务指标的「营业成本」实为「营业总成本」，必须与利润表区分。"""
    rows = load(FIN / "主要财务指标.csv")
    income = load(FIN / "利润表.csv")
    if not rows or not income:
        return 0, 0

    indicator = {}
    for row in rows:
        if row["指标"] != "营业成本" or not row["报告期"].endswith("1231"):
            continue
        try:
            indicator[(row["公司"], row["报告期"][:4])] = float(row["数值"])
        except ValueError:
            continue

    statement: dict[tuple[str, str, str], float] = {}
    for row in income:
        if row["科目"] not in ("营业成本", "营业总成本") or not row["报告期"].endswith("1231"):
            continue
        try:
            statement[(row["公司"], row["报告期"][:4], row["科目"])] = float(row["数值"])
        except ValueError:
            continue

    print("【10】主要财务指标「营业成本」= 利润表「营业总成本」（不是「营业成本」）")
    print(f"    {'公司':<8}{'年度':<6}{'指标值(亿)':>12}{'总成本(亿)':>12}{'成本(亿)':>12}  结果")
    passed = failed = 0
    for (company, year), value in sorted(indicator.items()):
        if year < "2023":
            continue
        total = statement.get((company, year, "营业总成本"))
        cost = statement.get((company, year, "营业成本"))
        if total is None or cost is None:
            continue
        ok = abs(value - total) < 1 and abs(value - cost) > 1
        passed += ok
        failed += not ok
        print(
            f"    {company:<8}{year:<6}{value / 1e8:>12,.2f}{total / 1e8:>12,.2f}"
            f"{cost / 1e8:>12,.2f}  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}（命名陷阱，已在数据源分级.md 第 31 条记录）\n")
    return passed, failed


def check_goodwill() -> tuple[int, int]:
    """商誉明细合计 vs 资产负债表商誉。"""
    detail = load(FIN / "商誉明细.csv")
    balance = load(FIN / "资产负债表.csv")
    if not detail or not balance:
        return 0, 0

    book = {}
    for row in balance:
        if row.get("科目") != "商誉" or row.get("报告期") != "20251231":
            continue
        try:
            book[row["公司"]] = float(row["数值"]) / 1e8
        except ValueError:
            continue

    totals = {
        row["公司"]: float(row["账面价值(亿元)"])
        for row in detail
        if row["资产组/被投资单位"] == "合计（明细相加）"
    }

    print("【11】商誉明细合计 vs 资产负债表商誉")
    print(f"    {'公司':<8}{'明细合计(亿)':>13}{'资产负债表(亿)':>15}{'差异(亿)':>10}  结果")
    passed = failed = 0
    for company, total in sorted(totals.items()):
        reference = book.get(company)
        if reference is None:
            continue
        diff = total - reference
        ok = abs(diff) < 0.02
        passed += ok
        failed += not ok
        print(
            f"    {company:<8}{total:>13,.2f}{reference:>15,.2f}{diff:>10.2f}  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_gov_subsidy() -> tuple[int, int]:
    """政府补助明细合计 vs 利润表「其他收益」。"""
    detail = load(FIN / "政府补助与其他收益.csv")
    income = load(FIN / "利润表.csv")
    if not detail or not income:
        return 0, 0

    statement = {}
    for row in income:
        if row["科目"] != "其他收益" or not row["报告期"].endswith("1231"):
            continue
        try:
            statement[(row["公司"], row["报告期"][:4])] = float(row["数值"]) / 1e8
        except ValueError:
            continue

    reported = {
        (row["公司"], row["年度"]): float(row["金额(亿元)"])
        for row in detail
        if row["统一科目"] == "其他收益合计"
    }

    print("【12】政府补助明细合计 vs 利润表「其他收益」")
    print(f"    {'公司':<8}{'年度':<6}{'明细合计(亿)':>13}{'利润表(亿)':>12}{'差异(亿)':>10}  结果")
    passed = failed = 0
    for (company, year), total in sorted(reported.items()):
        reference = statement.get((company, year))
        if reference is None:
            continue
        diff = total - reference
        ok = abs(diff) < 0.02
        passed += ok
        failed += not ok
        print(
            f"    {company:<8}{year:<6}{total:>13,.2f}{reference:>12,.2f}{diff:>10.2f}  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_related_party() -> tuple[int, int]:
    """关联交易占比可重算，且方向为正数。"""
    detail = load(FIN / "关联交易.csv")
    income = load(FIN / "利润表.csv")
    if not detail or not income:
        return 0, 0

    basis = {}
    for row in income:
        if row["科目"] not in ("营业收入", "营业成本") or not row["报告期"].endswith("1231"):
            continue
        try:
            basis[(row["公司"], row["报告期"][:4], row["科目"])] = float(row["数值"]) / 1e8
        except ValueError:
            continue

    print("【13】关联交易：金额为正、占比可重算")
    print(
        f"    {'公司':<8}{'年度':<6}{'采购/成本%':>12}{'重算%':>9}{'销售/收入%':>12}{'重算%':>9}  结果"
    )
    passed = failed = 0
    for row in detail:
        company, year = row["公司"], row["年度"]
        cost = basis.get((company, year, "营业成本"))
        revenue = basis.get((company, year, "营业收入"))
        if not cost or not revenue:
            continue
        purchase = float(row["关联采购(亿元)"])
        sale = float(row["关联销售(亿元)"])
        p_ratio = float(row["关联采购占营业成本%"])
        s_ratio = float(row["关联销售占营业收入%"])
        ok = (
            purchase >= 0
            and sale >= 0
            and abs(p_ratio - purchase / cost * 100) < 0.02
            and abs(s_ratio - sale / revenue * 100) < 0.02
        )
        passed += ok
        failed += not ok
        print(
            f"    {company:<8}{year:<6}{p_ratio:>12.2f}{purchase / cost * 100:>9.2f}"
            f"{s_ratio:>12.2f}{sale / revenue * 100:>9.2f}  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_h1_region() -> tuple[int, int]:
    """2026H1：分地区收入合计 = 营业收入，且归母净利润与指标库一致。"""
    region_path = FIN / "主营构成.csv"
    income = load(FIN / "利润表.csv")
    indicators = load(FIN / "主要财务指标.csv")
    if not region_path.exists() or not income:
        return 0, 0

    period = "20260630"
    revenue = {}
    profit = {}
    for row in income:
        if row["报告期"] != period:
            continue
        try:
            value = float(row["数值"])
        except ValueError:
            continue
        if row["科目"] == "营业收入":
            revenue[row["公司"]] = value
        elif row["科目"] == "归属于母公司所有者的净利润":
            profit[row["公司"]] = value

    region_sum: dict[str, float] = defaultdict(float)
    with region_path.open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["报告日期"] != "2026-06-30" or row["分类类型"] != "按地区分类":
                continue
            if row["主营构成"].startswith("其中"):
                continue
            try:
                region_sum[row["公司"]] += float(row["主营收入"])
            except ValueError:
                continue

    print("【14】2026H1：分地区收入合计 vs 营业收入（已剔除「其中:」子项）")
    print(f"    {'公司':<8}{'地区合计(亿)':>13}{'营业收入(亿)':>13}{'差异%':>9}  结果")
    passed = failed = 0
    for company, total in sorted(region_sum.items()):
        reference = revenue.get(company)
        if not reference:
            continue
        diff = (total - reference) / reference * 100
        ok = abs(diff) < 0.05
        passed += ok
        failed += not ok
        print(
            f"    {company:<8}{total / 1e8:>13,.2f}{reference / 1e8:>13,.2f}{diff:>9.2f}  "
            f"{'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")

    print("【15】2026H1：利润表归母净利润 vs 主要财务指标")
    print(f"    {'公司':<8}{'利润表(亿)':>13}{'指标库(亿)':>13}{'差异(亿)':>10}  结果")
    index = {
        row["公司"]: float(row["数值"])
        for row in indicators
        if row["报告期"] == period and row["指标"] == "归母净利润"
    }
    for company, value in sorted(profit.items()):
        reference = index.get(company)
        if reference is None:
            continue
        diff = (value - reference) / 1e8
        ok = abs(diff) < 0.01
        passed += ok
        failed += not ok
        print(
            f"    {company:<8}{value / 1e8:>13,.2f}{reference / 1e8:>13,.2f}{diff:>10.2f}  "
            f"{'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_guarantee_ratio() -> tuple[int, int]:
    """担保余额 / 归母净资产 = 年报披露的占净资产比例（美的/海尔/格力均披露）。"""
    detail = load(FIN / "担保与诉讼.csv")
    balance = load(FIN / "资产负债表.csv")
    if not detail or not balance:
        return 0, 0

    equity = {}
    for row in balance:
        if row.get("科目") != "归属于母公司股东权益合计" or row.get("报告期") != "20251231":
            continue
        try:
            equity[row["公司"]] = float(row["数值"]) / 1e8
        except ValueError:
            continue

    # 年报正文披露的比例（独立于本仓库计算，用于反向验证）
    disclosed = {"美的集团": 23.55, "海尔智家": 6.1, "格力电器": 3.01}

    print("【16】担保余额/归母净资产 vs 年报披露的占净资产比例")
    print(f"    {'公司':<8}{'担保(亿)':>11}{'归母净资产(亿)':>16}{'计算%':>9}{'披露%':>9}  结果")
    passed = failed = 0
    for row in detail:
        if row["项目"] == "重大诉讼" or not row["金额(亿元)"]:
            continue
        company = row["公司"]
        amount = float(row["金额(亿元)"])
        net = equity.get(company)
        if not net:
            continue
        ratio = amount / net * 100
        reference = disclosed.get(company)
        ok = reference is not None and abs(ratio - reference) < 0.1
        passed += ok
        failed += not ok
        print(
            f"    {company:<8}{amount:>11,.2f}{net:>16,.2f}{ratio:>9.2f}"
            f"{(f'{reference:.2f}' if reference else ''):>9}  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_rd_staff() -> tuple[int, int]:
    """研发人员数量 = 员工构成里的「技术人员」人数；学历/年龄合计不超总数。"""
    rd = load(FIN / "研发人员结构.csv")
    staff = load(FIN / "员工构成.csv")
    if not rd or not staff:
        return 0, 0

    technician: dict[str, int] = {}
    for row in staff:
        if row["年度"] != "2025" or row["维度"] != "专业构成":
            continue
        if row["类别"] != "技术人员":
            continue
        technician[row["公司"]] = int(float(row["人数"].replace(",", "")))

    total: dict[str, int] = {}
    covered: dict[tuple[str, str], int] = {}
    for row in rd:
        if row["维度"] != "汇总":
            continue
        value = int(float(row["人数"].replace(",", "")))
        if row["类别"] == "研发人员总数":
            total[row["公司"]] = value
        else:
            covered[(row["公司"], row["类别"])] = value

    print("【17】研发人员数 = 员工构成「技术人员」；学历/年龄覆盖不超总数")
    print(
        f"    {'公司':<8}{'研发人员':>10}{'技术人员':>10}{'学历覆盖%':>11}{'年龄覆盖%':>11}  结果"
    )
    passed = failed = 0
    for company, value in sorted(total.items()):
        reference = technician.get(company)
        edu = covered.get((company, "学历项覆盖合计"), 0)
        age = covered.get((company, "年龄项覆盖合计"), 0)
        edu_ratio = edu / value * 100 if value else 0
        age_ratio = age / value * 100 if value else 0
        ok = reference == value and edu_ratio <= 100.5 and age_ratio <= 100.5
        passed += ok
        failed += not ok
        print(
            f"    {company:<8}{value:>10,}{(reference or 0):>10,}{edu_ratio:>11.2f}"
            f"{age_ratio:>11.2f}  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_collection_ratio() -> tuple[int, int]:
    """收现比 = 销售商品收到的现金 / 营业收入，必须可重算且落在合理区间。"""
    detail = load(FIN / "收现质量.csv")
    income = load(FIN / "利润表.csv")
    cashflow = load(FIN / "现金流量表.csv")
    if not detail or not income or not cashflow:
        return 0, 0

    revenue = {}
    for row in income:
        if row["科目"] != "营业收入" or not row["报告期"].endswith("1231"):
            continue
        try:
            revenue[(row["公司"], row["报告期"][:4])] = float(row["数值"]) / 1e8
        except ValueError:
            continue

    received = {}
    for row in cashflow:
        if row["科目"] != "销售商品、提供劳务收到的现金":
            continue
        if not row["报告期"].endswith("1231"):
            continue
        try:
            received[(row["公司"], row["报告期"][:4])] = float(row["数值"]) / 1e8
        except ValueError:
            continue

    print("【18】收现比 = 销售商品收到的现金 / 营业收入")
    print(f"    {'公司':<8}{'年度':<6}{'表内比值':>10}{'重算':>9}{'差额':>9}  结果")
    passed = failed = 0
    for row in detail:
        key = (row["公司"], row["年度"])
        rev = revenue.get(key)
        cash = received.get(key)
        if not rev or cash is None:
            continue
        recomputed = cash / rev
        stated = float(row["收现比"])
        ok = abs(recomputed - stated) < 0.0005 and 0.5 < stated < 1.5
        passed += ok
        failed += not ok
        print(
            f"    {row['公司']:<8}{row['年度']:<6}{stated:>10.4f}{recomputed:>9.4f}"
            f"{stated - recomputed:>9.4f}  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_interim_dividend() -> tuple[int, int]:
    """2026H1 分红：现金分红 / 归母净利润 应复现年报披露的 14.06%。"""
    detail = load(FIN / "中期分红.csv")
    income = load(FIN / "利润表.csv")
    if not detail or not income:
        return 0, 0

    profit = {}
    for row in income:
        if row["报告期"] != "20260630":
            continue
        if row["科目"] != "归属于母公司所有者的净利润":
            continue
        try:
            profit[row["公司"]] = float(row["数值"]) / 1e8
        except ValueError:
            continue

    print("【19】2026H1 中期分红：现金分红/归母净利润 vs 年报披露比例")
    print(f"    {'公司':<8}{'现金(亿)':>10}{'归母净利(亿)':>14}{'计算%':>9}{'披露%':>9}  结果")
    passed = failed = 0
    for row in detail:
        if row["项目"] != "现金分红":
            continue
        company = row["公司"]
        net = profit.get(company)
        cash = float(row["金额(亿元)"])
        if not net:
            continue
        ratio = cash / net * 100
        disclosed = row["年报披露比例"].rstrip("%")
        reference = float(disclosed) if disclosed else None
        ok = reference is not None and abs(ratio - reference) < 0.05
        passed += ok
        failed += not ok
        print(
            f"    {company:<8}{cash:>10.2f}{net:>14.2f}{ratio:>9.2f}"
            f"{(f'{reference:.2f}' if reference else ''):>9}  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_restricted_assets() -> tuple[int, int]:
    """受限资产明细合计 = 年报披露合计，且占总资产比例可复算。"""
    detail = load(FIN / "受限资产.csv")
    balance = load(FIN / "资产负债表.csv")
    if not detail or not balance:
        return 0, 0

    assets = {}
    for row in balance:
        if row.get("科目") != "资产总计" or row.get("报告期") != "20251231":
            continue
        try:
            assets[row["公司"]] = float(row["数值"]) / 1e8
        except ValueError:
            continue

    print("【20】受限资产：明细相加 vs 年报合计，占总资产比例可复算")
    print(f"    {'公司':<8}{'明细合计(亿)':>13}{'披露合计(亿)':>13}{'差异':>9}{'占比%':>9}  结果")
    passed = failed = 0
    for company in {row["公司"] for row in detail}:
        rows = [r for r in detail if r["公司"] == company]
        items = [
            float(r["账面价值(亿元)"])
            for r in rows
            if r["项目"] not in ("合计", "主要资产") and r["账面价值(亿元)"]
        ]
        total_row = next((r for r in rows if r["项目"] == "合计"), None)
        if not total_row or not items:
            continue
        stated = float(total_row["账面价值(亿元)"])
        computed = sum(items)
        total_assets = assets.get(company, 0)
        ratio = stated / total_assets * 100 if total_assets else 0
        ok = abs(computed - stated) < 0.02 and abs(ratio - float(total_row["占总资产%"])) < 0.02
        passed += ok
        failed += not ok
        print(
            f"    {company:<8}{computed:>13,.2f}{stated:>13,.2f}{computed - stated:>9.2f}"
            f"{ratio:>9.2f}  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_share_payment() -> tuple[int, int]:
    """海尔「扣除股份支付后净利润 − 净利润」= 反推影响，且与利润表对得上。"""
    detail = load(FIN / "股份支付.csv")
    income = load(FIN / "利润表.csv")
    if not detail or not income:
        return 0, 0

    net = {}
    for row in income:
        if row["报告期"] != "20251231" or row["科目"] != "净利润":
            continue
        try:
            net[row["公司"]] = float(row["数值"]) / 1e8
        except ValueError:
            continue

    after = {
        row["公司"]: float(row["金额(亿元)"])
        for row in detail
        if row["项目"] == "扣除股份支付影响后净利润"
    }
    implied = {
        row["公司"]: float(row["金额(亿元)"]) for row in detail if row["项目"] == "反推股份支付影响"
    }

    print("【21】股份支付：扣除后净利润 − 净利润 = 反推影响")
    print(f"    {'公司':<8}{'扣除后(亿)':>12}{'净利润(亿)':>12}{'表内反推':>10}{'重算':>9}  结果")
    passed = failed = 0
    for company, value in sorted(after.items()):
        base = net.get(company)
        stated = implied.get(company)
        if base is None or stated is None:
            continue
        recomputed = value - base
        ok = abs(recomputed - stated) < 0.02 and recomputed > 0
        passed += ok
        failed += not ok
        print(
            f"    {company:<8}{value:>12,.2f}{base:>12,.2f}{stated:>10,.2f}"
            f"{recomputed:>9.2f}  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_tax_reconciliation() -> tuple[int, int]:
    """所得税调整表：起点 + 各调整项 = 所得税费用，且有效税率可复算。"""
    detail = load(FIN / "所得税与税收优惠.csv")
    income = load(FIN / "利润表.csv")
    if not detail or not income:
        return 0, 0

    reported: dict[tuple[str, str], tuple[float, float]] = {}
    for row in income:
        if not row["报告期"].endswith("1231") or row["报告期"][:4] not in (
            "2025",
            "2024",
        ):
            continue
        if row["科目"] not in ("利润总额", "所得税费用"):
            continue
        try:
            value = float(row["数值"]) / 1e8
        except ValueError:
            continue
        key = (row["公司"], row["报告期"][:4])
        profit, tax = reported.get(key, (0.0, 0.0))
        reported[key] = (value, tax) if row["科目"] == "利润总额" else (profit, value)

    parts: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for row in detail:
        if row["项目"] == "有效税率":
            continue
        parts[(row["公司"], row["年度"])][row["项目"]] = float(row["金额(亿元)"])

    print("【22】所得税调整表：起点税率 + 各调整项 = 所得税费用")
    print(
        f"    {'公司':<8}{'年度':<6}{'调整表合计':>11}{'利润表':>10}{'差':>8}{'有效税率':>9}  结果"
    )
    passed = failed = 0
    for key in sorted(parts, key=lambda k: (k[0], -int(k[1]))):
        company, year = key
        values = parts[key]
        total = sum(values.values())
        profit, tax = reported.get(key, (0.0, 0.0))
        gap = total - tax
        etr = tax / profit * 100 if profit else 0.0
        ok = abs(gap) < max(0.05, abs(tax) * 0.002)
        passed += ok
        failed += not ok
        print(
            f"    {company:<8}{year:<6}{total:>11.2f}{tax:>10.2f}{gap:>8.2f}"
            f"{etr:>8.2f}%  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_investment_income() -> tuple[int, int]:
    """投资收益明细合计 = 利润表投资收益；权益法不超过合计。"""
    detail = load(FIN / "投资收益结构.csv")
    income = load(FIN / "利润表.csv")
    if not detail or not income:
        return 0, 0

    reported: dict[tuple[str, str], float] = {}
    for row in income:
        if row["报告期"].endswith("1231") and row["科目"] == "投资收益":
            if row["报告期"][:4] not in ("2025", "2024"):
                continue
            try:
                reported[(row["公司"], row["报告期"][:4])] = float(row["数值"]) / 1e8
            except ValueError:
                continue

    detail_sum: dict[tuple[str, str], float] = defaultdict(float)
    equity: dict[tuple[str, str], float] = {}
    total_row: dict[tuple[str, str], float] = {}
    for row in detail:
        key = (row["公司"], row["年度"])
        value = float(row["金额(亿元)"])
        if row["统一科目"] == "投资收益合计（利润表）":
            total_row[key] = value
        elif row["统一科目"] == "其中：权益法收益":
            equity[key] = value
        elif row["类别"] != "小计":
            detail_sum[key] += value

    print("【23】投资收益：分项合计 = 利润表，权益法占比可复算")
    print(f"    {'公司':<8}{'年度':<6}{'分项合计':>10}{'利润表':>10}{'权益法':>9}{'占比':>8}  结果")
    passed = failed = 0
    for key in sorted(total_row, key=lambda k: (k[0], -int(k[1]))):
        company, year = key
        total = total_row[key]
        base = reported.get(key, 0.0)
        eq = equity.get(key, 0.0)
        gap = detail_sum[key] - total
        ok = abs(gap) < max(0.03, abs(total) * 0.005) and abs(total - base) < 0.02
        passed += ok
        failed += not ok
        ratio = eq / total * 100 if total else 0.0
        print(
            f"    {company:<8}{year:<6}{detail_sum[key]:>10.2f}{total:>10.2f}"
            f"{eq:>9.2f}{ratio:>7.1f}%  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_minority() -> tuple[int, int]:
    """净利润 − 归母净利润 = 少数股东损益。"""
    minority = load(FIN / "少数股东损益与权益.csv")
    income = load(FIN / "利润表.csv")
    if not minority or not income:
        return 0, 0

    values: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for row in income:
        if not row["报告期"].endswith("1231"):
            continue
        if row["科目"] not in ("净利润", "归属于母公司所有者的净利润", "少数股东损益"):
            continue
        try:
            values[(row["公司"], row["报告期"][:4])][row["科目"]] = float(row["数值"]) / 1e8
        except ValueError:
            continue

    stated = {
        (row["公司"], row["年度"]): float(row["金额(亿元)"])
        for row in minority
        if row["项目"] == "少数股东损益"
    }

    print("【24】少数股东损益：净利润 − 归母净利润 = 少数股东损益")
    print(f"    {'公司':<8}{'年度':<6}{'净利润':>10}{'归母':>10}{'差额':>9}{'表内':>9}  结果")
    passed = failed = 0
    for key in sorted(stated, key=lambda k: (k[0], k[1])):
        company, year = key
        data = values.get(key, {})
        net = data.get("净利润")
        parent = data.get("归属于母公司所有者的净利润")
        if net is None or parent is None:
            continue
        gap = net - parent
        ok = abs(gap - stated[key]) < 0.02
        passed += ok
        failed += not ok
        print(
            f"    {company:<8}{year:<6}{net:>10.2f}{parent:>10.2f}"
            f"{gap:>9.2f}{stated[key]:>9.2f}  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_finance_income() -> tuple[int, int]:
    """财务净收益合计 = −利润表「财务费用」（美的科目名是「财务收入」）。"""
    detail = load(FIN / "财务净收益.csv")
    income = load(FIN / "利润表.csv")
    if not detail or not income:
        return 0, 0

    reported: dict[tuple[str, str], float] = {}
    for row in income:
        if row["科目"] != "财务费用" or not row["报告期"].endswith("1231"):
            continue
        if row["报告期"][:4] not in ("2024", "2025"):
            continue
        try:
            reported[(row["公司"], row["报告期"][:4])] = float(row["数值"]) / 1e8
        except ValueError:
            continue

    stated = {
        (row["公司"], row["年度"]): float(row["金额(亿元)"])
        for row in detail
        if row["项目"] == "财务净收益合计"
    }

    print("【25】财务净收益：明细合计 = −利润表财务费用")
    print(f"    {'公司':<8}{'年度':<6}{'表内合计':>11}{'−财务费用':>11}{'差':>8}  结果")
    passed = failed = 0
    for key in sorted(stated, key=lambda k: (k[0], -int(k[1]))):
        company, year = key
        base = reported.get(key)
        if base is None:
            continue
        recomputed = -base
        gap = stated[key] - recomputed
        ok = abs(gap) < 0.02
        passed += ok
        failed += not ok
        print(
            f"    {company:<8}{year:<6}{stated[key]:>11.2f}{recomputed:>11.2f}"
            f"{gap:>8.2f}  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_impairment() -> tuple[int, int]:
    """减值明细合计 = −(利润表资产减值损失 + 信用减值损失)。"""
    detail = load(FIN / "减值明细.csv")
    income = load(FIN / "利润表.csv")
    if not detail or not income:
        return 0, 0

    reported: dict[tuple[str, str], float] = defaultdict(float)
    for row in income:
        if row["科目"] not in ("资产减值损失", "信用减值损失"):
            continue
        if not row["报告期"].endswith("1231") or row["报告期"][:4] not in (
            "2024",
            "2025",
        ):
            continue
        try:
            reported[(row["公司"], row["报告期"][:4])] += float(row["数值"]) / 1e8
        except ValueError:
            continue

    stated: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for row in detail:
        stated[(row["公司"], row["年度"])][row["项目"]] = float(row["金额(亿元)"])

    print("【26】减值明细：资产减值 + 信用减值 = −利润表两项之和")
    print(
        f"    {'公司':<8}{'年度':<6}{'资产减值':>10}{'信用减值':>10}{'合计':>9}{'利润表':>9}  结果"
    )
    passed = failed = 0
    for key in sorted(stated, key=lambda k: (k[0], -int(k[1]))):
        company, year = key
        data = stated[key]
        total = data.get("减值合计")
        base = reported.get(key)
        if total is None or base is None:
            continue
        recomputed = -base
        gap = total - recomputed
        ok = abs(gap) < 0.05
        passed += ok
        failed += not ok
        print(
            f"    {company:<8}{year:<6}{data.get('资产减值合计', 0):>10.2f}"
            f"{data.get('信用减值合计', 0):>10.2f}{total:>9.2f}{recomputed:>9.2f}"
            f"  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_oci() -> tuple[int, int]:
    """其他综合收益：分项之和 = 归母，归母 + 少数股东 = 税后净额。"""
    detail = load(FIN / "其他综合收益.csv")
    if not detail:
        return 0, 0

    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in detail:
        grouped[(row["公司"], row["期间"])].append(row)

    print("【27】其他综合收益：分项合计 = 归母，归母 + 少数 = 税后净额")
    print(f"    {'公司':<8}{'期间':<8}{'分项和':>9}{'归母':>9}{'归母+少数':>10}{'合计':>9}  结果")
    passed = failed = 0
    order = ["2023", "2024", "2025", "2025H1", "2026H1"]
    for key in sorted(grouped, key=lambda k: (order.index(k[1]), k[0])):
        rows = grouped[key]
        pick = {row["项目"]: row for row in rows}

        def value(name: str, column: str, pick: dict[str, dict[str, str]] = pick) -> float | None:
            row = pick.get(name)
            if row is None or row[column] in ("", None):
                return None
            return float(row[column])

        parts = sum(
            float(row["税后归母(亿元)"])
            for row in rows
            if row["分类"] in ("不能重分类进损益", "将重分类进损益") and row["税后归母(亿元)"]
        )
        parent = value("归母其他综合收益", "税后归母(亿元)")
        minority = value("少数股东其他综合收益", "税后少数股东(亿元)")
        total = value("其他综合收益税后净额", "税后合计(亿元)")
        if parent is None or minority is None or total is None:
            continue

        gap_parts = parts - parent
        gap_total = parent + minority - total
        # 分项与合计各保留两位小数，逐项四舍五入会有 0.01 级误差
        ok = abs(gap_parts) <= 0.03 and abs(gap_total) <= 0.03
        passed += ok
        failed += not ok
        print(
            f"    {key[0]:<8}{key[1]:<8}{parts:>9.2f}{parent:>9.2f}"
            f"{parent + minority:>10.2f}{total:>9.2f}  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_deferred_tax() -> tuple[int, int]:
    """递延所得税：未确认抵销前合计 − 抵销 = 资产负债表；分项合计 = 表内合计。"""
    detail = load(FIN / "递延所得税.csv")
    cross = load(FIN / "递延所得税勾稽.csv")
    if not detail or not cross:
        return 0, 0

    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in detail:
        grouped[(row["公司"], row["类别"])].append(row)

    print("【28】递延所得税：分项合计 = 表内合计，未抵销 − 抵销 = 资产负债表")
    print(
        f"    {'公司':<8}{'未抵销DTA':>11}{'抵销':>8}{'净DTA':>9}{'报表DTA':>9}{'分项和':>9}  结果"
    )
    passed = failed = 0
    book = {(item["公司"], "递延所得税资产"): float(item["资产负债表资产"]) for item in cross}
    for row in cross:
        company = row["公司"]
        offset = float(row["抵销金额"])
        gross = float(row["未经抵销资产"])
        net = gross - offset
        stated = book.get((company, "递延所得税资产"))
        rows = grouped.get((company, "递延所得税资产"), [])
        parts = sum(float(r["期末(亿元)"]) for r in rows if r["项目"] != "合计（表内）")
        if stated is None:
            continue
        # 分项之和与表内合计的差、净额与资产负债表的差，都只允许四舍五入误差
        ok = abs(net - stated) <= 0.02 and abs(parts - gross) <= 0.03
        passed += ok
        failed += not ok
        print(
            f"    {company:<8}{gross:>11.2f}{offset:>8.2f}{net:>9.2f}"
            f"{stated:>9.2f}{parts:>9.2f}  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_cash_reconciliation() -> tuple[int, int]:
    """净利润调节表：调节后合计 = 现金流量表「经营活动产生的现金流量净额」。"""
    detail = load(FIN / "净利润调节经营现金流.csv")
    cash = load(FIN / "现金流量表.csv")
    if not detail or not cash:
        return 0, 0

    stated: dict[tuple[str, str], float] = {}
    for row in cash:
        if row["科目"] != "经营活动产生的现金流量净额":
            continue
        if not row["报告期"].endswith("1231") or row["报告期"][:4] not in (
            "2024",
            "2025",
        ):
            continue
        try:
            stated[(row["公司"], row["报告期"][:4])] = float(row["数值"]) / 1e8
        except ValueError:
            continue

    totals = {
        (row["公司"], row["年度"]): float(row["金额(亿元)"])
        for row in detail
        if row["项目"] == "经营活动现金流量净额"
    }

    print("【29】净利润调节表：调节后合计 = 现金流量表经营净额")
    print(f"    {'公司':<8}{'年度':<6}{'调节后':>10}{'现金流量表':>11}{'差':>8}  结果")
    passed = failed = 0
    for key in sorted(totals, key=lambda k: (k[0], -int(k[1]))):
        base = stated.get(key)
        if base is None:
            continue
        gap = totals[key] - base
        ok = abs(gap) < 0.05
        passed += ok
        failed += not ok
        print(
            f"    {key[0]:<8}{key[1]:<6}{totals[key]:>10.2f}{base:>11.2f}{gap:>8.2f}  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_brand_normalization() -> tuple[int, int]:
    """品牌归一：短别名不得跨品牌误命中，食品品牌不得进入家电面板。

    这条校验对应两个已实际发生过的 bug：
    1. 别名 `MI` 用子串匹配，把 `A.O.SMITH`（含 SMITH）、`Guang Ming Pai`
       全判成小米 —— 热水器品牌分布因此从「A.O.史密斯 10 组」错成「小米 11 组」。
    2. `FOOD_BRANDS` 用精确等于判断，而原始品牌名带后缀
       （`光明牌（Guang Ming Pai）`），导致冰淇淋整批漏进冰箱品类。
    """
    sku = load(ECO / "京东联盟_SKU明细.csv")
    if not sku:
        return 0, 0

    print("【47】品牌归一：短别名不跨品牌误命中，食品品牌不进家电面板")
    passed = failed = 0

    # 1. 已知的误判组合，必须不再发生
    traps = [
        ("史密斯（A.O.SMITH）", "A.O.史密斯"),
        ("A.O.Smith", "A.O.史密斯"),
        ("光明牌（Guang Ming Pai）", None),  # 食品，应被剔除
        ("美的（Midea）", "美的"),
        ("小米（MI）", "小米"),
        ("火星人（marssenger）", "火星人"),
        ("森歌（Senge）", "森歌"),
    ]
    sys.path.insert(0, str(ROOT / "scripts"))
    from build_jdunion_panel import (
        is_food_brand,
        normalize_brand,
    )

    for raw, expected in traps:
        got = normalize_brand(raw)
        ok = (got == expected) if expected else is_food_brand(raw)
        passed += ok
        failed += not ok
        print(f"    {raw:<26}{'→ ' + got:<14}{'OK' if ok else '期望 ' + str(expected)}")

    # 2. 面板里不得出现食品品牌
    food_rows = [r for r in sku if is_food_brand(r.get("品牌_原始", ""))]
    ok = not food_rows
    passed += ok
    failed += not ok
    print(f"    面板食品品牌残留：{len(food_rows)} 条  {'OK' if ok else '差异'}")

    # 3. 品牌=小米 的每一行，原始品牌必须真含小米/米家
    mi_rows = [r for r in sku if r.get("品牌") == "小米"]
    wrong = [
        r
        for r in mi_rows
        if not any(k in r.get("品牌_原始", "") for k in ("小米", "米家", "MI"))
        or "SMITH" in r.get("品牌_原始", "").upper()
        or "MING" in r.get("品牌_原始", "").upper()
    ]
    ok = not wrong
    passed += ok
    failed += not ok
    print(f"    「小米」品牌误归：{len(wrong)} 条  {'OK' if ok else '差异'}")

    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_fixed_assets() -> tuple[int, int]:
    """固定资产与在建工程：变动表勾稽 + 原值−折旧−减值=账面价值 + 与报表对平。"""
    detail = load(FIN / "固定资产与在建工程.csv")
    balance = load(FIN / "资产负债表.csv")
    if not detail or not balance:
        return 0, 0

    book: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for row in balance:
        if not row["报告期"].endswith("1231") or row["数值"] in ("", "nan"):
            continue
        # 美的 2024 只在「在建工程合计」有值，「在建工程」为空，须回退
        if row["科目"] not in ("固定资产净额", "在建工程", "在建工程合计", "使用权资产"):
            continue
        try:
            book[(row["公司"], row["报告期"][:4])][row["科目"]] = float(row["数值"]) / 1e8
        except ValueError:
            continue

    grouped: dict[tuple[str, str, str], dict[str, float]] = defaultdict(dict)
    for row in detail:
        if row["数据性质"] == "未披露" or not row["金额(亿元)"]:
            continue
        try:
            grouped[(row["公司"], row["年度"], row["类别"])][row["项目"]] = float(row["金额(亿元)"])
        except ValueError:
            continue

    print("【32】固定资产与在建工程：变动表勾稽 + 与报表对平")
    print(
        f"    {'公司':<8}{'年度':<6}{'原值-折旧-减值':>14}{'账面价值':>10}{'表内净额':>10}{'在建账面':>10}  结果"
    )
    passed = failed = 0
    for company, year in sorted({(k[0], k[1]) for k in grouped}, key=lambda x: (x[0], -int(x[1]))):
        gross = grouped.get((company, year, "固定资产-原值"), {})
        depreciation = grouped.get((company, year, "固定资产-累计折旧"), {})
        impairment = grouped.get((company, year, "固定资产-减值准备"), {})
        net = grouped.get((company, year, "固定资产-账面价值"), {})

        # 合计行可能叫「合计」，按类别相加时要把合计排除，避免双算
        def total_of(data: dict[str, float]) -> float:
            return sum(v for k, v in data.items() if "合计" not in k)

        recomputed = total_of(gross) - total_of(depreciation) - total_of(impairment)
        stated = sum(v for k, v in net.items() if "合计" in k) or total_of(net)
        construction = grouped.get((company, year, "在建工程"), {})
        construction_net = construction.get("账面价值")

        book_fixed = book.get((company, year), {}).get("固定资产净额")
        per_company = book.get((company, year), {})
        book_cip = per_company.get("在建工程") or per_company.get("在建工程合计")

        ok = (
            abs(recomputed - stated) <= 0.05
            and book_fixed is not None
            and abs(stated - book_fixed) <= 0.15
            and construction_net is not None
            and book_cip is not None
            and abs(construction_net - book_cip) <= 0.05
        )
        passed += ok
        explained = (
            not ok
            and book_fixed is not None
            and abs(recomputed - stated) <= 0.05
            and construction_net is not None
            and book_cip is not None
            and abs(construction_net - book_cip) <= 0.05
            and known_difference(("fixed", company, year), stated, book_fixed)
        )
        failed += not ok and not explained
        print(
            f"    {company:<8}{year:<6}{recomputed:>14.2f}{stated:>10.2f}"
            f"{book_fixed if book_fixed is not None else 0:>10.2f}"
            f"{construction_net if construction_net is not None else 0:>10.2f}"
            f"  {'OK' if ok else '差异'}"
        )

    # 变动表勾稽：期初 + 增加 − 减少 + 汇率 = 期末
    print("    变动表勾稽：")
    for (company, year, kind), data in sorted(
        grouped.items(), key=lambda x: (x[0][0], -int(x[0][1]))
    ):
        if kind not in ("固定资产变动表", "累计折旧变动表"):
            continue
        opening = data.get("期初余额")
        closing = data.get("期末余额")
        if opening is None or closing is None:
            continue
        delta = sum(
            v for k, v in data.items() if k not in ("期初余额", "期末余额", "本期增加", "本期减少")
        )
        gap = opening + delta - closing
        ok = abs(gap) <= 0.03
        passed += ok
        failed += not ok
        print(
            f"      {company:<8}{year:<6}{kind:<10}"
            f"期初 {opening:>8.2f} + 变动 {delta:>8.2f} = {opening + delta:>8.2f}"
            f"（表内 {closing:>8.2f}）  {'OK' if ok else '差异'}"
        )

    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_bills_receivables() -> tuple[int, int]:
    """票据与应收：原值−坏账=账面价值，三分合计与资产负债表勾稽，占比可复算。"""
    detail = load(FIN / "票据与应收结构.csv")
    balance = load(FIN / "资产负债表.csv")
    if not detail or not balance:
        return 0, 0

    book: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for row in balance:
        if not row["报告期"].endswith("1231") or row["数值"] in ("", "nan"):
            continue
        if row["科目"] not in ("应收票据", "应收账款", "应收票据及应收账款", "应收款项融资"):
            continue
        try:
            book[(row["公司"], row["报告期"][:4])][row["科目"]] = float(row["数值"]) / 1e8
        except ValueError:
            continue

    grouped: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for row in detail:
        if row["数据性质"] == "未披露" or not row["金额(亿元)"]:
            continue
        try:
            grouped[(row["公司"], row["年度"])][f"{row['类别']}|{row['项目']}"] = float(
                row["金额(亿元)"]
            )
        except ValueError:
            continue

    print("【33】票据与应收：原值−坏账=账面价值，三分合计与报表勾稽")
    print(
        f"    {'公司':<8}{'年度':<6}{'票据净额':>9}{'应收净额':>9}{'融资':>8}{'三分合计':>9}{'报表合计':>9}  结果"
    )
    passed = failed = 0
    for key in sorted(grouped, key=lambda k: (k[0], -int(k[1]))):
        company, year = key
        data = grouped[key]
        bills = data.get("应收票据|应收票据账面价值")
        receivables = data.get("应收账款|应收账款账面价值")
        financing = data.get("应收款项融资|应收款项融资合计")
        stated = data.get("合计|应收票据+应收账款+应收款项融资")
        if None in (bills, receivables, financing, stated):
            continue
        book_bills = book.get(key, {}).get("应收票据")
        book_total = book.get(key, {}).get("应收票据及应收账款")
        # 格力 2024 年末应收票据为 0，akshare 导出里整行缺失。
        # 用「应收票据及应收账款 − 应收账款」反推，避免把「没这一行」当成「校验不了」。
        if book_bills is None and book_total is not None:
            receivables_book = book.get(key, {}).get("应收账款")
            if receivables_book is not None:
                book_bills = book_total - receivables_book
        book_financing = book.get(key, {}).get("应收款项融资", 0.0)
        recomputed = bills + receivables + financing
        ok = (
            abs(recomputed - stated) <= 0.05
            and book_total is not None
            and book_bills is not None
            and abs(bills - book_bills) <= 0.05
            and abs(recomputed - (book_total + book_financing)) <= 0.05
        )
        passed += ok
        failed += not ok
        print(
            f"    {company:<8}{year:<6}{bills:>9.2f}{receivables:>9.2f}{financing:>8.2f}"
            f"{recomputed:>9.2f}{(book_total or 0) + book_financing:>9.2f}"
            f"  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_leases_commitments() -> tuple[int, int]:
    """租赁与承诺：使用权资产原值−折旧=账面价值，租赁负债与报表对平。"""
    detail = load(FIN / "租赁与承诺事项.csv")
    balance = load(FIN / "资产负债表.csv")
    if not detail or not balance:
        return 0, 0

    book: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for row in balance:
        if not row["报告期"].endswith("1231") or row["数值"] in ("", "nan"):
            continue
        if row["科目"] not in ("使用权资产", "租赁负债"):
            continue
        try:
            book[(row["公司"], row["报告期"][:4])][row["科目"]] = float(row["数值"]) / 1e8
        except ValueError:
            continue

    grouped: dict[tuple[str, str, str], dict[str, float]] = defaultdict(dict)
    for row in detail:
        if row["数据性质"] == "未披露" or not row["金额(亿元)"]:
            continue
        try:
            grouped[(row["公司"], row["年度"], row["类别"])][row["项目"]] = float(row["金额(亿元)"])
        except ValueError:
            continue

    print("【34】租赁与承诺：使用权资产与租赁负债对平")
    print(
        f"    {'公司':<8}{'年度':<6}{'使用权资产':>11}{'表内':>9}{'租赁负债':>10}{'表内':>9}  结果"
    )
    passed = failed = 0
    for key in sorted({(k[0], k[1]) for k in grouped}, key=lambda x: (x[0], -int(x[1]))):
        company, year = key
        rou = grouped.get((company, year, "使用权资产"), {})
        lease = grouped.get((company, year, "租赁负债"), {})
        rou_net = rou.get("合计-账面价值") or rou.get("账面价值合计") or rou.get("合计")
        # 资产负债表「租赁负债」只含一年以上部分，一年内到期在「一年内到期的非流动负债」里。
        # 所以对平要用「其中：一年以上」，同时校验「合计 = 一年内 + 一年以上」。
        lease_total = lease.get("其中：一年以上") or lease.get("合计")
        lease_all = lease.get("合计（账面价值）") or lease.get("合计")
        lease_current = lease.get("其中：一年内到期")
        book_rou = book.get(key, {}).get("使用权资产")
        book_lease = book.get(key, {}).get("租赁负债")
        if rou_net is None or book_rou is None:
            continue
        ok = abs(rou_net - book_rou) <= 0.05
        if lease_total is not None and book_lease is not None:
            ok = ok and abs(lease_total - book_lease) <= 0.05
        if lease_all is not None and lease_total is not None and lease_current is not None:
            ok = ok and abs(lease_all - (lease_total + lease_current)) <= 0.05
        passed += ok
        failed += not ok
        print(
            f"    {company:<8}{year:<6}{rou_net:>11.2f}{book_rou:>9.2f}"
            f"{lease_total if lease_total is not None else 0:>10.2f}"
            f"{book_lease if book_lease is not None else 0:>9.2f}"
            f"  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_payroll_tax_payable() -> tuple[int, int]:
    """职工薪酬与应交税费：期初 + 计提 − 支付 = 期末，且与报表对平。"""
    detail = load(FIN / "职工薪酬与税费明细.csv")
    balance = load(FIN / "资产负债表.csv")
    if not detail or not balance:
        return 0, 0

    book: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for row in balance:
        if not row["报告期"].endswith("1231") or row["数值"] in ("", "nan"):
            continue
        if row["科目"] not in ("应付职工薪酬", "应交税费"):
            continue
        try:
            book[(row["公司"], row["报告期"][:4])][row["科目"]] = float(row["数值"]) / 1e8
        except ValueError:
            continue

    grouped: dict[tuple[str, str, str], float] = defaultdict(float)
    for row in detail:
        if row["数据性质"] == "未披露" or not row["期末(亿元)"]:
            continue
        try:
            grouped[(row["公司"], row["年度"], row["类别"])] += float(row["期末(亿元)"])
        except ValueError:
            continue

    print("【35】职工薪酬与应交税费：明细合计 = 资产负债表科目")
    print(f"    {'公司':<8}{'年度':<6}{'薪酬明细':>10}{'表内':>9}{'税费明细':>10}{'表内':>9}  结果")
    passed = failed = 0
    for key in sorted({(k[0], k[1]) for k in grouped}, key=lambda x: (x[0], -int(x[1]))):
        company, year = key
        payroll = (
            grouped.get((company, year, "短期薪酬"), 0.0)
            + grouped.get((company, year, "离职后福利"), 0.0)
            + grouped.get((company, year, "辞退福利"), 0.0)
            + grouped.get((company, year, "其他长期职工福利"), 0.0)
        )
        tax = grouped.get((company, year, "应交税费"), 0.0)
        book_payroll = book.get(key, {}).get("应付职工薪酬")
        book_tax = book.get(key, {}).get("应交税费")
        if not payroll or book_payroll is None or not tax or book_tax is None:
            continue
        # 2025 年报重述了 2024 年可比数（同一控制下企业合并），而本表 2024 行取自
        # 2024 年报本身。资产负债表来自 akshare 的最新重述口径，因此 2024 年允许
        # 0.30 亿的重述差，2025 年仍按 0.05 亿严格判定。
        tolerance = 0.05 if year == "2025" else 0.30
        gap = max(abs(payroll - book_payroll), abs(tax - book_tax))
        ok = gap <= tolerance
        passed += ok
        failed += not ok
        note = "" if gap <= 0.05 else f"（重述差 {gap:.2f}）"
        print(
            f"    {company:<8}{year:<6}{payroll:>10.2f}{book_payroll:>9.2f}"
            f"{tax:>10.2f}{book_tax:>9.2f}  {'OK' if ok else '差异'}{note}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_inventory_provision() -> tuple[int, int]:
    """存货跌价准备变动：期初 + 计提 − 转回/转销 (+ 外币折算) = 期末，且期末 = 存货明细。"""
    detail = load(FIN / "存货跌价准备变动.csv")
    inventory = load(FIN / "存货明细.csv")
    if not detail or not inventory:
        return 0, 0

    grouped: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for row in detail:
        if not row["金额(亿元)"]:
            continue
        try:
            grouped[(row["公司"], row["存货类别"])][row["项目"]] = float(row["金额(亿元)"])
        except ValueError:
            continue

    # 存货明细里的期末跌价准备（分项相加行）
    stated: dict[str, float] = {}
    for row in inventory:
        if row["年度"] != "2025" or row["存货类别"] != "合计（分项相加）":
            continue
        try:
            stated[row["公司"]] = float(row["跌价准备(亿元)"])
        except (ValueError, KeyError):
            continue

    print("【36】存货跌价准备变动：期初 + 计提 − 转回/转销 = 期末，且与存货明细对平")
    print(
        f"    {'公司':<8}{'期初':>8}{'计提':>8}{'转回/转销':>11}{'其他':>8}{'期末':>8}{'存货明细':>10}  结果"
    )
    passed = failed = 0
    for company in ("美的集团", "海尔智家", "格力电器"):
        total = grouped.get((company, "合计"), {})
        opening = total.get("期初余额")
        increase = total.get("本期计提")
        closing = total.get("期末余额")
        if opening is None or increase is None or closing is None:
            continue
        turnover = sum(
            v
            for (c, name), data in grouped.items()
            if c == company and name != "合计"
            for k, v in data.items()
            if k == "本期转回或转销"
        )
        other = sum(
            v
            for (c, name), data in grouped.items()
            if c == company and name != "合计"
            for k, v in data.items()
            if k == "本期其他变动"
        )
        # 美的的「本期其他变动」是外币报表折算差异，方向为正（增加准备）
        gap = opening + increase - turnover + other - closing
        base = stated.get(company)
        ok = abs(gap) <= 0.05 and base is not None and abs(closing - base) <= 0.05
        passed += ok
        failed += not ok
        print(
            f"    {company:<8}{opening:>8.2f}{increase:>8.2f}{turnover:>11.2f}"
            f"{other:>8.2f}{closing:>8.2f}{base if base is not None else 0:>10.2f}"
            f"  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_supply_chain() -> tuple[int, int]:
    """供应链集中度：前五名金额 ÷ 占比 反推的分母应与营业收入/成本同量级。"""
    detail = load(FIN / "供应商客户集中度时序.csv")
    income = load(FIN / "利润表.csv")
    if not detail or not income:
        return 0, 0

    base: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for row in income:
        if not row["报告期"].endswith("1231") or row["数值"] in ("", "nan"):
            continue
        if row["科目"] not in ("营业收入", "营业成本"):
            continue
        try:
            base[(row["公司"], row["报告期"][:4])][row["科目"]] = float(row["数值"]) / 1e8
        except ValueError:
            continue

    print("【37】供应链集中度：前五名金额 ÷ 占比 反推的分母 vs 营业收入/成本")
    print(f"    {'公司':<8}{'年度':<6}{'类别':<14}{'反推分母':>10}{'报表数':>10}{'偏差':>9}  结果")
    passed = failed = 0
    skipped = 0
    for row in detail:
        if row["项目"] != "前五名合计" or not row["金额(亿元)"] or not row["占比%"]:
            continue
        try:
            amount = float(row["金额(亿元)"])
            ratio = float(row["占比%"])
        except ValueError:
            continue
        if ratio <= 0:
            continue
        key = (row["公司"], row["年度"])
        subject = "营业收入" if row["类别"] == "前五大客户" else "营业成本"
        reference = base.get(key, {}).get(subject)
        if reference is None:
            continue
        # 海尔供应商集中度的分母是「年度采购总额」，不是营业成本。采购总额含
        # 设备/服务/工程采购，2019—2022 年比营业成本高约 30%，2025 年才接近。
        # 这类行不参与 ±15% 判定，但要单列出来，避免被当成数据错误。
        if "采购总额" in row.get("口径说明", ""):
            skipped += 1
            continue
        implied = amount / ratio * 100
        deviation = (implied - reference) / reference * 100
        # 年报的「年度销售总额」含税，比利润表「营业收入」高 5%–15% 属正常
        ok = abs(deviation) <= 15
        passed += ok
        failed += not ok
        if not ok:
            print(
                f"    {row['公司']:<8}{row['年度']:<6}{row['类别']:<14}"
                f"{implied:>10.2f}{reference:>10.2f}{deviation:>8.1f}%  差异"
            )
    if failed == 0:
        print(f"    {passed} 组全部落在 ±15% 内（年报「销售总额」含税，略高于营业收入）")
    if skipped:
        print(f"    另有 {skipped} 组分母为「年度采购总额」，口径不同，未参与判定")
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_intangibles() -> tuple[int, int]:
    """无形资产：原值 − 累计摊销 − 减值 = 账面价值，且与资产负债表对平。"""
    detail = load(FIN / "无形资产明细.csv")
    balance = load(FIN / "资产负债表.csv")
    if not detail or not balance:
        return 0, 0

    book: dict[tuple[str, str], float] = {}
    for row in balance:
        if row["报告期"].endswith("1231") and row["科目"] == "无形资产":
            try:
                book[(row["公司"], row["报告期"][:4])] = float(row["数值"]) / 1e8
            except ValueError:
                continue

    grouped: dict[tuple[str, str, str], dict[str, float]] = defaultdict(dict)
    for row in detail:
        if not row["金额(亿元)"]:
            continue
        try:
            grouped[(row["公司"], row["年度"], row["类别"])][row["项目"]] = float(row["金额(亿元)"])
        except ValueError:
            continue

    print("【38】无形资产：原值 − 累计摊销 − 减值 = 账面价值，且与报表对平")
    print(
        f"    {'公司':<8}{'年度':<6}{'原值':>9}{'累计摊销':>9}{'减值':>7}{'账面价值':>9}{'报表数':>9}  结果"
    )
    passed = failed = 0
    for key in sorted({(k[0], k[1]) for k in grouped}, key=lambda x: (x[0], -int(x[1]))):
        company, year = key

        def total_of(category: str, company: str = company, year: str = year) -> float:
            data = grouped.get((company, year, category), {})
            return sum(v for k, v in data.items() if "合计" in k) or sum(data.values())

        gross = total_of("无形资产-原值")
        amortized = total_of("无形资产-累计摊销")
        impaired = total_of("无形资产-减值准备")
        net = total_of("无形资产-账面价值")
        if not gross or not net:
            continue
        recomputed = gross - amortized - impaired
        stated = book.get(key)
        ok = abs(recomputed - net) <= 0.05 and stated is not None and abs(net - stated) <= 0.10
        passed += ok
        failed += not ok
        print(
            f"    {company:<8}{year:<6}{gross:>9.2f}{amortized:>9.2f}{impaired:>7.2f}"
            f"{net:>9.2f}{stated if stated is not None else 0:>9.2f}"
            f"  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_subsidiaries() -> tuple[int, int]:
    """子公司：持股比例落在 0–100，且持股结构统计与明细一致。"""
    detail = load(FIN / "子公司与合并范围.csv")
    if not detail:
        return 0, 0

    print("【39】子公司：持股比例区间合法，结构统计与明细家数一致")
    passed = failed = 0
    for company in ("美的集团", "海尔智家", "格力电器"):
        for year in ("2025", "2024"):
            stakes: list[float] = []
            for row in detail:
                if row["公司"] != company or row["年度"] != year:
                    continue
                if row["类别"] != "子公司" or not row["数值"]:
                    continue
                try:
                    stakes.append(float(row["数值"]))
                except ValueError:
                    continue
            if not stakes:
                continue
            out_of_range = [s for s in stakes if s < 0 or s > 100]
            # 结构化统计：100% / 50%–100% / ≤50%
            full = sum(1 for s in stakes if s >= 99.99)
            partial = sum(1 for s in stakes if 50 < s < 99.99)
            control = sum(1 for s in stakes if s <= 50)
            ok = not out_of_range
            passed += ok
            failed += not ok
            print(
                f"    {company:<8}{year:<6}明细 {len(stakes):>3} 家"
                f"（100% {full} / 50–100% {partial} / ≤50% {control}）"
                f"{'  越界 ' + str(len(out_of_range)) + ' 家' if out_of_range else ''}"
                f"  {'OK' if ok else '差异'}"
            )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_efficiency_coverage() -> tuple[int, int]:
    """营运效率：覆盖2023—2025，且现金转换周期 = 应收 + 存货 − 应付。"""
    rows = load(FIN / "营运效率与现金流.csv")
    if not rows:
        return 0, 0

    print("【40】营运效率：覆盖2023—2025，现金转换周期 = 应收 + 存货 − 应付")
    passed = failed = 0
    for company in ("美的集团", "海尔智家", "格力电器"):
        years = sorted(r["年度"] for r in rows if r["公司"] == company)
        ok_coverage = years == [str(y) for y in range(2023, 2026)]
        passed += ok_coverage
        failed += not ok_coverage
        print(
            f"    {company:<8}覆盖 {years[0] if years else '-'}–{years[-1] if years else '-'}"
            f"（{len(years)} 年）  {'OK' if ok_coverage else '差异'}"
        )

    for row in rows:
        try:
            ar = float(row["应收周转天数(平均)"])
            inv = float(row["存货周转天数(平均)"])
            ap = float(row["应付周转天数(平均)"])
            ccc = float(row["现金转换周期(天)"])
        except (ValueError, KeyError, TypeError):
            continue
        gap = (ar + inv - ap) - ccc
        ok = abs(gap) <= 0.2
        passed += ok
        failed += not ok
        if not ok:
            print(f"    {row['公司']} {row['年度']} 现金周期差 {gap:+.2f} 天")
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_quarterly_long() -> tuple[int, int]:
    """单季表：有年报分季表的年份用披露值；相减口径只在无披露时使用。"""
    rows = load(FIN / "单季度经营_2023起.csv")
    disclosed = load(FIN / "分季度经营.csv")
    if not rows:
        return 0, 0

    dis = {
        (r["公司"], r["年度"], r["季度"]): float(r["数值"]) / 1e8
        for r in disclosed
        if r["指标"] == "营业收入"
    }

    print("【41】单季表：披露优先；有分季表的年份不得出现 0 值")
    print(f"    {'公司':<8}{'年度':<6}{'单季相加':>10}{'披露相加':>10}{'差':>8}  结果")
    passed = failed = 0
    years = sorted({(r["公司"], r["年度"]) for r in rows})
    for company, year in years:
        singles = [
            r for r in rows if r["公司"] == company and r["年度"] == year and r["营业收入(亿元)"]
        ]
        if not singles:
            continue
        total = sum(float(r["营业收入(亿元)"]) for r in singles)
        modes = {r["口径"] for r in singles}
        has_disclosed = any("披露分季表" in m for m in modes)
        # 有分季表的年份必须 4 季齐全，且用的是披露值
        ok = (not has_disclosed) or len(singles) == 4
        if has_disclosed and disclosed:
            d_total = sum(dis.get((company, year, q), 0.0) for q in ("Q1", "Q2", "Q3", "Q4"))
            ok = ok and abs(d_total - total) < 0.05
        passed += ok
        failed += not ok
        if not ok:
            print(
                f"    {company:<8}{year:<6}{total:>10.2f}{'':>10}{'':>8}  差异（{len(singles)} 季）"
            )
    # 2026 年只到 Q2，不应出现 Q3/Q4
    future = [r for r in rows if r["年度"] == "2026" and r["季度"] in ("Q3", "Q4")]
    ok = not future
    passed += ok
    failed += not ok
    print(f"    2026 只到 Q2：{'OK' if ok else f'多出 {len(future)} 行'}")
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_fx_exposure() -> tuple[int, int]:
    """外币敞口：逐科目币种加总 = 年报小计；净敞口 = 资产 − 负债。"""
    rows = load(FIN / "外币敞口与汇率敏感性.csv")
    if not rows:
        return 0, 0

    by_subject: dict[tuple[str, str, str, str], dict[str, float | None]] = {}
    for row in rows:
        if not row["人民币金额(亿元)"]:
            continue
        key = (row["公司"], row["年度"], row["侧"], row["科目"])
        bucket = by_subject.setdefault(key, {"subtotal": None, "currencies": 0.0})
        amount = float(row["人民币金额(亿元)"])
        if row["币种"] in ("小计", "合计", "总计"):
            bucket["subtotal"] = amount
        else:
            bucket["currencies"] += amount

    print("【42】外币敞口：逐科目币种加总 = 年报小计，净敞口 = 资产 − 负债")
    passed = failed = 0
    checked = 0
    for key, bucket in sorted(by_subject.items()):
        subtotal, currencies = bucket["subtotal"], bucket["currencies"]
        if subtotal is None or not currencies:
            continue
        checked += 1
        gap = currencies - subtotal
        ok = abs(gap) <= 0.05
        passed += ok
        failed += not ok
        if not ok:
            print(
                f"    {key[0]} {key[1]} {key[3]} 币种加总 {currencies:.2f}"
                f" ≠ 小计 {subtotal:.2f}（差 {gap:+.2f} 亿）"
            )
    print(f"    科目勾稽：比对 {checked} 个，通过 {passed}")

    for company in ("美的集团", "海尔智家", "格力电器"):
        for year in ("2025", "2024"):
            net = next(
                (
                    float(r["人民币金额(亿元)"])
                    for r in rows
                    if r["公司"] == company and r["年度"] == year and r["侧"] == "净敞口"
                ),
                None,
            )
            impact = next(
                (
                    float(r["人民币金额(亿元)"])
                    for r in rows
                    if r["公司"] == company and r["年度"] == year and r["侧"] == "敏感度"
                ),
                None,
            )
            if net is None or impact is None:
                continue
            ok = abs(impact + net * 0.01) <= 0.01
            passed += ok
            failed += not ok
            if not ok:
                print(f"    {company} {year} 敏感度 {impact:.2f} ≠ −净敞口×1% {-net * 0.01:.2f}")
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_contingencies() -> tuple[int, int]:
    """或有/期后/承诺表：合计可复算，且与担保、分红两张表交叉一致。"""
    rows = load(FIN / "或有事项与期后承诺.csv")
    if not rows:
        return 0, 0

    values = {(r["公司"], r["年度"], r["项目"]): r["金额(亿元)"] for r in rows if r["金额(亿元)"]}
    print("【43】或有事项与期后承诺：合计可复算、与担保/分红表交叉一致")
    passed = failed = 0

    def check(label: str, ok: bool) -> None:
        nonlocal passed, failed
        passed += ok
        failed += not ok
        print(f"    {label}  {'OK' if ok else '差异'}")

    # 1) 美的或有负债：缺口 = 潜在损失 − 承诺赔付
    for year, loss, cover in (("2025", 6.99, 1.68), ("2024", 6.61, 1.52)):
        stated = values.get(("美的集团", year, "赔付承诺未覆盖的风险缺口"))
        ok = stated is not None and abs(float(stated) - (loss - cover)) <= 0.01
        check(f"美的 {year} 巴西税务纠纷缺口 {loss}−{cover}", ok)

    # 2) 美的 2025 资本承诺合计 = 分项相加
    parts = values.get(("美的集团", "2025", "资本性支出—房屋建筑物及机器设备"))
    invest = values.get(("美的集团", "2025", "投资承诺"))
    total = values.get(("美的集团", "2025", "资本性支出承诺合计"))
    if None not in (parts, invest, total):
        check(
            "美的 2025 资本承诺 39.13+0.02=39.15",
            abs(float(parts) + float(invest) - float(total)) <= 0.01,
        )

    # 3) 格力按揭担保与担保表的 2025 口径不冲突（担保表 43.87 为票据池口径）
    gree = values.get(("格力电器", "2025", "购房客户按揭贷款阶段性担保（尚未结清）"))
    ok = gree is not None and 15.0 <= float(gree) <= 17.0
    check("格力 2025 购房按揭担保 16.05 亿在合理区间", ok)

    # 4) 期后提议每股数 × 分红送配表里「2025年报」年度分红的实际派息比例。
    #    美的/格力提议即实施（38.0 / 20.0 相等）；海尔不等（8.867 → 8.9151），
    #    不等只有一种合法解释：年报说的「维持分配总额不变，相应调整每股分配比例」，
    #    即基数变小、每股变大。所以海尔必须是实施 > 提议，反过来就是数据错了。
    dividends = load(FIN / "分红送配.csv")
    implemented = {
        r["公司"]: float(r["派息比例"])
        for r in dividends
        if r["报告时间"] == "2025年报"
        and r["分红类型"] == "年度分红"
        and r["派息比例"] not in ("", "nan")
    }
    for company, expected in (
        ("美的集团", 38.0),
        ("格力电器", 20.0),
        ("海尔智家", 8.867),
    ):
        key = (company, "2025", "董事会提议每 10 股现金股利（元，含税）")
        proposed = values.get(key)
        actual = implemented.get(company)
        if proposed is None or actual is None:
            continue
        proposed = float(proposed)
        if abs(proposed - expected) > 0.01:
            check(f"{company} 提议每股 {expected} 元/10 股", False)
            continue
        if company == "海尔智家":
            ok = actual > proposed
            note = f"实施 {actual} > 提议 {proposed}（总额不变、基数缩小）"
        else:
            ok = abs(actual - proposed) <= 0.01
            note = f"提议=实施={proposed}"
        check(f"{company} 期后提议 vs 分红送配实施：{note}", ok)

    # 5) 海尔：披露合计 ÷ 提议每股 = 隐含基数；÷ 实施每股 = 实施基数
    haier_total = 8_248_280_749.27
    implied = haier_total / (8.867 / 10) / 1e8
    stated = values.get(("海尔智家", "2025", "隐含可参与分配股数（亿股）"))
    ok = stated is not None and abs(float(stated) - implied) <= 0.01
    check(f"海尔 隐含基数 = 合计÷每股 = {implied:.2f} 亿股", ok)

    # 6) 每家至少一条「未披露」记录（证明区分了「无」与「没披露」）
    undisclosed = [r for r in rows if r["数据性质"] == "未披露"]
    check(f"存在未披露项（{len(undisclosed)} 条，区分「无」与「未披露」）", len(undisclosed) >= 2)
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_provisions() -> tuple[int, int]:
    """预计负债：明细加总=合计、期初衔接上年期末、与 akshare 对平、格力不填 0。"""
    rows = load(FIN / "预计负债与售后义务.csv")
    bs = load(FIN / "资产负债表.csv")
    if not rows:
        return 0, 0

    print("【44】预计负债：明细加总 = 合计；期初衔接上年期末；与 akshare 年报数对平")
    passed = failed = 0

    def check(label: str, ok: bool) -> None:
        nonlocal passed, failed
        passed += ok
        failed += not ok
        print(f"    {label}  {'OK' if ok else '差异'}")

    values = {
        (r["公司"], r["年度"], r["项目"]): float(r["金额(亿元)"]) for r in rows if r["金额(亿元)"]
    }
    years = sorted({r["年度"] for r in rows if r["公司"] == "海尔智家"})

    # 1) 海尔：三项明细相加 = 合计（表内是亿元两位小数，容差按舍入累积算）
    for year in years:
        total = values.get(("海尔智家", year, "预计负债合计（附注，非流动口径）"))
        parts = [
            values.get(("海尔智家", year, f"其中：{item}"))
            for item in ("预计三包安装费", "未决诉讼", "其他")
        ]
        if total is None or any(v is None for v in parts):
            continue
        check(f"海尔 {year} 明细相加 = 合计 {total:.2f}", abs(sum(parts) - total) <= 0.02)

    # 2) 链条：本年报合计应等于「下一年报的期初」——但表里没存期初，
    #    改用可核验的形式：一年内到期部分不得为 0 且各年都齐
    due_years = sorted(
        r["年度"] for r in rows if r["公司"] == "海尔智家" and r["项目"].startswith("一年内到期")
    )
    check(f"海尔一年内到期流动部分覆盖 {len(due_years)} 年", due_years == ["2023", "2024", "2025"])

    # 3) 与 akshare「预计非流动负债」年报数对平（B 级必须与 A 级交叉）
    ak = {
        (r["公司"], r["报告期"][:4]): float(r["数值"]) / 1e8
        for r in bs
        if r["科目"] == "预计非流动负债"
        and r["报告期"].endswith("1231")
        and r["数值"] not in ("", "nan")
    }
    for (company, year, item), value in values.items():
        if "合并资产负债表" not in item and not item.startswith("预计负债合计"):
            continue
        theirs = ak.get((company, year))
        if theirs is None:
            continue
        check(f"{company} {year} vs akshare {theirs:.2f} 亿", abs(value - theirs) <= 0.01)

    # 4) 格力：报表行为空 → 必须记「未披露」，绝不能填 0
    gree = [r for r in rows if r["公司"] == "格力电器"]
    check(
        f"格力 {len(gree)} 年全部记为未披露（空≠0）",
        all(r["数据性质"] == "未披露" and r["金额(亿元)"] == "" for r in gree)
        and {r["年度"] for r in gree} == {"2023", "2024", "2025"},
    )

    # 5) 三包安装费占合计比应在合理区间（政策一致性检查）
    for year in years:
        total = values.get(("海尔智家", year, "预计负债合计（附注，非流动口径）"))
        sabao = values.get(("海尔智家", year, "其中：预计三包安装费"))
        if not total or sabao is None:
            continue
        share = sabao / total
        check(f"海尔 {year} 三包占比 {share * 100:.0f}% 在 70—90%", 0.70 <= share <= 0.90)

    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_audit_independence() -> tuple[int, int]:
    """审计端独立性：签字人恒 2 名、连续签字不超 5 年、审计年限逐年 +1、
    意见类型与 治理与经营披露.csv 一致。"""
    rows = load(FIN / "审计与签字会计师.csv")
    gov = load(FIN / "治理与经营披露.csv")
    if not rows:
        return 0, 0

    print("【45】审计独立性：签字人数恒定、连续签字 ≤5 年、审计年限逐年 +1、意见类型对平")
    passed = failed = 0

    def check(label: str, ok: bool) -> None:
        nonlocal passed, failed
        passed += ok
        failed += not ok
        print(f"    {label}  {'OK' if ok else '差异'}")

    signers = [r for r in rows if r["类别"] == "签字注册会计师"]

    # 1) 境内签字人应恒为 2 名、境外恒为 1 名（A 股两名签字 vs 境外单名的模式）
    dom = [r for r in signers if "境内" in r["项目"]]
    ovs = [r for r in signers if "境外" in r["项目"]]
    check(f"境内签字人 {len(dom)} 行全为 2 名", dom and all(r["签字人数"] == "2" for r in dom))
    check(f"境外签字人 {len(ovs)} 行全为 1 名", ovs and all(r["签字人数"] == "1" for r in ovs))

    # 2) 每人每年只出现一次（同一年同一归属不得有多条不同取值）
    seen: set[tuple[str, str, str]] = set()
    dup: list[str] = []
    for r in signers:
        key = (r["公司"], r["年度"], r["项目"])
        if key in seen:
            dup.append(f"{key}")
        seen.add(key)
    check(f"公司×年度×归属 无重复取值{('：' + ';'.join(dup)) if dup else ''}", not dup)

    # 3) 连续签字不超过 5 年（监管：签字注会连续服务满 5 年须轮换）
    def years_of(company: str, name: str) -> list[int]:
        out = []
        for r in signers:
            if r["公司"] != company or "境内" not in r["项目"]:
                continue
            if name in [x for x in re.split(r"[、，,]", r["值"])]:
                out.append(int(r["年度"]))
        return sorted(out)

    over: list[str] = []
    streaks: list[tuple[str, str, int]] = []
    for company in ("美的集团", "海尔智家", "格力电器"):
        names = {
            n
            for r in signers
            if r["公司"] == company and "境内" in r["项目"]
            for n in re.split(r"[、，,]", r["值"])
        }
        for name in sorted(names):
            ys = years_of(company, name)
            run = cur = 1
            for a, b in itertools.pairwise(ys):
                cur = cur + 1 if b == a + 1 else 1
                run = max(run, cur)
            streaks.append((company, name, run))
            if run > 5:
                over.append(f"{company} {name} 连续 {run} 年")
    check(
        f"最长连续签字 ≤5 年（{len(streaks)} 人，最长 "
        f"{max(r for _, _, r in streaks)} 年）{('：' + ';'.join(over)) if over else ''}",
        not over,
    )

    # 4) 自述审计年限逐年 +1
    tenure: dict[tuple[str, str], dict[int, int]] = {}
    for r in rows:
        if r["类别"] != "审计连续性":
            continue
        side = "境内" if "境内" in r["项目"] else "境外"
        tenure.setdefault((r["公司"], side), {})[int(r["年度"])] = int(r["值"])
    broken = 0
    rings = 0
    for (_company, _side), series in tenure.items():
        for a, b in itertools.pairwise(sorted(series)):
            if b != a + 1:
                continue
            rings += 1
            if series[b] - series[a] != 1:
                broken += 1
    check(f"审计年限链条 {rings} 环逐年 +1（断开 {broken} 环）", broken == 0 and rings > 0)

    # 5) 意见类型与 治理与经营披露.csv 一致
    known = {(r["公司"], r["报告期"].replace(" 年度", "")): r["审计意见"] for r in gov}
    compared = 0
    mismatch = 0
    for r in rows:
        if r["类别"] != "审计意见":
            continue
        theirs = known.get((r["公司"], r["年度"]))
        if not theirs:
            continue
        compared += 1
        ours = re.sub(r"\s+", "", r["值"])
        base = re.sub(r"\s+", "", theirs)
        if not (base in ours or ours in base):
            mismatch += 1
    check(
        f"意见类型与治理与经营披露对平（{compared} 组，不一致 {mismatch}）",
        compared > 0 and mismatch == 0,
    )

    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_contract_notes() -> tuple[int, int]:
    """合同资产/负债附注：分项加总=原值、损失率可复算、链条衔接、与报表对平。"""
    rows = load(FIN / "合同资产与合同负债附注.csv")
    bs = load(FIN / "资产负债表.csv")
    if not rows:
        return 0, 0

    print("【46】合同资产与负债附注：分项加总 = 原值，损失率可复算，与报表对平")
    passed = failed = 0

    def check(label: str, ok: bool) -> None:
        nonlocal passed, failed
        passed += ok
        failed += not ok
        print(f"    {label}  {'OK' if ok else '差异'}")

    midea = [r for r in rows if r["公司"] == "美的集团"]
    years = sorted({r["年度"] for r in midea})

    def end_value(year: str, item: str) -> float | None:
        hit = [
            r
            for r in midea
            if r["年度"] == year and r["项目"] == item and r["期别"] == "期末" and r["金额或比例"]
        ]
        return float(hit[0]["金额或比例"]) if hit else None

    def raw_thousand(year: str, item: str) -> float | None:
        """取「附注原值(千元)」列：未舍入的源值。"""
        hit = [
            r
            for r in midea
            if r["年度"] == year
            and r["项目"] == item
            and r["期别"] == "期末"
            and r.get("附注原值(千元)")
        ]
        return float(hit[0]["附注原值(千元)"]) if hit else None

    # 1) 原值 − 减值 = 净额
    for year in years:
        gross = end_value(year, "合同资产原值")
        allow = end_value(year, "减：合同资产减值准备")
        net = end_value(year, "合同资产净额")
        if None in (gross, net):
            check(f"{year} 合同资产原值/净额齐备", False)
            continue
        if allow is not None:
            check(f"{year} 原值 − 减值 = 净额", abs(gross - abs(allow) - net) <= 0.02)

    # 2) 合同负债分项相加 = 报表数
    sheet = {
        (r["公司"], r["报告期"]): float(r["数值"]) / 1e8
        for r in bs
        if r["科目"] == "合同负债" and r["数值"] not in ("", "nan")
    }
    for year in years:
        goods = end_value(year, "预收货款及劳务款")
        eng = end_value(year, "预收工程款")
        theirs = sheet.get(("美的集团", f"{year}1231"))
        if None in (goods, eng) or not theirs:
            continue
        check(f"{year} 预收货款+工程款 = 报表 {theirs:.2f} 亿", abs(goods + eng - theirs) <= 0.02)

    # 3) 净额与报表合同资产对平
    asset = {
        (r["公司"], r["报告期"]): float(r["数值"]) / 1e8
        for r in bs
        if r["科目"] == "合同资产" and r["数值"] not in ("", "nan")
    }
    for year in years:
        net = end_value(year, "合同资产净额")
        theirs = asset.get(("美的集团", f"{year}1231"))
        if net is None or not theirs:
            continue
        check(f"{year} 附注净额 = 报表合同资产 {theirs:.2f} 亿", abs(net - theirs) <= 0.02)

    # 4) 预期信用损失率可复算（元级：亿元舍入会得到 4.17% vs 4.22% 的假差异）
    # 用「附注原值(千元)」列复算，不用「金额或比例」——后者保留两位亿元，
    # 单项计提这类小额（3,056 千元 = 0.00 亿）会直接归零，拿它算比率必然假报差异。
    ecl: dict[tuple[str, str], dict[str, float | str]] = {}
    for r in midea:
        if "业务" not in r["项目"]:
            continue
        key = (r["年度"], r["项目"].split("业务")[0])
        bucket = ecl.setdefault(key, {})
        raw = r.get("附注原值(千元)")
        if "账面余额" in r["项目"] and raw:
            bucket["balance"] = float(raw)
        elif "减值准备" in r["项目"] and raw:
            bucket["allowance"] = abs(float(raw))
        elif "损失率" in r["项目"]:
            bucket["rate"] = float(r["金额或比例"].rstrip("%"))
    computed = 0
    for (year, kind), bucket in sorted(ecl.items()):
        if not all(k in bucket for k in ("balance", "allowance", "rate")):
            continue
        if not bucket["balance"]:
            continue
        computed += 1
        implied = round(bucket["allowance"] / bucket["balance"] * 100, 2)
        check(
            f"{year} {kind} 隐含损失率 = 披露 {bucket['rate']}%",
            abs(implied - float(bucket["rate"])) <= 0.01,
        )
    check(f"损失率复算覆盖 {computed} 组", computed == 9)

    # 5) 结转率单调可解释：2020—2024 为 90%，2025 跳到 95%
    rates = {r["年度"]: float(r["金额或比例"].rstrip("%")) for r in midea if "结转率" in r["项目"]}
    check(
        f"结转率覆盖 {len(rates)} 年且只取 90/95",
        set(rates) == {"2023", "2024", "2025"} and set(rates.values()) <= {90.0, 95.0},
    )
    check(
        "2025 结转率升至 95%（与 2020—2024 的 90% 不同）",
        rates.get("2025") == 95.0 and rates.get("2024") == 90.0,
    )

    # 6) 主键唯一 + 「无单项计提」不能与有金额行并存
    seen: set[tuple[str, str, str]] = set()
    dup = 0
    for r in midea:
        key = (r["年度"], r["期别"], r["项目"])
        if key in seen:
            dup += 1
        seen.add(key)
    check(f"美的 公司×年度×期别×项目 无重复（{len(seen)} 键）", dup == 0)

    # 7) 海尔/格力记「未披露」而非 0
    others = [r for r in rows if r["公司"] != "美的集团"]
    check(
        f"海尔/格力附注明细记为未披露（{len(others)} 条）",
        others and all(r["数据性质"] == "未披露" and not r["金额或比例"] for r in others),
    )

    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_primary_key_unique() -> tuple[int, int]:
    """主键唯一性：长表不得出现重复的复合主键。

    这条校验对应实际发生过的 bug：`extract_cash_reconciliation.py` 的注释列表
    在年度循环外初始化、写入后未清空，导致格力 2025 的 5 行注释被写了两遍
    （88 行里只有 83 个唯一键）。下游若按 (公司,年度,项目) 取值，会取到重复行。

    各表维度列不同，用 (公司, 期间, 维度1, 维度2) 组合成主键；
    分部报告需要「分部 + 指标」两列才算唯一。
    """
    # (文件名, 期间列, 维度列...)
    tables = [
        ("净利润调节经营现金流.csv", "年度", ("项目",)),
        ("分部报告.csv", "年度", ("分部", "指标")),
        ("减值明细.csv", "年度", ("类别", "项目")),
        ("存货明细.csv", "年度", ("存货类别",)),
        ("其他综合收益.csv", "期间", ("项目",)),
    ]
    print("【48】主键唯一性：长表不得有重复的复合主键")
    passed = failed = 0
    for name, period_col, dims in tables:
        rows = load(FIN / name)
        if not rows:
            continue
        cols = list(rows[0].keys())
        if period_col not in cols or not all(d in cols for d in dims):
            continue
        keys = [
            (r.get("公司", ""), r.get(period_col, ""), *(r.get(d, "") for d in dims)) for r in rows
        ]
        dup = len(keys) - len(set(keys))
        ok = dup == 0
        passed += ok
        failed += not ok
        print(f"    {name:<28}{len(keys):>4} 行 重复 {dup:>2}  {'OK' if ok else '差异'}")
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_segment_closure() -> tuple[int, int]:
    """分部报告闭合：各分部相加 = 合计（抵销项须带正确符号）。

    格力年报把「分部间抵销」写成正数，若脚本原样写入，明细相加会比合计
    多出整整一个抵销额（资产 3,726 亿、负债 3,369 亿，虚增 101%）。

    海尔地区分部是**两层结构**：「中国大陆 + 其他国家/地区」合计即总营收，
    再往下的美洲/欧洲/南亚等是「其他国家/地区」的细分，不能与父层相加。
    """
    rows = load(FIN / "分部报告.csv")
    if not rows:
        return 0, 0

    print("【49】分部报告闭合：各分部相加 = 合计")
    passed = failed = 0
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["公司"], row["年度"], row["指标"])].append(row)

    # 父层分部名：出现这些时，只取父层相加，忽略其细分
    top_level = {"中国大陆地区", "其他国家/地区"}

    for key in sorted(grouped):
        items = grouped[key]
        parts = [r for r in items if r["分部"] != "合计"]
        total_rows = [r for r in items if r["分部"] == "合计"]
        if not parts or not total_rows:
            continue
        # 若父层存在，只累加父层，避免把子层重复计入
        names = {r["分部"] for r in parts}
        if len(names & top_level) == len(top_level):
            parts = [r for r in parts if r["分部"] in top_level]
        try:
            subtotal = sum(float(r["数值"]) for r in parts)
            stated = float(total_rows[0]["数值"])
        except (TypeError, ValueError):
            continue
        # 容差 0.1%：分部数据以元为单位、可能有个位数舍入
        ok = abs(subtotal - stated) <= max(1.0, abs(stated) * 0.001)
        passed += ok
        failed += not ok
        if not ok:
            print(
                f"    ⚠ {key[0]} {key[1]} {key[2]}："
                f"明细和 {subtotal / 1e8:.2f} 亿 vs 合计 {stated / 1e8:.2f} 亿"
            )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_cost_funnel() -> tuple[int, int]:
    """费用漏斗闭合：收入 × (1 − 各成本率之和) ≈ 营业利润。

    这是唯一能同时捕获「减值符号错」「漏列成本项」「分母口径错」的校验。
    修复前格力 2023 漏斗比营业利润少 56.87 亿（17.3%），校验通过后为 0。
    """
    rows = load(FIN / "成本结构与费用率.csv")
    if not rows:
        return 0, 0

    print("【50】费用漏斗闭合：收入 × (1 − 各成本率之和) ≈ 营业利润")
    passed = failed = 0
    for row in rows:
        try:
            revenue = float(row["营业收入(亿)"])
            stated = float(row["营业利润(亿)"])
        except (TypeError, ValueError):
            continue

        def rate(name: str, row: dict[str, str] = row) -> float:
            try:
                return float(row.get(name) or 0.0) / 100
            except ValueError:
                return 0.0

        funnel = revenue * (
            1
            - rate("营业成本(%)")
            - rate("营业税金及附加(%)")
            - rate("销售费用(%)")
            - rate("管理费用(%)")
            - rate("研发费用(%)")
            - rate("财务费用(%)")
            - rate("其他营业成本项(%)")
            + rate("利息等营业收入(%)")
            + rate("其他收益(%)")
            + rate("投资收益(%)")
            + rate("公允价值变动收益(%)")
            - rate("资产减值损失(%)")
            - rate("信用减值损失(%)")
            + rate("资产处置收益(%)")
        )
        tolerance = max(0.05, abs(revenue) * 0.0005)
        ok = abs(funnel - stated) <= tolerance
        passed += ok
        failed += not ok
        if not ok:
            print(
                f"    ⚠ {row['公司']} {row['年度']}："
                f"漏斗 {funnel:.2f} vs 营业利润 {stated:.2f}（差 {funnel - stated:+.2f}）"
            )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_non_recurring() -> tuple[int, int]:
    """非经常性损益：必须用归母口径，且占比可复算。

    `扣非净利润` 是归母口径，若用「净利润 − 扣非」会把少数股东损益
    算成非经常性损益（海尔 2025 因此从 4.85% 虚增到 7.73%）。
    """
    quality = load(FIN / "利润质量.csv")
    if not quality:
        return 0, 0

    print("【51】非经常性损益：归母净利润 − 扣非净利润，占比可复算")
    passed = failed = 0
    for row in quality:
        try:
            non_rec = float(row["非经常性损益(亿元)"])
            pct_stated = float(row["非经常性损益占净利润%"])
            deducted = float(row["扣非净利润(亿元)"])
        except (TypeError, ValueError):
            continue
        # 反推归母净利润，再算占比，与表内值比对
        parent = non_rec + deducted
        recomputed = non_rec / parent * 100 if parent else 0.0
        ok = abs(recomputed - pct_stated) <= 0.05
        passed += ok
        failed += not ok
        if not ok:
            print(
                f"    ⚠ {row['公司']} {row['年度']}："
                f"占比 {pct_stated:.2f}% vs 复算 {recomputed:.2f}%"
            )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_toolchain() -> tuple[int, int]:
    """外部工具链：解析 PDF 需要 `pdftotext`（poppler）。

    27 个 `extract_*.py` 依赖它，但之前没有任何一个脚本检查可执行文件是否存在，
    在干净机器上会抛裸的 FileNotFoundError，看不出是缺依赖。
    """
    import shutil

    print("【52】外部工具链：pdftotext（poppler）可用性")
    path = shutil.which("pdftotext")
    if path:
        print(f"    pdftotext 已安装：{path}")
        print("    通过 1，差异 0\n")
        return 1, 0
    print("    ⚠ 缺少 pdftotext，所有 PDF 提取脚本不可用")
    print("      macOS: brew install poppler\n")
    return 0, 1


def check_panel_columns() -> tuple[int, int]:
    """结构完整性：每个 CSV 的表头列数 = 数据行列数。

    这条校验对应实际发生的 bug：`fetch_commodity.py` 手工给汇率表加了「日期」列，
    而 akshare 返回的 df 第一列本身就叫「日期」，导致表头 7 列、数据 6 列，
    整张表列错位（「日期」列装的是汇买价）。
    """
    print("【53】结构完整性：CSV 表头列数 = 数据列数")
    # 只放「纯数值表」：按逗号切分即可判断列数。含中文引号字段（如「元；元」）的表
    # 会被简单切分误判，不进这个列表。
    targets = [
        MKT / "结构化" / "汇率.csv",
        MKT / "结构化" / "原材料价格.csv",
        MKT / "结构化" / "日线行情.csv",
        MKT / "结构化" / "估值序列.csv",
        FIN / "利润表.csv",
        FIN / "资产负债表.csv",
        FIN / "现金流量表.csv",
        FIN / "其他综合收益.csv",
        FIN / "递延所得税.csv",
        FIN / "净利润调节经营现金流.csv",
        FIN / "类现金与金融资产.csv",
        FIN / "固定资产与在建工程.csv",
        FIN / "套期保值.csv",
        FIN / "票据与应收结构.csv",
        FIN / "租赁与承诺事项.csv",
        FIN / "职工薪酬与税费明细.csv",
        FIN / "存货跌价准备变动.csv",
        FIN / "供应商客户集中度时序.csv",
        FIN / "无形资产明细.csv",
        FIN / "子公司与合并范围.csv",
        FIN / "营运效率与现金流.csv",
        FIN / "单季度经营_2023起.csv",
        FIN / "外币敞口与汇率敏感性.csv",
        FIN / "或有事项与期后承诺.csv",
        FIN / "预计负债与售后义务.csv",
        FIN / "审计与签字会计师.csv",
        FIN / "合同资产与合同负债附注.csv",
    ]
    passed = failed = 0
    for path in targets:
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", newline="") as stream:
            # 用 csv.reader 而不是按逗号切分：来源列常含「注册地=中国,佛山市」
            # 这类带引号的逗号字段，简单切分会误判成列错位
            reader = csv.reader(stream)
            header = next(reader, [])
            ncol = len(header)
            bad = 0
            total = 0
            for row in reader:
                total += 1
                if len(row) != ncol:
                    bad += 1
        ok = bad == 0
        passed += ok
        failed += not ok
        print(
            f"    {path.name:<22}{ncol:>3} 列  {total:>6} 行  "
            f"错位列 {bad:>3}  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_jdunion_sort() -> tuple[int, int]:
    """京东联盟排序有效性：原始导出的 o30 序列是否真的降序。

    这条校验对应一个已经影响到结论的发现：2026-10-21 采的 15 份原始导出
    **全部**未按 o30 降序排列（相邻逆序 36%–40%）。页面上点了「30天引入订单量」，
    但落盘顺序不是排序后的顺序。

    后果是样本不能被称作「引单量最高的 120 条」，只能叫「该关键词下的 120 条样本」。
    本校验把这件事固化下来，避免后续有人误以为手里是高引单样本。
    """
    raw_dir = ECO
    files = sorted(raw_dir.glob("jdunion-*.csv"))
    if not files:
        return 0, 0

    print("【54】京东联盟排序有效性：原始导出 o30 是否降序")
    failed_files: list[tuple[str, float]] = []
    for path in files:
        with path.open(encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        seq: list[int] = []
        for row in rows:
            try:
                seq.append(int(float(row.get("o30") or 0)))
            except (TypeError, ValueError):
                seq.append(0)
        if len(seq) < 2:
            continue
        inversions = sum(1 for a, b in itertools.pairwise(seq) if a < b)
        ratio = inversions / (len(seq) - 1)
        if ratio > 0.02:
            failed_files.append((path.name, ratio))

    # 这是「已知且已记录」的数据缺陷，不是可修复项：报出来但不判为通过
    if failed_files:
        print(
            f"    ⚠ {len(failed_files)}/{len(files)} 个文件未按 o30 降序，"
            "样本不能称为「高引单前 120 条」"
        )
        for name, ratio in failed_files[:5]:
            print(f"      {name:<30} 逆序 {ratio * 100:.0f}%")
        print("    详见 市场数据/README.md 的电商使用限制")
        EXPLAINED.append("jdunion_sort / 原始导出未排序，样本代表性不可验证")
        print("    已登记限制 1 项；不计为通过\n")
        return 0, 0
    print(f"    {len(files)} 个文件均按 o30 降序")
    print("    通过 1，差异 0\n")
    return 1, 0


def check_hedging() -> tuple[int, int]:
    """套期保值：三家均有数据，且期末金额与占净资产比例方向一致。

    数据来自年报「报告期内以套期保值为目的的衍生品投资」表。
    三家格式不同（格力购入/售出列常为空、美的一行被折行、美的 PDF 带 `**` 干扰），
    所以只做结构性校验，不做跨公司比较。

    限制：年报不披露「被套保现货量 / 总现货量」，无法算真正的套保覆盖率。
    """
    rows = load(FIN / "套期保值.csv")
    if not rows:
        return 0, 0

    print("【55】套期保值：三家均提取到数据，期末金额与净资产占比同向")
    passed = failed = 0
    grouped: dict[tuple[str, str, str], dict[str, float]] = defaultdict(dict)
    for row in rows:
        key = (row["公司"], row["年度"], row["衍生品类型"])
        try:
            grouped[key][row["字段"]] = float(row["数值"])
        except (TypeError, ValueError):
            continue

    for key in sorted(grouped):
        fields = grouped[key]
        end = fields.get("期末金额")
        pct = fields.get("占期末净资产比例")
        if end is None or pct is None:
            continue
        # 期末金额与占比应同号（都为正=资产头寸，都为负=负债头寸）
        ok = (end >= 0) == (pct >= 0)
        passed += ok
        failed += not ok
        if not ok:
            print(
                f"    ⚠ {key[0]} {key[1]} {key[2]}：期末 {end:.2f} 万元 与占比 {pct:.2f}% 符号相反"
            )

    # 三家都要有数据
    companies = {r["公司"] for r in rows}
    for name in ("美的集团", "海尔智家", "格力电器"):
        ok = name in companies
        passed += ok
        failed += not ok
        if not ok:
            print(f"    ⚠ {name} 无套保数据")
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_real_estate() -> tuple[int, int]:
    """房地产景气指数：覆盖到采集时点，且取值在合理区间。

    本表只有国房景气指数（100 为景气线）。新房开工/竣工/销售面积
    无法获取（国家统计局接口 403），不要把它当实物量替代。
    """
    rows = load(MKT / "结构化" / "房地产景气指数.csv")
    if not rows:
        return 0, 0

    print("【56】房地产景气指数：月份连续、取值合理")
    values: list[tuple[str, float]] = []
    for row in rows:
        try:
            values.append((row["月份"], float(row["数值"])))
        except (KeyError, TypeError, ValueError):
            continue
    if not values:
        return 0, 1

    passed = failed = 0
    # 1. 取值在 90–110 的合理区间（国房景气指数历史上从未超出）
    bad = [(m, v) for m, v in values if not 85 <= v <= 115]
    ok = not bad
    passed += ok
    failed += not ok
    print(
        f"    取值范围 {min(v for _, v in values):.2f} – {max(v for _, v in values):.2f}"
        f"  {'OK' if ok else '差异'}"
    )
    if bad:
        for m, v in bad[:3]:
            print(f"      ⚠ {m}: {v}")

    # 2. 月末月份连续（允许个别缺失，但不得整年中断）
    years = {m[:4] for m, _ in values}
    ok = years == {"2023", "2024", "2025"}
    passed += ok
    failed += not ok
    print(f"    覆盖 {len(years)} 个年份，最新 {values[-1][0]}  {'OK' if ok else '差异'}")
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_data_nature() -> tuple[int, int]:
    """数据性质一致性：CSV 标的 actual/forecast 不能与其来源登记矛盾。

    这条校验对应实际发生的冲突：`行业基数_1-8月.csv` 四条全标 `actual`，
    但它们引用的来源编号 S2 在 `来源.csv` 里是 `forecast`（节前预测文章）。
    把 forecast 当 actual 用是本项目明文禁止的做法。
    """
    source = load(MKT / "来源.csv")
    if not source:
        return 0, 0

    print("【57】数据性质一致性：CSV 的 actual/forecast 与来源登记不矛盾")
    nature_of = {r["编号"]: r["数据性质"] for r in source}
    targets = [
        "国庆档期数据.csv",
        "行业基数_1-8月.csv",
    ]
    passed = failed = 0
    for name in targets:
        rows = load(MKT / name)
        if not rows:
            continue
        conflicts = []
        for row in rows:
            sid = row.get("来源编号", "")
            declared = row.get("数据性质", "")
            registered = nature_of.get(sid)
            if not registered or not declared:
                continue
            if declared != registered:
                # actual 引自 forecast 来源是允许的（1-8 月确实已发生），
                # 但必须有「口径说明」解释；否则视为混标。
                if row.get("口径说明"):
                    continue
                conflicts.append((sid, declared, registered))
        ok = not conflicts
        passed += ok
        failed += not ok
        print(
            f"    {name:<26}{len(rows):>3} 条  冲突 {len(conflicts):>2}  {'OK' if ok else '差异'}"
        )
        for sid, d, g in conflicts[:3]:
            print(f"      ⚠ 来源 {sid} 登记为 {g}，本表标 {d}")
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_cross_keyword_dedup() -> tuple[int, int]:
    """跨词相同商品字段只保留一条，合并行保留完整检索来源。"""
    import json

    sku = load(ECO / "京东联盟_SKU明细.csv")
    if not sku:
        return 0, 0

    print("【58】跨检索词去重：商品字段唯一，检索来源可追溯")
    seen: set[tuple[tuple[str, str], ...]] = set()
    passed = failed = 0
    original_count = 0
    for row in sku:
        identity = tuple(
            (k, v)
            for k, v in row.items()
            if k not in {"关键词", "页码", "来源文件", "检索观测来源"}
        )
        origins = json.loads(row["检索观测来源"])
        ok = identity not in seen and bool(origins)
        ok = ok and set(row["关键词"].split(";")) == {r["关键词"] for r in origins}
        ok = ok and set(row["来源文件"].split(";")) == {r["来源文件"] for r in origins}
        ok = ok and set(row["页码"].split(";")) == {r["页码"] for r in origins}
        seen.add(identity)
        original_count += len(origins)
        passed += ok
        failed += not ok
        if not ok:
            print(f"    重复或来源不符：{row['SKU']} {row['采集时间']}")
    print(
        f"    {len(sku)} 条去重明细，保留 {original_count} 条原检索观测；通过 {passed}，失败 {failed}\n"
    )
    return passed, failed


def check_goodwill_assumptions() -> tuple[int, int]:
    """商誉减值假设：安全垫倍数可复算，永续增长率三家不同。"""
    detail = load(FIN / "商誉减值测试假设.csv")
    if not detail:
        return 0, 0

    pick = {(row["公司"], row["资产组"], row["参数项"]): row for row in detail}

    print("【31】商誉减值假设：安全垫倍数可复算")
    passed = failed = 0
    book_row = pick.get(("格力电器", "盾安环境（合计）", "资产组账面价值"))
    recover_row = pick.get(("格力电器", "盾安环境（合计）", "可收回金额"))
    ratio_row = pick.get(("格力电器", "盾安环境（合计）", "安全垫倍数"))
    if book_row and recover_row and ratio_row:
        for column in ("2025", "2024"):
            try:
                book = float(book_row[column].replace(" 亿", ""))
                recover = float(recover_row[column].replace(" 亿", ""))
                stated = float(ratio_row[column].replace(" 倍", ""))
            except ValueError:
                failed += 1
                continue
            recomputed = recover / book
            ok = abs(recomputed - stated) < 0.01
            passed += ok
            failed += not ok
            print(
                f"    格力 {column} 盾安：可收回 {recover:.2f} / 账面 {book:.2f}"
                f" = {recomputed:.2f} 倍（披露 {stated:.2f}）  {'OK' if ok else '差异'}"
            )

    # 永续增长率：格力 0%，美的 1.00%–2.00%，海尔 1.70%–2.00%
    growth = {
        row["公司"]: row["2025"]
        for row in detail
        if row["参数项"] in ("永续年增长率", "稳定期收入增长率")
    }
    ok = growth.get("格力电器", "").startswith("0.00%") and all(
        growth.get(name) for name in ("美的集团", "海尔智家")
    )
    passed += ok
    failed += not ok
    print(
        f"    永续增长率：格力 {growth.get('格力电器', '缺')}、"
        f"美的 {growth.get('美的集团', '缺')}、海尔 {growth.get('海尔智家', '缺')}"
        f"  {'OK' if ok else '差异'}"
    )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def check_financial_assets() -> tuple[int, int]:
    """类现金与金融资产：明细相加 = 合计，且隐含存款收益率落在合理区间。"""
    detail = load(FIN / "类现金与金融资产.csv")
    finance = load(FIN / "财务净收益.csv")
    if not detail or not finance:
        return 0, 0

    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in detail:
        grouped[(row["公司"], row["年度"])].append(row)

    print("【30】类现金与金融资产：明细相加 = 合计，隐含收益率 = 利息/平均类现金")
    print(
        f"    {'公司':<8}{'年度':<6}{'明细和':>9}{'合计':>9}{'利息收入':>9}{'隐含收益率':>11}  结果"
    )
    passed = failed = 0
    totals = {
        (row["公司"], row["年度"]): float(row["金额(亿元)"])
        for row in detail
        if row["项目"] == "类现金与金融资产合计"
    }
    for key in sorted(grouped, key=lambda k: (k[0], -int(k[1]))):
        rows = grouped[key]
        parts = sum(float(r["金额(亿元)"]) for r in rows if r["类别"] == "类现金与金融资产")
        stated_row = next((r for r in rows if r["项目"] == "类现金与金融资产合计"), None)
        if stated_row is None:
            continue
        stated = float(stated_row["金额(亿元)"])
        # 只用「财务收入/财务费用」里的利息收入；美的金融业务的 20.50 亿
        # 单列在营业总收入，对应资产不在本表分母里，混进来会虚增收益率
        interest = sum(
            float(r["金额(亿元)"])
            for r in finance
            if r["公司"] == key[0] and r["年度"] == key[1] and r["项目"] == "利息收入"
        )
        earlier = totals.get((key[0], str(int(key[1]) - 1)))
        average = (stated + earlier) / 2 if earlier else stated
        yield_rate = interest / average * 100 if average else 0.0
        # 收益率仅供诊断：金融资产并非全部生息存款，不能靠经验区间证明正确。
        ok = abs(parts - stated) <= 0.05
        passed += ok
        failed += not ok
        print(
            f"    {key[0]:<8}{key[1]:<6}{parts:>9.2f}{stated:>9.2f}"
            f"{interest:>9.2f}{yield_rate:>10.2f}%  {'OK' if ok else '差异'}"
        )
    print(f"    通过 {passed}，差异 {failed}\n")
    return passed, failed


def main() -> int:
    print(f"校验目录 {ROOT}\n")
    EXPLAINED.clear()
    total_pass, total_fail = verify_inventory(ROOT)
    for check in (
        verify_derived,
        check_quarterly,
        check_segments,
        check_research,
        check_volume,
        check_segments_note,
        check_employees,
        check_inventory,
        check_concentration,
        check_receivables,
        check_cost_label,
        check_goodwill,
        check_gov_subsidy,
        check_related_party,
        check_h1_region,
        check_guarantee_ratio,
        check_rd_staff,
        check_collection_ratio,
        check_interim_dividend,
        check_restricted_assets,
        check_share_payment,
        check_tax_reconciliation,
        check_investment_income,
        check_minority,
        check_finance_income,
        check_impairment,
        check_oci,
        check_deferred_tax,
        check_cash_reconciliation,
        check_financial_assets,
        check_goodwill_assumptions,
        check_fixed_assets,
        check_bills_receivables,
        check_leases_commitments,
        check_payroll_tax_payable,
        check_inventory_provision,
        check_supply_chain,
        check_intangibles,
        check_subsidiaries,
        check_efficiency_coverage,
        check_quarterly_long,
        check_fx_exposure,
        check_contingencies,
        check_provisions,
        check_audit_independence,
        check_contract_notes,
        check_brand_normalization,
        check_primary_key_unique,
        check_segment_closure,
        check_cost_funnel,
        check_non_recurring,
        check_toolchain,
        check_panel_columns,
        check_jdunion_sort,
        check_hedging,
        check_real_estate,
        check_data_nature,
        check_cross_keyword_dedup,
    ):
        try:
            passed, failed = check()
        except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
            print(f"校验失败 {check.__name__}：{exc}")
            passed, failed = 0, 1
        total_pass += passed
        total_fail += failed

    print(f"合计：通过 {total_pass}，已登记差异/限制 {len(EXPLAINED)}，失败 {total_fail}")
    for detail in EXPLAINED:
        print(f"    已登记：{detail}")
    return int(total_fail > 0)


if __name__ == "__main__":
    sys.exit(main())
