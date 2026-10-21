"""采集家电核心原材料期货价格与汇率。

家电成本结构中原材料占 80% 以上，其中铜、铝、钢材、塑料是最主要的四项。
本脚本采集上期所/大商所主力连续合约日线，用于：
- 计算原材料价格同比变化，解释毛利率波动
- 建立「铜价 → 空调成本 → 毛利率」的传导分析

合约代码（新浪主力连续）：
- CU0 沪铜、AL0 沪铝、ZN0 沪锌（压缩机、电机、换热器）
- RB0 螺纹钢、I0 铁矿石（钣金、结构件）
- L0 塑料LLDPE、V0 PVC（外壳、管路）
- USDCNY 人民币汇率

用法：
    uv run --with akshare python3 scripts/fetch_commodity.py --all
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "市场数据" / "结构化" / "原材料价格.csv"
FX_OUT = ROOT / "市场数据" / "结构化" / "汇率.csv"

# 合约代码 → (名称, 单位, 用途)
COMMODITIES = {
    "CU0": ("沪铜", "元/吨", "换热器、电机绕组、电线"),
    "AL0": ("沪铝", "元/吨", "换热器翅片、外壳"),
    "ZN0": ("沪锌", "元/吨", "镀锌板、防腐"),
    "RB0": ("螺纹钢", "元/吨", "钣金结构件（钢材代理指标）"),
    # 热卷比螺纹钢更接近家电钣金的真实采购品：家电外壳/压缩机壳体用冷轧板，
    # 冷轧由热卷轧制而来，两者价差相对稳定。螺纹钢是建筑用钢，与家电需求
    # 关联度弱于热卷。冷轧板本身无期货合约，热卷是最接近的可交易代理。
    "HC0": ("热卷", "元/吨", "冷轧板上游，家电钣金更优代理"),
    "I0": ("铁矿石", "元/吨", "钢材上游"),
    "L0": ("塑料LLDPE", "元/吨", "外壳、包装"),
    "V0": ("PVC", "元/吨", "管路、外壳"),
}


def clean(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    return "" if text.lower() in ("nan", "none", "nat") else text


def fetch_commodities(ak) -> None:
    rows: list[list[str]] = []
    for code, (name, unit, usage) in COMMODITIES.items():
        try:
            df = ak.futures_main_sina(symbol=code, start_date="20210101", end_date="20261231")
        except Exception as exc:
            print(f"  {name}({code}) 失败: {exc}", file=sys.stderr)
            continue
        if df is None or df.empty:
            print(f"  {name}({code}) 无数据", file=sys.stderr)
            continue
        for _, record in df.iterrows():
            rows.append(
                [
                    name,
                    code,
                    unit,
                    usage,
                    clean(record.get("日期", "")),
                    clean(record.get("开盘价", "")),
                    clean(record.get("最高价", "")),
                    clean(record.get("最低价", "")),
                    clean(record.get("收盘价", "")),
                    clean(record.get("成交量", "")),
                    clean(record.get("持仓量", "")),
                ]
            )
        print(f"  {name}({code}): {len(df)} 个交易日")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            [
                "品种",
                "合约代码",
                "单位",
                "主要用途",
                "日期",
                "开盘",
                "最高",
                "最低",
                "收盘",
                "成交量",
                "持仓量",
            ]
        )
        writer.writerows(rows)
    print(f"  写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")


def fetch_fx(ak) -> None:
    """人民币汇率（中国银行牌价）。"""
    try:
        df = ak.currency_boc_sina(symbol="美元", start_date="20210101", end_date="20261231")
    except Exception as exc:
        print(f"  汇率失败: {exc}", file=sys.stderr)
        return
    if df is None or df.empty:
        return
    # akshare 返回的 df 第一列本身就叫「日期」，不能再手工加一个，
    # 否则表头 7 列、数据 6 列，整表错位（曾实际发生）。
    columns = [str(c) for c in df.columns]
    if "日期" not in columns:
        columns = ["日期", *columns]
        df = df.copy()
        df.insert(0, "日期", df.index)
    with FX_OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(columns)
        for _, record in df.iterrows():
            writer.writerow([clean(record.get(c)) for c in columns])
    print(f"  汇率: {len(df)} 行，列 {columns}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all", action="store_true", default=True, help="默认执行全部；保留该开关用于兼容旧命令"
    )
    args = parser.parse_args()
    if not args.all:  # 默认 True；仅显式 --no-all 时才打印帮助
        parser.print_help()
        return 1

    try:
        import akshare as ak
    except ImportError:
        print("需要 akshare", file=sys.stderr)
        return 1

    print(f"采集时间 {datetime.now():%Y-%m-%d %H:%M:%S}\n")
    print("原材料期货...")
    fetch_commodities(ak)
    print("\n汇率...")
    fetch_fx(ak)
    return 0


if __name__ == "__main__":
    sys.exit(main())
