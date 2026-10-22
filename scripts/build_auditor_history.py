"""从逐年原件核验的机构名称生成2006—2025沿革CSV与Markdown。

名称区间为人工复核结果，不用当前事务所反推历史。每年仍须在自己的
年报中找到完整机构名称及审计证据；签署页优先于公司资料表。只归一
空白和中英文括号；格力2013—2015资料表错用“有限公司”时按签署页。
变更原因来自归档公告；不推断审计意见购买、财务舞弊或监管动因。
所有年份指财报年度；原始PDF及索引不改写。运行本脚本不联网。
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from collect_audit_reports import compact, pages, sha
from collect_auditor_history import OUT, annual_candidates

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "财务数据/审计机构沿革_2006-2025.csv"
TARGET = ROOT / "审计研究/三家公司近20年审计事务所及变更沿革_2006-2025.md"
NAMES = {
    "华证中洲": "天健华证中洲（北京）会计师事务所有限公司",
    "光华": "天健光华（北京）会计师事务所有限公司",
    "正信": "天健正信会计师事务所有限公司",
    "天健": "天健会计师事务所（特殊普通合伙）",
    "普华": "普华永道中天会计师事务所（特殊普通合伙）",
    "汇德": "山东汇德会计师事务所有限公司",
    "山东和信": "山东和信会计师事务所（特殊普通合伙）",
    "和信": "和信会计师事务所（特殊普通合伙）",
    "中审": "中审会计师事务所有限公司",
    "亚太有限": "中审亚太会计师事务所有限公司",
    "亚太合伙": "中审亚太会计师事务所（特殊普通合伙）",
    "众环": "中审众环会计师事务所（特殊普通合伙）",
}
RANGES = {
    "美的": [
        (2006, 2007, "华证中洲"),
        (2008, 2008, "光华"),
        (2009, 2011, "正信"),
        (2012, 2014, "天健"),
        (2015, 2025, "普华"),
    ],
    "海尔": [(2006, 2012, "汇德"), (2013, 2018, "山东和信"), (2019, 2025, "和信")],
    "格力": [
        (2006, 2007, "中审"),
        (2008, 2012, "亚太有限"),
        (2013, 2014, "亚太合伙"),
        (2015, 2025, "众环"),
    ],
}
NOTES = {
    ("美的", 2006): "合并更名；前任华证见当年公告",
    ("美的", 2008): "更名：华证中洲→光华",
    ("美的", 2009): "合并改聘；2010年初决议服务2009年度",
    ("美的", 2012): "分所及原团队转入天健；2013年初决议",
    ("美的", 2013): "上市主体切换：000527→000333；机构仍为天健",
    ("美的", 2015): "主动改聘：天健→普华永道中天",
    ("海尔", 2013): "原团队参与转制；汇德→山东和信",
    ("海尔", 2019): "事务所更名：山东和信→和信",
    ("格力", 2008): "合并更名；2009年公告服务2008年度",
    ("格力", 2013): "特殊普通合伙转制；2014年公告",
    ("格力", 2015): "原审计业务机构转入中审众环，改聘承接",
}


def normalize(text):
    return compact(text).replace("(", "（").replace(")", "）")


def rows():
    result = []
    for item in sorted(annual_candidates(), key=lambda x: (x["name"], x["year"])):
        issuer, year = item["name"], item["year"]
        company = "美的" if issuer.startswith("美的") else issuer
        short = next(n for start, end, n in RANGES[company] if start <= year <= end)
        firm = NAMES[short]
        path = OUT / "年报" / f"{issuer}_{year}_{item['announcementId']}.pdf"
        texts = pages(path)
        candidates = []
        for number, text in enumerate(texts, 1):
            if normalize(firm) not in normalize(text):
                continue
            score = 0
            if "中国注册会计师" in text and (
                "审计意见" in compact(text) or "中国·" in compact(text)
            ):
                score = 5
            elif "中国注册会计师" in text:
                score = 4
            elif "会计师事务所名称" in compact(text):
                score = 3
            elif "聘任、解聘" in text:
                score = 2
            elif "审计" in text:
                score = 1
            candidates.append((score, number, text))
        if not candidates:
            raise ValueError(f"未在当年原件找到全名：{issuer} {year} {firm}")
        _, number, text = max(candidates, key=lambda x: (x[0], -x[1]))
        metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        result.append(
            {
                "公司": company,
                "财报年度": str(year),
                "上市主体": issuer,
                "市场": "A股财报",
                "事务所简称": short,
                "事务所法定名称": firm,
                "变动说明": NOTES.get((company, year), "与上年相同" if year > 2006 else "区间起点"),
                "来源等级": "A",
                "数据性质": "披露值；变动分类为分析判断",
                "原始文件": path.relative_to(ROOT).as_posix(),
                "PDF页序": str(number),
                "官方URL": metadata["url"],
                "SHA256": metadata["sha256"],
                "证据摘录": compact(text),
            }
        )
    return sorted(result, key=lambda r: (r["公司"], r["财报年度"]))


def link(row):
    return f"[年报PDF {row['PDF页序']}](<../{row['原始文件']}#page={row['PDF页序']}>)"


def section(name):
    """正文模板链接以最终报告为基准，补上统一的中间材料目录。"""
    text = (OUT / name).read_text(encoding="utf-8").rstrip()
    return text.replace(
        "](<审计机构沿革_2006-2025/", "](<中间材料/审计机构沿革_2006-2025/"
    ).replace("](<审计报告/", "](<中间材料/审计报告/")


def table(headers, records):
    return ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"] + [
        "| " + " | ".join(str(v).replace("|", "\\|").replace("\n", " ") for v in row) + " |"
        for row in records
    ]


def main():
    data = rows()
    assert len(data) == 60
    with CSV.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(data[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(data)
    lines = [
        "# 三家公司近20年审计事务所及变更沿革（2006—2025）",
        "",
        "核验截止：2026-10-22。研究对象为年度合并及母公司财务报表审计机构；以最近20个完整财年2006—2025为主表，2026聘任情况另注。",
        "",
        "**主要发现：美的2015年度由天健主动改聘普华永道中天；海尔2013年度由山东汇德转至原团队参与组建的山东和信；格力2015年度由中审亚太改聘承接原审计业务机构的中审众环。其他名称变化多涉及合并、更名或组织形式转制，须逐项判断。**",
        "",
        "美的2006—2012列原上市公司广东美的电器（000527），2013—2025列美的集团（000333）；两者不是同一法人连续20年的审计记录。海尔600690由青岛海尔更名为海尔智家，不能与另一上市主体海尔电器的审计历史混同。",
        "",
        "## 一、变更事件与原因",
        "",
        section("变更事件正文.md"),
        "",
        "## 二、逐年审计机构总表",
        "",
        "名称简称对应下方完整法定名称。**粗体**标记上表涉及的名称变化或主体切换年份（包括美的2006区间起点）。每格均链接本年度原件，未用相邻年度或连续服务年限填补。",
        "",
    ]
    matrix = []
    for year in range(2006, 2026):
        cells = []
        for company in ("美的", "海尔", "格力"):
            row = next(r for r in data if r["公司"] == company and r["财报年度"] == str(year))
            short = row["事务所简称"]
            if (company, year) in NOTES:
                short = f"**{short}**"
            cells.append(f"{short}；{link(row)}")
        matrix.append([year, *cells])
    lines += table(["财报年度", "美的（2013起主体切换）", "海尔", "格力"], matrix)
    lines += ["", "### 简称与完整名称", "", *table(["简称", "法定名称"], NAMES.items())]
    lines += [
        "",
        "## 三、境外机构及2026年聘任补充",
        "",
        section("境外与限制正文.md"),
        "",
        "## 四、逐年证据索引",
        "",
        "以下均为巨潮法定披露的A 级原件；页码为PDF文件页序，不是印刷页码。具体名称为披露值，变动分类为对原公告事实的分析判断。完整摘录、原件哈希和变动说明见[可复核CSV](../财务数据/审计机构沿革_2006-2025.csv)。",
        "",
    ]
    lines += table(
        ["公司／财报年度", "实际出具财报审计报告的机构", "变动说明", "原件与官方链接"],
        [
            [
                r["上市主体"] + "／" + r["财报年度"],
                r["事务所法定名称"],
                r["变动说明"],
                link(r) + f"；[官方]({r['官方URL']})",
            ]
            for r in data
        ],
    )
    lines += [
        "",
        "复现：`python -X utf8 scripts/build_auditor_history.py`；采集：`python -X utf8 scripts/collect_auditor_history.py --search --download --scan --supplements`。",
        "",
    ]
    TARGET.write_text("\n".join(lines), encoding="utf-8")
    print(TARGET.relative_to(ROOT), "60年度记录")


def validate():
    errors = []
    with CSV.open(encoding="utf-8-sig", newline="") as stream:
        data = list(csv.DictReader(stream))
    expected = {(c, str(y)) for c in RANGES for y in range(2006, 2026)}
    if len(data) != 60 or {(r["公司"], r["财报年度"]) for r in data} != expected:
        errors.append("公司×年度未完整覆盖或重复")
    for row in data:
        path = ROOT / row["原始文件"]
        if not path.exists() or sha(path) != row["SHA256"]:
            errors.append(f"原件缺失或哈希变化：{path}")
            continue
        text = pages(path)[int(row["PDF页序"]) - 1]
        if normalize(row["事务所法定名称"]) not in normalize(text):
            errors.append(f"页段不支持全名：{path}")
        if row["财报年度"] not in compact("".join(pages(path)[:3])):
            errors.append(f"封面不支持年度：{path}")
    text = TARGET.read_text(encoding="utf-8")
    for dest in re.findall(r"\]\((<[^>]+>|[^)]+)\)", text):
        dest = dest.strip("<>").split("#", 1)[0]
        if dest.startswith(("http://", "https://")):
            continue
        path = (TARGET.parent / dest).resolve()
        if not path.is_file():
            errors.append(f"坏链接：{dest}")
        elif path.parent == OUT / "变更公告":
            meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
            if sha(path) != meta["sha256"]:
                errors.append(f"变更公告哈希变化：{path}")
    for company, year, expected_firm in [
        ("格力", "2008", "亚太有限"),
        ("格力", "2013", "亚太合伙"),
        ("格力", "2015", "众环"),
        ("美的", "2009", "正信"),
        ("美的", "2012", "天健"),
        ("美的", "2015", "普华"),
    ]:
        if not any(
            r["公司"] == company and r["财报年度"] == year and r["事务所简称"] == expected_firm
            for r in data
        ):
            errors.append(f"换所边界错误：{company}{year}")
    return errors


if __name__ == "__main__":
    main()
