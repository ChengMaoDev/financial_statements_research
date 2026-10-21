"""拼多多搜索页采集器（Playwright + CDP）。

## 为什么用 CDP 而不是解析 DOM

拼多多移动端搜索页是 XRender 同构渲染，商品卡片的 `<a>` 链接**不在 DOM 里**
（实测 `document.querySelectorAll('a')` 返回 0 个 goods 链接），
卡片由 JS 动态挂载。直接解析 DOM 拿不到商品 ID。

可靠路径：监听 `POST https://mobile.yangkeduo.com/proxy/api/search` 的响应体，
商品在 `items[].item_data.goods_model`。每次滚动触发一页（20 条），`total` 上限 300。

## 排序

`s?search_key=X&sort_type=_sales` 是**有效**的销量排序参数（实测 URL 与响应一致）。
但排序基准是 API 的 `sales` 字段，而不是页面展示的 `sales_tip`，两者并不等价（见下）。

## 三个口径陷阱（必须记住）

1. **`sales` 与 `sales_tip` 不一致**。实测同一商品展示「已抢3928件」而 `sales=53000`；
   展示「已拼54.7万+件」而 `sales=100000`。`sales` 明显被封顶在 100,000，
   且与展示文本不是同一口径。**禁止用 `sales` 当销量**。
2. **`sales_tip` 有三种主语**：`已拼`/`已抢`/`总售`（商品或店铺口径未明示）、
   `本店已拼XX万+`（店铺级）、`品牌热销XX万+件`（品牌级）。混排时不可相加。
3. **`已拼54.7万+件` 这类展示值带「+」，是区间下界**，只可用于分档。

因此本数据集只保留：排序位次（在 `_sales` 下的相对位置）+ 展示值原文。
不做销量求和，不折算市场份额。

用法：
    uv run python3 scripts/collect_pinduoduo.py --dry-run   # 只打印采集计划
    在 Playwright 上下文内调用 collect() 见下。
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "市场数据" / "电商"

# 关键词 → (文件标识, 品类)
KEYWORDS: dict[str, tuple[str, str]] = {
    "热水器": ("pdd-waterheater", "热水器"),
    "洗碗机": ("pdd-dishwasher", "洗碗机"),
    "干衣机": ("pdd-dryer", "干衣机"),
    "集成灶": ("pdd-integratedstove", "集成灶"),
}

# 展示值解析：已拼/已抢/总售/热卖 + 数字 + 万 + 件
SALES_TIP = re.compile(r"(本店已拼|品牌热销|已拼|已抢|总售|热卖)\s*([\d.]+)\s*(万)?\s*\+?\s*件?")

# 口径分类：商品级 vs 店铺级 vs 品牌级
SCOPE = {
    "已拼": "商品",
    "已抢": "商品",
    "总售": "商品",
    "热卖": "商品",
    "本店已拼": "店铺",
    "品牌热销": "品牌",
}


def parse_tip(tip: str) -> tuple[str, float | None, bool]:
    """返回 (口径, 折算件数, 是否为区间下界)。

    `已拼54.7万+件` → ('商品', 547000.0, True)
    `已拼3件`      → ('商品', 3.0, False)
    """
    match = SALES_TIP.search(tip or "")
    if not match:
        return ("", None, False)
    prefix, number, wan = match.group(1), float(match.group(2)), match.group(3)
    value = number * 10000 if wan else number
    has_plus = "+" in match.group(0)
    return (SCOPE.get(prefix, ""), value, has_plus)


def write_csv(rows: list[list[object]], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = [
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
    ]
    with out_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    return len(rows)


def build_row(keyword: str, rank: int, goods: dict[str, object], is_ad: bool) -> list[object]:
    tip = str(goods.get("sales_tip") or "")
    scope, lower, is_range = parse_tip(tip)
    price_raw = goods.get("price_info")
    return [
        keyword,
        rank,
        str(goods.get("goods_id") or ""),
        str(goods.get("goods_name") or "")[:200],
        tip,
        scope,
        "" if lower is None else f"{lower:g}",
        1 if is_range else 0,
        str(price_raw or ""),
        str(goods.get("mall_id") or ""),
        1 if is_ad else 0,
    ]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="只打印采集计划")
    args = parser.parse_args()
    for keyword, (stem, category) in KEYWORDS.items():
        print(f"{keyword} → {stem}.csv（品类：{category}）")
    if not args.dry_run:
        print("\n采集需在 Playwright 上下文内执行，见模块 docstring。")
