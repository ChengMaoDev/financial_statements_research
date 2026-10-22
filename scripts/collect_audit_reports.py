"""Collect official audit disclosures and reproduce the audit-report catalogs.

Scope: the 23 locally archived A/H/D financial reports for 2023-2026H1.
Raw PDFs are immutable. CNINFO search responses and download metadata are retained;
review decisions live in audit_report_review.json, separately from generated CSVs.
Commands: --search (official index), --download (reviewable candidates), --build
(reviewed catalogs/extracts), --verify. No network requests during build/verify.
Missing review reports do not imply that no review took place. D translations share
an engagement ID with A reports but retain their own file/version records.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "审计研究" / "中间材料" / "审计报告"
EVIDENCE = OUT / "检索记录"
REVIEW = OUT / "audit_report_review.json"
CACHE = Path(tempfile.gettempdir()) / "opencode" / "audit-collection"
COMPANIES = {"美的": "000333", "海尔": "600690", "格力": "000651"}


def stamp():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pages(path):
    # Cache is keyed by bytes, not filename: changed originals cannot reuse old text.
    CACHE.mkdir(parents=True, exist_ok=True)
    cache = CACHE / (sha(path) + ".json")
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    result = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        capture_output=True,
        encoding="utf-8",
        check=True,
    ).stdout.split("\f")
    if result and not result[-1].strip():
        result.pop()
    save(cache, result)
    return result


def compact(text):
    return re.sub(r"\s+", "", text)


def search_official():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://www.cninfo.com.cn/"})
    for company, code in COMPANIES.items():
        identity = session.post(
            "https://www.cninfo.com.cn/new/information/topSearch/query",
            data={"keyWord": code, "maxNum": 10},
            timeout=30,
        )
        identity.raise_for_status()
        issuer = next(x for x in identity.json() if x["code"] == code)
        for keyword in ("审计报告", "审阅报告"):
            number = 1
            while True:
                target = EVIDENCE / f"{company}_{keyword}_{number}.json"
                if target.exists():
                    data = json.loads(target.read_text(encoding="utf-8"))
                    response = data["response"]
                else:
                    query = {
                        "pageNum": number,
                        "pageSize": 30,
                        "tabName": "fulltext",
                        "column": "sse" if code.startswith("6") else "szse",
                        "stock": code + "," + issuer["orgId"],
                        "searchkey": keyword,
                        "secDate": "2024-01-01~2026-10-22",
                        "isHLtitle": "false",
                    }
                    res = session.post(
                        "https://www.cninfo.com.cn/new/hisAnnouncement/query",
                        data=query,
                        timeout=40,
                    )
                    res.raise_for_status()
                    response = res.json()
                    save(
                        target,
                        {
                            "url": res.url,
                            "method": "POST",
                            "parameters": query,
                            "retrieved_at": stamp(),
                            "response": response,
                        },
                    )
                items = response.get("announcements") or []
                print(company, keyword, number, "total", response.get("totalAnnouncement"))
                for item in items:
                    title = re.sub("<[^>]+>", "", item["announcementTitle"])
                    print(title, item["adjunctUrl"])
                if number * 30 >= response.get("totalAnnouncement", 0):
                    break
                number += 1


def download_candidates():
    for path in sorted(EVIDENCE.glob("*_审计报告_*.json")):
        company = path.name.split("_")[0]
        value = json.loads(path.read_text(encoding="utf-8"))
        for item in value["response"].get("announcements") or []:
            title = re.sub("<[^>]+>", "", item["announcementTitle"])
            disclosed = datetime.fromtimestamp(item["announcementTime"] / 1000).date().isoformat()
            # CNINFO can ignore secDate when searchkey is present: filter each hit.
            if not "2024-01-01" <= disclosed <= "2026-10-22":
                continue
            year = re.search(r"202[345]", title)
            kind = "内控审计" if "内部控制" in title or "内控" in title else "财报审计"
            if not year and kind == "内控审计":
                period = str(int(disclosed[:4]) - 1)
            elif year:
                period = year[0]
            else:
                continue
            if period not in ("2023", "2024", "2025") or "审计报告" not in title:
                continue
            if any(x in title for x in ("专项", "募集", "差异", "责任")):
                continue
            identifier = str(item["announcementId"])
            name = f"{company}_A股_{period}_{kind}_zh-CN_{identifier}.pdf"
            target = OUT / "A股" / name
            meta = target.with_suffix(".http.json")
            if target.exists():
                record = json.loads(meta.read_text(encoding="utf-8"))
                if sha(target) != record["sha256"]:
                    raise ValueError(f"Changed archived file: {target}")
                print("REUSE", name)
                continue
            url = "https://static.cninfo.com.cn/" + item["adjunctUrl"]
            try:
                res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=50)
                res.raise_for_status()
                if not res.content.startswith(b"%PDF-"):
                    raise ValueError("Response is not a PDF")
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(res.content)
                record = {
                    "url": url,
                    "final_url": res.url,
                    "retrieved_at": stamp(),
                    "title": title,
                    "announcement_id": identifier,
                    "disclosed_at": datetime.fromtimestamp(item["announcementTime"] / 1000)
                    .date()
                    .isoformat(),
                    "sha256": sha(target),
                    "bytes": target.stat().st_size,
                    "pages": len(pages(target)),
                    "index_path": path.relative_to(ROOT).as_posix(),
                }
                save(meta, record)
                print("DOWNLOADED", name, record["pages"])
            except (requests.RequestException, ValueError) as error:
                save(
                    EVIDENCE / f"download_failure_{identifier}.json",
                    {"url": url, "at": stamp(), "error": str(error)},
                )
                print("FAILED", name, str(error))


def search_hk():
    for company, stock in (("美的", "1000231771"), ("海尔", "1000066160")):
        for keyword in ("核數師報告", "審閱報告", "審計報告"):
            target = EVIDENCE / f"HK_{company}_{keyword}.json"
            if target.exists():
                continue
            params = {
                "sortDir": "0",
                "sortByOptions": "DateTime",
                "category": "0",
                "market": "SEHK",
                "stockId": stock,
                "documentType": "-1",
                "fromDate": "20240101",
                "toDate": "20261022",
                "title": keyword,
                "searchType": "0",
                "t1code": "-2",
                "t2Gcode": "-2",
                "t2code": "-2",
                "rowRange": "100",
                "lang": "zh",
            }
            url = "https://www1.hkexnews.hk/search/titleSearchServlet.do"
            try:
                res = requests.get(
                    url,
                    params=params,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Referer": "https://www1.hkexnews.hk/search/titlesearch.xhtml",
                    },
                    timeout=30,
                )
                res.raise_for_status()
                payload = res.json()
                save(
                    target,
                    {"url": res.url, "parameters": params, "at": stamp(), "response": payload},
                )
                print(company, keyword, str(payload)[:160])
            except (requests.RequestException, ValueError) as error:
                save(target, {"url": url, "parameters": params, "at": stamp(), "error": str(error)})
                print(company, keyword, "FAILED", error)


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def ocr_scans():
    """Optional local OCR for signed image-only Midea PDFs, not for source replacement.

    Uses already installed PyMuPDF/rapidocr_onnxruntime. Inspect page images before
    accepting names/numbers; OCR text is auxiliary evidence, never an original.
    """
    import fitz
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR

    engine = RapidOCR()
    for source in sorted((OUT / "A股").glob("美的*.pdf")):
        target = EVIDENCE / (source.stem + ".ocr.json")
        if target.exists():
            continue
        document = fitz.open(source)
        count = min(9, len(document))
        result = []
        for index in range(count):
            image = document[index].get_pixmap(matrix=fitz.Matrix(1.6, 1.6))
            array = np.frombuffer(image.samples, dtype=np.uint8).reshape(
                image.height, image.width, image.n
            )
            detected, _ = engine(array)
            result.append({"pdf_page": index + 1, "lines": [x[1] for x in detected or []]})
            print(source.name, "OCR", index + 1, flush=True)
        save(
            target,
            {
                "path": source.relative_to(ROOT).as_posix(),
                "sha256": sha(source),
                "method": "RapidOCR local auxiliary extraction; original scanned signatures retained",
                "pages": result,
            },
        )


def inventory():
    with (ROOT / "H股年报/来源清单.csv").open(encoding="utf-8-sig", newline="") as stream:
        sources = list(csv.DictReader(stream))
    for row in sources:
        row["仓库路径"] = row["仓库路径"].replace("origin/年度报告/", "年度报告/")
        path = ROOT / row["仓库路径"]
        if not path.is_file() or sha(path) != row["SHA-256"]:
            raise ValueError(f"Financial report absent or changed: {row['document_id']}")
    return sources


def opinion(text, review=False):
    text = compact(text)
    if review:
        found = re.search(r"(?:按照我們的審閱|按照吾等的審閱).*?(?:擬備|編製)。", text)
    else:
        found = re.search(
            r"(?:我們認為|吾等認為|我们认为|Inouropinion).*?(?:。|Enterprises\.)", text
        )
    if not found:
        raise ValueError("Opinion/conclusion not found")
    return found[0]


def export_excerpt(source, first, last, target):
    import fitz

    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        with fitz.open(source) as document, fitz.open() as excerpt:
            excerpt.insert_pdf(document, from_page=first - 1, to_page=last - 1)
            excerpt.set_metadata(
                {
                    "title": "研究摘页（非官方独立披露原件）",
                    "subject": f"Source {source.relative_to(ROOT).as_posix()}, PDF pages {first}-{last}",
                }
            )
            excerpt.save(target)
    if len(pages(target)) != last - first + 1:
        raise ValueError(f"Excerpt length mismatch: {target}")


def report_row(source, decision, file_id, path, first, last, attribute, http=None, extracted=None):
    raw = extracted if extracted is not None else pages(path)
    text = "\n".join(raw[first - 1 : last])
    review = decision.get("type") == "中期审阅"
    control = decision.get("type") == "内控审计"
    if control:
        quote = re.search(r"我们认为.*?有效的财务报告内部控制。", compact(text))
        if not quote:
            raise ValueError(f"Internal control opinion missing: {path}")
        quote = quote[0]
    else:
        quote = opinion(text, review)
    market = source["披露市场"]
    if control:
        accounting, standard, scope = (
            "企业内部控制基本规范",
            "企业内部控制审计指引及中国注册会计师执业准则",
            "财务报告内部控制有效性",
        )
    elif review:
        accounting = "国际会计准则第34号"
        standard = (
            "国际审阅准则第2410号" if source["公司"] == "美的" else "香港审阅委聘准则第2410号"
        )
        scope = "中期简明合并财务报表及附注"
    elif market in ("A", "D"):
        accounting, standard, scope = (
            "中国企业会计准则",
            "中国注册会计师审计准则",
            "合并及母公司财务报表及附注",
        )
    else:
        accounting = "国际财务报告会计准则（IFRS）"
        standard = "国际审计准则（ISA）" if source["公司"] == "美的" else "香港审计准则（HKSA）"
        scope = "合并财务报表及附注"
    record = {
        "文件ID": file_id,
        "报告ID": decision.get("engagement", source["document_id"]) + ("_IC" if control else ""),
        "公司": source["发行人全称"],
        "市场": market,
        "报告期": source["报告期末"],
        "报告类型": decision.get("type", "财报审计"),
        "事务所法定名称": decision["firm"],
        "签字人或项目合伙人": decision["signers"],
        "报告编号": decision["number"],
        "出具日期": decision["date"],
        "披露日期": http["disclosed_at"] if http else source["披露日期"],
        "会计准则": accounting,
        "审计或审阅准则": standard,
        "覆盖范围": scope,
        "意见或结论分类": "未发现重大不符合编制准则事项（审阅结论）" if review else "无保留意见",
        "意见或结论原文": quote,
        "持续经营相关表述": "审计责任段载有持续经营通用表述；未见单独持续经营重大不确定性段落"
        if not review and not control
        else "不适用或未见专门段落",
        "强调事项或其他事项": "未见单列强调事项或其他事项段；其他信息及责任段不计为其他事项段",
        "关键审计事项及PDF页序": "; ".join(
            f"{name}（PDF {page}）" for name, page in decision.get("kam", [])
        ),
        "语言": "en" if market == "D" else "zh-Hant" if market == "H" else "zh-CN",
        "文件属性": attribute,
        "官方公告URL": source["公告页或官方索引URL"],
        "PDF下载URL": http["url"] if http else source["PDF下载URL"],
        "PDF最终URL": http["final_url"] if http else source["PDF最终URL"],
        "本地路径": path.relative_to(ROOT).as_posix(),
        "PDF总页数": len(raw),
        "报告起始PDF页": first,
        "报告终止PDF页": last,
        "印刷页码": decision["printed"],
        "字节数": path.stat().st_size,
        "SHA-256": sha(path),
        "获取日期": http["retrieved_at"] if http else source["下载时间"],
        "版本及复用关系": decision.get(
            "note",
            "同一报告的独立披露与年报内嵌版本不另算审计业务"
            if market == "A"
            else "按本市场签署报告单独记录",
        ),
        "检索证据路径": http.get("index_path", "") if http else "H股年报/来源清单.csv",
        "独立版本与年报金额抽查": "不适用（内嵌版本）",
        "核验状态": "已核对原文意见、期间及签署页",
        "摘页路径": "",
        "摘页SHA-256": "",
    }
    return record


def build():
    decisions = json.loads(REVIEW.read_text(encoding="utf-8"))
    sources = inventory()
    catalog, mappings, evidence = [], [], []
    for source in sources:
        identifier = source["document_id"]
        base = {
            "财报ID": identifier,
            "公司": source["发行人全称"],
            "市场": source["披露市场"],
            "证券代码": source["证券代码"],
            "报告期末": source["报告期末"],
            "财报原件路径": source["仓库路径"],
            "财报SHA-256": source["SHA-256"],
            "关联类型": "主鉴证",
            "鉴证状态": "",
            "报告ID": "",
            "文件ID": "",
            "财报内报告PDF页序": "",
            "印刷页码": "",
            "官方来源": source["PDF下载URL"],
            "对应关系": "",
            "核验状态": "已核对原件",
            "缺口说明": "",
        }
        if identifier in decisions["unaudited"]:
            decision = decisions["unaudited"][identifier]
            text_pages = pages(ROOT / source["仓库路径"])
            quote = decision["quote"]
            if not any(
                compact(quote) in compact(text_pages[i - 1]) for i in decision["evidence_pages"]
            ):
                raise ValueError(f"Unaudited evidence missing: {identifier}")
            base.update(
                {
                    "鉴证状态": "明确未经审计；本文件未见外部审阅报告",
                    "财报内报告PDF页序": ";".join(map(str, decision["evidence_pages"])),
                    "对应关系": quote,
                    "缺口说明": "未据此推断明确未经审阅；H股审阅不替代本市场财报鉴证。官方标题检索未定位本期独立审阅报告。",
                }
            )
            evidence.append(
                {"财报ID": identifier, "页码": decision["evidence_pages"], "原文": quote}
            )
            mappings.append(base)
            continue
        decision = decisions["reports"][identifier]
        first, last = decision["range"]
        record = report_row(
            source,
            decision,
            identifier + "_embedded",
            ROOT / source["仓库路径"],
            first,
            last,
            "年报或中期报告内嵌",
        )
        excerpt = (
            OUT
            / (source["披露市场"] + "股")
            / "摘页"
            / f"{identifier}_{record['报告类型']}_研究摘页.pdf"
        )
        export_excerpt(ROOT / source["仓库路径"], first, last, excerpt)
        record.update(
            {"摘页路径": excerpt.relative_to(ROOT).as_posix(), "摘页SHA-256": sha(excerpt)}
        )
        catalog.append(record)
        base.update(
            {
                "鉴证状态": "已审阅" if decision.get("type") == "中期审阅" else "已审计",
                "报告ID": record["报告ID"],
                "文件ID": record["文件ID"],
                "财报内报告PDF页序": f"{first}-{last}",
                "印刷页码": decision["printed"],
                "对应关系": "A股报告英文版本；共用审计业务ID"
                if source["披露市场"] == "D"
                else "本市场报告",
                "缺口说明": "独立版本未定位；内嵌报告完整" if source["披露市场"] != "A" else "",
            }
        )
        mappings.append(base)
    by_id = {x["document_id"]: x for x in sources}
    for path in sorted((OUT / "A股").glob("*.pdf")):
        company, _, year, kind, *_ = path.stem.split("_")
        prefix = {"美的": "MIDEA", "海尔": "HAIER", "格力": "GREE"}[company] + "_A_" + year
        http = json.loads(path.with_suffix(".http.json").read_text(encoding="utf-8"))
        if sha(path) != http["sha256"]:
            raise ValueError(f"Downloaded bytes changed: {path}")
        decision = dict(decisions["reports"][prefix])
        if company == "美的":
            ocr = json.loads((EVIDENCE / (path.stem + ".ocr.json")).read_text(encoding="utf-8"))
            raw = ["\n".join(x["lines"]) for x in ocr["pages"]]
        else:
            raw = pages(path)
        first = (
            next(i for i, t in enumerate(raw, 1) if "我们审计了" in compact(t))
            if kind == "财报审计"
            else 2
        )
        year_signed, month_signed, day_signed = map(int, decision["date"].split("-"))
        signed_date = rf"{year_signed}年0?{month_signed}月0?{day_signed}日"
        last = next(
            i
            for i, t in enumerate(raw[:10], 1)
            if i >= first and re.search(signed_date, compact(t))
        )
        decision.update({"printed": f"报告正文1—{last - first + 1}", "type": kind})
        if kind == "内控审计":
            decision["number"] = re.search(
                r"(?:众环审字|和信审字|普华永道中天特审字).*?号", compact("\n".join(raw[:3]))
            )[0]
            decision["kam"] = []
            if company == "美的" and year in ("2023", "2025"):
                decision["note"] = (
                    "内控审计范围排除部分当年新并购子公司；须结合报告正文的范围说明理解无保留意见。"
                )
        else:
            decision["kam"] = [
                (
                    name,
                    next(
                        i
                        for i, t in enumerate(raw, 1)
                        if i >= first
                        and compact(name).replace("（", "(").replace("）", ")")
                        in compact(t).replace("（", "(").replace("）", ")")
                    ),
                )
                for name, _ in decision["kam"]
            ]
        # OCR-derived text is passed explicitly for scanned PDFs; metadata remains tied to raw bytes.
        record = report_row(
            by_id[prefix],
            decision,
            prefix + "_" + ("IC" if kind == "内控审计" else "official"),
            path,
            first,
            last,
            "官方独立披露",
            http,
            raw,
        )
        record["PDF总页数"] = http["pages"]
        if kind == "财报审计":
            annual = compact("\n".join(pages(ROOT / by_id[prefix]["仓库路径"])))
            balance = compact("\n".join(raw))
            amount = re.search(r"资产总计(\d{1,3}(?:,\d{3})+(?:\.\d{2})?)", balance)
            if not amount or amount[1] not in annual:
                raise ValueError(f"Total assets differ from financial report: {prefix}")
            record["独立版本与年报金额抽查"] = (
                "资产总计 "
                + amount[1]
                + (" 人民币千元" if company == "美的" else " 人民币元")
                + "，与目标年报一致"
            )
        else:
            record["独立版本与年报金额抽查"] = "不适用（内控审计）"
        if company == "美的":
            record["核验状态"] += "；扫描件OCR辅助，与年报及签署页交叉核对"
        catalog.append(record)
        target = next(x for x in mappings if x["财报ID"] == prefix and x["关联类型"] == "主鉴证")
        if kind == "财报审计":
            target.update(
                {
                    "文件ID": record["文件ID"],
                    "对应关系": "官方独立版本已取得；年报内嵌版本保留页码对应",
                }
            )
        else:
            mappings.append(
                {
                    **target,
                    "关联类型": "补充内控审计",
                    "鉴证状态": "内控审计（不替代财报审计）",
                    "报告ID": record["报告ID"],
                    "文件ID": record["文件ID"],
                    "财报内报告PDF页序": "不适用（独立公告）",
                    "印刷页码": record["印刷页码"],
                    "对应关系": "独立内控报告",
                    "官方来源": http["url"],
                }
            )
    write_csv(ROOT / "财务数据/审计报告对应清单.csv", mappings)
    write_csv(ROOT / "财务数据/审计报告文件清单.csv", catalog)
    save(EVIDENCE / "未审计证据.json", evidence)
    build_summary(mappings, catalog)
    print("Built mappings:", len(mappings), "file/version records:", len(catalog))


def build_summary(mappings, catalog):
    main = [row for row in mappings if row["关联类型"] == "主鉴证"]
    official = [row for row in catalog if row["文件属性"] == "官方独立披露"]
    engagements = {row["报告ID"] for row in catalog if row["报告类型"] != "内控审计"}
    lines = [
        "# 三家公司财报审计与中期审阅报告收集说明（2023—2026H1）",
        "",
        "检索与复核日期：2026-10-22。对象为美的集团、海尔智家、格力电器；",
        "范围按本地已保存的财报逐份确定，不自动扩展到仅有索引的历史年度。",
        "",
        f"已覆盖 {len(main)} 份财报：12 份 A 股、7 份 H 股、4 份 D 股。",
        "其中 17 份年度财报有审计报告，2 份 H 股中期财报有外部审阅报告；",
        "另 4 份 A/D 股中期财报明确未经审计，本文件及本轮官方检索未见外部审阅报告。",
        "后者不等于已证实‘未经审阅’，也不以 H 股审阅结论替代中国准则财报的鉴证。",
        "",
        "## 对应总表",
        "",
        "表内页码均为原财报 PDF 文件页序，印刷页码与精确 URL 另见 CSV。",
        "",
        "| 财报 | 状态 | 事务所 | 出具日期 | 财报内 PDF 页序 |",
        "|---|---|---|---|---|",
    ]
    records = {row["文件ID"]: row for row in catalog}
    for row in main:
        report = records.get(row["文件ID"], {})
        lines.append(
            f"| {row['财报ID']} | {row['鉴证状态']} | {report.get('事务所法定名称', '不适用')} | {report.get('出具日期', '不适用')} | {row['财报内报告PDF页序']} |"
        )
    lines += [
        "",
        "年度报告的正式意见段均为无保留意见；两份 H 股中期报告为审阅结论，",
        "表述为未发现使核数师相信资料未按 IAS 34 编制的事项，不是审计意见。",
        "意见和结论原文、准则、关键审计事项、签署信息在文件清单中逐条记录。",
        "",
        "## 原件归档、复用和计数",
        "",
        f"- 官方独立 PDF：{len(official)} 份，其中财报审计 9 份、内控审计 9 份，均从巨潮官方全文 URL 下载，放在 `中间材料/审计报告/A股/`。",
        "- 完整内嵌审计/审阅版本：19 份（A 9、H 7、D 3），直接引用原财报，不重复复制年报。",
        "- 为方便阅读生成 19 份研究摘页，存于 `中间材料/审计报告/{市场}股/摘页/`。包含签署页，属于衍生件，不是官方独立披露原件。",
        f"- 去除独立披露、年报内嵌及 A/D 中英文版本重复后，财报审计和中期审阅共 {len(engagements)} 个报告业务 ID：14 个年度审计、2 个中期审阅；补充内控审计 9 个，单独计数。",
        "- 海尔 D 股年度报告是中国企业会计准则英文版本，编号、报告日期、主体与签署信息对应 A 股和信报告，因此 A/D 共用报告业务 ID，但保留英文文件版本及页码。",
        "- 海尔 H 股由国卫出具 IFRS 报告，A/D 由和信出具中国准则报告；不能以同一公司为理由合并。美的 A 股普华永道中天与 H 股罗兵咸永道也分开记录；美的 H 股按 ISA、海尔 H 股按 HKSA 执行年度审计。",
        "- 美的 2023 年无 H 股；格力无 H/D 股，不为这些不适用组合创建虚构报告。",
        "",
        "## 检索证据与限制",
        "",
        "巨潮按公司代码、机构 ID、‘审计报告’及‘审阅报告’检索，保留全部分页响应。",
        "接口返回了查询日期以外的历史记录，脚本逐条过滤披露日期，不据返回范围做未经核实的结论。",
        "报告标题未标年份的内控文件先按披露年度推定候选期间，随后以正文资产负债表日、签署页复核。",
        "港交所按两家发行人分别查‘核數師報告’‘審閱報告’‘審計報告’，保存请求及返回结果；",
        "前两种标题没有命中，第三种主要命中 A 股报告和内控报告的海外监管披露，不能当作另一套 H 股审计。",
        "H 股自身报告的完整正文已在官方年报和中期报告内取得；D 股采用已归档公司官网/EQS 法定披露版本。",
        "D 股独立英文审计 PDF 本轮未定位，未穷尽德国公告平台的历史标题检索；这是独立版本定位限制，不是缺少完整审计报告。",
        "检索记录位于 `中间材料/审计报告/检索记录/`，原财报 URL 来自仓库根目录下的 `H股年报/来源清单.csv`。",
        "",
        "美的 6 份独立财报/内控 PDF 为扫描签章版，原件未改变。使用已有本地 RapidOCR 和 PyMuPDF",
        "辅助定位前 9 页或内控报告全篇，OCR JSON 保留原始识别结果；签章姓名存在识别误差，",
        "按原页及年报正文交叉核对录入，不把 OCR 输出当最终事实。2023/2024 签字人姚文平、吴芳芳，",
        "2025 签字人为周伟然、吴芳芳。独立年度文件包含财务报表及附注，不能把其全部页数当作审计意见篇幅。",
        "",
        "## 与已有底表的差异与需人工复核项",
        "",
        "1. `财务数据/关键审计事项.csv` 漏列海尔 2023 年‘商誉及使用寿命不确定无形资产的减值准备’（A 股 PDF 105），2024 年也漏列同项（PDF 114）。原表未静默修改。",
        "2. 该底表把美的 2025 年收入确认及商誉事项的先后顺序对调；原报告顺序为收入确认在前、商誉减值测试在后（A 股 PDF 127—128）。本轮按原文记录。",
        "3. 海尔 H 股 2024/2025 年繁体报告的存货关键审计事项末句含‘有待獲得可得憑據支持’（PDF 156/160）。正式意见段为无保留，不能只凭该句改判；需人工与英文版核对翻译及披露质量。本轮保留原文件与提示。",
        "4. 美的 2023/2025 年内控报告说明部分新并购子公司未纳入内控审计范围。无保留内控意见应结合这一范围理解，不推广为对全部业务无例外的保证。",
        "5. 审计责任段提及持续经营风险是通用责任表述，未见单独的持续经营重大不确定性段落；关键审计事项、其他信息及责任段均不自动等同强调事项或非无保留意见。",
        "",
        "## 复现与校验",
        "",
        "```powershell",
        "python -X utf8 scripts/collect_audit_reports.py --search --search-hk --download",
        "python -X utf8 scripts/collect_audit_reports.py --ocr",
        "python -X utf8 scripts/collect_audit_reports.py --build --verify",
        "python -X utf8 scripts/verify_all.py",
        "```",
        "",
        "下载已存在文件时核对哈希并跳过；检索响应缓存可供离线复核。修改检索日期范围时应另存新检索记录，",
        "不覆盖历史响应。正常重建 CSV 不联网；新文件 OCR 需要已安装的 rapidocr_onnxruntime、PyMuPDF、numpy。",
        "所有财报原件与既有来源清单哈希比对；新增报告核对文件哈希、页码范围、期间、主体、意见和签署页。",
        "新增验证纳入 `scripts/verify_all.py`；实际校验输出、负向测试和工具限制见 `中间材料/审计报告/检索记录/执行校验.json`。",
        "本轮新增审计目录校验为 0 差异；错配期间、虚构路径、重复版本、虚构意见四项负向测试均被拦截。",
        "全仓校验为通过 621、需关注 13。13 项来自原有季度/分部口径、美的产销推算、海尔存货重分类、",
        "供应商销售总额口径、海尔固定资产口径及京东排序等检查，不属于新增审计目录错误；未在本任务中改写。",
        "全仓脚本原逻辑即使有关注项也返回 0，因此不能把退出码 0 解释为全仓数据完全一致。",
        "本报告收集结果不构成对原始财报全部金额的复审；与独立文件抽查资产总额和报告编号可追溯，未重做会计师的审计程序。",
        "",
        "## 交付路径",
        "",
        "- `财务数据/审计报告对应清单.csv`：23 条主对应记录及 9 条补充内控记录。",
        "- `财务数据/审计报告文件清单.csv`：19 个内嵌版本和 18 个官方独立版本，按报告业务 ID 去重。",
        "- `审计研究/中间材料/审计报告/`：原始 PDF、研究摘页、人工复核配置与检索证据。",
        "- `scripts/collect_audit_reports.py`：检索、下载、派生与验证。",
        "",
    ]
    (ROOT / "审计研究/审计报告收集说明_2023-2026H1.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def validate(mapping_rows=None, file_rows=None):
    """Return errors, including absent catalogs, mismatched periods and missing PDFs."""
    errors = []
    try:
        if mapping_rows is None:
            with (ROOT / "财务数据/审计报告对应清单.csv").open(
                encoding="utf-8-sig", newline=""
            ) as stream:
                mapping_rows = list(csv.DictReader(stream))
        if file_rows is None:
            with (ROOT / "财务数据/审计报告文件清单.csv").open(
                encoding="utf-8-sig", newline=""
            ) as stream:
                file_rows = list(csv.DictReader(stream))
        sources = {row["document_id"]: row for row in inventory()}
        decisions = json.loads(REVIEW.read_text(encoding="utf-8"))
        records = {row["文件ID"]: row for row in file_rows}
        if len(records) != len(file_rows):
            errors.append("Duplicate file ID")
        main = [row for row in mapping_rows if row["关联类型"] == "主鉴证"]
        if len(main) != 23 or {row["财报ID"] for row in main} != set(sources):
            errors.append("Financial report coverage is not one-to-one")
        for row in mapping_rows:
            key = row["财报ID"]
            if key not in sources:
                errors.append("Unknown financial report: " + key)
                continue
            source = sources[key]
            if row["报告期末"] != source["报告期末"] or row["市场"] != source["披露市场"]:
                errors.append("Period/market mismatch: " + key)
            if row["财报原件路径"] != source["仓库路径"] or row["财报SHA-256"] != source["SHA-256"]:
                errors.append("Source mismatch: " + key)
            if not row["文件ID"]:
                if not key.endswith("2026H1") or "未经审计" not in row["鉴证状态"]:
                    errors.append("Unsupported absent report: " + key)
                continue
            report = records.get(row["文件ID"])
            if (
                report is None
                or report["报告ID"] != row["报告ID"]
                or report["报告期"] != row["报告期末"]
                or report["公司"] != row["公司"]
            ):
                errors.append("Report mapping mismatch: " + key)
        known_files = set()
        for row in file_rows:
            label = row["文件ID"]
            source_id = "_".join(label.split("_")[:3])
            if source_id not in decisions["reports"]:
                errors.append("Unknown reviewed report: " + label)
                continue
            decision = decisions["reports"][source_id]
            if (
                row["报告期"] != sources[source_id]["报告期末"]
                or row["出具日期"] != decision["date"]
            ):
                errors.append("Reviewed period/date mismatch: " + label)
            if (
                row["事务所法定名称"] != decision["firm"]
                or row["签字人或项目合伙人"] != decision["signers"]
            ):
                errors.append("Reviewed firm/signatory mismatch: " + label)
            for field in (
                "报告ID",
                "报告期",
                "公司",
                "事务所法定名称",
                "出具日期",
                "意见或结论原文",
                "PDF下载URL",
                "SHA-256",
            ):
                if not row.get(field):
                    errors.append("Missing " + field + ": " + label)
            path = ROOT / row["本地路径"]
            if not path.is_file():
                errors.append("Missing PDF: " + label)
                continue
            if sha(path) != row["SHA-256"] or not path.read_bytes().startswith(b"%PDF-"):
                errors.append("PDF bytes/hash invalid: " + label)
            if path.stat().st_size != int(row["字节数"]):
                errors.append("PDF length invalid: " + label)
            first, last = int(row["报告起始PDF页"]), int(row["报告终止PDF页"])
            if not 1 <= first <= last <= len(pages(path)) == int(row["PDF总页数"]):
                errors.append("PDF page range invalid: " + label)
            extracted = pages(path)
            if "扫描件OCR" in row["核验状态"]:
                ocr = json.loads((EVIDENCE / (path.stem + ".ocr.json")).read_text(encoding="utf-8"))
                if ocr["sha256"] != row["SHA-256"]:
                    errors.append("OCR provenance mismatch: " + label)
                extracted = ["\n".join(x["lines"]) for x in ocr["pages"]]
            report_text = compact("\n".join(extracted[first - 1 : last]))
            if (
                row["报告期"][:4] not in report_text
                or compact(row["意见或结论原文"]) not in report_text
            ):
                errors.append("Report period/opinion not present on cited pages: " + label)
            if row["文件属性"] == "官方独立披露":
                if row["SHA-256"] in known_files:
                    errors.append("Duplicate official PDF counted twice: " + label)
                known_files.add(row["SHA-256"])
                meta = json.loads(path.with_suffix(".http.json").read_text(encoding="utf-8"))
                if meta["sha256"] != row["SHA-256"]:
                    errors.append("Download provenance hash mismatch: " + label)
            if row["摘页路径"]:
                excerpt = ROOT / row["摘页路径"]
                if not excerpt.is_file() or sha(excerpt) != row["摘页SHA-256"]:
                    errors.append("Excerpt absent/changed: " + label)
                elif len(pages(excerpt)) != last - first + 1:
                    errors.append("Excerpt page range invalid: " + label)
                elif [compact(t) for t in pages(excerpt)] != [
                    compact(t) for t in pages(path)[first - 1 : last]
                ]:
                    errors.append("Excerpt content does not match source pages: " + label)
        if len(file_rows) != 37:
            errors.append("Unexpected report version count")
        if len({r["报告ID"] for r in file_rows if r["报告类型"] != "内控审计"}) != 16:
            errors.append("Engagement deduplication failed")
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        errors.append(str(error))
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("search", "search-hk", "download", "ocr", "build", "verify"):
        parser.add_argument("--" + option, action="store_true")
    args = parser.parse_args()
    if args.search:
        search_official()
    if args.search_hk:
        search_hk()
    if args.download:
        download_candidates()
    if args.ocr:
        ocr_scans()
    if args.build:
        build()
    if args.verify:
        errors = validate()
        for error in errors:
            print("FAIL", error)
        print("Audit catalog errors:", len(errors))
        return int(bool(errors))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
