"""采集三家公司的扩展财务与治理数据。

在 `fetch_akshare.py`（主要财务指标）之外，补齐分析所需的其余维度：
- 三张报表全量（资产负债表 / 利润表 / 现金流量表）
- 分红送配历史
- 股东户数变化
- 财务分析指标（杜邦分解等）

数据均为人民币原值，来自东方财富/新浪/巨潮，可与年报 PDF 交叉校验。

用法：
    uv run --with akshare python3 scripts/fetch_akshare_extended.py --all
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "财务数据"

# akshare 用 sh/sz 前缀
COMPANIES = {
    "000333": ("美的集团", "sz000333"),
    "600690": ("海尔智家", "sh600690"),
    "000651": ("格力电器", "sz000651"),
}

STATEMENTS = {
    "资产负债表": "资产负债表.csv",
    "利润表": "利润表.csv",
    "现金流量表": "现金流量表.csv",
}


def write_rows(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  写入 {path.relative_to(ROOT)}: {len(rows)} 行")


def clean(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    return "" if text.lower() in ("nan", "none", "nat") else text


def fetch_statements(ak) -> None:
    """三张报表：保留全部报告期，长表格式便于跨公司对比。"""
    for statement, filename in STATEMENTS.items():
        rows: list[list[str]] = []
        for code, (name, sina_code) in COMPANIES.items():
            try:
                df = ak.stock_financial_report_sina(stock=sina_code, symbol=statement)
            except Exception as exc:
                print(f"  {name} {statement} 失败: {exc}", file=sys.stderr)
                continue
            if "报告日" not in df.columns:
                print(f"  {name} {statement} 缺报告日列", file=sys.stderr)
                continue
            for _, record in df.iterrows():
                period = clean(record["报告日"])
                for field, value in record.items():
                    if field == "报告日":
                        continue
                    text = clean(value)
                    if not text:
                        continue
                    rows.append([name, code, period, field, text])
            print(f"  {name} {statement}: {len(df)} 期")
        write_rows(
            OUT / filename,
            ["公司", "股票代码", "报告期", "科目", "数值"],
            rows,
        )


def write_frame(path: Path, company: str, code: str, df, columns: list[str]) -> int:
    """按真实列名写出 DataFrame。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a" if exists else "w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        if not exists:
            writer.writerow(["公司", "股票代码", *columns])
        for _, record in df.iterrows():
            writer.writerow([company, code] + [clean(record.get(c)) for c in columns])
    return len(df)


def fetch_dividend(ak) -> None:
    """分红送配历史。"""
    path = OUT / "分红送配.csv"
    path.unlink(missing_ok=True)
    total = 0
    for code, (name, _) in COMPANIES.items():
        try:
            df = ak.stock_dividend_cninfo(symbol=code)
        except Exception as exc:
            print(f"  {name} 分红失败: {exc}", file=sys.stderr)
            continue
        if df.empty:
            continue
        count = write_frame(path, name, code, df, list(df.columns))
        print(f"  {name} 分红: {count} 条")
        total += count
    print(f"  写入 {path.relative_to(ROOT)}: {total} 行")


def fetch_holders(ak) -> None:
    """股东户数变化，反映筹码集中度。"""
    path = OUT / "股东户数.csv"
    path.unlink(missing_ok=True)
    total = 0
    for code, (name, _) in COMPANIES.items():
        try:
            df = ak.stock_zh_a_gdhs_detail_em(symbol=code)
        except Exception as exc:
            print(f"  {name} 股东户数失败: {exc}", file=sys.stderr)
            continue
        if df.empty:
            continue
        # 去掉重复的代码/名称列（已在前面写了）
        columns = [c for c in df.columns if c not in ("代码", "名称")]
        count = write_frame(path, name, code, df, columns)
        print(f"  {name} 股东户数: {count} 条")
        total += count
    print(f"  写入 {path.relative_to(ROOT)}: {total} 行")


def fetch_indicators(ak) -> None:
    """财务分析指标（杜邦分解、周转率等）。"""
    path = OUT / "财务分析指标.csv"
    path.unlink(missing_ok=True)
    total = 0
    for code, (name, _) in COMPANIES.items():
        try:
            # 研究期是 2017—2025，起点必须对齐；原先设 2020 会缺 2017—2019
            # 的杜邦分解与周转率（akshare 实测可回溯到 2017-03-31）。
            df = ak.stock_financial_analysis_indicator(symbol=code, start_year="2017")
        except Exception as exc:
            print(f"  {name} 分析指标失败: {exc}", file=sys.stderr)
            continue
        if df.empty:
            continue
        # 新浪源的「销售毛利率」近年在部分报告期停填（29/114 有值），
        # 但「主营业务成本率」100% 有值，毛利率 ≡ 100 − 成本率，可无损回填。
        if "销售毛利率(%)" in df.columns and "主营业务成本率(%)" in df.columns:

            def fill(row):
                gross = clean(row.get("销售毛利率(%)"))
                cost = clean(row.get("主营业务成本率(%)"))
                if gross or not cost:
                    return gross
                try:
                    return f"{100 - float(cost):.3f}"
                except (TypeError, ValueError):
                    return ""

            df = df.copy()
            df["销售毛利率(%)"] = df.apply(fill, axis=1)
        count = write_frame(path, name, code, df, list(df.columns))
        print(f"  {name} 分析指标: {count} 期")
        total += count
    print(f"  写入 {path.relative_to(ROOT)}: {total} 行")


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
    print("三张报表...")
    fetch_statements(ak)
    print("\n分红送配...")
    fetch_dividend(ak)
    print("\n股东户数...")
    fetch_holders(ak)
    print("\n财务分析指标...")
    fetch_indicators(ak)
    return 0


if __name__ == "__main__":
    sys.exit(main())
