"""其他综合收益：不经利润表、但直接进股东权益的盈亏。

为什么重要：
2026 年上半年人民币升值，三家的「外币财务报表折算差额」同时转负，金额对归母
净利润的冲击达到：

| 公司 | 归母 OCI | 占归母净利润 | 其中外币折算 | 其中现金流量套期 |
|---|---|---|---|---|
| 美的 | -39.72 亿 | -15.0% | -33.64 亿 | -6.61 亿 |
| 海尔 | -27.55 亿 | -26.7% | -23.93 亿 | +0.31 亿 |
| 格力 | -9.20 亿 | -6.9% | -0.91 亿 | -0.04 亿 |

OCI 不进净利润，但进综合收益和净资产。只看净利润会漏掉这一层，尤其对海外
收入占 51.79% 的海尔和 43.50% 的美的。

五个陷阱：

1. **只有美的按千元列示**，海尔/格力按元。直接相加差 1000 倍。
2. **美的是四列利润表**（合并本期/合并上期/公司本期/公司上期），
   公司列大量为「-」。必须只取前两列，否则会把母公司数当成合并数。
3. **美的科目名是「财务收入」式的表内两列**，但 OCI 表的项目名与另外两家不完全
   一致：美的把「权益法下不能转损益」「其他债权投资公允价值变动」并入「其他」，
   所以**三家项目数不同，不能按行对齐**，只能按项目名对齐。
4. **OCI 期末余额 ≠ 累计税后净额**：格力 2025 年有 3.75 亿「其他综合收益结转
   留存收益」（其他权益工具投资处置），直接从 OCI 转入未分配利润，不经过损益。
   校验余额变动时必须把这笔单列，否则差额会被误判为数据错误。
5. **标签会跨行断开**：美的「1.重新计量设定受益计划变 / 动额」、海尔
   「（一）归属母公司所有者的其他综 / 合收益的税后净额」。按行正则取不到，
   必须先拼接 pending 标签。且海尔有整行无数字的空项（「（4）其他债权投资信用
   减值准备」），若不识别就会把下一行的数字挂到这一项上。

用法：
    uv run python3 scripts/extract_oci.py --all
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "年度报告"
FIN = ROOT / "财务数据"
OUT = FIN / "其他综合收益.csv"
OUT_IMPACT = FIN / "其他综合收益冲击.csv"

# (文件名, 换算到元的倍数, 列数) —— 列数=2 表示只有合并本期/上期，=4 表示美的式四列
REPORTS = {
    "美的2024.pdf": (1_000, 4),
    "美的2025.pdf": (1_000, 4),
    "美的2026半年度.pdf": (1_000, 4),
    "海尔2024.pdf": (1, 2),
    "海尔2025.pdf": (1, 2),
    "海尔2026半年度.pdf": (1, 2),
    "格力2024.pdf": (1, 2),
    "格力2025.pdf": (1, 2),
    "格力2026半年度.pdf": (1, 2),
}

# (公司, 期间) -> (文件名, 用本期还是上期)
PERIODS = {
    ("美的集团", "2023"): ("美的2024.pdf", 1),
    ("美的集团", "2024"): ("美的2025.pdf", 1),
    ("美的集团", "2025"): ("美的2025.pdf", 0),
    ("美的集团", "2025H1"): ("美的2026半年度.pdf", 1),
    ("美的集团", "2026H1"): ("美的2026半年度.pdf", 0),
    ("海尔智家", "2023"): ("海尔2024.pdf", 1),
    ("海尔智家", "2024"): ("海尔2025.pdf", 1),
    ("海尔智家", "2025"): ("海尔2025.pdf", 0),
    ("海尔智家", "2025H1"): ("海尔2026半年度.pdf", 1),
    ("海尔智家", "2026H1"): ("海尔2026半年度.pdf", 0),
    ("格力电器", "2023"): ("格力2024.pdf", 1),
    ("格力电器", "2024"): ("格力2025.pdf", 1),
    ("格力电器", "2025"): ("格力2025.pdf", 0),
    ("格力电器", "2025H1"): ("格力2026半年度.pdf", 1),
    ("格力电器", "2026H1"): ("格力2026半年度.pdf", 0),
}

ORDER = ["美的集团", "海尔智家", "格力电器"]
PERIOD_ORDER = ["2023", "2024", "2025", "2025H1", "2026H1"]

# 项目名关键词 → (分类, 统一项目名)。顺序即优先级，具体项在前。
ITEMS = [
    ("重新计量设定受益计划", "不能重分类进损益", "重新计量设定受益计划变动额"),
    ("权益法下不能转损益", "不能重分类进损益", "权益法下不能转损益的其他综合收益"),
    (
        "其他权益工具投资公允价值变动",
        "不能重分类进损益",
        "其他权益工具投资公允价值变动",
    ),
    (
        "企业自身信用风险公允价值变动",
        "不能重分类进损益",
        "企业自身信用风险公允价值变动",
    ),
    ("权益法下可转损益", "将重分类进损益", "权益法下可转损益的其他综合收益"),
    ("其他债权投资公允价值变动", "将重分类进损益", "其他债权投资公允价值变动"),
    ("金融资产重分类", "将重分类进损益", "金融资产重分类计入其他综合收益的金额"),
    ("其他债权投资信用减值准备", "将重分类进损益", "其他债权投资信用减值准备"),
    ("现金流量套期", "将重分类进损益", "现金流量套期储备"),
    ("外币财务报表折算差额", "将重分类进损益", "外币财务报表折算差额"),
    ("外币报表折算差额", "将重分类进损益", "外币财务报表折算差额"),
    ("其他", "将重分类进损益", "其他综合收益其他项"),
]  # 「其他」的实际归属靠表内小节位置判断，见 parse()

# 完整项目名（用于判断跨行标签是否已拼全）。顺序无关，只做相等/前缀判断。
FULL_NAMES = [
    "重新计量设定受益计划变动额",
    "权益法下不能转损益的其他综合收益",
    "其他权益工具投资公允价值变动",
    "企业自身信用风险公允价值变动",
    "权益法下可转损益的其他综合收益",
    "其他债权投资公允价值变动",
    "金融资产重分类计入其他综合收益的金额",
    "其他债权投资信用减值准备",
    "现金流量套期储备",
    "外币财务报表折算差额",
]

START = re.compile(r"^[一二三四五六七八]、\s*其他综合收益的税后净额")
NUMBER = re.compile(r"^\(?-?[\d,]+(?:\.\d+)?\)?$|^-$")
SPLIT = re.compile(r"\s{2,}")
# 序号有三种写法：`1.` `1．`（全角点）`（一）` `(1)`，都要去掉才能认出小计行
ENUM = re.compile(
    r"^(?:\(?[一二三四五六七八九十]+\)|\（[一二三四五六七八九十]+\）|\d+[.．、]|\（\d+\）)?"
)
# 附注号（七、63 / 五、49 / 四(45)）夹在标签与金额之间，解析前必须摘掉
NOTE_REF = re.compile(r"(?:[一二三四五六七八九十]+[、.]\s?\d+|[一二三四五六七八九十]+\(\d+\))$")
# 页码「122 / 247」和跨页页眉「海尔智家股份有限公司2024 年年度报告」会混进标签
NOISE = re.compile(r"^\d+\s*/\s*\d+$|股份有限公司.*年度报告$|年度报告全文$")


def pdf_text(pdf: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    return result.stdout


def number(token: str) -> float:
    token = token.strip()
    if token == "-":
        return 0.0
    negative = token.startswith("(") and token.endswith(")")
    return -float(token.strip("()").replace(",", "")) if negative else float(token.replace(",", ""))


def canon(label: str) -> tuple[str, str] | None:
    s = re.sub(r"\s+", "", label)
    s = ENUM.sub("", s)
    if "综合收益总额" in s:
        return ("STOP", "")
    if "其他综合收益的税后净额" in s:
        if "归属" in s and "母公司" in s:
            return ("小计", "归母其他综合收益")
        if "少数" in s:
            return ("小计", "少数股东其他综合收益")
        return ("小计", "其他综合收益税后净额")
    if s.endswith("不能重分类进损益的其他综合收益"):
        return ("小计", "不能重分类小计")
    if s.endswith("将重分类进损益的其他综合收益"):
        return ("小计", "将重分类小计")
    # 「其他」是最短的项目名，且三家都把它放在小节末尾，必须先拦下来
    if s.endswith("其他") and not s.endswith("其他综合收益"):
        return ("将重分类进损益", "其他综合收益其他项")
    # 用「统一项目名」做后缀匹配：pending 会把上一项、页码、页眉一起拼进来，
    # 当前项永远在最后。不能用关键词匹配，关键词是前缀（「权益法下可转损益」）。
    for _, category, name in ITEMS:
        if s.endswith(name):
            return (category, name)
    return None


def complete(label: str) -> bool:
    """标签是否已拼全（海尔/美的会把长标签劈成三行，数字夹在中间）。"""
    s = re.sub(r"\s+", "", label)
    s = ENUM.sub("", s)
    if s.endswith("其他综合收益的税后净额"):
        return True
    if s in ("不能重分类进损益的其他综合收益", "将重分类进损益的其他综合收益"):
        return True
    if s == "其他":
        return True
    return any(s.endswith(name) for name in FULL_NAMES)


def parse(filename: str) -> dict[str, tuple[float, float]]:
    """返回 {统一项目: (本期, 上期)}，单位元，符号正=收益。"""
    factor, columns = REPORTS[filename]
    lines = pdf_text(PDF_DIR / filename).splitlines()
    start = next((i for i, line in enumerate(lines) if START.match(line)), None)
    if start is None:
        raise ValueError(f"{filename} 未找到「其他综合收益的税后净额」表头")

    out: dict[str, tuple[float, float]] = {}
    pending = ""
    held: list[str] = []
    section = "不能重分类进损益"

    def flush(label: str, values: list[str], factor: float) -> bool:
        """写入一项；返回 False 表示已到表尾。"""
        nonlocal section
        key = canon(label)
        if key is None:
            return True
        if key[0] == "STOP":
            return False
        if key[1] == "不能重分类小计":
            section = "不能重分类进损益"
        elif key[1] == "将重分类小计":
            section = "将重分类进损益"
        name = key[1]
        if name == "其他综合收益其他项":
            name = f"{section}的其他"
        current = number(values[0]) * factor
        previous = number(values[1]) * factor if len(values) > 1 else 0.0
        out.setdefault(name, (current, previous))
        return True

    for raw in lines[start:]:
        parts = [p for p in SPLIT.split(raw.strip()) if p]
        if not parts:
            continue
        values: list[str] = []
        while parts and NUMBER.match(parts[-1]) and len(values) < columns:
            values.insert(0, parts.pop())
        # 页码「56」独占一行，会被当成一个金额；本表金额都以千元/元计，不会有 1–3 位整数
        if not parts and len(values) == 1 and len(values[0]) <= 3:
            continue
        fragment = NOTE_REF.sub("", "".join(parts))
        if NOISE.match(fragment):
            continue
        pending += fragment

        if values:
            # 数字可能单独占一行，而标签要到下一行才补全（海尔、美的都会这样断）
            held = values
        if held and complete(pending):
            label, pending, values = pending, "", held
            held = []
            if not flush(label, values, factor):
                break
        elif not values and not held and complete(pending):
            label, pending = pending, ""
            if not flush(label, ["-", "-"], factor):
                break
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all", action="store_true", default=True, help="默认执行全部；保留该开关用于兼容旧命令"
    )
    args = parser.parse_args()
    if not args.all:  # 默认 True；仅显式 --no-all 时才打印帮助
        parser.print_help()
        return 1

    cache: dict[str, dict[str, tuple[float, float]]] = {}
    for filename in REPORTS:
        cache[filename] = parse(filename)
        print(f"  {filename}: {len(cache[filename])} 项")

    rows: list[list[str]] = []
    problems: list[str] = []
    for company in ORDER:
        for period in PERIOD_ORDER:
            filename, side = PERIODS[(company, period)]
            data = cache[filename]
            if not data:
                problems.append(f"{company} {period} 空表")
                continue

            picked = {name: values[side] / 1e8 for name, values in data.items()}
            total = picked.get("其他综合收益税后净额", 0.0)
            parent = picked.get("归母其他综合收益", 0.0)
            minority = picked.get("少数股东其他综合收益", 0.0)

            items = {
                k: v
                for k, v in picked.items()
                if k
                not in (
                    "其他综合收益税后净额",
                    "归母其他综合收益",
                    "少数股东其他综合收益",
                    "不能重分类小计",
                    "将重分类小计",
                )
            }
            item_sum = sum(items.values())
            if abs(item_sum - parent) > 0.05:
                problems.append(f"{company} {period} 分项合计 {item_sum:.2f} ≠ 归母 {parent:.2f}")
            if abs(parent + minority - total) > 0.05:
                problems.append(
                    f"{company} {period} 归母+少数 {parent + minority:.2f} ≠ 合计 {total:.2f}"
                )

            def emit(
                category: str,
                name: str,
                value: float | None,
                nature: str,
                company: str = company,
                period: str = period,
            ) -> None:
                if value is None:
                    cells = ["", "", ""]
                elif name in ("归母其他综合收益", "不能重分类小计", "将重分类小计"):
                    cells = [f"{value:.2f}", "", ""]
                elif name == "少数股东其他综合收益":
                    cells = ["", f"{value:.2f}", ""]
                elif name == "其他综合收益税后净额":
                    cells = ["", "", f"{value:.2f}"]
                else:
                    cells = [f"{value:.2f}", "", ""]
                rows.append([company, period, category, name, *cells, nature])

            for category, name in (
                ("不能重分类进损益", "重新计量设定受益计划变动额"),
                ("不能重分类进损益", "权益法下不能转损益的其他综合收益"),
                ("不能重分类进损益", "其他权益工具投资公允价值变动"),
                ("不能重分类进损益", "企业自身信用风险公允价值变动"),
            ):
                emit(
                    category,
                    name,
                    picked.get(name),
                    "披露值" if name in picked else "未单列",
                )
            emit("小计", "不能重分类小计", picked.get("不能重分类小计"), "披露值")

            for category, name in (
                ("将重分类进损益", "权益法下可转损益的其他综合收益"),
                ("将重分类进损益", "其他债权投资公允价值变动"),
                ("将重分类进损益", "金融资产重分类计入其他综合收益的金额"),
                ("将重分类进损益", "其他债权投资信用减值准备"),
                ("将重分类进损益", "现金流量套期储备"),
                ("将重分类进损益", "外币财务报表折算差额"),
                ("将重分类进损益", "将重分类进损益的其他"),
                ("不能重分类进损益", "不能重分类进损益的其他"),
            ):
                emit(
                    category,
                    name,
                    picked.get(name),
                    "披露值" if name in picked else "未单列",
                )
            emit("小计", "将重分类小计", picked.get("将重分类小计"), "披露值")

            emit("小计", "归母其他综合收益", parent, "披露值")
            emit("小计", "少数股东其他综合收益", minority, "披露值")
            emit("合计", "其他综合收益税后净额", total, "披露值")

    fields = [
        "公司",
        "期间",
        "分类",
        "项目",
        "税后归母(亿元)",
        "税后少数股东(亿元)",
        "税后合计(亿元)",
        "数据性质",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    impact = build_impact(rows)
    with OUT_IMPACT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            [
                "公司",
                "期间",
                "归母其他综合收益(亿元)",
                "归母净利润(亿元)",
                "占归母净利润%",
                "归母综合收益(亿元)",
                "累计其他综合收益(亿元)",
                "占归母权益%",
                "余额变动(亿元)",
                "余额变动与本期差额(亿元)",
                "差额说明",
                "数据性质",
            ]
        )
        writer.writerows(impact)

    print(
        f"\n{'公司':<8}{'期间':<8}{'归母OCI':>10}{'折人民币':>10}{'归母净利':>10}{'占比':>9}{'累计OCI':>10}"
    )
    print("-" * 68)
    for row in impact:
        print(f"{row[0]:<8}{row[1]:<8}{row[2]:>10}{'':>10}{row[3]:>10}{row[4]:>9}{row[6]:>10}")

    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    print(f"写入 {OUT_IMPACT.relative_to(ROOT)}: {len(impact)} 行")
    for problem in problems:
        print(f"校验问题：{problem}", file=sys.stderr)
    return 0


# 余额变动与本期 OCI 的差额，逐项人工核对过年报附注，全部有出处
RESIDUAL_NOTE = {
    (
        "格力电器",
        "2024",
    ): "其他综合收益结转留存收益 2.69 亿（附注五、49 转入留存收益列）",
    (
        "格力电器",
        "2025",
    ): "其他综合收益结转留存收益 3.75 亿（其他权益工具投资处置，附注五、49）",
    ("格力电器", "2026H1"): "其他综合收益结转留存收益 0.47 亿（附注 50）",
    (
        "海尔智家",
        "2024",
    ): "2025 年报将 2024 年归母 OCI 重述为 -11.60 亿（原披露 -11.76 亿），"
    "但资产负债表期初未同步重述，差 0.16 亿",
}


def build_impact(rows: list[list[str]]) -> list[list[str]]:
    """归母 OCI 对净利润与净资产的冲击，并校验 OCI 余额变动是否可解释。"""
    profit = load_series("利润表.csv", "归属于母公司所有者的净利润")
    equity = load_series("资产负债表.csv", "归属于母公司股东权益合计")
    balance = load_series("资产负债表.csv", "其他综合收益")

    impact: list[list[str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        company, period, name = row[0], row[1], row[3]
        if name != "归母其他综合收益" or (company, period) in seen:
            continue
        seen.add((company, period))
        oci = float(row[4])
        net = profit.get((company, period))
        eq = equity.get((company, period))
        bal = balance.get((company, period))
        if net is None or eq is None:
            continue

        # 期初余额：年度取上年末，半年取上年末（不是上年同期）
        opening_period = {
            "2023": None,
            "2024": "2023",
            "2025": "2024",
            "2025H1": "2024",
            "2026H1": "2025",
        }[period]
        before = balance.get((company, opening_period)) if opening_period else None
        delta = bal - before if bal is not None and before is not None else None
        residual = delta - oci if delta is not None else None

        impact.append(
            [
                company,
                period,
                f"{oci:.2f}",
                f"{net:.2f}",
                f"{oci / net * 100:.2f}",
                f"{net + oci:.2f}",
                f"{bal:.2f}" if bal is not None else "",
                f"{bal / eq * 100:.2f}" if bal is not None and eq else "",
                f"{delta:.2f}" if delta is not None else "",
                f"{residual:.2f}" if residual is not None else "",
                RESIDUAL_NOTE.get((company, period), ""),
                "计算值",
            ]
        )
    return impact


def load_series(filename: str, subject: str) -> dict[tuple[str, str], float]:
    path = FIN / filename
    out: dict[tuple[str, str], float] = {}
    with path.open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["科目"] != subject:
                continue
            period = row["报告期"]
            key = (
                period[:4]
                if period.endswith("1231")
                else f"{period[:4]}H1"
                if period.endswith("0630")
                else None
            )
            if key is None:
                continue
            try:
                out[(row["公司"], key)] = float(row["数值"]) / 1e8
            except ValueError:
                continue
    return out


if __name__ == "__main__":
    sys.exit(main())
