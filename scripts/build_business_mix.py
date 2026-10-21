"""按统一口径重构「家电主业收入占比」，观察三家的多元化进程。

为什么必须重建：
三家的分产品披露口径在过去 9 年里都改过，直接拿「空调」「消费电器」「智能家居」
做时间序列会出现断层：

- 美的：2017—2023 用「暖通空调 + 消费电器」，2024 起改成
  「智能家居业务 + 商业及工业解决方案」。**2024 年不是业务变了，是标签变了。**
- 格力：2021 年拆出「工业制品」「绿色能源」，2024 年又合并成
  「工业制品及绿色能源」并改名「消费电器」统称空调+生活电器。
- 海尔：口径最稳定，2019 起一直是六大品类 + 装备部品及渠道综合服务。

本表的处理：
1. 把每家的分项映射到「家电主业」与「非家电」两桶，映射规则写在 SEGMENT_MAP。
2. 排除「其他(补充)」——它是主营收入与营业收入的差额，不是业务分部。
3. 排除「其中:」子项——它们是上层科目的拆分，直接求和会虚增。
4. 分母用「营业收入」而非「主营收入合计」，保证与利润表一致。

用法：
    uv run python3 scripts/build_business_mix.py
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "财务数据"
OUT = DATA / "家电主业占比.csv"

COMPANIES = ["美的集团", "海尔智家", "格力电器"]

# 公司 → {分项名称: 归属}，归属取 "家电" / "非家电"
SEGMENT_MAP: dict[str, dict[str, str]] = {
    "美的集团": {
        "暖通空调": "家电",
        "消费电器": "家电",
        "智能家居业务": "家电",
        "机器人及自动化系统": "非家电",
        "商业及工业解决方案": "非家电",
        "其他": "非家电",
    },
    "海尔智家": {
        "电冰箱": "家电",
        "洗衣机": "家电",
        "空调": "家电",
        "厨电": "家电",
        "水家电": "家电",
        "装备部品及渠道综合服务": "非家电",
        "渠道综合服务业务及其他": "非家电",
    },
    "格力电器": {
        "空调": "家电",
        "生活电器": "家电",
        "消费电器": "家电",
        "智能装备": "非家电",
        "工业制品": "非家电",
        "绿色能源": "非家电",
        "工业制品及绿色能源": "非家电",
        "其他": "非家电",
        "其他主营": "非家电",
    },
}

# 口径断点：跨这些年份的占比变化不能解释为业务变化。
# 依据是各家年报自身对上年可比数的重述（见数据源分级.md 第 33 条）。
BREAKS = {
    "美的集团": {
        2024: "分产品口径从「暖通空调/消费电器/机器人」改为「智能家居/商业及工业解决方案」，上年可比数已重述为 66.22%"
    },
    "海尔智家": {
        2021: "2021 年因同一控制下合并物流业务，上年可比数重述；「装备部品及渠道综合服务」由 273.9 亿降至 150.0 亿",
        2024: "「装备部品及渠道综合服务」并入更多物流业务，非家电占比由 5.51% 升至 11.33%",
    },
}


def main() -> int:
    revenue: dict[tuple[str, str], float] = {}
    with (DATA / "利润表.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if not row["报告期"].endswith("1231"):
                continue
            if row["科目"] != "营业收入":
                continue
            try:
                revenue[(row["公司"], row["报告期"][:4])] = float(row["数值"]) / 1e8
            except ValueError:
                continue

    buckets: dict[tuple[str, str, str], float] = defaultdict(float)
    unmapped: dict[str, set[str]] = defaultdict(set)
    with (DATA / "主营构成.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["分类类型"] != "按产品分类" or not row["报告日期"].endswith("12-31"):
                continue
            company = row["公司"]
            year = row["报告日期"][:4]
            name = row["主营构成"]
            if name.startswith("其中"):
                continue
            # 「其他(补充)」= 主营收入与营业收入的差额（材料销售等），
            # 单列为第三类，不并进家电或非家电，否则表内合计不到 100%。
            if name == "其他(补充)":
                try:
                    buckets[(company, year, "其他业务")] += float(row["主营收入"]) / 1e8
                except ValueError:
                    continue
                continue
            mapping = SEGMENT_MAP.get(company, {})
            if name not in mapping:
                unmapped[company].add(name)
                continue
            try:
                value = float(row["主营收入"]) / 1e8
            except ValueError:
                continue
            buckets[(company, year, mapping[name])] += value

    rows: list[list[str]] = []
    for company in COMPANIES:
        years = sorted({y for (c, y, _) in buckets if c == company})
        for year in years:
            home = buckets.get((company, year, "家电"), 0.0)
            other = buckets.get((company, year, "非家电"), 0.0)
            extra = buckets.get((company, year, "其他业务"), 0.0)
            total = revenue.get((company, year))
            if not total:
                continue
            rows.append(
                [
                    company,
                    year,
                    f"{home:.2f}",
                    f"{other:.2f}",
                    f"{extra:.2f}",
                    f"{total:.2f}",
                    f"{home / total * 100:.2f}",
                    f"{other / total * 100:.2f}",
                    f"{extra / total * 100:.2f}",
                    f"{1 - (home + other + extra) / total:.4f}",
                    BREAKS.get(company, {}).get(int(year), ""),
                    "计算值",
                ]
            )

    fields = [
        "公司",
        "年度",
        "家电主业收入(亿元)",
        "非家电收入(亿元)",
        "其他业务收入(亿元)",
        "营业收入(亿元)",
        "家电主业占比%",
        "非家电占比%",
        "其他业务占比%",
        "未分类差额占比",
        "口径断点说明",
        "数据性质",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    print(
        f"{'公司':<8}{'年度':<6}{'家电主业(亿)':>13}{'占比%':>9}"
        f"{'非家电(亿)':>12}{'占比%':>9}{'其他(亿)':>10}{'占比%':>8}"
    )
    print("-" * 76)
    for row in rows:
        print(
            f"{row[0]:<8}{row[1]:<6}{float(row[2]):>13,.1f}{float(row[6]):>9.2f}"
            f"{float(row[3]):>12,.1f}{float(row[7]):>9.2f}"
            f"{float(row[4]):>10,.1f}{float(row[8]):>8.2f}"
        )

    residuals = [abs(float(r[9])) for r in rows]
    print(f"\n未分类差额占比最大 {max(residuals) * 100:.2f}%（越小说明分部覆盖越完整）")
    for company, names in unmapped.items():
        if names:
            print(f"  {company} 未映射分项：{sorted(names)}")
    print(f"写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
