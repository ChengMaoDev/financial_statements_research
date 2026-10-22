"""解析淘宝搜索结果页商品卡片，导出为 CSV。

## 背景

淘宝搜索页商品卡片的 DOM 类是 CSS Modules 哈希（`doubleCardWrapperAdapt--*`），
不能硬编码。本模块改为**从商品链接向上回溯**到含销量文案的祖先节点，
这样哈希变化时仍然可用。

## 三个踩过的坑（2026-10-21 实测）

1. **`sort=sale-desc` URL 参数无效**。实测 `?sort=sale-desc`、`?sort=bid`、
   不带 sort 三者返回顺序几乎一致，且完全不降序（400+/4/0/400+/0/200+）。
   必须**点击页面上的「销量」tab**（`li.next-tabs-tab` 且文本为「销量」）才生效。
2. **点击「销量」后，文案从「人付款」变成「人收货」**。只匹配「人付款」会得到 0 条。
3. **店铺字段会被「N年老店」抢占**。卡片末尾常见 `9年老店`、`16年老店`，
   它也以「店」结尾。必须排除 `^\\d+年老店$`。

## 字段口径

- `销量展示`：卡片上的「N人收货 / N万+人收货」。**累计口径 + 区间取整**，
  是该商品上架以来的收货人数，不是档期销量。
- `销量_折算`：把展示值折算为数字（`1万+` → 10000）。仅供分档，不可当精确计数。
- `价格_raw`：可能被淘宝打码为 `1??` / `2??` / `4???`，即只保留首位数字。
  `价格可读=0` 表示被打码，**不可用于均价计算**。
- `店铺`：卡片最后一个真正的店铺名。

## 翻页

淘宝的 `page` URL 参数**不生效**（实测 `&page=2` 仍返回第一页数据）。
必须点击分页控件的「下一页」按钮，SPA 会改写 URL 并加载新数据。

用法：
    uv run python3 scripts/parse_taobao.py --audit   # 校验已落盘 CSV
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from ecommerce_fields import FIELDS, enrich

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "市场数据" / "电商"

# 销量展示：已拼/已抢/总售 等主语都出现过，淘宝侧主要是「人付款」「人收货」
SALES_RE = re.compile(r"([\d.]+)\s*(万)?\s*\+?\s*人(付款|收货)")
PRICE_RE = re.compile(r"¥\s*\|\s*([\d?]+)(?:\s*\|\s*\.(\d+))?")

# 店龄标签，形如「9年老店」「16年老店」，不是店铺名
SHOP_AGE_RE = re.compile(r"^\d+年老店$")


def parse_sales(text: str) -> tuple[str, float | None, str]:
    """「1万+人收货」→ ('1万+人收货', 10000.0, '收货')。

    返回 (原始展示值, 折算件数, 口径)。无法解析时返回 ("", None, "")。
    """
    match = SALES_RE.search(text)
    if not match:
        return ("", None, "")
    number = float(match.group(1))
    value = number * 10000 if match.group(2) else number
    return (match.group(0), value, match.group(3))


def parse_price(text: str) -> tuple[str, bool]:
    """解析卡片价格。返回 (原始价串, 是否可读)。

    淘宝会把尾部数字打码成 `?`：`1??`（=1xx）、`2??`（=2xx）、`4???`（=4xxx）。
    打码时返回 `价格可读=False`，避免污染均价。
    """
    match = PRICE_RE.search(text)
    if not match:
        return ("", False)
    integer_part = match.group(1)
    raw = integer_part + ("." + match.group(2) if match.group(2) else "")
    return (raw, "?" not in integer_part)


def parse_shop(segments: list[str]) -> str:
    """从卡片分段里取店铺名：末尾以「店」结尾、且不是店龄标签的段。"""
    for seg in reversed(segments):
        candidate = seg.strip()
        if not candidate.endswith("店") or len(candidate) >= 30:
            continue
        if SHOP_AGE_RE.match(candidate):
            continue
        return candidate
    return ""


def parse_card(text: str, href: str, page_no: int = 1) -> dict[str, object] | None:
    """从卡片纯文本解析出结构化字段。无销量文案时返回 None。"""
    flat = text.replace("\n", " | ").strip()
    sales_display, sales_value, sales_kind = parse_sales(flat)
    if not sales_display:
        return None
    price_raw, price_ok = parse_price(flat)

    item_id = ""
    match = re.search(r"[?&]id=(\d+)", href)
    if match:
        item_id = match.group(1)

    segments = [s.strip() for s in flat.split("|") if s.strip()]
    title = segments[0][:200] if segments else ""
    shop = parse_shop(segments)

    return {
        "page": page_no,
        "item_id": item_id,
        "title": title,
        "sales_display": sales_display,
        "sales_value": sales_value,
        "sales_kind": sales_kind,
        "price_raw": price_raw,
        "price_ok": price_ok,
        "shop": shop,
    }


HEADER = [
    "关键词",
    "页码",
    "商品ID",
    "标题",
    "销量展示",
    "销量_折算",
    "价格_raw",
    "价格可读",
    "店铺",
    "数值性质",
    "采集时间",
    *FIELDS,
]


def write_csv(keyword: str, rows: list[dict[str, object]], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(HEADER)
        for row in rows:
            writer.writerow(
                [
                    keyword,
                    row["page"],
                    row["item_id"],
                    row["title"],
                    row["sales_display"],
                    "" if row["sales_value"] is None else f"{row['sales_value']:g}",
                    row["price_raw"],
                    1 if row["price_ok"] else 0,
                    row["shop"],
                    "区间下界" if "+" in str(row["sales_display"]) else "展示整数",
                    str(row.get("collected_at", "")),
                    *enrich("taobao", str(row["item_id"]), str(row["title"])),
                ]
            )
    return len(rows)


def enrich_existing() -> None:
    """历史 CSV 是唯一采集输入，只追加可复算字段，保留所有原始行。"""
    for path in sorted(DATA_DIR.glob("taobao-*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        output = []
        for row in rows:
            extra = [
                "区间下界" if "+" in row["销量展示"] else "展示整数",
                row.get("采集时间") or "2026-10-21",
                *enrich("taobao", row["商品ID"], row["标题"]),
            ]
            output.append([*(row[field] for field in HEADER[:9]), *extra])
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(HEADER)
            writer.writerows(output)
        print(f"补充 {path.name}：{len(rows)} 行")


def audit() -> int:
    """校验已落盘 CSV：列数、排序单调性、店铺名合法性、标题是否含关键词。

    返回阻断性问题数。标题关键词不命中只作提示，不计入阻断项——
    实测淘宝会把「烘干机」「烘鞋器」「集成烹饪中心」等同类变体排在结果里，
    这是平台检索的正常行为，不是采集错误。
    """
    issues = 0
    for path in sorted(DATA_DIR.glob("taobao-*.csv")):
        with path.open(encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
            fields = reader.fieldnames or []
        keyword = rows[0]["关键词"] if rows else ""

        bad_shop = [r for r in rows if SHOP_AGE_RE.match(r["店铺"] or "")]
        title_miss = [r for r in rows if keyword and keyword not in r["标题"]]
        readable = sum(1 for r in rows if r["价格可读"] == "1")

        print(f"{path.name}: {len(rows)} 条，{len(fields)} 列")
        print(f"  价格可读: {readable}/{len(rows)} ({readable / len(rows) * 100:.0f}%)")
        if bad_shop:
            print(f"  [!] 店龄误判: {len(bad_shop)} 条")
            issues += len(bad_shop)
        if title_miss:
            print(f"  [提示] 标题不含「{keyword}」: {len(title_miss)} 条（同类变体，非阻断）")
        for page in sorted({r["页码"] for r in rows}):
            values = [float(r["销量_折算"]) for r in rows if r["页码"] == page and r["销量_折算"]]
            ordered = all(values[i] >= values[i + 1] for i in range(len(values) - 1))
            print(f"    第{page}页: {len(values)} 条，降序={ordered}")
            if not ordered:
                issues += 1
    return issues


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", action="store_true", help="校验已落盘 CSV")
    parser.add_argument("--enrich", action="store_true", help="给历史样本追加链接及标题规格")
    args = parser.parse_args()
    if args.enrich:
        enrich_existing()
    if args.audit:
        raise SystemExit(1 if audit() else 0)
    parser.print_help()
