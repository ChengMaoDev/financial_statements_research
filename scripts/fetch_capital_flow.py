"""采集市场交易层面的数据：融资融券、北向资金、股权质押、大宗交易。

这些数据反映资金态度与股权结构风险，与财报互补。

用法：
    uv run --with akshare python3 scripts/fetch_capital_flow.py --all
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "市场数据" / "结构化"

COMPANIES = {
    "000333": ("美的集团", "深"),
    "600690": ("海尔智家", "沪"),
    "000651": ("格力电器", "深"),
}


def clean(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    return "" if text.lower() in ("nan", "none", "nat") else text


def write_rows(path: Path, header: list[str], rows: list[list[str]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    return len(rows)


def fetch_margin(ak) -> None:
    """融资融券明细，近 60 个交易日。"""
    rows: list[list[str]] = []
    end = datetime.now()
    for offset in range(90):
        day = end - timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        date = day.strftime("%Y%m%d")
        for code, (name, market) in COMPANIES.items():
            try:
                if market == "沪":
                    df = ak.stock_margin_detail_sse(date=date)
                else:
                    df = ak.stock_margin_detail_szse(date=date)
            except Exception as exc:
                print(f"  {name} {date} 融资融券失败: {exc}", file=sys.stderr)
                continue
            if df is None or df.empty:
                continue
            column = "标的证券代码" if "标的证券代码" in df.columns else "证券代码"
            hit = df[df[column].astype(str).str.zfill(6) == code]
            if hit.empty:
                continue
            record = hit.iloc[0]
            rows.append(
                [
                    name,
                    code,
                    date,
                    clean(record.get("融资买入额", "")),
                    clean(record.get("融资余额", "")),
                    clean(record.get("融券余量", "")),
                    clean(record.get("融资融券余额", "")),
                ]
            )
    write_rows(
        OUT / "融资融券.csv",
        ["公司", "股票代码", "日期", "融资买入额", "融资余额", "融券余量", "融资融券余额"],
        rows,
    )
    print(f"  融资融券: {len(rows)} 行")


def fetch_northbound(ak) -> None:
    """北向资金个股持股。"""
    rows: list[list[str]] = []
    for code, (name, _) in COMPANIES.items():
        try:
            df = ak.stock_hsgt_individual_em(symbol=code)
        except Exception as exc:
            print(f"  {name} 北向失败: {exc}", file=sys.stderr)
            continue
        if df is None or df.empty:
            continue
        for _, record in df.iterrows():
            rows.append(
                [
                    name,
                    code,
                    clean(record.get("持股日期", "")),
                    clean(record.get("持股数量", "")),
                    clean(record.get("持股市值", "")),
                    clean(record.get("持股数量占发行股百分比", "")),
                ]
            )
    write_rows(
        OUT / "北向资金持股.csv",
        ["公司", "股票代码", "持股日期", "持股数量", "持股市值", "持股占比"],
        rows,
    )
    print(f"  北向资金: {len(rows)} 行")


def fetch_pledge(ak) -> None:
    """股权质押比例。"""
    rows: list[list[str]] = []
    for code, (name, _) in COMPANIES.items():
        try:
            df = ak.stock_gpzy_pledge_ratio_em(date="20260630")
        except Exception as exc:
            print(f"  {name} 质押数据失败: {exc}", file=sys.stderr)
            continue
        if df is None or df.empty:
            continue
        column = "股票代码" if "股票代码" in df.columns else "证券代码"
        hit = df[df[column].astype(str).str.zfill(6) == code]
        for _, record in hit.iterrows():
            rows.append([name, code] + [clean(record.get(c)) for c in df.columns])
        break
    if rows:
        header = ["公司", "股票代码"] + [c for c in (df.columns if rows else [])]
        write_rows(OUT / "股权质押.csv", header, rows)
        print(f"  股权质押: {len(rows)} 行")
    else:
        print("  股权质押: 无数据")


def fetch_holders_detail(ak) -> None:
    """股东户数只保存在财务数据目录，复用同一采集入口。"""
    from fetch_akshare_extended import fetch_holders

    fetch_holders(ak)


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
    print("资金与股权...")
    fetch_margin(ak)
    fetch_northbound(ak)
    fetch_pledge(ak)
    fetch_holders_detail(ak)
    return 0


if __name__ == "__main__":
    sys.exit(main())
