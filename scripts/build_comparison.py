"""生成三家公司核心指标横向对比表。

从已采集的结构化数据中提取可比指标，输出一张宽表。
所有数值均标注来源与口径，便于回溯校验。

用法：
    uv run python3 scripts/build_comparison.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "财务数据"
OUT = ROOT / "财务数据" / "三家对比_2025.csv"

COMPANIES = ["美的集团", "海尔智家", "格力电器"]
PERIOD = "20251231"

# 指标 → akshare 中的名称
METRICS = [
    "营业总收入",
    "营业成本",
    "归母净利润",
    "扣非净利润",
    "经营现金流量净额",
    "股东权益合计(净资产)",
    "毛利率",
    "销售净利率",
    "净资产收益率(ROE)",
    "资产负债率",
    "基本每股收益",
    "每股净资产",
    "商誉",
]


def load_metrics() -> dict[tuple[str, str], float]:
    path = DATA / "主要财务指标.csv"
    values: dict[tuple[str, str], float] = {}
    with path.open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["报告期"] != PERIOD:
                continue
            try:
                values[(row["公司"], row["指标"])] = float(row["数值"])
            except ValueError:
                continue
    return values


def load_assets() -> dict[str, float]:
    """从资产负债表取总资产与总负债。"""
    path = DATA / "资产负债表.csv"
    result: dict[str, float] = {}
    with path.open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["报告期"] != PERIOD:
                continue
            if row["科目"] == "资产总计":
                try:
                    result[row["公司"]] = float(row["数值"])
                except ValueError:
                    continue
    return result


def load_market_cap() -> dict[str, float]:
    path = DATA / "公司概况.csv"
    result: dict[str, float] = {}
    with path.open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            try:
                result[row["公司"]] = float(row["总市值"])
            except (ValueError, KeyError):
                continue
    return result


def load_ttm_valuation() -> dict[tuple[str, str], float]:
    """读取已采集的估值序列，取每家最新一点。"""
    path = ROOT / "市场数据" / "结构化" / "估值序列.csv"
    latest: dict[tuple[str, str], tuple[str, float]] = {}
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            try:
                value = float(row["value"])
            except (ValueError, KeyError):
                continue
            key = (row["公司"], row["指标"])
            date = row.get("date", "")
            if key not in latest or date > latest[key][0]:
                latest[key] = (date, value)
    return {key: value for key, (_, value) in latest.items()}


def main() -> int:
    metrics = load_metrics()
    assets = load_assets()
    caps = load_market_cap()
    if not metrics:
        print("缺少主要财务指标数据", file=sys.stderr)
        return 1

    rows: list[list[str]] = []
    header = ["指标", "单位", *COMPANIES]

    # 金额类（亿元）
    # 注意：主要财务指标.csv 的「营业成本」实为「营业总成本」（含税金、销售、
    # 管理、研发、财务费用），与利润表的「营业成本」不是一回事，这里必须用利润表。
    income_cost: dict[str, float] = {}
    # 「营业收入」与「营业总收入」是两个口径：后者含其他业务收入。
    # 三家对比_2026H1.csv 用的是「营业收入」，本表若只给「营业总收入」，
    # 两份对比文件无法直接对齐（美的差 20.50 亿、格力差 6.71 亿）。两个都入表。
    income_revenue: dict[str, float] = {}
    with (DATA / "利润表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["报告期"] != PERIOD or row["科目"] not in ("营业成本", "营业收入"):
                continue
            try:
                value = float(row["数值"])
            except ValueError:
                continue
            if row["科目"] == "营业成本":
                income_cost[row["公司"]] = value
            else:
                income_revenue[row["公司"]] = value

    for metric in [
        "营业总收入",
        "归母净利润",
        "扣非净利润",
        "经营现金流量净额",
        "股东权益合计(净资产)",
    ]:
        line = [metric, "亿元"]
        for company in COMPANIES:
            value = metrics.get((company, metric))
            line.append(f"{value / 1e8:.2f}" if value is not None else "")
        rows.append(line)

    line = ["营业收入", "亿元"]
    for company in COMPANIES:
        value = income_revenue.get(company)
        line.append(f"{value / 1e8:.2f}" if value is not None else "")
    rows.append(line)

    line = ["营业成本", "亿元"]
    for company in COMPANIES:
        value = income_cost.get(company)
        line.append(f"{value / 1e8:.2f}" if value is not None else "")
    rows.append(line)

    line = ["营业总成本", "亿元"]
    for company in COMPANIES:
        value = metrics.get((company, "营业成本"))
        line.append(f"{value / 1e8:.2f}" if value is not None else "")
    rows.append(line)

    # 总资产、总负债（来自资产负债表）
    for label, _key in [("总资产", "资产总计")]:
        line = [label, "亿元"]
        for company in COMPANIES:
            value = assets.get(company)
            line.append(f"{value / 1e8:.2f}" if value is not None else "")
        rows.append(line)

    # 比率类
    for metric in ["毛利率", "销售净利率", "净资产收益率(ROE)", "资产负债率"]:
        line = [metric, "%"]
        for company in COMPANIES:
            value = metrics.get((company, metric))
            line.append(f"{value:.2f}" if value is not None else "")
        rows.append(line)

    # 每股类
    for metric in ["基本每股收益", "每股净资产"]:
        line = [metric, "元"]
        for company in COMPANIES:
            value = metrics.get((company, metric))
            line.append(f"{value:.2f}" if value is not None else "")
        rows.append(line)

    # 商誉
    line = ["商誉", "亿元"]
    for company in COMPANIES:
        value = metrics.get((company, "商誉"))
        line.append(f"{value / 1e8:.2f}" if value is not None else "")
    rows.append(line)

    # 计算指标：净现比、研发强度、市值
    line = ["净现比(经营现金流/净利润)", "倍"]
    for company in COMPANIES:
        cash = metrics.get((company, "经营现金流量净额"))
        profit = metrics.get((company, "归母净利润"))
        line.append(f"{cash / profit:.2f}" if cash and profit else "")
    rows.append(line)

    line = ["总市值", "亿元"]
    for company in COMPANIES:
        cap = caps.get(company)
        line.append(f"{cap / 1e8:.2f}" if cap else "")
    rows.append(line)

    line = ["PE(市值/归母净利润)", "倍"]
    for company in COMPANIES:
        cap = caps.get(company)
        profit = metrics.get((company, "归母净利润"))
        line.append(f"{cap / profit:.2f}" if cap and profit else "")
    rows.append(line)

    # PB 必须用**归母**净资产：与同表「每股净资产」（也是归母口径）保持一致。
    # 用「股东权益合计」（含少数股东）会让 PB 偏低，且 PB 与每股净资产互相矛盾。
    # 美的少数股东 132.03 亿，差异 2.71 → 2.87。
    line = ["PB(市值/归母净资产)", "倍"]
    for company in COMPANIES:
        cap = caps.get(company)
        book = metrics.get((company, "每股净资产"))
        shares = metrics.get((company, "基本每股收益"))
        # 归母净资产 = 总股本 × 每股净资产；总股本用「归母净利润 / 基本每股收益」反推
        profit = metrics.get((company, "归母净利润"))
        parent_equity = None
        if book is not None and shares and profit:
            share_count = profit / shares
            parent_equity = book * share_count
        line.append(f"{cap / parent_equity:.2f}" if cap and parent_equity else "")
    rows.append(line)

    # 市场口径 PE(TTM) / PB，来自百度估值接口，供与上面自算值对照
    ttm = load_ttm_valuation()
    line = ["PE(TTM,市场口径)", "倍"]
    for company in COMPANIES:
        value = ttm.get((company, "市盈率(TTM)"))
        line.append(f"{value:.2f}" if value else "")
    rows.append(line)

    line = ["PB(市场口径)", "倍"]
    for company in COMPANIES:
        value = ttm.get((company, "市净率"))
        line.append(f"{value:.2f}" if value else "")
    rows.append(line)

    # 研发强度（来自治理与经营披露）
    research: dict[str, float] = {}
    research_path = DATA / "治理与经营披露.csv"
    if research_path.exists():
        with research_path.open(encoding="utf-8-sig") as stream:
            for row in csv.DictReader(stream):
                if row["报告期"] != "2025 年度":
                    continue
                try:
                    research[row["公司"]] = float(row["研发投入_合计"])
                except (ValueError, KeyError):
                    continue
    line = ["研发投入合计", "亿元"]
    for company in COMPANIES:
        value = research.get(company)
        line.append(f"{value / 1e8:.2f}" if value else "")
    rows.append(line)

    line = ["研发强度(研发投入/营收)", "%"]
    for company in COMPANIES:
        value = research.get(company)
        revenue = metrics.get((company, "营业总收入"))
        line.append(f"{value / revenue * 100:.2f}" if value and revenue else "")
    rows.append(line)

    line = ["员工人数", "人"]
    employees: dict[str, float] = {}
    if research_path.exists():
        with research_path.open(encoding="utf-8-sig") as stream:
            for row in csv.DictReader(stream):
                if row["报告期"] != "2025 年度":
                    continue
                try:
                    employees[row["公司"]] = float(row["员工人数"])
                except (ValueError, KeyError):
                    continue
    for company in COMPANIES:
        value = employees.get(company)
        line.append(f"{value:.0f}" if value else "")
    rows.append(line)

    line = ["人均营收", "万元"]
    for company in COMPANIES:
        revenue = metrics.get((company, "营业总收入"))
        count = employees.get(company)
        line.append(f"{revenue / count / 1e4:.2f}" if revenue and count else "")
    rows.append(line)

    line = ["人均净利润", "万元"]
    for company in COMPANIES:
        profit = metrics.get((company, "归母净利润"))
        count = employees.get(company)
        line.append(f"{profit / count / 1e4:.2f}" if profit and count else "")
    rows.append(line)

    # ---- 以下为新增维度：薪酬、集中度、债务、返利、现金流、利润质量 ----
    def load_lookup(filename: str, key_field: str, value_field: str) -> dict[str, str]:
        """按 (公司) 取 2025 年的某个字段。"""
        path = DATA / filename
        result: dict[str, str] = {}
        if not path.exists():
            return result
        with path.open(encoding="utf-8-sig") as stream:
            for row in csv.DictReader(stream):
                if row.get("年度") != "2025":
                    continue
                if row.get(key_field) != value_field:
                    continue
                result.setdefault(row["公司"], row.get("数值", row.get("人数", "")))
        return result

    def wide(filename: str, column: str) -> dict[str, str]:
        path = DATA / filename
        result: dict[str, str] = {}
        if not path.exists():
            return result
        with path.open(encoding="utf-8-sig") as stream:
            for row in csv.DictReader(stream):
                if row.get("年度") != "2025":
                    continue
                result[row["公司"]] = row.get(column, "")
        return result

    def add_row(label: str, unit: str, values: dict[str, str]) -> None:
        rows.append([label, unit] + [values.get(c, "") for c in COMPANIES])

    # 人均薪酬：员工构成.csv 中「薪酬/人均薪酬」行，单位元
    salary_rows = {}
    with (DATA / "员工构成.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["年度"] == "2025" and row["类别"] == "人均薪酬":
                try:
                    salary_rows[row["公司"]] = f"{float(row['人数'].replace(',', '')) / 1e4:.2f}"
                except ValueError:
                    continue
    add_row("人均薪酬", "万元", salary_rows)

    # 集中度：客户供应商集中度.csv
    concentration: dict[str, dict[str, str]] = {}
    with (DATA / "客户供应商集中度.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["年度"] != "2025" or row["维度"] not in ("客户", "供应商"):
                continue
            concentration.setdefault(row["公司"], {})[row["维度"]] = row["占总额比例%"]
    add_row(
        "前五大客户集中度",
        "%",
        {c: v.get("客户", "") for c, v in concentration.items()},
    )
    add_row(
        "前五大供应商集中度",
        "%",
        {c: v.get("供应商", "") for c, v in concentration.items()},
    )

    # 债务：有息负债与偿债能力.csv
    add_row(
        "有息负债",
        "亿元",
        wide("有息负债与偿债能力.csv", "有息负债合计(亿元)"),
    )
    add_row(
        "净有息负债",
        "亿元",
        wide("有息负债与偿债能力.csv", "净有息负债(亿元)"),
    )
    add_row(
        "利息保障倍数",
        "倍",
        wide("有息负债与偿债能力.csv", "利息保障倍数"),
    )

    # 渠道返利与占款
    add_row(
        "预提销售返利",
        "亿元",
        wide("渠道返利与占款.csv", "预提销售返利(亿元)"),
    )
    add_row(
        "净占款(不含返利)",
        "亿元",
        wide("渠道返利与占款.csv", "净占款-不含返利(亿元)"),
    )

    # 现金流结构
    add_row("自由现金流", "亿元", wide("现金流结构.csv", "自由现金流(亿元)"))
    add_row("资本开支", "亿元", wide("现金流结构.csv", "资本开支(亿元)"))
    add_row(
        "资本开支强度",
        "%",
        wide("现金流结构.csv", "资本开支强度%"),
    )

    # 利润质量
    add_row(
        "非经常性损益占净利润",
        "%",
        wide("利润质量.csv", "非经常性损益占净利润%"),
    )
    add_row(
        "其他收益占利润总额",
        "%",
        wide("利润质量.csv", "其他收益占利润总额%"),
    )
    add_row(
        "减值损失占利润总额",
        "%",
        wide("利润质量.csv", "减值损失占利润总额%"),
    )

    # 毛利率季节性：Q4 单季 vs 全年
    q4: dict[str, str] = {}
    q4_path = DATA / "分季度盈利能力.csv"
    if q4_path.exists():
        with q4_path.open(encoding="utf-8-sig") as stream:
            for row in csv.DictReader(stream):
                if row["年度"] == "2025" and row["季度"] == "Q4":
                    q4[row["公司"]] = row["单季毛利率%"]
    add_row("Q4 单季毛利率", "%", q4)

    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)

    # 控制台输出
    print(f"{'指标':<26}{'单位':<6}" + "".join(f"{c:>14}" for c in COMPANIES))
    print("-" * 76)
    for row in rows:
        print(f"{row[0]:<26}{row[1]:<6}" + "".join(f"{v:>14}" for v in row[2:]))

    print(f"\n写入 {OUT.relative_to(ROOT)}")
    print("口径：2025 年度合并报表；市值为采集时点（2026-10-21）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
