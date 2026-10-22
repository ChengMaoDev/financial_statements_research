"""合并京东联盟（JD Union）商品搜索导出，生成组级品类面板 CSV。

## 数据来源

`union.jd.com/proManager` 商品推广页（登录态）。原始导出保留在
`市场数据/电商/jdunion-<kw>.csv`。2026-10-21旧样本曾尝试排序，但结果未降序；
2026-10-22补采热泵干衣机一页60条。两批均为检索样本，不代表最高引单商品。

## 共享数值的处理

同一个店铺下，一批 SKU 会共享**完全相同**的 `inOrderCount30Days` 与
`inOrderComm30Days`（后者精确到分，19 个不同型号的电视共用 6,362,047.64）。
平台未披露其聚合层级，不能直接认定为SKU真实订单数或商品系列总量。

因此在 SKU 级求和会成倍放大。本脚本按
`(采集日期, 品类, 店铺, 引单量_30天, 支出佣金_30天)` 折叠成**组级观测**，
SKU 明细保留在 `京东联盟_SKU明细.csv` 供核对。

## 字段口径

- `引单量_30天`：近30天引单展示数；不少值只有1位有效数字，部分小值是否精确未经确认。
  仅保留展示量级，不据此计算真实销量、倍数或跨组总量。
- `支出佣金_30天`：近 30 天佣金支出（元），未取整。缺陷是随佣金率浮动，
  佣金率 1% 和 10% 的同销量商品会差 10 倍，**不能当销售额或销量代理**。
- `代表到手价_元`：组内 SKU 的到手价中位数。
- `SKU数`：组内去重后的SKU个数；保留全部来源关键词，不等于系列铺货总数。

## 能回答 / 不能回答

能：描述同一采集日的检索结果、展示价格和引单量级。

不能：品牌实际销量、销售额、市场份额；不能把引单量求和当品类销量
（引单量≠成交件数，且只覆盖开通联盟佣金的商品）。

用法：
    uv run python3 scripts/build_jdunion_panel.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

from ecommerce_fields import FIELDS, enrich

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "市场数据" / "电商"
OUT_GROUP = RAW_DIR / "京东联盟_组级面板.csv"
OUT_SKU = RAW_DIR / "京东联盟_SKU明细.csv"

# 原始文件后缀 → (检索关键词, 品类)
# 注意：「冰箱」单词会命中冰淇淋（cat1=食品），已弃用，改用「电冰箱」。
KEYWORDS = {
    "aircon": ("空调", "空调"),
    "k_gree": ("格力空调", "空调"),
    "k_midea": ("美的空调", "空调"),
    "k_haier": ("海尔空调", "空调"),
    "fridge2": ("电冰箱", "冰箱"),
    "washer": ("洗衣机", "洗衣机"),
    "washer2": ("滚筒洗衣机", "洗衣机"),
    "tv": ("电视", "电视"),
    "hood": ("油烟机", "油烟机"),
    "stove": ("燃气灶", "燃气灶"),
    # 2026-10-21 补采，大家电补齐
    "waterheater": ("热水器", "热水器"),
    "dishwasher": ("洗碗机", "洗碗机"),
    "dryer": ("干衣机", "干衣机"),
    "integratedstove": ("集成灶", "集成灶"),
    "dryer_heatpump": ("热泵干衣机", "干衣机"),
}

BRAND_ALIASES = [
    ("美的", ["美的", "Midea", "华凌"]),
    ("海尔", ["海尔", "Haier", "统帅", "Leader", "卡萨帝", "Casarte"]),
    ("格力", ["格力", "GREE"]),
    ("小米", ["小米", "米家", "MI"]),
    ("海信", ["海信", "Hisense", "Vidda", "科龙", "KELON"]),
    ("TCL", ["TCL"]),
    ("奥克斯", ["奥克斯", "AUX", "AUFIT", "京灿"]),
    ("老板", ["老板", "Robam"]),
    ("方太", ["方太", "FOTILE"]),
    ("华帝", ["华帝", "VATTI"]),
    ("创维", ["创维", "Skyworth", "酷开", "coocaa"]),
    ("长虹", ["长虹", "CHANGHONG"]),
    ("容声", ["容声", "Ronshen"]),
    ("小天鹅", ["小天鹅", "LittleSwan"]),
    ("康佳", ["康佳", "KONKA"]),
    # 热水器 / 厨电 / 集成灶 品牌（2026-10-21 补采时加入）
    ("A.O.史密斯", ["A.O.史密斯", "A.O.Smith", "史密斯", "AOSMITH", "AO史密斯", "AOSmith"]),
    ("林内", ["林内", "Rinnai"]),
    ("能率", ["能率", "Noritz"]),
    ("万和", ["万和", "Vanward"]),
    ("万家乐", ["万家乐", "Macro"]),
    ("樱花", ["樱花", "SAKURA"]),
    ("帅康", ["帅康", "Sacon"]),
    ("火星人", ["火星人", "Marssenger"]),
    ("美大", ["美大", "Meida"]),
    ("亿田", ["亿田", "Entive"]),
    ("森歌", ["森歌", "Senge"]),
    ("西门子", ["西门子", "SIEMENS"]),
    ("博世", ["博世", "BOSCH"]),
    ("松下", ["松下", "Panasonic"]),
    ("九阳", ["九阳", "Joyoung"]),
    ("苏泊尔", ["苏泊尔", "SUPOR"]),
]

# 非商品条目：家政清洗服务、配件、食品。这些不是家电销量信号。
# 注意：只匹配「明确是配件/耗材/服务」的语义，不要只匹配某个词。
# 反例（已踩过）：
#   - 「保洁柜」是集成灶的消毒柜，不是保洁服务
#   - 「免拆洗」是油烟机卖点，不是清洗服务
#   - 「可折叠易收纳」是干衣机卖点
#   - 「洗碗粉/洗碗块/洗碗盐」是洗碗机耗材，属独立类目，不是洗碗机整机
POLLUTION = re.compile(
    # 食品（「冰箱」检索词会命中冰淇淋）；「速冻」只在非家电标题里才算污染
    r"冰淇淋|雪糕|冰棍|冰激凌|冷饮|水饺|汤圆|"
    r"^伊利|^蒙牛|^光明|^八喜|哈根达斯|和路雪|梦龙|"
    # 明确的服务（只匹配「服务本身」，不要匹配卖点式的「上门安装」）
    r"家政|上门服务|家电清洗|保洁服务|安装服务|延保|"
    # 明确的配件（「挂架」常作为电视的赠品出现在标题里，不能单独匹配）
    r"电视柜|电视挂架|遥控器|空调伴侣|空调罩|空调挡风|滤芯|"
    r"冰箱贴|活性炭|冰箱垫|隔板|"
    # 洗碗机耗材：除粉/块/盐/凝珠外，「漂洗剂/光亮剂/洗碗液/洗涤剂」同样是耗材。
    # 漏掉它们会让 39 元的洗碗液留在面板里，而且它恰好是品类最高引单量档
    # （o30=20000）——品类最高档因此是错的（剔除后降到 9000）。
    r"洗碗粉|洗碗块|洗碗凝珠|洗碗盐|软水盐|亮碟剂|机体清洁剂|洗碗机清洁剂|"
    r"漂洗剂|光亮剂|洗碗液|洗涤剂|洗涤清洁剂|洗护合一|"
    r"晾衣架|烘干架|烘衣袋|"
    # 燃气灶/集成灶的可替换零件（「火盖」是卖点词，需配合「配件/分火器/灶芯」才判定）
    r"分火器|点火针|炉头配件|灶芯"
)

# 食品类目（京东 cat1=食品饮料 相关）整类剔除，避免「冰箱」搜出冰淇淋。
# 这些量级占位在原始数据里很显眼（伊利、八喜、光明），必须显式处理。
# 注意：这里做**子串**匹配，因为原始品牌名常带后缀（「光明牌（Guang Ming Pai）」
# 「蒙牛（MENGNIU）」），精确等于会漏掉。
FOOD_BRANDS = (
    "伊利",
    "蒙牛",
    "光明",
    "八喜",
    "哈根达斯",
    "和路雪",
    "梦龙",
    "德芙",
    "明治",
    "喜之郎",
    "美登高",
    "冰记",
    "东北大板",
)


def is_food_brand(raw: str) -> bool:
    """原始品牌名是否属于食品品牌。必须在 normalize 之前判断。"""
    text = (raw or "").strip()
    return any(key in text for key in FOOD_BRANDS)


def _alias_hit(alias: str, text: str) -> bool:
    """别名是否命中。

    CJK 别名用子串匹配（「史密斯」可命中「A.O.史密斯」这类写法）；
    **纯 ASCII 别名必须整词匹配**，否则会大量误命中：
      - `MI`   是 `SMITH`、`Midea`、`Ming` 的子串 → 会把它牌错判成小米
      - `Senge` 是 `marssenger` 的子串 → 会把火星人错判成森歌
    """
    if not alias.isascii():
        return alias in text
    return (
        re.search(rf"(?<![A-Za-z]){re.escape(alias)}(?![A-Za-z])", text, re.IGNORECASE) is not None
    )


def normalize_brand(raw: str) -> str:
    text = (raw or "").strip()
    # 长别名优先，避免短别名抢先命中（如「A.O.史密斯」先于任何短词）
    for canonical, keys in BRAND_ALIASES:
        if any(_alias_hit(k, text) for k in sorted(keys, key=len, reverse=True)):
            return canonical
    return text or "未知"


def load_raw() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(RAW_DIR.glob("jdunion-*.csv")):
        # 下载会保留下划线，如 jdunion-k_gree.csv，这里统一成登记用的键
        key = path.stem.removeprefix("jdunion-").replace("-", "_")
        if key not in KEYWORDS:
            print(f"跳过未登记的关键词文件 {path.name}", file=sys.stderr)
            continue
        keyword, category = KEYWORDS[key]
        with path.open(encoding="utf-8-sig") as stream:
            for row in csv.DictReader(stream):
                row["kw_file"] = key
                row["keyword"] = keyword
                row["category"] = category
                row["source_file"] = path.relative_to(ROOT).as_posix()
                rows.append(row)
    return rows


def to_int(value: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def to_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main() -> int:
    raw = load_raw()
    if not raw:
        print("没有找到 jdunion-*.csv 原始导出", file=sys.stderr)
        return 1

    seen: set[tuple[str, str]] = set()
    sku_rows: list[dict[str, object]] = []
    dropped = 0

    for row in raw:
        name = row.get("name", "")
        if POLLUTION.search(name):
            dropped += 1
            continue
        key = (row["kw_file"], row["sku"])
        if key in seen:
            continue
        seen.add(key)
        brand_raw = row.get("brand", "")
        if is_food_brand(brand_raw):
            dropped += 1
            continue
        sku_rows.append(
            {
                "category": row["category"],
                "keyword": row["keyword"],
                "page": row.get("page", ""),
                "sku": row["sku"],
                "name": name,
                "brand_raw": brand_raw,
                "brand": normalize_brand(brand_raw),
                "shop": row.get("shop", ""),
                "price": to_float(row.get("price", "")),
                "o30": to_int(row.get("o30", "")),
                "c30": to_float(row.get("c30", "")),
                "comments": to_int(row.get("comments", "")),
                "good": row.get("good", ""),
                "comm_rate": row.get("commShare", ""),
                "source_file": row["source_file"],
                "collected": row.get("collected_at", "2026-10-21"),
                "coupon": row.get("coupon", ""),
            }
        )

    # 折叠成组级观测
    #
    # 组键 = (品类, 店铺, o30, c30)。这个键的前提是「同店铺同 o30 同 c30 = 同一个
    # 投放单元」。但当 o30=0 且 c30=0 时，键退化成 (品类, 店铺)，会把该店铺下
    # 完全无关的商品并成一组：实测 6 个组吞掉 29 个 SKU，例如把 TCL 488 元的
    # 和海尔 1579 元的商品并在一起算出 833 元的「代表价」，还有一家店的美的
    # 与华帝 SKU 数 3:3 平票、按插入顺序选中美的，6 条华帝机型被计入美的。
    #
    # 因此 o30=0 且 c30=0 时不折叠，用 SKU 自身作键（一个 SKU 一个组）。
    groups: dict[tuple[str, str, int, float | None, str, str], list[dict[str, object]]] = {}
    for row in sku_rows:
        o30 = int(row["o30"])
        c30 = row["c30"]
        degenerate = o30 == 0 and (c30 is None or float(c30) == 0.0)
        key = (
            str(row["category"]),
            str(row["shop"]),
            o30,
            c30,
            str(row["sku"]) if degenerate else "",
            str(row["collected"])[:10],
        )
        groups.setdefault(key, []).append(row)

    group_rows: list[list[str]] = []
    for (category, shop, o30, c30, sku_key, snapshot), observations in groups.items():
        # SKU 明细保留检索词观测；组内价格与型号数按唯一 SKU 计算。
        unique = {str(member["sku"]): member for member in observations}
        members = list(unique.values())
        prices = [float(m["price"]) for m in members if m["price"]]
        brand_counts: dict[str, int] = {}
        for m in members:
            brand_counts[str(m["brand"])] = brand_counts.get(str(m["brand"]), 0) + 1
        top_brand = max(brand_counts, key=lambda b: brand_counts[b])
        group_rows.append(
            [
                category,
                shop,
                top_brand,
                str(o30),
                "" if c30 is None else f"{c30:.2f}",
                f"{statistics.median(prices):.2f}" if prices else "",
                str(len(members)),
                ";".join(sorted({str(member["keyword"]) for member in observations})),
                str(min(float(m["price"]) for m in members if m["price"])) if prices else "",
                str(max(float(m["price"]) for m in members if m["price"])) if prices else "",
                hashlib.sha256(
                    repr((category, shop, o30, c30, sku_key, snapshot)).encode("utf-8")
                ).hexdigest()[:20],
                snapshot,
            ]
        )

    group_rows.sort(key=lambda r: (r[0], -int(r[3]), -(float(r[4]) if r[4] else 0)))

    def write(path: Path, header: list[str], rows: list[list[str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(rows)

    write(
        OUT_GROUP,
        [
            "品类",
            "店铺",
            "主导品牌",
            "引单量_30天",
            "支出佣金_30天",
            "代表到手价_元",
            "SKU数",
            "来源关键词",
            "最低到手价_元",
            "最高到手价_元",
            "组标识",
            "采集日期",
        ],
        group_rows,
    )

    sku_export = [
        [
            str(r["category"]),
            str(r["keyword"]),
            str(r["page"]),
            str(r["sku"]),
            str(r["name"]),
            str(r["brand_raw"]),
            str(r["brand"]),
            str(r["shop"]),
            "" if r["price"] is None else f"{r['price']:.2f}",
            str(r["o30"]),
            "" if r["c30"] is None else f"{r['c30']:.2f}",
            str(r["comments"]),
            str(r["good"]),
            str(r["comm_rate"]),
            str(r["source_file"]),
            str(r["collected"]),
            str(r["coupon"]),
            *enrich("jd", str(r["sku"]), str(r["name"])),
        ]
        for r in sku_rows
    ]
    write(
        OUT_SKU,
        [
            "品类",
            "关键词",
            "页码",
            "SKU",
            "标题",
            "品牌_原始",
            "品牌",
            "店铺",
            "到手价_元",
            "引单量_30天",
            "支出佣金_30天",
            "评价数",
            "好评率",
            "佣金率",
            "来源文件",
            "采集时间",
            "优惠券标记_原始",
            *FIELDS,
        ],
        sku_export,
    )

    stamp = datetime.now().isoformat(timespec="seconds")
    print(f"原始 {len(raw)} 条 → SKU 明细 {len(sku_rows)} 条 → 组级观测 {len(group_rows)} 条")
    print(f"剔除非商品条目 {dropped} 条（家政服务/配件/食品）")
    print(f"写入 {OUT_GROUP.relative_to(ROOT)}")
    print(f"写入 {OUT_SKU.relative_to(ROOT)}（{stamp}）")

    by_cat: dict[str, int] = {}
    for row in group_rows:
        by_cat[row[0]] = by_cat.get(row[0], 0) + 1
    for cat, count in sorted(by_cat.items(), key=lambda kv: -kv[1]):
        print(f"  {cat}: {count} 组")
    return 0


def import_snapshot(path: Path) -> None:
    """只导入浏览器白名单字段；输入不得覆盖已有关键词快照。"""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload["keyword"] != "dryer_heatpump":
        raise ValueError("仅接受本次热泵干衣机补采")
    target = RAW_DIR / "jdunion-dryer_heatpump.csv"
    if target.exists():
        raise FileExistsError(f"快照已存在，拒绝覆盖：{target.name}")
    columns = [
        "sku",
        "name",
        "brand",
        "shop",
        "price",
        "o30",
        "c30",
        "comments",
        "good",
        "commShare",
        "coupon",
        "dtype",
    ]
    with target.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["kw", "page", *columns, "collected_at", "source_url"])
        for row in payload["rows"]:
            writer.writerow(
                [
                    "dryer_heatpump",
                    "1",
                    *(row[column] for column in columns),
                    payload["collected_at"],
                    payload["source_url"],
                ]
            )
    print(f"补采原始导出 {target.name}：{len(payload['rows'])} 行")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--import-json", type=Path, help="导入本次浏览器补采的热泵干衣机样本")
    args = parser.parse_args()
    if args.import_json:
        import_snapshot(args.import_json)
    sys.exit(main())
