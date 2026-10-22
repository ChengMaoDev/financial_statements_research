"""从巨潮资讯网抓取三家公司的定期报告清单。

巨潮资讯网（cninfo.com.cn）是深交所指定信息披露平台，A 股公司公告的
法定发布渠道，因此这里取到的公告元数据是一手来源。

本脚本只抓**元数据清单**（标题、日期、PDF 链接），不下载正文：
正文 PDF 体积大，按需再下，避免仓库膨胀。

用法：
    uv run python3 scripts/fetch_cninfo_index.py            # 抓清单并写 CSV
    uv run python3 scripts/fetch_cninfo_index.py --check    # 只统计，不写文件
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from research_scope import in_scope

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "定期报告"
OUT_CSV = OUT_DIR / "定期报告清单.csv"

QUERY_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
BASE_PDF = "http://static.cninfo.com.cn/"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# 公司 → (股票代码, 巨潮 orgId, 交易所 column)
COMPANIES = {
    "美的集团": ("000333", "9900005965", "szse"),
    "海尔智家": ("600690", "gssh0600690", "sse"),
    "格力电器": ("000651", "gssz0000651", "szse"),
}

# 巨潮的公告分类。用分类查询比标题过滤可靠：
# 标题过滤依赖分页扫全量（美的 700 条、海尔 458 条），容易漏。
CATEGORIES = {
    "category_ndbg_szsh": "年度报告",
    "category_bndbg_szsh": "半年度报告",
    "category_yjdbg_szsh": "一季度报告",
    "category_sjdbg_szsh": "三季度报告",
}

# 排除非正文：摘要、英文版、已取消、更正稿。保留正文中文版。
EXCLUDE = re.compile(
    r"摘要|英文|English|已取消|取消|更正|"
    r"（\s*[Ee]nglish\s*）|\(\s*[Ee]nglish\s*\)"
)


def post_form(url: str, payload: dict[str, str], timeout: int = 30) -> str:
    data = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": UA,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Referer": "http://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def period_of(title: str, kind: str) -> str:
    """从标题提取报告期标签，如「2025年年度报告」→ 2025 年度。"""
    year = re.search(r"(20\d{2})\s*年", title)
    if not year:
        return ""
    suffix = {
        "年度报告": "年度",
        "半年度报告": "H1",
        "一季度报告": "Q1",
        "三季度报告": "Q3",
    }[kind]
    return f"{year.group(1)} {suffix}"


def fetch_category(
    name: str, code: str, org: str, column: str, category: str, kind: str
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    page = 1
    while page <= 10:
        payload = {
            "pageNum": str(page),
            "pageSize": "30",
            "column": column,
            "tabName": "fulltext",
            "stock": f"{code},{org}",
            "seDate": "2023-01-01~2026-12-31",
            "category": category,
            "searchkey": "",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }
        raw = post_form(QUERY_URL, payload)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            print(f"  {name}/{kind} 第 {page} 页非 JSON，停止", file=sys.stderr)
            break
        items = data.get("announcements") or []
        if not items:
            break
        for item in items:
            title = (item.get("announcementTitle") or "").strip()
            if EXCLUDE.search(title):
                continue
            if not in_scope(period_of(title, kind)):
                continue
            stamp = item.get("announcementTime")
            date = datetime.fromtimestamp(stamp / 1000).strftime("%Y-%m-%d") if stamp else ""
            rows.append(
                {
                    "公司": name,
                    "股票代码": code,
                    "报告类型": kind,
                    "报告期": period_of(title, kind),
                    "披露日期": date,
                    "标题": title,
                    "PDF链接": BASE_PDF + (item.get("adjunctUrl") or ""),
                }
            )
        total = data.get("totalRecordNum") or 0
        if page * 30 >= total:
            break
        page += 1
        time.sleep(0.4)
    return rows


def dedupe(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """同一报告期可能有多个版本，保留披露日期最晚的（更正稿优先）。"""
    best: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        key = (row["公司"], row["报告类型"], row["报告期"])
        current = best.get(key)
        if current is None or row["披露日期"] > current["披露日期"]:
            best[key] = row
    return list(best.values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只统计，不写文件")
    args = parser.parse_args()

    all_rows: list[dict[str, str]] = []
    for name, (code, org, column) in COMPANIES.items():
        print(f"抓取 {name}（{code}）...")
        for category, kind in CATEGORIES.items():
            rows = fetch_category(name, code, org, column, category, kind)
            if rows:
                print(f"  {kind}: {len(rows)} 条")
            all_rows.extend(rows)
            time.sleep(0.5)

    all_rows = dedupe(all_rows)
    all_rows.sort(key=lambda r: (r["公司"], r["报告期"], r["报告类型"]))
    print(f"\n去重后共 {len(all_rows)} 份定期报告")

    for name in COMPANIES:
        subset = [r for r in all_rows if r["公司"] == name]
        kinds: dict[str, int] = {}
        for row in subset:
            kinds[row["报告类型"]] = kinds.get(row["报告类型"], 0) + 1
        periods = sorted({r["报告期"] for r in subset})
        print(f"  {name}: {len(subset)} 份 {kinds}")
        print(f"    报告期: {', '.join(periods)}")

    if args.check:
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = ["公司", "股票代码", "报告类型", "报告期", "披露日期", "标题", "PDF链接"]
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"\n写入 {OUT_CSV.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
