"""签字注册会计师、审计机构与审计年限：审计端的独立性信号。

为什么重要
----------
已有 `治理与经营披露.csv` 记了 2023—2025 的「审计意见 + 事务所名称」，
`关键审计事项.csv` 记了 KAM 与报酬。但**签字注册会计师**没人记，
而它才是审计独立性最直接的观测点：

- 中国证监会要求签字注册会计师**连续提供服务满 5 年必须轮换**。
  美的境内签字「姚文平」2020—2024 连续 5 年后在 2025 换成「周伟然」，
  正好卡在规则边界上；格力「吴梓豪」2019 签字、2020—2021 缺席、
  2022 又回来——这种「隔两年复任」是否合规取决于冷却期怎么算，值得盯。
- 海尔「和信」已连续审计 13 年（2025 年报自述），事务所层面的长期连任
  与签字人轮换是两件不同的事，分开看才知道独立性靠什么维持。

三家披露格式完全不同，这是本脚本复杂度的来源
--------------------------------------------
| 公司 | 境内签字人标签 | 境外签字人标签 | 有境外审计吗 |
|---|---|---|---|
| 美的 | 境内会计师事务所注册会计师姓名（2024 起另有「境内签字会计师姓名」） | 境外会计师事务所注册会计师姓名 | 2024 年 H 股上市后才有（罗兵咸永道） |
| 海尔 | 签字会计师姓名（在「公司聘请的会计师事务所（境内）」块里） | 签字会计师姓名（在（境外）块里，**标签完全同名**） | 一直有（国卫 HLB） |
| 格力 | 签字会计师姓名 + 境内会计师事务所注册会计师姓名（两处一致） | 无 | 无 |

三个坑（都是本轮实测踩到的）
----------------------------
1. **海尔的境内与境外签字人用同一个标签「签字会计师姓名」**，靠上方
   「事务所（境内）／（境外）」分块。若按「取第一个命中」会把两半混成一个，
   按「取最后命中」会把境外的人记成境内。开发过程中就因此把海尔 2025 的
   境内签字人记成「张军、李祥智 邱伟业」（两个不同的人挤进一条）。
   **必须按分块上下文判归属**，并按出现顺序对齐同块的名称行。
2. **标签会被排版拆进多行**。海尔 2025 的「公司聘请的会／计师事务所／（境内）」
   竖排成三行，任何以完整标签开头的正则在 2025 都匹配不到。
   所以判归属要同时接受「事务所（境内）」「公司聘请的会计师事务所（境内）」「（境内）」三种写法。
3. **同一家公司一年可能有两处披露同一件事**（正文表 + 审计报告页），
   写法还可能不一致（美的「姚文平、吴芳芳」与「姚文平，吴芳芳」顿号/逗号不同）。
   本脚本把同一归属的多处取值**先归一再比较**，不一致就报警而不是随便取一个。

审计年限链条（海尔自述，可自验证）
----------------------------------
海尔 2019—2025 年报各自披露「境内会计师事务所审计年限」7/8/9/10/11/12/13 年，
「境外」8 年起为 1/2/3/4/5/6 年。**逐年恰好 +1**——这条链本身就是一个校验：
若某年跳变，说明要么读错、要么那一年换了事务所而表述口径变了。

用法
----
    uv run python3 scripts/extract_audit.py --all
"""

from __future__ import annotations

import argparse
import csv
import itertools
import re
import sys
from pathlib import Path

from pdf_util import pdf_text, report_pdf

ROOT = Path(__file__).resolve().parent.parent
FIN = ROOT / "财务数据"

COMPANIES = (("美的集团", "美的"), ("海尔智家", "海尔"), ("格力电器", "格力"))
YEARS = [str(y) for y in range(2019, 2026)]

