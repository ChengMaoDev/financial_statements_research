"""逐项核对本地十二份 PDF 的合并报表，生成带 PDF 页码的证据表。

只在合并报表区块按行标签、单位、本期/上期列提取，不在全文搜索相似金额。
旧版披露与数据库不同，只有数据库匹配另一份本地报告的后续比较数才记版本差异。
金额误差最多允许 PDF 最后一位的舍入；缺文件、缺项目、无法解释的差异返回非零。
用法：uv run python scripts/verify_against_pdf.py [--write]
"""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from pdf_util import pdf_text as pdf_text

ROOT = Path(__file__).resolve().parent.parent
FIN = ROOT / "财务数据"
OUT = FIN / "原文交叉核验.csv"
COMPANIES = {"美的": "美的集团", "海尔": "海尔智家", "格力": "格力电器"}
METRICS = {
    "资产负债表": {
        "货币资金": ("货币资金",),
        "应收账款": ("应收账款",),
        "存货": ("存货",),
        "流动资产合计": ("流动资产合计",),
        "资产总计": ("资产总计",),
        "短期借款": ("短期借款",),
        "应付账款": ("应付账款",),
        "流动负债合计": ("流动负债合计",),
        "负债合计": ("负债合计",),
        "归属于母公司股东权益合计": (
            "归属于母公司股东权益合计",
            "归属于母公司所有者权益合计",
            "归属于母公司所有者权益（或股东权益）合计",
            "归属于母公司所有者权益（或股东权益）",
            "归属于母公司所有者权益（或股东权益）合",
            "归属于母公司所有者权益",
        ),
        "少数股东权益": ("少数股东权益",),
        "所有者权益(或股东权益)合计": (
            "股东权益合计",
            "所有者权益合计",
            "所有者权益（或股东权益）合计",
            "所有者权益（或股东权益）",
            "所有者权益（或股东权",
        ),
    },
    "利润表": {
        "营业总收入": ("营业总收入",),
        "营业收入": ("营业收入",),
        "营业成本": ("营业成本",),
        "销售费用": ("销售费用",),
        "管理费用": ("管理费用",),
        "研发费用": ("研发费用",),
        "财务费用": ("财务费用", "财务收入"),
        "营业利润": ("营业利润",),
        "利润总额": ("利润总额",),
        "所得税费用": ("所得税费用",),
        "净利润": ("净利润",),
        "归属于母公司所有者的净利润": ("归属于母公司股东的净利润",),
    },
    "现金流量表": {
        "销售商品、提供劳务收到的现金": ("销售商品、提供劳务收到的现金",),
        "经营活动产生的现金流量净额": ("经营活动产生的现金流量净额", "经营活动产生的现金流量净"),
        "投资活动产生的现金流量净额": ("投资活动产生的现金流量净额", "投资活动产生的现金流量净"),
        "筹资活动产生的现金流量净额": ("筹资活动产生的现金流量净额", "筹资活动产生的现金流量净"),
        "现金及现金等价物净增加额": ("现金及现金等价物净增加额",),
    },
}
NUMBER = re.compile(r"\(?-?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?|(?<!\d)-?\d{5,}(?:\.\d+)?")
PREFIX = re.compile(r"^(?:[一二三四五六七八九十]+[、.]|\d+[.、]|其中[：:]|减[：:]|加[：:])+")


@dataclass(frozen=True)
class Evidence:
    company: str
    period: str
    statement: str
    metric: str
    value: float
    unit: int
    path: Path
    page: int
    vintage: str
    column: str


def compact(text: str) -> str:
    result = re.sub(r"\s+", "", text)
    for before, after in (
        ("/(使用)", ""),
        ("/(减少)", ""),
        ("(使用)/产生", "产生"),
        ("使用的现金流量", "产生的现金流量"),
        ("净(减少)/增加额", "净增加额"),
        ("所得税(费用)/贷项", "所得税费用"),
        ("财务(费用)/收入", "财务收入"),
    ):
        result = result.replace(before, after)
    return result


@cache
def report_lines(path: Path) -> list[tuple[int, str]]:
    return [
        (i, line)
        for i, page in enumerate(pdf_text(path).split("\f"), 1)
        for line in page.splitlines()
    ]


