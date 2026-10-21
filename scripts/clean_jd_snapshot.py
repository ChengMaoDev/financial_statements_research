"""清洗京东空调快照原始文本，生成结构化 CSV。

原始文本由 Playwright MCP 的 browser_evaluate 导出，每行四个制表符分隔字段：
标题、已售展示值、价格、店铺。搜索页会混入其他品牌商品，需按品牌关键词过滤。

产出字段口径说明：
- 已售展示值是**累计**口径且区间化取整（如「已售100万+」表示 ≥100 万，非精确值）。
- 不能当作国庆或任何单一档期的销量。
- 两次快照相减才能得到区间增量。

用法：
    uv run python3 scripts/clean_jd_snapshot.py
"""

from __future__ import annotations

import csv
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "市场数据" / "快照"
OUT = ROOT / "市场数据" / "京东空调快照.csv"

BRANDS = {
    "格力": ["格力", "GREE"],
    "美的": ["美的", "Midea", "华凌"],
    "海尔": ["海尔", "Haier", "统帅", "Leader"],
}
# 排除：搜索结果混入的其他品牌
EXCLUDE = ["美的", "Midea", "华凌", "海尔", "Haier", "统帅", "奥克斯", "小米", "TCL", "AUFIT"]


def parse_sold(value: str) -> float | None:
    """「已售100万+」→ 100.0（万）；「已售3000+」→ 0.3（万）。"""
    match = re.search(r"([\d.]+)\s*(万)?", value)
    if not match:
        return None
    number = float(match.group(1))
    return number if match.group(2) else number / 10000


def belongs(title: str, brand: str) -> bool:
    """标题是否属于该品牌，且不是混入的其他品牌。"""
    if not any(key in title for key in BRANDS[brand]):
        return False
    # 若标题同时含其他品牌关键词则剔除
    foreign = [k for k in EXCLUDE if k not in BRANDS[brand] and k in title]
    return not foreign


def main() -> int:
    rows: list[list[str]] = []
    captured = datetime.now().isoformat(timespec="seconds")

    for brand in BRANDS:
        path = RAW_DIR / f"raw-{brand}.txt"
        if not path.exists():
            print(f"缺少 {path.name}", file=sys.stderr)
            continue
        text = path.read_text(encoding="utf-8").strip()
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        text = text.replace("\\n", "\n").replace('\\"', '"').replace("\\t", "\t")
        kept = dropped = 0
        for line in text.splitlines():
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            title, sold, price, shop = (
                parts[0].strip(),
                parts[1].strip(),
                parts[2].strip(),
                parts[3].strip(),
            )
            if not belongs(title, brand):
                dropped += 1
                continue
            value = parse_sold(sold)
            rows.append(
                [
                    captured,
                    brand,
                    title,
                    price,
                    sold,
                    "" if value is None else f"{value:g}",
                    shop,
                    "累计口径·区间化取整·非档期销量",
                ]
            )
            kept += 1
        print(f"{brand}: 保留 {kept} 条，剔除 {dropped} 条（其他品牌）")

    rows.sort(key=lambda r: (r[1], -(float(r[5]) if r[5] else 0)))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            ["抓取时间", "公司", "标题", "价格_元", "已售展示值", "已售_万台", "店铺", "口径"]
        )
        writer.writerows(rows)
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