# 签字人标签：三家写法不同，且可能被拆行
SIGNER_LABELS = (
    "境内会计师事务所注册会计师姓名",
    "境外会计师事务所注册会计师姓名",
    "境内签字会计师姓名",
    "境外签字会计师姓名",
    "签字会计师姓名",
)
# 分块归属标记（海尔用「事务所（境内）/（境外）」给同名标签分组）
BLOCK_MARKERS = (
    (
        "境内",
        (
            "公司聘请的会计师事务所（境内）",
            "会计师事务所（境内）",
            "事务所（境内）",
            "（境内）",
            "境内",
        ),
    ),
    (
        "境外",
        (
            "公司聘请的会计师事务所（境外）",
            "会计师事务所（境外）",
            "事务所（境外）",
            "（境外）",
            "境外",
        ),
    ),
)
# 值到下一个标签或注释之间，最多回看几行找归属标记
LOOKBACK = 8

SPLIT = re.compile(r"\s{2,}")
NAME_SEP = re.compile(r"[、，,;/]")
NOISE = re.compile(r"注[：:]|^\s*$|适用|不适用")


def text_of(short: str, year: str) -> str:
    return pdf_text(report_pdf(ROOT, f"{short}{year}"))


def flatten(value: str) -> str:
    """去掉分隔符差异与空白，便于把「姚文平、吴芳芳」与「姚文平，吴芳芳」视作同一值。"""
    return NAME_SEP.sub("", re.sub(r"\s+", "", value))


def normalize(value: str) -> str:
    """统一用顿号分隔，输出保持年报原始人名顺序。"""
    parts = [p.strip() for p in NAME_SEP.split(value) if p.strip()]
    return "、".join(parts)


def names_in(value: str) -> list[str]:
    return [p.strip() for p in NAME_SEP.split(re.sub(r"\s+", "", value)) if p.strip()]


def signer_value(raw: str, label: str) -> str | None:
    """从「签字会计师姓名   张三、李四」这类行里取值，过滤掉表头噪声。"""
    tail = raw.split(label, 1)[1].strip()
    if not tail or NOISE.search(tail):
        return None
    # 值可能带办公地址等后续列，取第一段中文姓名串
    m = re.match(r"[\u4e00-\u9fa5][\u4e00-\u9fa5、，,;/\s]{1,40}", tail)
    if not m:
        return None
    value = m.group(0).strip()
    # 单个 2—4 字才算人名，避免把「有限公司」一类词吞进来
    for name in names_in(value):
        if not 2 <= len(name) <= 4:
            return None
    return normalize(value)


def block_side(lines: list[str], at: int) -> str | None:
    """回看若干行，判断这个「签字会计师姓名」属于境内还是境外块。

    只认**紧邻的**标记：同名标签在海尔年报里境内、境外各出现一次，
    靠最近的上方标记归属。找不到就返回 None（由调用方保守处理，不猜）。
    """
    for i in range(at - 1, max(-1, at - 1 - LOOKBACK), -1):
        row = re.sub(r"\s+", "", lines[i])
        if not row:
            continue
        for side, tokens in BLOCK_MARKERS:
            # 该行本身是另一个签字人行时，说明上一个块已结束
            if "签字会计师姓名" in row or "注册会计师姓名" in row:
                return None
            if any(row.endswith(t) or t in row for t in tokens[:4]):
                return side
    return None


def extract_signers(text: str) -> dict[str, set[str]]:
    """返回 {归属: {该归属下的取值,…}}。归属 = 境内 / 境外 / 未知。

    显式带「境内/境外」前缀的标签直接定归属；裸「签字会计师姓名」用分块回看。
    """
    lines = text.splitlines()
    out: dict[str, set[str]] = {"境内": set(), "境外": set(), "未知": set()}
    for i, raw in enumerate(lines):
        for label in SIGNER_LABELS:
            if label not in raw:
                continue
            value = signer_value(raw, label)
            if not value:
                continue
            if label.startswith("境内"):
                side = "境内"
            elif label.startswith("境外"):
                side = "境外"
            else:
                # 裸标签：标签自身可能带前缀（同行写着「（境内）…签字会计师姓名」）
                prefix = re.sub(r"\s+", "", raw.split(label)[0])
                side = (
                    "境内"
                    if "境内" in prefix
                    else ("境外" if "境外" in prefix else (block_side(lines, i) or "未知"))
                )
            out[side].add(value)
    return out


