"""抓取 2026 年国庆档期公开家电市场数据，落盘为可溯源 CSV。

只抓公开可验证内容；每条记录保留来源 URL、发布日期与数据性质（实际/预测）。
不抓取需登录或付费的数据库，不生成估算值。

用法：
    uv run --with requests --with beautifulsoup4 python3 scripts/fetch_national_day.py
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "市场数据"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

# 已核实的来源。kind: actual=已发生, forecast=预测, disclosure=公司自述
SOURCES = [
    {
        "id": "S1",
        "name": "人民日报《国庆假期全国消费市场总体平稳》",
        "url": "https://paper.people.com.cn/rmrb/pc/content/202610/08/content_30184469.html",
        "date": "2026-10-08",
        "org": "商务部商务大数据",
        "kind": "actual",
        "note": "10月1日至6日口径",
    },
    {
        "id": "S2",
        "name": "第一财经《家电市场存量博弈，厂商十一假期低价冲量意愿减弱》",
        "url": "https://www.yicai.com/news/103381427.html",
        "date": "2026-09-29",
        "org": "奥维云网 / NIQ GfK",
        "kind": "actual",
        "note": "仅保留1—8月5477亿元/-9.7%的历史监测推总；预测值已删除",
    },
    {
        "id": "S5",
        "name": "新华网《这个国庆，中国消费『燃』在哪？》",
        "url": "https://www.xinhuanet.com/fortune/20261009/819f527624034968a67a4612bdb708e8/c.html",
        "date": "2026-10-09",
        "org": "国家税务总局增值税发票数据",
        "kind": "actual",
        "note": "家电和音像器材销售收入同比",
    },
]

# 结构化记录：品类/指标/数值/同比/期间/来源/性质
RECORDS = [
    # 商务部实际数据
    ("行业", "家电以旧换新销量", "284.8", "万台", "", "2026-10-01至10-06", "S1", "actual"),
    ("行业", "家电以旧换新带动销售额", "123.4", "亿元", "", "2026-10-01至10-06", "S1", "actual"),
    ("行业", "消费品以旧换新带动销售额", "334.8", "亿元", "", "2026-10-01至10-06", "S1", "actual"),
    ("行业", "以旧换新惠及人次", "639.2", "万人次", "", "2026-10-01至10-06", "S1", "actual"),
    ("行业", "一级能效洗碗机销售额", "", "", "+8.4%", "2026-10-01至10-06", "S1", "actual"),
    ("行业", "节水器具销售额", "", "", "+18.1%", "2026-10-01至10-06", "S1", "actual"),
    # 税务口径
    ("行业", "家用电器和音像器材销售收入", "", "", "+40.1%", "2026年国庆假期", "S5", "actual"),
    ("行业", "厨具卫具零售", "", "", "+52.3%", "2026年国庆假期", "S5", "actual"),
]

# 1-8 月行业基数（奥维云网推总，可验证）
BASE = [
    ("行业", "家电大盘零售额", "5477", "亿元", "-9.7%", "2026年1-8月", "S2", "actual"),
]

ANCHORS = {
    "S1": (
        "家电以旧换新284.8万台",
        "带动销售额123.4亿元",
        "334.8亿元",
        "639.2万人次",
        "8.4%",
        "18.1%",
    ),
    "S2": ("5477亿元", "减少9.7%"),
    "S5": ("家用电器和音像器材销售收入同比增长40.1%", "厨具卫具零售同比增长52.3%"),
}


def scope_note(record: tuple[str, ...]) -> str:
    if record in BASE:
        return "1—8月已发生监测推总，引用同一篇混合预测文章的历史段落；不是国庆预测兑现值"
    return (
        "公司自述，未经独立验证"
        if record[7] == "disclosure"
        else "节前预测，非实际值"
        if record[7] == "forecast"
        else "媒体转引政府统计，范围和期间以原文为准"
    )


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    print(f"写入 {path.relative_to(ROOT)}: {len(rows)} 行")


def verify_source(source: dict[str, str], cache_dir: Path | None) -> tuple[bool, str]:
    """确认关键原句，不把 HTTP 200 当作数据核验；失败时不写 CSV。"""
    try:
        if cache_dir is not None:
            text = (cache_dir / f"{source['id']}.txt").read_text(encoding="utf-8")
        else:
            response = requests.get(source["url"], headers=UA, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            text = BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True)
        body = re.sub(r"\s+", "", text)
        missing = [anchor for anchor in ANCHORS[source["id"]] if anchor not in body]
        return (
            not missing,
            f"原句 {len(ANCHORS[source['id']]) - len(missing)}/{len(ANCHORS[source['id']])}；缺失 {missing}",
        )
    except (requests.RequestException, OSError) as error:
        return False, str(error)[:120]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir", type=Path, help="使用已核对的 S1.txt、S2.txt、S5.txt 离线原文"
    )
    args = parser.parse_args()
    print("校验来源原句：")
    failed = 0
    for source in SOURCES:
        ok, detail = verify_source(source, args.source_dir)
        print(f"  {'OK ' if ok else 'FAIL'} {source['id']} {detail}")
        failed += not ok
    if failed:
        print(f"{failed} 个来源未通过，未写入任何 CSV", file=sys.stderr)
        return 1
    header = ["品类", "指标", "数值", "单位", "同比", "期间", "来源编号", "数据性质", "口径说明"]
    write_csv(OUT / "国庆档期数据.csv", header, [[*r, scope_note(r)] for r in RECORDS])
    write_csv(OUT / "行业基数_1-8月.csv", header, [[*r, scope_note(r)] for r in BASE])

    source_rows = [
        [s["id"], s["name"], s["org"], s["date"], s["kind"], s["url"], s["note"]] for s in SOURCES
    ]
    write_csv(
        OUT / "来源.csv",
        ["编号", "资料", "机构", "发布日期", "数据性质", "链接", "说明"],
        source_rows,
    )

    print(
        f"\n抓取完成：{len(RECORDS) + len(BASE)} 条记录，{len(SOURCES)} 个来源，{failed} 个不可达。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
