"""汇总三家公司的法定披露索引，写入数据源清单。

本脚本不抓正文，只抓**元数据索引**：
- A 股定期报告清单（巨潮资讯网，深交所指定披露平台）
- H 股公告索引（港交所披露易，美的 00300 / 海尔 06690）

港交所的价值在于 A 股没有的部分：月度证券变动报表、翌日披露报表、
董事会会议召开日期（财报披露的前置信号）、中期股息分派细节。

用法：
    uv run python3 scripts/fetch_hkex_index.py
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "定期报告"
OUT_CSV = OUT_DIR / "港股公告索引.csv"

BASE = "https://www1.hkexnews.hk"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# 公司 → (H 股代码, 港交所 stockId)。格力无 H 股。
COMPANIES = {
    "美的集团": ("00300", "1000231771"),
    "海尔智家": ("06690", "1000066160"),
}

# 只保留有分析价值的类别，过滤掉纯合规的翌日披露报表噪声。
KEEP_KEYWORDS = [
    "年報",
    "年报",
    "中期報告",
    "中期报告",
    "季度",
    "月報表",
    "月报表",
    "股息",
    "業績",
    "业绩",
    "盈利",
    "董事會會議",
    "董事会会议",
    "回購",
    "回购",
    "股東週年大會",
    "股东周年大会",
    "股東特別大會",
]


def fetch(sid: str, from_date: str, to_date: str) -> list[dict[str, str]]:
    params = {
        "sortDir": "0",
        "sortByOptions": "DateTime",
        "category": "0",
        "market": "SEHK",
        "stockId": sid,
        "documentType": "-1",
        "fromDate": from_date,
        "toDate": to_date,
        "title": "",
        "searchType": "0",
        "t1code": "-2",
        "t2Gcode": "-2",
        "t2code": "-2",
        "rowRange": "100",
        "lang": "zh",
    }
    url = f"{BASE}/search/titleSearchServlet.do?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Referer": f"{BASE}/search/titlesearch.xhtml"},
    )
    with urllib.request.urlopen(request, timeout=40) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    return json.loads(payload.get("result") or "[]")


def to_iso(hk_date: str) -> str:
    """港交所返回 dd/mm/yyyy，转为 yyyy-mm-dd。"""
    parts = (hk_date or "").split(" ")[0].split("/")
    if len(parts) != 3:
        return ""
    day, month, year = parts
    return f"{year}-{month}-{day}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    rows: list[dict[str, str]] = []
    for name, (code, sid) in COMPANIES.items():
        print(f"抓取 {name}（H 股 {code}）...")
        items = fetch(sid, "20230101", "20261021")
        kept = 0
        for item in items:
            title = (item.get("TITLE") or "").strip()
            if not any(key in title for key in KEEP_KEYWORDS):
                continue
            rows.append(
                {
                    "公司": name,
                    "港股代码": code,
                    "披露日期": to_iso(item.get("DATE_TIME", "")),
                    "类别": item.get("LONG_TEXT") or "",
                    "标题": title.replace("\n", " "),
                    "链接": BASE + (item.get("FILE_LINK") or ""),
                }
            )
            kept += 1
        print(f"  原始 {len(items)} 条，保留 {kept} 条")
        time.sleep(0.6)

    rows.sort(key=lambda r: (r["公司"], r["披露日期"]), reverse=True)
    print(f"\n合计 {len(rows)} 条")

    if args.check:
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = ["公司", "港股代码", "披露日期", "类别", "标题", "链接"]
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"写入 {OUT_CSV.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
