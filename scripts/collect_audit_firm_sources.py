"""保存事务所评价用的官方材料及媒体报道，不生成或修改原审计报告。

运行 python -X utf8 scripts/collect_audit_firm_sources.py。
官方排名按所披露年度比较；续聘公告为公司转引事务所提供的数据，
不等于监管机构对规模数字或审计质量的独立认证。
"""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "审计研究/中间材料/审计报告/事务所评价来源"
URLS = {
    "香港证监会20260924执法演讲.pdf": "https://www.sfc.hk/-/media/EN/files/COM/Speech/E_keynote-speech_24-Sep-2026.pdf",
    "国卫20260903香港会财局处分.html": "https://www.afrc.org.hk/en-hk/news-centre/press-releases/afrc-reprimands-hlb-for-multiple-audit-deficiencies-and-imposes-fines",
    "普华永道20240913财政部处罚新华社报道.html": "https://www.news.cn/fortune/20240913/4a09e9065ad045e8801686463d58709a/c.html",
    "和信2026证监会处罚_访问记录.html": "https://www.csrc.gov.cn/csrc/c101928/c7665087/content.shtml",
    "普华永道2024证监会通报_访问记录.html": "https://www.csrc.gov.cn/csrc/c100028/c7506543/content.shtml",
    "和信青岛中程处罚经济导报报道.html": "http://www.sdenews.com/html/2026/10/219.shtml",
    "美的2026续聘公告.pdf": "https://static.cninfo.com.cn/finalpage/2026-03-31/1225058136.PDF",
    "海尔2026续聘公告.pdf": "https://static.cninfo.com.cn/finalpage/2026-03-27/1225038306.PDF",
    "格力2026续聘公告.pdf": "https://static.cninfo.com.cn/finalpage/2026-04-29/1225250433.PDF",
    "普华永道2024监管记录自披露.pdf": "https://www.pwccn.com/zh/audit-assurance/capabilities/csrc-2024-3.pdf",
    "中注协2023综合评价正式排名.pdf": "https://www.cicpa.org.cn/xxfb/news/202411/W020241126541468095453.pdf",
    "中注协2022综合评价正式排名.pdf": "https://www.cicpa.org.cn/xxfb/tzgg/202310/W020250108629048273804.pdf",
    "和信2026续聘披露_保龄宝.pdf": "https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-04-25/72b87b36-8e80-45d3-add2-b3a2e2319f7f.PDF",
}


def collect(item):
    name, url = item
    path = OUT / name
    meta = path.with_suffix(path.suffix + ".json")
    if meta.exists():
        value = json.loads(meta.read_text(encoding="utf-8"))
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == value.get("sha256"):
            return name, "已缓存"
    if path.exists():
        raise ValueError(f"证据文件存在但未通过哈希核验，保留原件并停止：{path}")
    try:
        response = requests.get(url, timeout=35, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        if path.suffix == ".pdf" and not response.content.startswith(b"%PDF-"):
            raise ValueError("Not PDF")
        with path.open("xb") as stream:
            stream.write(response.content)
        value = {
            "url": url,
            "final_url": response.url,
            "at": datetime.now().astimezone().isoformat(),
            "sha256": hashlib.sha256(response.content).hexdigest(),
        }
    except (requests.RequestException, ValueError) as error:
        value = {"url": url, "at": datetime.now().astimezone().isoformat(), "error": str(error)}
    meta.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    return name, value


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(collect, URLS.items()):
            print(result)
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://www.cninfo.com.cn/"})
    for company, code in (("美的", "000333"), ("海尔", "600690"), ("格力", "000651")):
        target = OUT / (company + "_续聘检索.json")
        if target.exists():
            continue
        response = session.post(
            "https://www.cninfo.com.cn/new/information/topSearch/query",
            data={"keyWord": code, "maxNum": 10},
            timeout=30,
        )
        response.raise_for_status()
        identity = next(x for x in response.json() if x["code"] == code)
        params = {
            "pageNum": 1,
            "pageSize": 30,
            "tabName": "fulltext",
            "column": "sse" if code.startswith("6") else "szse",
            "stock": code + "," + identity["orgId"],
            "searchkey": "续聘",
            "secDate": "2026-01-01~2026-10-22",
            "isHLtitle": "false",
        }
        res = session.post(
            "https://www.cninfo.com.cn/new/hisAnnouncement/query", data=params, timeout=35
        )
        res.raise_for_status()
        data = {"url": res.url, "query": params, "response": res.json()}
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        for item in (data["response"].get("announcements") or [])[:6]:
            print(company, item["announcementTitle"], item["adjunctUrl"])


if __name__ == "__main__":
    main()
