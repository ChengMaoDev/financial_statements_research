"""从 akshare 采集三家公司的 A 股财务与市场数据。

akshare 的数据来自东方财富、同花顺等公开接口，为**人民币原值**，
与年报 PDF 可逐位交叉校验。相比港股口径（按汇率换算成 HKD），
A 股口径才是分析的正确基准。

重要口径说明：
- `营业总收入` 含其他业务收入，**不等于**年报的 `营业收入`。
  格力 2025 年：营业总收入 1711.18 亿，年报营业收入 1704.47 亿，差 6.7 亿。
  做同比和占比分析时必须统一口径，不可混用。
- `毛利率` 等比率指标由 akshare 按营业总收入计算，与年报口径可能微差。

用法：
    uv run --with akshare python3 scripts/fetch_akshare.py --all
    uv run --with akshare python3 scripts/fetch_akshare.py --check
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from datetime import datetime
from pathlib import Path

from normalize_snapshots import usable_report

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "财务数据"

COMPANIES = {
    "000333": "美的集团",
    "600690": "海尔智家",
    "000651": "格力电器",
}

# 主要会计数据：年报口径可比的核心指标
KEY_INDICATORS = [
    "营业总收入",
    "营业成本",
    "归母净利润",
    "扣非净利润",
    "净利润",
    "经营现金流量净额",
    "股东权益合计(净资产)",
    "总资产",
    "毛利率",
    "销售净利率",
    "净资产收益率(ROE)",
    "资产负债率",
    "基本每股收益",
    "每股净资产",
    "商誉",
]


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def fetch_abstract(ak) -> list[list[str]]:
    """主要财务指标，长表格式：公司 / 指标 / 报告期 / 数值。"""
    rows: list[list[str]] = []
    for code, name in COMPANIES.items():
        df = ak.stock_financial_abstract(symbol=code)
        available = [i for i in KEY_INDICATORS if i in df["指标"].values]
        missing = [i for i in KEY_INDICATORS if i not in df["指标"].values]
        if missing:
            print(f"  {name} 缺失指标: {missing}", file=sys.stderr)
        for indicator in available:
            series = df[df["指标"] == indicator].iloc[0]
            for column, value in series.items():
                if column in ("选项", "指标") or value is None:
                    continue
                if not usable_report(name, str(column)):
                    continue
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    continue
                if math.isnan(number):
                    continue
                rows.append([name, code, indicator, column, f"{number:.2f}"])
        print(f"  {name}: {len(available)} 项指标")
    return rows


def fetch_quarterly(ak) -> list[list[str]]:
    """分季度数据。年报不直接给 Q4，用全年减前三季推算时需注明。"""
    rows: list[list[str]] = []
    for code, name in COMPANIES.items():
        try:
            df = ak.stock_financial_abstract(symbol=code)
        except Exception as exc:
            print(f"  {name} 季度数据失败: {exc}", file=sys.stderr)
            continue
        series = df[df["指标"] == "营业总收入"]
        if series.empty:
            continue
        record = series.iloc[0]
        for column, value in record.items():
            if column in ("选项", "指标"):
                continue
            if not usable_report(name, str(column)):
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if math.isnan(number):
                continue
            rows.append([name, code, column, f"{number:.2f}"])
    return rows


def fetch_valuation(ak) -> list[list[str]]:
    """估值指标：市值、PE、PB。用于横向比较。"""
    rows: list[list[str]] = []
    for code, name in COMPANIES.items():
        try:
            df = ak.stock_individual_info_em(symbol=code)
            info = dict(zip(df["item"], df["value"], strict=False))
            rows.append(
                [
                    name,
                    code,
                    str(info.get("总市值", "")),
                    str(info.get("流通市值", "")),
                    str(info.get("行业", "")),
                    str(info.get("上市时间", "")),
                    str(info.get("总股本", "")),
                ]
            )
            print(f"  {name}: 市值 {info.get('总市值')}")
        except Exception as exc:
            print(f"  {name} 估值失败: {exc}", file=sys.stderr)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="采集全部")
    parser.add_argument("--check", action="store_true", help="只校验不写文件")
    args = parser.parse_args()

    if not (args.all or args.check):
        parser.print_help()
        return 1

    try:
        import akshare as ak
    except ImportError:
        print("需要 akshare：uv run --with akshare python3 ...", file=sys.stderr)
        return 1

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("采集主要财务指标...")
    abstract = fetch_abstract(ak)
    print(f"  合计 {len(abstract)} 行")

    print("采集估值信息...")
    valuation = fetch_valuation(ak)

    if args.check:
        print(f"\n校验完成：{len(abstract)} 行财务指标，{len(valuation)} 行估值")
        return 0

    write_csv(
        OUT / "主要财务指标.csv",
        ["公司", "股票代码", "指标", "报告期", "数值", "采集时间"],
        [[*row, stamp] for row in abstract],
    )
    print(f"写入 {OUT / '主要财务指标.csv'}")

    write_csv(
        OUT / "公司概况.csv",
        ["公司", "股票代码", "总市值", "流通市值", "行业", "上市时间", "总股本"],
        valuation,
    )
    print(f"写入 {OUT / '公司概况.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
