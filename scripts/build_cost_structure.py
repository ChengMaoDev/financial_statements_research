"""拆解成本结构与费用率。

回答「为什么毛利率接近但净利率差一倍」这类问题：
- 毛利率、期间费用率、净利率的完整漏斗
- 销售/管理/研发/财务费用率分项
- 其他收益、投资收益、减值损失对利润的贡献

用法：
    uv run python3 scripts/build_cost_structure.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIN = ROOT / "财务数据"
OUT = FIN / "成本结构与费用率.csv"

COMPANIES = ["美的集团", "海尔智家", "格力电器"]
YEARS = ["2023", "2024", "2025"]

# 展示名 → 利润表科目
ITEMS = {
    "营业收入": "营业收入",
    "营业成本": "营业成本",
    "营业税金及附加": "营业税金及附加",
    "销售费用": "销售费用",
    "管理费用": "管理费用",
    "研发费用": "研发费用",
    "财务费用": "财务费用",
    "其他收益": "其他收益",
    "投资收益": "投资收益",
    "公允价值变动收益": "公允价值变动收益",
    "资产减值损失": "资产减值损失",
    "信用减值损失": "信用减值损失",
    "资产处置收益": "资产处置收益",
    "营业利润": "营业利润",
    "利润总额": "利润总额",
    "净利润": "净利润",
    "归母净利润": "归属于母公司所有者的净利润",
    # 「营业总成本」含六个分项之外的科目（利息支出、手续费及佣金支出等），
    # 美的/格力有财务公司，这部分约占总成本 1%–2%。不单列的话，
    # 用六项费用率相加的漏斗会比「营业总成本」少算一截，无法闭合到营业利润。
    "其他营业成本项": "__other_cost__",
    # 「营业总收入 − 营业收入」= 利息收入 + 已赚保费 + 手续费收入。
    # 营业利润是按**营业总收入**算的，而本表分母用营业收入，
    # 所以必须把这部分单列成收益项，否则漏斗永远差这一块（格力 6.71 亿、美的 20.50 亿）。
    "利息等营业收入": "__other_revenue__",
}


def main() -> int:
    path = FIN / "利润表.csv"
    if not path.exists():
        print("缺少利润表", file=sys.stderr)
        return 1

    values: dict[tuple[str, str, str], float] = {}
    with path.open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            try:
                values[(row["公司"], row["报告期"], row["科目"])] = float(row["数值"])
            except (ValueError, KeyError):
                continue

    rows: list[list[str]] = []
    for company in COMPANIES:
        for year in YEARS:
            period = f"{year}1231"
            revenue = values.get((company, period, "营业收入"))
            if not revenue:
                continue
            record = [company, year, f"{revenue / 1e8:.2f}"]
            for label, subject in ITEMS.items():
                if label == "营业收入":
                    continue
                if subject == "__other_cost__":
                    # 营业总成本 − 六个已单列分项
                    total_cost = values.get((company, period, "营业总成本"))
                    listed = sum(
                        values.get((company, period, s), 0.0)
                        for s in (
                            "营业成本",
                            "营业税金及附加",
                            "销售费用",
                            "管理费用",
                            "研发费用",
                            "财务费用",
                        )
                    )
                    residual = (total_cost - listed) if total_cost is not None else None
                    record.append(f"{residual / revenue * 100:.2f}" if residual is not None else "")
                    continue
                if subject == "__other_revenue__":
                    # 营业总收入 − 营业收入
                    total_rev = values.get((company, period, "营业总收入"))
                    residual = (total_rev - revenue) if total_rev is not None else None
                    record.append(f"{residual / revenue * 100:.2f}" if residual is not None else "")
                    continue
                value = values.get((company, period, subject))
                # 费用与成本用正数展示（利润表里资产减值损失为负）
                if value is None:
                    record.append("")
                    continue
                if label in ("资产减值损失", "信用减值损失"):
                    # 统一约定：正数=损失（费用），负数=收益（转回）。
                    # 信用减值可能为净转回（格力 2025 为 +5.12 亿收益），
                    # 用 abs() 会把它当成损失，漏斗少算两倍。
                    # 利润表里减值损失本身是负数，取反后即「损失=正」。
                    record.append(f"{-value / revenue * 100:.4f}")
                elif label == "资产处置收益":
                    # 这是收益项（利润表正数=收益），漏斗里直接加，
                    # 所以按本金符号存，不能取反。
                    record.append(f"{value / revenue * 100:.4f}")
                elif label in ("营业利润", "利润总额", "净利润", "归母净利润"):
                    record.append(f"{value / 1e8:.2f}")
                else:
                    record.append(f"{value / revenue * 100:.2f}")
            rows.append(record)

    header = ["公司", "年度", "营业收入(亿)"] + [
        f"{label}(%)"
        if label not in ("营业利润", "利润总额", "净利润", "归母净利润")
        else f"{label}(亿)"
        for label in ITEMS
        if label != "营业收入"
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)

    # 控制台：费用率漏斗
    index = {name: header.index(name) for name in header}
    print(
        f"{'公司':<8}{'年':<6}{'毛利率':>8}{'销售':>7}{'管理':>7}"
        f"{'研发':>7}{'财务':>7}{'净利率':>8}"
    )
    print("-" * 58)
    # 漏斗闭合校验：收入×(1−各成本率之和) 必须等于营业利润
    closed = 0
    broken: list[tuple[str, str, float]] = []
    for row in rows:
        gross = 100 - float(row[index["营业成本(%)"]])
        net = float(row[index["归母净利润(亿)"]]) / float(row[2]) * 100
        print(
            f"{row[0]:<8}{row[1]:<6}{gross:>8.2f}{row[index['销售费用(%)']]:>7}"
            f"{row[index['管理费用(%)']]:>7}{row[index['研发费用(%)']]:>7}"
            f"{row[index['财务费用(%)']]:>7}{net:>8.2f}"
        )
        revenue = float(row[2])
        funnel = revenue * (
            1
            - float(row[index["营业成本(%)"]]) / 100
            - float(row[index["营业税金及附加(%)"]]) / 100
            - float(row[index["销售费用(%)"]]) / 100
            - float(row[index["管理费用(%)"]]) / 100
            - float(row[index["研发费用(%)"]]) / 100
            - float(row[index["财务费用(%)"]]) / 100
            - float(row[index["其他营业成本项(%)"]]) / 100
            + float(row[index["利息等营业收入(%)"]]) / 100
            + float(row[index["其他收益(%)"]]) / 100
            + float(row[index["投资收益(%)"]]) / 100
            + float(row[index["公允价值变动收益(%)"]]) / 100
            - float(row[index["资产减值损失(%)"]]) / 100
            - float(row[index["信用减值损失(%)"]]) / 100
            + float(row[index["资产处置收益(%)"]]) / 100
        )
        stated = float(row[index["营业利润(亿)"]])
        # 容差按收入规模取 0.05%：各费用率保留 2 位小数，
        # 1700 亿收入下每项舍入误差可达 ±0.0085 亿，十几项累积约 ±0.1 亿；
        # 1000 亿以上规模用绝对值 1.0 亿做上限，避免把舍入误差报成口径错误。
        tolerance = max(0.05, abs(revenue) * 0.0005)
        if abs(funnel - stated) > tolerance:
            broken.append((row[0], row[1], funnel - stated))
        else:
            closed += 1
    print(f"\n漏斗闭合：{closed}/{len(rows)} 期与营业利润一致（容差 = max(0.05, 收入×0.05%)）")
    for company, year, gap in broken:
        print(f"  ⚠ {company} {year} 漏斗 − 营业利润 = {gap:+.2f} 亿")
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    print("口径：费用率为占营业收入比；净利率为归母净利润/营业收入")
    print(
        "注意：2023/2024 年营业成本为最新重述口径，与当年年报原披露值不同（见数据源分级.md 第 20 条）"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