def extract(path: Path, statement: str) -> list[Evidence]:
    short = path.stem[:2]
    year = path.stem[2:6]
    interim = "半年度" in path.stem
    period = f"{year}{'0630' if interim else '1231'}"
    prior = f"{int(year) - 1}{'1231' if statement == '资产负债表' else period[4:]}"
    lines = report_lines(path)
    heading = re.compile(
        rf"^(?:\d+[.、]|\d{{4}}(?:年半年度|年度))?合并(?:及公司)?{statement}(?:[（(]续[）)])?$"
    )
    start = next((i for i, (_, line) in enumerate(lines) if heading.match(compact(line))), None)
    if start is None:
        raise ValueError(f"{path.name} 找不到合并{statement}")
    end = next(
        (
            i
            for i in range(start + 1, len(lines))
            if re.match(
                r"^(?:\d+[.、]|\d{4}(?:年半年度|年度))?(?:母公司|公司|合并(?:及公司)?)(?:资产负债表|利润表|现金流量表|股东权益变动表|所有者权益变动表)",
                compact(lines[i][1]),
            )
            and not heading.match(compact(lines[i][1]))
        ),
        len(lines),
    )
    unit_text = compact("".join(line for _, line in lines[start : start + 8]))
    unit = 1000 if "千元" in unit_text else 10000 if "万元" in unit_text else 1
    if "元" not in unit_text:
        raise ValueError(f"{path.name} 合并{statement}单位不可识别")
    found: dict[str, list[Evidence]] = {}
    for i in range(start + 1, end):
        page, line = lines[i]
        matches = list(NUMBER.finditer(line))
        body = line
        if not matches and i + 1 < end:
            body += lines[i + 1][1]
            matches = list(NUMBER.finditer(body))
        if not matches:
            continue
        label = PREFIX.sub("", compact(body[: matches[0].start()]))
        label = re.sub(r"(?:四|五|七|十八)[、(（][^\s]*$", "", label)
        label = re.sub(r"[（(](?:净)?(?:亏损|损失|收益).*", "", label)
        for metric, aliases in METRICS[statement].items():
            if metric in found or not any(
                label == alias or label.startswith(alias + "（") or label.startswith(alias + "(")
                for alias in aliases
            ):
                continue
            # 跨行的归母净利润标签可能先出现，下一行才有「净利润」与金额。
            sign = (
                -1
                if short == "美的"
                and statement == "利润表"
                and metric
                in {
                    "营业成本",
                    "销售费用",
                    "管理费用",
                    "研发费用",
                    "财务费用",
                    "所得税费用",
                }
                else 1
            )
            values: list[Evidence] = []
            for column, token in enumerate(matches[:2]):
                raw = token.group()
                value = float(raw.strip("()").replace(",", "")) * (-1 if raw.startswith("(") else 1)
                values.append(
                    Evidence(
                        COMPANIES[short],
                        period if column == 0 else prior,
                        statement,
                        metric,
                        value * unit * sign,
                        unit,
                        path,
                        page,
                        period,
                        "本期" if column == 0 else "比较期",
                    )
                )
            found[metric] = values
    missing = METRICS[statement].keys() - found.keys()
    if missing:
        raise ValueError(f"{path.name} 合并{statement}缺项目：{', '.join(sorted(missing))}")
    return [entry for entries in found.values() for entry in entries]


def audit(root: Path) -> tuple[list[list[str]], int]:
    books: dict[tuple[str, str, str, str], float] = {}
    for statement in METRICS:
        with (root / "财务数据" / f"{statement}.csv").open(encoding="utf-8-sig") as stream:
            for row in csv.DictReader(stream):
                if row["科目"] in METRICS[statement]:
                    books[(row["公司"], row["报告期"], statement, row["科目"])] = float(row["数值"])
    evidence = [
        entry
        for path in sorted((root / "年度报告").glob("*.pdf"))
        for statement in METRICS
        for entry in extract(path, statement)
    ]
    if len({entry.path for entry in evidence}) != 12:
        raise ValueError("必须核对十二份本地报告，不得缺失")
    rows: list[list[str]] = []
    failures = 0
    for entry in evidence:
        key = (entry.company, entry.period, entry.statement, entry.metric)
        book = books.get(key)
        versions = [
            other
            for other in evidence
            if (other.company, other.period, other.statement, other.metric) == key
        ]
        latest = max(versions, key=lambda item: item.vintage)
        ok = book is not None and abs(book - entry.value) <= entry.unit / 2 + 0.02
        version = (
            book is not None
            and entry.vintage < latest.vintage
            and abs(book - latest.value) <= latest.unit / 2 + 0.02
        )
        status = "一致" if ok else "后续披露版本差异" if version else "待复核"
        failures += status == "待复核"
        rows.append(
            [
                entry.company,
                entry.period,
                entry.statement,
                entry.metric,
                f"{entry.value:.2f}",
                "" if book is None else f"{book:.2f}",
                status,
                "A",
                entry.path.relative_to(root).as_posix(),
                str(entry.page),
                str(entry.unit),
                entry.column,
                entry.vintage,
                "披露值",
                latest.path.relative_to(root).as_posix() if version else "",
            ]
        )
    return rows, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="生成证据 CSV；默认只核验")
    args = parser.parse_args()
    try:
        rows, failures = audit(ROOT)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"PDF 核验失败：{exc}")
        return 1
    for row in rows:
        if row[6] == "待复核":
            print(" | ".join(row[:10]))
    if args.write:
        with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(
                [
                    "公司",
                    "报告期",
                    "报表",
                    "科目",
                    "PDF金额(元)",
                    "数据库金额(元)",
                    "结果",
                    "来源等级",
                    "原始文件",
                    "PDF页码",
                    "单位倍数",
                    "列别",
                    "披露版本",
                    "数据性质",
                    "后续核对文件",
                ]
            )
            writer.writerows(rows)
    versions = sum(row[6] == "后续披露版本差异" for row in rows)
    print(
        f"PDF 核验 {len(rows)} 项：一致 {len(rows) - versions - failures}，后续披露版本差异 {versions}，待复核 {failures}"
    )
    return int(failures > 0)


if __name__ == "__main__":
    raise SystemExit(main())
