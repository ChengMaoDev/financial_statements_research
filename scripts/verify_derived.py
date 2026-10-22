"""研究期间报表恒等式与本轮修正公式的独立复算。

2023—2025年度及截至2026H1的累计报表逐期勾稽。金额容差为原值1元或
亿元表末位舍入；百分比容差为 0.02 个百分点。恒等式和可复现不代表原始披露真实。
"""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path

from research_scope import usable_report, usable_segment

ROOT = Path(__file__).resolve().parent.parent


def load(root: Path, name: str) -> list[dict[str, str]]:
    with (root / name).open(encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def verify(root: Path = ROOT) -> tuple[int, int]:
    passed = failed = 0

    def check(label: str, actual: float, expected: float, tolerance: float = 0.02) -> None:
        nonlocal passed, failed
        ok = abs(actual - expected) <= tolerance
        passed += ok
        failed += not ok
        if not ok:
            print(f"    复算失败 {label}：{actual:.6f} ≠ {expected:.6f}")

    books: dict[str, dict[tuple[str, str], dict[str, float]]] = {}
    for name in ("资产负债表", "利润表", "现金流量表"):
        grouped: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
        for row in load(root, f"财务数据/{name}.csv"):
            if not "20230101" <= row["报告期"] <= "20260630":
                continue
            try:
                grouped[(row["公司"], row["报告期"])][row["科目"]] = float(row["数值"])
            except ValueError:
                continue
        books[name] = grouped
    equations = {
        "资产负债表": (
            ("资产总计", ("负债合计", "所有者权益(或股东权益)合计")),
            ("资产总计", ("流动资产合计", "非流动资产合计")),
            ("负债合计", ("流动负债合计", "非流动负债合计")),
            ("所有者权益(或股东权益)合计", ("归属于母公司股东权益合计", "少数股东权益")),
        ),
        "利润表": (("净利润", ("归属于母公司所有者的净利润", "少数股东损益")),),
        "现金流量表": (
            (
                "现金及现金等价物净增加额",
                (
                    "经营活动产生的现金流量净额",
                    "投资活动产生的现金流量净额",
                    "筹资活动产生的现金流量净额",
                    "汇率变动对现金及现金等价物的影响",
                ),
            ),
        ),
    }
    for name, statement_groups in books.items():
        for (company, period), data in statement_groups.items():
            for total, parts in equations[name]:
                check(
                    f"{company} {period} {total}", data[total], sum(data[part] for part in parts), 1
                )
    income = books["利润表"]
    balance = books["资产负债表"]
    for row in load(root, "财务数据/有息负债与偿债能力.csv"):
        company, year = row["公司"], row["年度"]
        bs = balance[(company, f"{year}1231")]
        debt = sum(
            bs.get(item, 0.0)
            for item in (
                "短期借款",
                "一年内到期的非流动负债",
                "长期借款",
                "应付债券",
                "租赁负债",
                "应付短期债券",
            )
        )
        net = debt - bs.get("货币资金", 0.0) - bs.get("交易性金融资产", 0.0)
        check(f"{company} {year} 有息负债", float(row["有息负债合计(亿元)"]), debt / 1e8, 0.006)
        check(
            f"{company} {year} 净负债率",
            float(row["净负债率%"]),
            net / bs["归属于母公司股东权益合计"] * 100,
            0.006,
        )
    comparison = {r["指标"]: r for r in load(root, "财务数据/三家对比_2025.csv")}
    caps = {r["公司"]: float(r["总市值"]) for r in load(root, "财务数据/公司概况.csv")}
    for company in caps:
        check(
            f"{company} PB",
            float(comparison["PB(市值/归母净资产)"][company]),
            caps[company] / balance[(company, "20251231")]["归属于母公司股东权益合计"],
            0.006,
        )
    h1 = {r["指标"]: r for r in load(root, "财务数据/三家对比_2026H1.csv")}
    for company in caps:
        revenue = income[(company, "20260630")]["营业收入"]
        overseas = float(h1["海外收入"][company].replace(",", ""))
        check(
            f"{company} 海外占比",
            float(h1["海外收入占比"][company]),
            overseas * 1e8 / revenue * 100,
        )
    top5: dict[tuple[str, str, str], dict[str, dict[str, str]]] = defaultdict(dict)
    for row in load(root, "财务数据/供应商客户集中度时序.csv"):
        if row["类别"] in ("前五大客户", "前五大供应商"):
            top5[(row["公司"], row["年度"], row["类别"])][row["项目"]] = row
    for key, entries in top5.items():
        total, related = entries["前五名合计"], entries["其中:关联方"]
        if related["金额(亿元)"] and related["占比%"]:
            expected = float(total["金额(亿元)"]) * float(related["占比%"]) / float(total["占比%"])
            # 海尔金额、占比都是独立披露值，比例舍入可产生较大反推误差。
            if related["数据性质"] == "计算值":
                check(f"{key} 关联方金额", float(related["金额(亿元)"]), expected, 0.03)
    closes: dict[tuple[str, str], tuple[str, float]] = {}
    for row in load(root, "市场数据/结构化/日线行情_不复权.csv"):
        date = row["日期"]
        if date[:4] >= "2026":
            continue
        key = (row["公司"], date[:4])
        if key not in closes or closes[key][0] < date:
            closes[key] = date, float(row["收盘"])
    for row in load(root, "财务数据/股东回报.csv"):
        key = (row["公司"], row["年度"])
        point = closes.get(key)
        if point:
            check(f"{key} 年末价", float(row["年末收盘价(元)"]), point[1], 0.001)
            check(
                f"{key} 年末日期",
                float(row["年末价格日期"].replace("-", "")),
                float(point[0].replace("-", "")),
                0,
            )
            check(
                f"{key} 股息率",
                float(row["股息率%(近似)"]),
                float(row["每股派息合计(元)"]) / point[1] * 100,
                0.006,
            )
        elif row["年末价格日期"] or row["股息率%(近似)"]:
            check(f"{key} 缺年末价应留空", 1, 0, 0)
    groups: dict[tuple[str, str, str, str, str, str], dict[str, float]] = defaultdict(dict)
    for row in load(root, "市场数据/电商/京东联盟_SKU明细.csv"):
        degenerate = row["引单量_30天"] == "0" and row["支出佣金_30天"] in ("", "0.00")
        key = (
            row["品类"],
            row["店铺"],
            row["引单量_30天"],
            row["支出佣金_30天"],
            row["SKU"] if degenerate else "",
            row["采集时间"][:10],
        )
        groups[key][row["SKU"]] = float(row["到手价_元"])
    panel = load(root, "市场数据/电商/京东联盟_组级面板.csv")
    check("京东组标识唯一", len({r["组标识"] for r in panel}), len(panel), 0)
    check("京东组数", len(panel), len(groups), 0)
    for row in panel:
        prefix = (row["品类"], row["店铺"], row["引单量_30天"], row["支出佣金_30天"])
        candidates = [
            members
            for key, members in groups.items()
            if key[:4] == prefix and key[5] == row["采集日期"]
        ]
        matches = [
            members
            for members in candidates
            if len(members) == int(row["SKU数"])
            and abs(statistics.median(members.values()) - float(row["代表到手价_元"])) <= 0.006
        ]
        check(f"京东组 {row['组标识']} 型号数和价格", bool(matches), 1, 0)
    for name in ("资产负债表", "利润表", "现金流量表", "主要财务指标"):
        bad = [
            row
            for row in load(root, f"财务数据/{name}.csv")
            if not usable_report(row["公司"], row["报告期"])
        ]
        check(f"{name} 不得恢复已删除异常报告期", len(bad), 0, 0)
    segments = load(root, "财务数据/主营构成.csv")
    check(
        "不得恢复海尔2018未确认的产品构成",
        sum(not usable_segment(row["公司"], row["报告日期"], row["分类类型"]) for row in segments),
        0,
        0,
    )
    collection = load(root, "财务数据/收现质量.csv")
    check("不得恢复增值税还原估算列", "含税还原后收现比(估)" in collection[0], 0, 0)
    industry = load(root, "市场数据/国庆档期数据.csv")
    check(
        "不得恢复预测和不可核实营销记录",
        sum(row["数据性质"] != "actual" or row["来源编号"] not in {"S1", "S5"} for row in industry),
        0,
        0,
    )
    quarterly = load(root, "财务数据/单季度经营_2023起.csv")
    excluded = {
        ("美的集团", "2023"),
        ("格力电器", "2023"),
        ("海尔智家", "2023"),
        ("海尔智家", "2024"),
    }
    for row in quarterly:
        if row["季度"] == "Q4" and (row["公司"], row["年度"]) in excluded:
            check(
                f"{row['公司']} {row['年度']} 不得恢复混合版本成本",
                bool(row["营业成本(亿元)"] or row["单季毛利率%"] or row["营业收入_累计相减(亿元)"]),
                0,
                0,
            )
    print(f"报表勾稽与公式复算：通过 {passed}，失败 {failed}")
    return passed, failed


if __name__ == "__main__":
    raise SystemExit(int(verify()[1] > 0))
