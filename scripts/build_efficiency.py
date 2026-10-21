"""计算营运资本周期与现金流质量指标。

这些是判断商业模式优劣的核心指标，直接反映三家的差异：
- 现金转换周期（CCC）：格力的渠道压货模式 vs 美的的 T+3 vs 海尔的全球分销
- 净现比：经营现金流 / 归母净利润，检验利润含金量
- 自由现金流：经营现金流 - 资本开支
- 营运资本占用：应收 + 存货 - 应付

所有输入来自资产负债表与现金流量表，输出标注为计算值。

用法：
    uv run python3 scripts/build_efficiency.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIN = ROOT / "财务数据"
OUT = FIN / "营运效率与现金流.csv"

COMPANIES = ["美的集团", "海尔智家", "格力电器"]
YEARS = ["2021", "2022", "2023", "2024", "2025"]


def load(name: str) -> list[dict[str, str]]:
    path = FIN / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def index_statement(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], float]:
    """(公司, 报告期, 科目) → 数值。"""
    result: dict[tuple[str, str, str], float] = {}
    for row in rows:
        try:
            result[(row["公司"], row["报告期"], row["科目"])] = float(row["数值"])
        except (ValueError, KeyError):
            continue
    return result


def pick(
    data: dict[tuple[str, str, str], float],
    company: str,
    period: str,
    subjects: list[str],
) -> float | None:
    """按优先级取第一个存在的科目。"""
    for subject in subjects:
        value = data.get((company, period, subject))
        if value is not None:
            return value
    return None


def main() -> int:
    balance = index_statement(load("资产负债表.csv"))
    income = index_statement(load("利润表.csv"))
    cashflow = index_statement(load("现金流量表.csv"))
    if not balance or not income:
        print("缺少报表数据", file=sys.stderr)
        return 1

    rows: list[list[str]] = []
    for company in COMPANIES:
        for year in YEARS:
            period = f"{year}1231"
            revenue = pick(income, company, period, ["营业收入"])
            cost = pick(income, company, period, ["营业成本"])
            profit = pick(income, company, period, ["归属于母公司所有者的净利润"])
            operating = pick(cashflow, company, period, ["经营活动产生的现金流量净额"])
            capex = pick(
                cashflow,
                company,
                period,
                [
                    "购建固定资产、无形资产和其他长期资产支付的现金",
                    "购建固定资产、无形资产和其他长期资产所支付的现金",
                ],
            )
            receivable = pick(balance, company, period, ["应收账款"])
            inventory = pick(balance, company, period, ["存货"])
            payable = pick(balance, company, period, ["应付账款"])
            contract = pick(balance, company, period, ["合同负债"])
            prepaid = pick(balance, company, period, ["预付款项"])

            # 期初余额用于计算平均占用
            prior = f"{int(year) - 1}1231"
            receivable_prev = pick(balance, company, prior, ["应收账款"]) or receivable
            inventory_prev = pick(balance, company, prior, ["存货"]) or inventory
            payable_prev = pick(balance, company, prior, ["应付账款"]) or payable

            if not revenue or not cost:
                continue

            def days(avg: float | None, flow: float | None) -> float | None:
                if avg is None or not flow:
                    return None
                return avg / flow * 365

            ar_avg = (
                (receivable + receivable_prev) / 2
                if receivable is not None and receivable_prev is not None
                else None
            )
            inv_avg = (
                (inventory + inventory_prev) / 2
                if inventory is not None and inventory_prev is not None
                else None
            )
            ap_avg = (
                (payable + payable_prev) / 2
                if payable is not None and payable_prev is not None
                else None
            )

            dso = days(ar_avg, revenue)
            dio = days(inv_avg, cost)
            dpo = days(ap_avg, cost)
            ccc = (dso + dio - dpo) if None not in (dso, dio, dpo) else None

            rows.append(
                [
                    company,
                    year,
                    f"{revenue / 1e8:.2f}" if revenue else "",
                    f"{operating / 1e8:.2f}" if operating else "",
                    f"{capex / 1e8:.2f}" if capex else "",
                    f"{(operating - capex) / 1e8:.2f}" if operating and capex else "",
                    f"{operating / profit:.2f}" if operating and profit else "",
                    f"{dso:.1f}" if dso is not None else "",
                    f"{dio:.1f}" if dio is not None else "",
                    f"{dpo:.1f}" if dpo is not None else "",
                    f"{ccc:.1f}" if ccc is not None else "",
                    f"{(receivable / revenue * 365):.1f}" if receivable and revenue else "",
                    f"{(inventory / cost * 365):.1f}" if inventory and cost else "",
                    f"{(payable / cost * 365):.1f}" if payable and cost else "",
                    f"{(contract / revenue * 100):.1f}" if contract and revenue else "",
                    f"{(prepaid / cost * 100):.1f}" if prepaid and cost else "",
                ]
            )

    header = [
        "公司",
        "年度",
        "营业收入(亿)",
        "经营现金流(亿)",
        "资本开支(亿)",
        "自由现金流(亿)",
        "净现比",
        "应收周转天数(平均)",
        "存货周转天数(平均)",
        "应付周转天数(平均)",
        "现金转换周期(天)",
        "应收周转天数(期末)",
        "存货周转天数(期末)",
        "应付周转天数(期末)",
        "合同负债占收入%",
        "预付款占成本%",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)

    print(
        f"{'公司':<8}{'年':<6}{'净现比':>8}{'DSO':>8}{'DIO':>8}{'DPO':>8}{'CCC':>8}{'FCF(亿)':>10}"
    )
    print("-" * 66)
    for row in rows:
        print(
            f"{row[0]:<8}{row[1]:<6}{row[6]:>8}{row[7]:>8}{row[8]:>8}"
            f"{row[9]:>8}{row[10]:>8}{row[5]:>10}"
        )
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    print("口径：周转天数用期初期末平均值；DSO/DIO/DPO 分别除以收入/成本/成本")
    return 0


if __name__ == "__main__":
    sys.exit(main())
