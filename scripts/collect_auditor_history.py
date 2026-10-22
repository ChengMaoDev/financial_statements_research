"""归档2006—2025审计机构沿革的一手年报及聘任公告。

美的2006—2012按原上市公司美的电器000527列示，2013起按000333。
所有检索结果保留；本地再按期间、标题过滤，避免接口日期字段失效。
--search 获取索引，--download 下载年度原件，--scan 输出审计机构上下文。
只保留原始文件，不以连续服务年限反推缺失年度。PDF转换复用哈希缓存。
"""

from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import requests
from collect_audit_reports import pages, save, sha, stamp

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "审计研究/中间材料/审计机构沿革_2006-2025"
ISSUERS = {
    "美的集团": ("000333", "9900005965", "szse", 2013, 2025),
    "美的电器": ("000527", "gssz0000527", "szse", 2006, 2012),
    "海尔": ("600690", "gssh0600690", "sse", 2006, 2025),
    "格力": ("000651", "gssz0000651", "szse", 2006, 2025),
}
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.cninfo.com.cn/"}
EXTRA = {
    "美的2006更名": "https://static.cninfo.com.cn/finalpage/2006-12-28/19845078.PDF",
    "美的2008更名": "https://static.cninfo.com.cn/finalpage/2008-11-12/46221405.PDF",
    "美的2009变更独董意见": "https://static.cninfo.com.cn/finalpage/2010-01-09/57487399.PDF",
    "美的2012变更": "https://static.cninfo.com.cn/finalpage/2013-01-15/62019506.PDF",
    "格力2008更名": "https://static.cninfo.com.cn/finalpage/2009-02-24/49481403.PDF",
    "格力2013转制": "https://static.cninfo.com.cn/finalpage/2014-02-13/63564416.PDF",
    "海尔2019更名": "https://static.cninfo.com.cn/finalpage/2019-10-31/1207048280.PDF",
    "海尔2020国际审计聘任": "https://static.cninfo.com.cn/finalpage/2021-02-08/1209256459.PDF",
    "美的2023H股聘任": "https://static.cninfo.com.cn/finalpage/2023-09-19/1217886944.PDF",
    "美的2015改聘": "https://static.cninfo.com.cn/finalpage/2015-11-18/1201775281.PDF",
    "格力2015改聘": "https://static.cninfo.com.cn/finalpage/2015-12-10/1201824794.PDF",
    "海尔2013聘请": "https://static.cninfo.com.cn/finalpage/2013-08-28/63004992.PDF",
    "美的电器2012变更独董意见": "https://static.cninfo.com.cn/finalpage/2013-01-15/62019510.PDF",
}
# 索引标题未标明英文，实读PDF后确认这两份“修订版”为英译本；主表选中文原版。
ENGLISH_IDS = {"1202388592", "1203625873"}


def supplements():
    for name, url in EXTRA.items():
        path = OUT / "变更公告" / (name + ".pdf")
        meta = path.with_suffix(".json")
        if not path.exists():
            res = requests.get(url, headers=HEADERS, timeout=40)
            res.raise_for_status()
            if not res.content.startswith(b"%PDF-"):
                raise ValueError(url)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(res.content)
            save(meta, {"url": url, "at": stamp(), "sha256": sha(path)})
        elif sha(path) != json.loads(meta.read_text(encoding="utf-8"))["sha256"]:
            raise ValueError(path)
        print(name, flush=True)
        for i, text in enumerate(pages(path), 1):
            print("PDF", i, text, flush=True)


