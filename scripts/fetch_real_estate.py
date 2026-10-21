"""采集房地产行业月度数据，用于分析地产周期向白电需求的传导。

## 为什么需要这份数据

家电需求的一条主要传导链是「新房开工 → 竣工交付 → 精装配套/首次安装」。
房地产数据本身不直接进财务报表，但它是解释以下指标变化的外部变量：

- 工程渠道应收（地产商欠款）
- 合同负债（预收装修订单）
- 渠道库存与存货周转
- 促销费用率（需求不足时靠补贴冲量）

## 采集范围与限制

**能拿到**：国房景气指数（`macro_china_real_estate`），1998-01 起月度，
100 为景气线。

**拿不到**（已逐一验证）：

| 指标 | 尝试的路径 | 结果 |
|---|---|---|
| 房屋新开工面积 | 国家统计局 `data.stats.gov.cn/easyquery.htm` | 403（IP 被 ACL 拦截） |
| 房屋竣工面积 | 同上 | 403 |
| 商品房销售面积/额 | 同上 | 403 |
| 70 城房价指数 | `macro_china_new_house_price` | **只有北京、上海两城**，非全国 |
| 房地产开发投资 | akshare 无对应接口 | 不存在 |

因此本表只有国房景气指数一个指标。**不要把它当作新开工/竣工面积的替代**——
它是综合景气度，不是实物量。

用法：
    uv run python3 scripts/fetch_real_estate.py
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "市场数据" / "结构化" / "房地产景气指数.csv"


def clean(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    return "" if text.lower() in ("nan", "none", "nat") else text


def fetch(ak) -> int:
    """国房景气指数：一个综合指标，月度，全国口径。"""
    try:
        df = ak.macro_china_real_estate()
    except Exception as exc:
        print(f"  国房景气指数采集失败: {exc}", file=sys.stderr)
        return 0

    if df is None or df.empty:
        print("  国房景气指数返回空", file=sys.stderr)
        return 0

    stamp = f"{datetime.now():%Y-%m-%d %H:%M:%S}"
    rows: list[list[str]] = []
    for _, record in df.iterrows():
        date = clean(record.get("日期"))
        if not date:
            continue
        rows.append(
            [
                "行业",
                date[:7],
                "国房景气指数",
                clean(record.get("最新值")),
                "指数",
                "100 为景气线，高于为景气、低于为景气度不足",
                "国家统计局",
                "actual",
                stamp,
            ]
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            [
                "品类",
                "月份",
                "指标",
                "数值",
                "单位",
                "口径说明",
                "数据来源",
                "数据性质",
                "采集时间",
            ]
        )
        writer.writerows(rows)

    print(f"  写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    if rows:
        print(f"    范围 {rows[0][1]} → {rows[-1][1]}")
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all",
        action="store_true",
        default=True,
        help="采集全部（当前只有国房景气指数一个指标）",
    )
    parser.parse_args()

    try:
        import akshare as ak
    except ImportError:
        print("需要 akshare：先 uv sync", file=sys.stderr)
        return 1

    print(f"采集时间 {datetime.now():%Y-%m-%d %H:%M:%S}\n")
    print("房地产行业数据...")
    count = fetch(ak)
    if count == 0:
        return 1

    print("\n注意：新房开工/竣工/销售面积无法获取（国家统计局接口返回 403），")
    print("本表只有国房景气指数一个综合指标，不是实物量替代。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
