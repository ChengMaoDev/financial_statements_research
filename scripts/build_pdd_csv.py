"""把拼多多采集结果写成 CSV。

输入是 `tools.playwright` 回传的原始行数组，格式：
    [kwid, goods_id, goods_name, sales_tip, sales_raw, price_info, price_cents, mall_id, is_ad]

## 为什么不用 `sales` 字段

实测 `sales` 与页面展示的 `sales_tip` **严重不一致**：
- 「总售1500+件」→ sales=431
- 「已抢1000+件」→ sales=1716
- 「已拼54.7万+件」→ sales=100000（封顶）

`sales` 既不是商品累计销量，也不是店铺销量，且被截断在 100,000。
**本脚本丢弃 `sales`，只保留 `sales_tip` 原文并解析出下界。**

用法：
    uv run python3 scripts/build_pdd_csv.py
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from ecommerce_fields import FIELDS, enrich

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "市场数据" / "电商"
INBOX = Path(__file__).resolve().parent / "_pdd_inbox"

TIP_RE = re.compile(r"(本店已拼|品牌热销|已拼|已抢|总售|热卖)\s*([\d.]+)\s*(万)?\s*\+?\s*(件)?")
SCOPE = {
    "已拼": "商品",
    "已抢": "商品",
    "总售": "未确认",
    "热卖": "未确认",
    "本店已拼": "店铺",
    "品牌热销": "品牌",
}
HEADER = [
    "关键词",
    "排序位",
    "商品ID",
    "标题",
    "销量展示",
    "口径",
    "销量下界_件",
    "是否区间",
    "价格_元",
    "店铺ID",
    "是否广告",
    "展示主语",
    "数值性质",
    "价格口径",
    "来源文件",
    "采集时间",
    *FIELDS,
]


def parse_tip(tip: str) -> tuple[str, float | None, bool]:
    match = TIP_RE.search(tip or "")
    if not match:
        return ("", None, False)
    prefix, number, wan = match.group(1), float(match.group(2)), match.group(3)
    value = number * 10000 if wan else number
    return (SCOPE.get(prefix, ""), value, "+" in match.group(0))


def convert(stem: str, keyword: str) -> int:
    src = INBOX / f"{stem}.tsv"
    dst = OUT_DIR / f"{stem}.csv"
    rows = []
    with src.open(encoding="utf-8") as stream:
        for rank, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 5:
                continue
            goods_id, name, tip, price_info, mall_id = parts[0:5]
            is_ad = parts[5] if len(parts) > 5 else "0"
            scope, lower, is_range = parse_tip(tip)
            rows.append(
                [
                    keyword,
                    rank,
                    goods_id,
                    name,
                    tip,
                    scope,
                    "" if lower is None else f"{lower:g}",
                    1 if is_range else 0,
                    price_info,
                    mall_id,
                    is_ad,
                    match.group(1) if (match := TIP_RE.search(tip)) else "",
                    "区间下界"
                    if lower is not None and is_range
                    else "展示整数"
                    if lower is not None
                    else "非销量/未知",
                    "搜索页展示，规格/优惠未核实",
                    src.relative_to(ROOT).as_posix(),
                    "2026-10-21",
                    *enrich("pdd", goods_id, name),
                ]
            )
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(HEADER)
        writer.writerows(rows)
    return len(rows)


def main() -> int:
    plans = [
        ("pdd-waterheater", "热水器"),
        ("pdd-dishwasher", "洗碗机"),
        ("pdd-dryer", "干衣机"),
        ("pdd-integratedstove", "集成灶"),
    ]
    for stem, keyword in plans:
        if not (INBOX / f"{stem}.tsv").exists():
            print(f"跳过 {stem}：缺 {INBOX.name}/{stem}.tsv")
            continue
        count = convert(stem, keyword)
        print(f"{stem}.csv: {count} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