def search_issuer(pair):
    name, (code, org, market, _, _) = pair
    for kind, keyword in (("年报", ""), ("事务所", "会计师事务所"), ("审计机构", "审计机构")):
        for number in range(1, 21):
            path = OUT / "检索" / f"{name}_{kind}_{number}.json"
            if path.exists():
                response = json.loads(path.read_text(encoding="utf-8"))["response"]
            else:
                query = {
                    "pageNum": number,
                    "pageSize": 30,
                    "tabName": "fulltext",
                    "column": market,
                    "stock": f"{code},{org}",
                    "searchkey": keyword,
                    "seDate": "2006-01-01~2026-10-22",
                    "isHLtitle": "false",
                    "category": "category_ndbg_szsh" if kind == "年报" else "",
                }
                res = requests.post(
                    "https://www.cninfo.com.cn/new/hisAnnouncement/query",
                    data=query,
                    headers=HEADERS,
                    timeout=40,
                )
                res.raise_for_status()
                response = res.json()
                save(path, {"url": res.url, "query": query, "at": stamp(), "response": response})
            total = response.get("totalAnnouncement") or response.get("totalRecordNum") or 0
            print(name, kind, number, total, flush=True)
            if not response.get("announcements") or number * 30 >= total:
                break


def annual_candidates():
    best = {}
    for path in sorted((OUT / "检索").glob("*_年报_*.json")):
        name = path.name.split("_")[0]
        lower, upper = ISSUERS[name][3:]
        for item in (
            json.loads(path.read_text(encoding="utf-8"))["response"].get("announcements") or []
        ):
            if str(item["announcementId"]) in ENGLISH_IDS:
                continue
            title = re.sub("<[^>]+>", "", item["announcementTitle"])
            match = re.search(r"(20\d{2})\s*年", title)
            if not match or not lower <= int(match[1]) <= upper:
                continue
            if any(word in title for word in ("摘要", "英文", "取消", "公告", "说明", "English")):
                continue
            year = int(match[1])
            if "年度报告" not in title and "年报" not in title:
                continue
            key = (name, year)
            if key not in best or item["announcementTime"] > best[key]["announcementTime"]:
                best[key] = {
                    **item,
                    "name": name,
                    "year": year,
                    "index": path.relative_to(ROOT).as_posix(),
                }
    return list(best.values())


def download(item):
    name = f"{item['name']}_{item['year']}_{item['announcementId']}.pdf"
    target = OUT / "年报" / name
    meta = target.with_suffix(".json")
    if target.exists():
        data = json.loads(meta.read_text(encoding="utf-8"))
        if sha(target) != data["sha256"]:
            raise ValueError(f"原件哈希改变：{target}")
        return name
    url = "https://static.cninfo.com.cn/" + item["adjunctUrl"]
    res = requests.get(url, headers=HEADERS, timeout=60)
    res.raise_for_status()
    if not res.content.startswith(b"%PDF-"):
        raise ValueError(f"非PDF：{url}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write(res.content)
    save(meta, {"url": url, "at": stamp(), "sha256": sha(target), "item": item})
    return name


def scan():
    for item in sorted(annual_candidates(), key=lambda r: (r["name"], r["year"])):
        path = OUT / "年报" / f"{item['name']}_{item['year']}_{item['announcementId']}.pdf"
        if not path.exists():
            continue
        found = []
        for number, text in enumerate(pages(path), 1):
            lines = text.splitlines()
            for i, line in enumerate(lines):
                if re.search(r"会计师事务所|核數師|核数师", line):
                    context = "\n".join(lines[max(0, i - 1) : i + 3])
                    found.append({"page": number, "text": context})
        save(path.with_suffix(".scan.json"), found)
        print(item["name"], item["year"], len(found), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for mode in ("search", "download", "scan", "supplements"):
        parser.add_argument("--" + mode, action="store_true")
    args = parser.parse_args()
    if args.search:
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(search_issuer, ISSUERS.items()))
    if args.download:
        items = annual_candidates()
        print("候选年报", len(items), flush=True)
        with ThreadPoolExecutor(max_workers=4) as pool:
            for name in pool.map(download, items):
                print("归档", name, flush=True)
    if args.scan:
        scan()
    if args.supplements:
        supplements()
    for path in sorted((OUT / "检索").glob("*_事务所_*.json")):
        for item in (
            json.loads(path.read_text(encoding="utf-8"))["response"].get("announcements") or []
        ):
            title = item["announcementTitle"]
            if any(word in title for word in ("变更", "改聘", "更名", "转制")):
                date = datetime.fromtimestamp(item["announcementTime"] / 1000).date()
                print(path.name, date, title, item["adjunctUrl"], flush=True)


if __name__ == "__main__":
    main()
