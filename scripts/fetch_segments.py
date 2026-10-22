"""采集三家公司的经营结构数据。

主营构成是判断商业模式的基础：分产品、分地区收入与毛利率，
直接反映三家公司的业务重心和盈利来源差异。

用法：
    uv run --with akshare python3 scripts/fetch_segments.py --all
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

from normalize_snapshots import usable_segment

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "财务数据" / "主营构成.csv"

# 东财接口需要带交易所前缀
COMPANIES = {
    "SZ000333": "美的集团",
    "SH600690": "海尔智家",
    "SZ000651": "格力电器",
}

COLUMNS = [
    "报告日期",
    "分类类型",
    "主营构成",
    "主营收入",
    "收入比例",
    "主营成本",
    "成本比例",
    "主营利润",
    "利润比例",
    "毛利率",
]


def clean(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    return "" if text.lower() in ("nan", "none") else text


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

    rows: list[list[str]] = []
    for symbol, name in COMPANIES.items():
        try:
            df = ak.stock_zygc_em(symbol=symbol)
        except Exception as exc:
            print(f"  {name} 失败: {exc}", file=sys.stderr)
            continue
        if df.empty:
            continue
        for _, record in df.iterrows():
            if not usable_segment(
                name, clean(record.get("报告日期")), clean(record.get("分类类型"))
            ):
                continue
            rows.append([name] + [clean(record.get(c)) for c in COLUMNS])
        periods = sorted({clean(v) for v in df["报告日期"]})
        print(f"  {name}: {len(df)} 条，报告期 {len(periods)} 个")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["公司", *COLUMNS])
        writer.writerows(rows)
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    print(f"采集时间 {datetime.now():%Y-%m-%d %H:%M:%S}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
