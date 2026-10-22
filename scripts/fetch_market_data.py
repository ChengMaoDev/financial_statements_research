"""采集三家公司的股权结构、估值与市场数据。

补充财务数据之外的分析维度：
- 十大股东与十大流通股东（股权集中度、机构态度）
- 估值序列（PE/PB/PS 历史，判断当前估值位置）
- 日线行情（用于计算区间收益、波动率）

用法：
    uv run --with akshare python3 scripts/fetch_market_data.py --all
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "市场数据" / "结构化"

# 公司 → (纯代码, 带前缀, 名称)
COMPANIES = {
    "000333": ("sz000333", "美的集团"),
    "600690": ("sh600690", "海尔智家"),
    "000651": ("sz000651", "格力电器"),
}

# 报告期：近三年年报 + 最新中报
TOP_HOLDER_DATES = ["20231231", "20241231", "20251231", "20260630"]

VALUATION_INDICATORS = ["市盈率(TTM)", "市净率", "市销率"]


def clean(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    return "" if text.lower() in ("nan", "none", "nat") else text


def write_frame(path: Path, company: str, code: str, df, columns: list[str]) -> int:
    columns = [column for column in columns if column not in ("公司", "股票代码")]
    exists = path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a" if exists else "w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        if not exists:
            writer.writerow(["公司", "股票代码", *columns])
        for _, record in df.iterrows():
            writer.writerow([company, code] + [clean(record.get(c)) for c in columns])
    return len(df)


def fetch_holders(ak) -> None:
    """十大股东与十大流通股东。"""
    for label, fn in [
        ("十大股东", "stock_gdfx_top_10_em"),
        ("十大流通股东", "stock_gdfx_free_top_10_em"),
    ]:
        path = OUT / f"{label}.csv"
        path.unlink(missing_ok=True)
        total = 0
        func = getattr(ak, fn)
        for code, (prefixed, name) in COMPANIES.items():
            for date in TOP_HOLDER_DATES:
                try:
                    df = func(symbol=prefixed, date=date)
                except Exception as exc:
                    print(f"  {name} {date} 失败: {exc}", file=sys.stderr)
                    continue
                if df is None or df.empty:
                    continue
                df = df.copy()
                df["报告期"] = date
                columns = ["报告期"] + [c for c in df.columns if c != "报告期"]
                total += write_frame(path, name, code, df, columns)
        print(f"  {label}: {total} 行")


def fetch_valuation(ak) -> None:
    """估值序列，近五年。"""
    path = OUT / "估值序列.csv"
    path.unlink(missing_ok=True)
    total = 0
    for code, (_, name) in COMPANIES.items():
        for indicator in VALUATION_INDICATORS:
            try:
                df = ak.stock_zh_valuation_baidu(symbol=code, indicator=indicator, period="近五年")
            except Exception as exc:
                print(f"  {name} {indicator} 失败: {exc}", file=sys.stderr)
                continue
            if df is None or df.empty:
                continue
            df = df.copy()
            df["指标"] = indicator
            columns = ["指标", "date", "value"]
            total += write_frame(path, name, code, df, columns)
            print(f"  {name} {indicator}: {len(df)} 点")
    print(f"  估值序列合计 {total} 行")


def fetch_price(ak) -> None:
    """同时保存后复权与不复权行情，股息率只能使用不复权价格。"""
    for filename, adjustment in (("日线行情.csv", "hfq"), ("日线行情_不复权.csv", "")):
        path = OUT / filename
        path.unlink(missing_ok=True)
        total = 0
        for code, (_, name) in COMPANIES.items():
            try:
                df = ak.stock_zh_a_hist(
                    symbol=code,
                    period="daily",
                    start_date="20210101",
                    end_date=f"{datetime.now():%Y%m%d}",
                    adjust=adjustment,
                )
            except Exception as exc:
                raise RuntimeError(f"{name} {filename} 行情采集失败") from exc
            if df is None or df.empty:
                raise ValueError(f"{name} {filename} 返回空数据")
            columns = list(df.columns)
            if not adjustment:
                columns = ["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额"]
            total += write_frame(path, name, code, df, columns)
        print(f"  {filename}: {total} 行")


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
    print("股权结构...")
    fetch_holders(ak)
    print("\n估值序列...")
    fetch_valuation(ak)
    print("\n日线行情...")
    fetch_price(ak)
    return 0


if __name__ == "__main__":
    sys.exit(main())