# ------------------------------------------------------------------ 其他字段


def first_value(text: str, *labels: str) -> str:
    for raw in text.splitlines():
        for label in labels:
            if label in raw:
                tail = raw.split(label, 1)[1].strip()
                if tail and not NOISE.search(tail):
                    return re.sub(r"\s+", " ", tail)[:60]
    return ""


def audit_years(text: str, side: str) -> int | None:
    label = f"{side}会计师事务所审计年限"
    for raw in text.splitlines():
        if label in raw:
            m = re.search(r"(\d+)\s*年?", raw.split(label, 1)[1])
            if m:
                return int(m.group(1))
    return None


OPINION_LABELS = ("审计意见类型", "内控审计报告意见类型")


def opinion(text: str) -> str:
    """审计意见类型。海尔的表述在正文里（「出具了标准无保留意见的审计报告」），
    不一定有「审计意见类型」这个表头，两种都要认。"""
    got = first_value(text, *OPINION_LABELS)
    if got:
        return got
    m = re.search(r"出具了(.{0,12}?意见)的?审计报告", re.sub(r"\s+", "", text))
    return m.group(1) if m else ""


# ------------------------------------------------------------------ 主流程


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    if not args.all:
        parser.print_help()
        return 0

    problems: list[str] = []
    rows: list[list[str]] = []
    tenure: dict[str, dict[str, int]] = {}

    for company, short in COMPANIES:
        for year in YEARS:
            text = text_of(short, year)
            if not text.strip():
                problems.append(f"{company} {year} 年报文本缺失")
                continue

            signers = extract_signers(text)
            for side in ("境内", "境外"):
                values = signers[side]
                if not values:
                    if side == "境内":
                        problems.append(f"{company} {year} 未解析到境内签字会计师")
                    continue
                # 同一归属出现多个不同取值 → 分块判错，必须报警而不是取其一
                if len(values) > 1:
                    problems.append(
                        f"{company} {year} 境内签字会计师有 {len(values)} 种取值"
                        f"（{sorted(values)}），分块归属可能判错"
                    )
                    continue
                for value in sorted(values):
                    rows.append(
                        [
                            company,
                            year,
                            "签字注册会计师",
                            f"{side}会计师事务所签字人",
                            value,
                            len(names_in(value)),
                            "披露值",
                            f"{short}{year}.pdf 第一节/审计报告",
                        ]
                    )
            # 「未知」桶多半是**第三处重复披露**（正文表 + 境内标签行 + 审计报告页），
            # 与已定归属同值就当作一致性确认吸收掉；只有对不上任何归属的才报警。
            # 早先这里一律报警，美的/格力每年误报一条，掩盖了真会出错的情形。
            assigned = {flatten(v) for side in ("境内", "境外") for v in signers[side]}
            leftover = {v for v in signers["未知"] if flatten(v) not in assigned}
            if leftover:
                problems.append(
                    f"{company} {year} 有 {len(leftover)} 个签字人标签"
                    f"判不出境内/境外且与已知值不符（{sorted(leftover)}）"
                )

            # 审计意见 + 年限
            rows.append(
                [
                    company,
                    year,
                    "审计意见",
                    "审计报告意见类型",
                    opinion(text),
                    "",
                    "披露值",
                    f"{short}{year}.pdf 第一节 重要提示/审计报告",
                ]
            )
            for side in ("境内", "境外"):
                n = audit_years(text, side)
                if n:
                    rows.append(
                        [
                            company,
                            year,
                            "审计连续性",
                            f"{side}会计师事务所审计年限",
                            str(n),
                            "",
                            "披露值",
                            f"{short}{year}.pdf 其他相关资料",
                        ]
                    )
                    tenure.setdefault(f"{company}|{side}", {})[year] = n

    # ---------------- 校验 1：审计年限链条（逐年恰好 +1）
    print("[链条] 自述审计年限逐年应 +1（跳变=读错或换了事务所）")
    for key, series in sorted(tenure.items()):
        years = sorted(series)
        for a, b in itertools.pairwise(years):
            if int(b) != int(a) + 1:
                continue
            delta = series[b] - series[a]
            mark = "OK" if delta == 1 else f"★跳 {delta:+d} 年"
            print(f"    {key} {a}→{b}: {series[a]}→{series[b]} {mark}")
            if delta != 1:
                problems.append(f"{key} 审计年限 {a}→{b} 变化 {delta} 年，不连续")

    # ---------------- 校验 2：签字人连续服务年限不得超过 5 年
    print("\n[轮换] 境内签字注册会计师连续服务年限（监管要求满 5 年轮换）")
    streak: dict[tuple[str, str], list[str]] = {}
    for company, _short in COMPANIES:
        for year in YEARS:
            hit = [
                r
                for r in rows
                if r[0] == company and r[1] == year and r[2] == "签字注册会计师" and "境内" in r[3]
            ]
            if not hit:
                continue
            for name in names_in(hit[0][4]):
                streak.setdefault((company, name), []).append(year)
    for (company, name), seen in sorted(streak.items()):
        # 连续 = 年份相邻，中间不能断
        runs, cur = [], [seen[0]]
        for a, b in itertools.pairwise(seen):
            if int(b) == int(a) + 1:
                cur.append(b)
            else:
                runs.append(cur)
                cur = [b]
        runs.append(cur)
        longest = max(runs, key=len)
        flag = "OK" if len(longest) <= 5 else "★超 5 年未轮换"
        if len(longest) > 5:
            problems.append(f"{company} {name} 连续签字 {len(longest)} 年，超过 5 年上限")
        gap = "（中途隔年复任）" if len(runs) > 1 else ""
        print(
            f"    {company} {name}：签字 {len(seen)} 年"
            f"（{seen[0]}—{seen[-1]}），最长连续 {len(longest)} 年"
            f"{gap} {flag}"
        )

    # ---------------- 校验 3：签字人轮换确实发生了（每家每年境内都应换人）
    print("\n[交叉] 意见类型与关键审计事项表应一致")
    gov_path = FIN / "治理与经营披露.csv"
    known: dict[tuple[str, str], str] = {}
    if gov_path.exists():
        with gov_path.open(encoding="utf-8-sig") as stream:
            for row in csv.DictReader(stream):
                period = row["报告期"].replace(" 年度", "")
                known[(row["公司"], period)] = row["审计意见"]
    for row in rows:
        if row[2] != "审计意见":
            continue
        theirs = known.get((row[0], row[1]))
        if theirs is None:
            continue
        ours = re.sub(r"\s+", "", row[4])
        base = re.sub(r"\s+", "", theirs)
        ok = base in ours or ours in base or ours == base
        print(
            f"    {row[0]} {row[1]}：本表 {ours or '—'} vs 治理与经营披露 {base}"
            f"  {'OK' if ok else '差异'}"
        )
        if not ok:
            problems.append(f"{row[0]} {row[1]} 审计意见与治理与经营披露.csv 不一致")

    out = FIN / "审计与签字会计师.csv"
    fields = ["公司", "年度", "类别", "项目", "值", "签字人数", "数据性质", "来源"]
    with out.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)

    print(f"\n{'公司':<8}{'年度':<6}{'境内签字人':<18}{'境外签字人':<12}{'年限':>6}")
    print("-" * 58)
    for company, _ in COMPANIES:
        for year in YEARS:
            dom = next(
                (
                    r[4]
                    for r in rows
                    if r[0] == company and r[1] == year and "境内会计师事务所签字人" in r[3]
                ),
                "—",
            )
            ovs = next(
                (
                    r[4]
                    for r in rows
                    if r[0] == company and r[1] == year and "境外会计师事务所签字人" in r[3]
                ),
                "—",
            )
            n = next(
                (
                    r[4]
                    for r in rows
                    if r[0] == company and r[1] == year and r[3] == "境内会计师事务所审计年限"
                ),
                "—",
            )
            print(f"{company:<8}{year:<6}{dom:<18}{ovs:<12}{n:>6}")

    tail = out.relative_to(ROOT)
    print(f"\n写入 {tail}: {len(rows)} 行")
    for problem in problems:
        print(f"注意：{problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
