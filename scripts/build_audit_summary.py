"""从已核验的审计报告清单生成按公司汇总的 Markdown 表格。

只读取现有清单和事务所评价正文，不联网、不改 PDF 或 CSV。年度财报按市场和期间列示，
独立 PDF 与年报内嵌版本合并展示；海尔 D 股译本仍单列并说明复用。
中期审阅与内控审计另表列示，不推断未披露的签字人。
运行：python -X utf8 scripts/build_audit_summary.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "审计研究/三家公司审计机构_签字会计师与审计意见汇总_2023-2026H1.md"
COMPANIES = ("美的集团股份有限公司", "海尔智家股份有限公司", "珠海格力电器股份有限公司")
FIRM_REVIEW = ROOT / "审计研究/中间材料/审计报告/事务所评价来源/事务所水平评价正文.md"


def firm_review():
    """将评价正文的同目录证据链接转换为汇总文件相对链接。"""
    text = FIRM_REVIEW.read_text(encoding="utf-8")
    return re.sub(
        r"\]\(<([^>]+)>\)",
        lambda match: f"](<中间材料/审计报告/事务所评价来源/{match[1]}>)",
        text,
    )


def validate_summary():
    """离线检查链接、评价正文同步、证据哈希和下载来源，避免静默丢失评价。"""
    from collect_audit_firm_sources import OUT, URLS

    errors = []
    if not TARGET.is_file():
        return [f"汇总文件不存在：{TARGET}"]
    text = TARGET.read_text(encoding="utf-8")
    if not text.endswith(firm_review().rstrip() + "\n"):
        errors.append("汇总中的事务所评价与来源正文不同步")
    for target in re.findall(r"\]\((<[^>]+>|[^)]+)\)", text):
        link = target.strip("<>")
        if link.startswith(("https://", "http://", "#")):
            continue
        path = (TARGET.parent / link.split("#", 1)[0]).resolve()
        if not path.is_file():
            errors.append(f"本地引用不存在：{link}")
            continue
        if path.parent != OUT:
            continue
        metadata = path.with_suffix(path.suffix + ".json")
        if not metadata.is_file():
            errors.append(f"缺少来源记录：{path.name}")
            continue
        data = json.loads(metadata.read_text(encoding="utf-8"))
        if hashlib.sha256(path.read_bytes()).hexdigest() != data.get("sha256"):
            errors.append(f"证据哈希不一致：{path.name}")
        if data.get("url") != URLS.get(path.name):
            errors.append(f"证据下载来源不一致：{path.name}")
    return errors


def load(name):
    with (ROOT / "财务数据" / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def cell(text):
    return text.replace("|", "\\|").replace("\n", " ")


def citation(row):
    path = "../" + row["本地路径"]
    first, last = row["报告起始PDF页"], row["报告终止PDF页"]
    return f"[原件](<{path}#page={first}>)，PDF {first}—{last}；[官方链接]({row['PDF下载URL']})"


def table(headers, rows):
    return ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"] + [
        "| " + " | ".join(cell(str(value)) for value in row) + " |" for row in rows
    ]


def main():
    files = load("审计报告文件清单.csv")
    mappings = load("审计报告对应清单.csv")
    annual = [
        r for r in files if r["报告类型"] == "财报审计" and r["文件属性"] == "年报或中期报告内嵌"
    ]
    controls = [r for r in files if r["报告类型"] == "内控审计"]
    reviews = {r["文件ID"]: r for r in files if r["报告类型"] == "中期审阅"}
    official = {
        r["报告ID"]: r
        for r in files
        if r["报告类型"] == "财报审计" and r["文件属性"] == "官方独立披露"
    }
    assert len(annual) == 17 and len(controls) == 9 and len(reviews) == 2
    for row in files:
        if not (ROOT / row["本地路径"]).is_file():
            raise FileNotFoundError(row["本地路径"])
    lines = [
        "# 三家公司审计机构、签字会计师与审计意见汇总（2023—2026H1）",
        "",
        "整理依据：已归档的官方独立审计报告、A/H/D 股年报及中期报告，复核日期为 2026-10-22。",
        "本表将‘审计员’按报告实际披露记为签字注册会计师、项目合伙人或项目董事，‘审计公司’记为会计师事务所法定名称。",
        "期间指财报所属期间；出具日期指报告签署日，两者不可混同。所有页码均为所链接 PDF 的文件页序。",
        "",
        "**年度财报结论：本轮 17 个市场/年度版本的正式审计意见均为无保留意见。**",
        "其中海尔 3 份 D 股报告为 A 股和信报告的英文版本，不另计为新的审计业务。两份 H 股中期报告为审阅报告，结论另列。",
        "",
    ]
    for company in COMPANIES:
        lines += [f"## {company}", "", "### 年度财务报表审计", ""]
        rows = []
        for row in sorted(
            (r for r in annual if r["公司"] == company), key=lambda r: (r["市场"], r["报告期"])
        ):
            source = official.get(row["报告ID"], row) if row["市场"] == "A" else row
            rows.append(
                [
                    row["报告期"][:4],
                    row["市场"] + "股",
                    row["事务所法定名称"],
                    row["签字人或项目合伙人"],
                    row["出具日期"],
                    row["意见或结论分类"],
                    citation(source),
                ]
            )
        lines += table(
            [
                "财报年度",
                "市场",
                "审计机构",
                "签字会计师／项目负责人",
                "出具日期",
                "审计意见",
                "原文依据",
            ],
            rows,
        )
        if company == COMPANIES[0]:
            lines += [
                "",
                "2023—2024 年 A 股项目合伙人为姚文平，2025 年改为周伟然，另一签字人为吴芳芳。",
                "H 股年度报告披露相应项目合伙人；普华永道中天与羅兵咸永道按不同法律实体记录。2023 年美的尚未在 H 股上市。",
            ]
        elif company == COMPANIES[1]:
            lines += [
                "",
                "A 股项目合伙人依次为赵波、左伟、张军，另一签字人均为李祥智。D 股英文报告保留原文拼写，",
                "其与 A 股的对应依据包括报告编号、日期、主体及签署信息，并非只凭姓名拼写判断。H 股由國衛出具另一套国际准则报告。",
            ]
        else:
            lines += [
                "",
                "2023—2025 年审计机构均为中审众环；签字组合由吴梓豪／邱以武，变为邱以武／王慧军，再变为邱以武／邬夏霏。格力没有 H 股或 D 股报告。",
            ]
        lines += ["", "### 2026 年半年度：审计／审阅情况", ""]
        interim_rows = []
        for row in sorted(
            (
                r
                for r in mappings
                if r["公司"] == company
                and r["报告期末"] == "2026-06-30"
                and r["关联类型"] == "主鉴证"
            ),
            key=lambda r: r["市场"],
        ):
            report = reviews.get(row["文件ID"])
            if report:
                interim_rows.append(
                    [
                        row["市场"] + "股",
                        "外部审阅（非审计）",
                        report["事务所法定名称"],
                        report["签字人或项目合伙人"],
                        report["出具日期"],
                        "未发现未按 IAS 34 编制的事项；不发表审计意见",
                        citation(report),
                    ]
                )
            else:
                first = row["财报内报告PDF页序"].split(";")[0]
                interim_rows.append(
                    [
                        row["市场"] + "股",
                        "明确未经审计；未见外部审阅报告",
                        "不适用／未取得本期外部报告",
                        "不适用／未披露",
                        "不适用",
                        "无本期审计意见可列；不能据此断言未经审阅",
                        f"[财报原件](<../{row['财报原件路径']}#page={first}>)，PDF {row['财报内报告PDF页序']}；[官方链接]({row['官方来源']})",
                    ]
                )
        lines += table(
            ["市场", "鉴证情况", "出具机构", "披露的签字人", "出具日期", "结论／限制", "原文依据"],
            interim_rows,
        )
        lines += [
            "",
            "### 补充：内部控制审计",
            "",
            "以下意见针对财务报告内部控制的有效性，不能替代财务报表审计意见。",
            "",
        ]
        rows = []
        for row in sorted((r for r in controls if r["公司"] == company), key=lambda r: r["报告期"]):
            # IC reports do not necessarily label an engagement partner: retain names only.
            signers = re.sub(r"（[^）]+）", "", row["签字人或项目合伙人"])
            rows.append(
                [
                    row["报告期"][:4],
                    row["事务所法定名称"],
                    signers,
                    row["出具日期"],
                    "无保留意见：在所有重大方面保持有效的财务报告内部控制",
                    citation(row),
                ]
            )
        lines += table(
            ["年度", "审计机构", "签字注册会计师", "出具日期", "内控审计意见摘要", "原文依据"], rows
        )
        if company == COMPANIES[0]:
            lines += [
                "",
                "范围提示：美的 2023、2025 年内控审计报告对部分当年新并购子公司的范围作出说明，阅读内控意见时需结合正文，不应表述为所有业务均无例外。",
            ]
        lines += [""]
    lines += [
        "## 审计意见与审阅结论应如何理解",
        "",
        "无保留意见表示审计师认为所审计财务报表在所有重大方面按相应编制准则公允列报，不等于企业没有风险，也不是对年报全部经营叙述逐项提供保证。",
        "A/D 股报告覆盖合并及母公司财务报表；H 股报告覆盖合并财务报表。美的 H 股年度审计按 ISA，海尔 H 股年度审计按 HKSA；两者采用的财报编制框架为 IFRS。",
        "",
        "两份中期审阅报告的结论原文如下；审阅范围小于审计，报告明确不发表审计意见。",
        "",
    ]
    lines += table(
        ["公司与期间", "审阅结论原文", "依据"],
        [[r["公司"] + "／2026H1 H股", r["意见或结论原文"], citation(r)] for r in reviews.values()],
    )
    lines += [
        "",
        "## 核验说明与保留事项",
        "",
        "- A 股年度财报和内控独立 PDF 均已归档；H/D 股报告已在年报或中期报告原件中取得完整正文，不将研究摘页称为官方独立文件。",
        "- 审计意见按正式意见段分类；关键审计事项、其他信息段及审计责任段不自动构成非无保留意见。",
        "- 海尔 H 股 2024、2025 年中文报告的存货关键审计事项末句存在需与英文版复核的表述，见收集说明；本表按正式意见段记为无保留意见，不据该句自行改判。",
        "- 本表从已核验清单生成，先核对原件存在性；同一报告独立版本与内嵌版本只展示一次。",
        "- [审计报告收集说明](审计报告收集说明_2023-2026H1.md)、[完整文件清单](../财务数据/审计报告文件清单.csv)、[财报对应清单](../财务数据/审计报告对应清单.csv)。",
        "",
        "复现：`python -X utf8 scripts/build_audit_summary.py`。",
        "",
    ]
    lines += [firm_review().rstrip(), ""]
    TARGET.write_text("\n".join(lines), encoding="utf-8")
    print(TARGET.relative_to(ROOT).as_posix())
    print("年度财报行 17；半年度行 6；内控审计行 9；审阅结论原文 2。")


if __name__ == "__main__":
    main()
