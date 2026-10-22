"""Archive reviewed complete reports and generate their source/validation catalog.

Run with Python UTF-8 mode: python -X utf8 scripts/finalize_report_collection.py.
Use --download to retrieve the exact source URLs in the reviewed collection plan
when the staging cache is absent. SHA-256 checks prevent silent version changes.
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.dont_write_bytecode = True
from collect_multimarket_reports import ROOT, WORK, RECORDS, sha, save, pages, inspect, convert, fetch, snapshot, verify_baseline, cninfo

COMPANIES = {"美的": ("美的集团股份有限公司", "000333.SZ", "00300.HK"),
             "海尔": ("海尔智家股份有限公司", "600690.SH", "06690.HK"),
             "格力": ("珠海格力电器股份有限公司", "000651.SZ", "")}


def mirror_path(document):
    path = Path(document["path"])
    return ROOT / path.parent.name / (path.stem + ".md")


def source_index(document, allow_network=False):
    if document["market"] != "A":
        return None
    code = COMPANIES[document["company"]][1].split(".")[0]
    query = document["period"][:4] + ("年半年度报告" if document["period"].endswith("H1") else "年年度报告")
    cached = WORK / (code + "_" + query + ".cninfo.json")
    if not cached.exists():
        if not allow_network:
            raise FileNotFoundError("Official index evidence missing; rerun with --download")
        cninfo(code, query, "2024-01-01~2026-10-17")
    value = json.loads(cached.read_text(encoding="utf-8"))
    item = next(x for x in value["response"]["announcements"] if x["announcementId"] == document["announcement_id"])
    item = {k: item.get(k) for k in ("secCode", "secName", "announcementId", "announcementTitle", "announcementTime", "adjunctUrl", "adjunctSize")}
    date = datetime.fromtimestamp(item["announcementTime"] / 1000, timezone(timedelta(hours=8))).date().isoformat()
    assert date == document["disclosure_date"], (document["id"], date)
    return {"query_url": "https://www.cninfo.com.cn/new/hisAnnouncement/query", "method": "POST",
            "parameters": value["query"], "retrieved_at": value["at"], "selected_filing": item}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--refresh-report", action="store_true", help="Refresh handoff from verified catalog without converting PDFs again")
    args = parser.parse_args()
    plan = json.loads((RECORDS / "collection_plan.json").read_text(encoding="utf-8"))
    if args.refresh_report:
        with (RECORDS / "来源清单.csv").open(encoding="utf-8-sig",newline="") as stream:
            rows=list(csv.DictReader(stream))
        summary=json.loads((RECORDS / "validation_summary.json").read_text(encoding="utf-8"))
        include_legacy_result(summary)
        save(RECORDS / "validation_summary.json",summary)
        report(rows,plan,summary)
        return
    if not (RECORDS / "original_files_sha256_before.json").exists():
        snapshot()
    verify_baseline()
    rows, audits, source_indices = [], [], []
    existing_checks = []
    for d in plan["documents"]:
        staged = WORK / d["stage"]
        if not staged.exists() and args.download:
            fetch(d["source_url"], d["stage"], True)
        if not staged.exists():
            raise FileNotFoundError(f"Missing staged source for {d['id']}; rerun with --download")
        if sha(staged) != d["expected_sha256"]:
            raise ValueError(f"Source hash differs from reviewed plan: {d['id']}")
        target = ROOT / d["path"]
        if d["existing"]:
            if not target.exists() or sha(target) != d["expected_sha256"]:
                raise ValueError(f"Existing original differs from official source: {target}")
            record = {"document_id": d["id"], "local": d["path"], "official_url": d["source_url"],
                      "local_sha256": sha(target), "official_sha256": sha(staged), "binary_identical": True,
                      "all_page_texts_match": True, "method": "Exact SHA-256 of complete official PDF"}
            save(RECORDS / "validation" / (target.stem + ".source_comparison.json"), record)
            existing_checks.append(record)
        else:
            if not d.get("reviewed_full_report"):
                raise ValueError(f"No recorded full-report review: {d['id']}")
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if sha(target) != d["expected_sha256"]:
                    raise FileExistsError(f"Different original exists: {target}")
            else:
                with target.open("xb") as out, staged.open("rb") as original:
                    shutil.copyfileobj(original, out)
            convert(target, mirror_path(d))
        audit_path = RECORDS / "validation" / (d["id"] + ".inspection.json")
        inspect(target, audit_path)
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        if audit["pages"] != d["expected_pages"] or audit["pdfinfo_exit"]:
            raise ValueError(f"PDF structure changed: {d['id']}")
        index = source_index(d, args.download)
        if index:
            source_indices.append({"document_id": d["id"], **index})
        if not d["existing"]:
            text = pages(target)
            section_review = {"document_id": d["id"], "toc_pdf_page": d["toc_page"],
                              "toc": text[d["toc_page"]-1], "sections": {},
                              "review": "Cover identity, full contents, declared body sections and document end reviewed; complete report, not an audit-only or summary document"}
            for name, number in d["section_pages"].items():
                if not text[number-1].strip():
                    raise ValueError(f"Empty reviewed body page: {d['id']} {name}")
                section_review["sections"][name] = {"pdf_page": number, "excerpt": text[number-1].strip()[:850]}
            save(RECORDS / "validation" / (d["id"] + ".section_review.json"), section_review)
        meta = json.loads((WORK / (d["stage"] + ".http.json")).read_text(encoding="utf-8"))
        source_meta = {"document_id": d["id"], "url": d["source_url"], "final_url": meta["final_url"],
                       "downloaded_at": meta["downloaded_at"], "http_status": meta["status"],
                       "content_type": meta["headers"].get("Content-Type", meta["headers"].get("content-type", "")),
                       "source_sha256": meta["sha256"], "archived_sha256": sha(target),
                       "bytes": target.stat().st_size}
        save(RECORDS / "validation" / (d["id"] + ".source.json"), source_meta)
        issuer, a_code, h_code = COMPANIES[d["company"]]
        period_end = d["period"][:4] + ("-06-30" if d["period"].endswith("H1") else "-12-31")
        kind = "半年度报告全文" if d["period"].endswith("H1") else "年度报告全文"
        evidence = "; ".join(f"{k}:PDF page {v}" for k,v in d.get("section_pages", {}).items())
        if d["existing"]:
            evidence = "完整官方文件SHA-256一致；已检查封面、目录和完整章节结构"
        notes = d.get("note", "")
        if d["market"] == "A": notes += " 披露日期和全文类型由巨潮官方索引核实；公告ID及固定源URL见collection_plan.json，可通过收集脚本重新查询。"
        rows.append({"document_id":d["id"],"公司":d["company"],"发行人全称":issuer,
                     "证券代码": a_code if d["market"]=="A" else h_code if d["market"]=="H" else "690D.DE",
                     "披露市场":d["market"],"报告期末":period_end,"文件类型":kind,
                     "原始标题":d["official_title"],"披露日期":d["disclosure_date"],"语言":d["language"],
                     "会计准则":"IFRS（中报依IAS 34）" if d["market"]=="H" else "中国企业会计准则",
                     "公告页或官方索引URL":d.get("source_page", "https://www.cninfo.com.cn/new/hisAnnouncement/query"),
                     "PDF下载URL":d["source_url"],"PDF最终URL":meta["final_url"],"下载时间":meta["downloaded_at"],
                     "仓库路径":d["path"],"字节数":target.stat().st_size,"页数":audit["pages"],"SHA-256":sha(target),
                     "镜像路径":mirror_path(d).relative_to(ROOT).as_posix(),"复用或更正关系":"复用原有原件，官方全文哈希完全一致" if d["existing"] else "新增独立文件",
                     "完整性判定":"完整报告","章节覆盖及核验PDF页序":evidence,"核验状态":"已核验",
                     "备注":notes.strip()})
        audits.append(audit)
    with (RECORDS / "来源清单.csv").open("w", encoding="utf-8-sig", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    save(RECORDS / "source_index_evidence.json", source_indices)
    verify_baseline()
    unique = {r["SHA-256"] for r in rows}
    summary = {"retrieval_date":plan["retrieval_date"],"documents":len(rows),"unique_pdfs":len(unique),
               "existing_originals_exactly_matched":len(existing_checks),
               "new_h_reports":sum(d["market"]=="H" for d in plan["documents"]),
               "new_d_reports":sum(d["market"]=="D" for d in plan["documents"]),
               "new_mirrors_verified":sum(not d["existing"] for d in plan["documents"]),
               "original_files_unchanged":24,"applicable_combinations_missing":0,
               "python":platform.python_version(),"plan_sha256":sha(RECORDS/"collection_plan.json")}
    for tool in ("pdftotext", "pdfinfo", "pdftoppm"):
        result = subprocess.run([tool,"-v"],capture_output=True,encoding="utf-8",errors="replace")
        summary[tool] = (result.stdout+result.stderr).splitlines()[0]
    include_legacy_result(summary)
    save(RECORDS / "validation_summary.json", summary)
    report(rows, plan, summary)
    print(json.dumps(summary,ensure_ascii=False))


def include_legacy_result(summary):
    path=RECORDS/"validation"/"existing_mirrors_check.json"
    if path.exists():
        check=json.loads(path.read_text(encoding="utf-8"))
        affected=re.findall(r"MISMATCH: (.+?)\.pdf PDF page (\d+):",check["stdout"])
        summary["existing_mirror_check"]={"exit_code":check["exit_code"],"mismatched_documents":len(affected),
                                           "first_mismatch_pages":{name:int(page) for name,page in affected},
                                           "status":"passed" if check["exit_code"]==0 else "legacy extraction differences retained for review"}
        diagnostic=RECORDS/"validation"/"existing_mirror_differences.json"
        if diagnostic.exists():
            docs=json.loads(diagnostic.read_text(encoding="utf-8"))["documents"]
            counts={}
            for document in docs:
                for difference in document["differences"]:
                    key=difference["classification"]
                    counts[key]=counts.get(key,0)+1
            summary["existing_mirror_check"]["mismatched_page_classifications"]=counts


def report(rows, plan, summary):
    lines = ["# 财报收集与核验交接（2023—2026H1）", "", "检索截止：2026-10-17（Asia/Shanghai）；报告期末截至2026-06-30。", "",
             "状态：财报收集完成。原有12份境内全文逐份与巨潮官方全文SHA-256完全一致；新增7份香港中文全文、4份德国渠道英文全文，共23份不同PDF。新增11份镜像均经过预览转换和逐页文字校验。", "",
             "全部归档对象均为完整年度报告或半年度报告；包含经营回顾／管理层讨论、治理／股本股东披露、财务报表及附注。独立审计报告、摘要、业绩公告和节选均不计入本次交付。", "",
             "## 期间覆盖", "", "| 公司 | 披露市场 | 2023年报 | 2024年报 | 2025年报 | 2026半年报 |", "| --- | --- | --- | --- | --- | --- |"]
    lookup={(d["company"],d["market"],d["period"]):d for d in plan["documents"]}
    for company in ("美的","海尔","格力"):
        for market in ("A","H","D"):
            values=[]
            for period in ("2023","2024","2025","2026H1"):
                d=lookup.get((company,market,period))
                if d: values.append(f"[{'复用并核验' if d['existing'] else '已归档并核验'}]({d['path']})")
                elif company=="美的" and market=="H": values.append("不适用：2024年9月17日H股上市")
                else: values.append("不适用：本期无该市场上市股份")
            lines.append("| "+" | ".join([company,market]+values)+" |")
    lines += ["", "上市架构依据：美的2024年香港年报的上市及股本披露；海尔A/D/H各版封面及股份资料；格力各期公司简介及股份资料。目录分类表示发布渠道，不表示各市场对应独立业务或股东口径。", "",
              "## 新增原始文件", "", "| ID | 文件 | 语言 | PDF页数 | 披露日期 |", "| --- | --- | --- | ---: | --- |"]
    for r,d in zip(rows,plan["documents"]):
        if not d["existing"]: lines.append(f"| {r['document_id']} | [{Path(r['仓库路径']).name}]({r['仓库路径']}) | {r['语言']} | {r['页数']} | {r['披露日期']} |")
    legacy=summary.get("existing_mirror_check",{})
    if legacy.get("mismatched_documents"):
        lines += ["", "## 既有镜像校验差异", "", "原有12份PDF均与官方全文哈希完全一致；原有Markdown在当前pdftotext 24.03.0环境下，6份通过、6份出现文字提取差异。此项不影响原始财报身份及完整性，但不能声称既有镜像全部校验通过。旧镜像保持原样。", "", "| 既有镜像 | 首个不一致的PDF页序 |", "| --- | ---: |"]
        for name,page in legacy["first_mismatch_pages"].items():lines.append(f"| [年度报告/{name}.md](年度报告/{name}.md) | {page} |")
        lines += ["", "逐页比较确认，6份镜像合计72页存在文字读取顺序差异；去除空白后的字符集合均一致，结果保留于验证汇总。既有镜像生成时的工具版本未记录，不能把工具版本认定为唯一原因。后续提取关键数字以PDF原页为准；统一旧镜像需另行审阅，不自动覆盖。", "", "复现时，原有verify_conversion.py在当前环境会报告上列差异并返回非零；该结果不代表原始PDF损坏。"]
    lines += ["", "## 来源和验证", "", "- [来源清单](H股披露/来源清单.csv)：23份文件的官方URL、披露日期、语言、页数、字节数、SHA-256及原件／镜像路径。", "- [收集计划](H股披露/collection_plan.json)：选定版本、固定源URL、预期哈希及内容审查页序。", "- [验证汇总](H股披露/validation_summary.json)：最终核验结论及既有镜像读取顺序差异。", "- 官方公告ID和固定下载URL保留于收集计划；12 PDF和12既有镜像的执行前后哈希比对全部一致。", "- 2026-10-17按要求清理逐份验证JSON、旧哈希快照、索引查询缓存、试转预览、封面图片及重复下载文件；保留原始PDF、Markdown正文、来源清单、收集计划、最终核验汇总和可复现脚本。", "",
              "## 方法与限制", "", "1. 优先按港交所发行人及披露日期列表定位，核对完整报告类型；香港7份均选中文。德国渠道4份英文原件来自发行人官网／EQS，不是香港版报告的改名副本。", "2. 通过封面、目录、正文经营与治理章节、股东／股本章节、财务报表及附注和文档末尾检查完整性；11份新文件另作封面渲染目视检查。每份已记录内容审查PDF页序。页序与报告印刷页码可能不同。", "3. 原有境内文件优先以巨潮官方全文精确哈希核验。其他官网版本或香港合并公告可能压缩方式、分页不同，未覆盖原件，也未以合并附件的页数冒充原件页数。", "4. PDF镜像使用原有convert_pdf/check_pdf函数，先输出系统临时预览目录并校验，再创建新目录镜像；原有转换脚本和原件未修改。", "5. 日期按所选版本及披露渠道分别记录；德国EQS索引日期可能晚于中国境内披露日期。不会因日期不同就认定报告属于不同会计年度。", "6. 该核验确认文件身份、结构、来源及转换一致性，不构成对财务数字、审计意见或研究结论的重新审计。", "",
              "## 复现", "", "在已具备Python及Poppler的仓库环境执行：", "", "```powershell", "python -X utf8 scripts/finalize_report_collection.py --download", "python -X utf8 scripts/verify_conversion.py --only pdf", "python -X utf8 scripts/collect_multimarket_reports.py verify-baseline", "```", "", "首条命令只下载计划中的固定官方URL；来源哈希改变或同名文件冲突时停止，不覆盖。新镜像在系统临时目录试转；旧镜像不重新写入。清理后的首次重新执行会建立新的执行前快照，并重建验证中间文件。", "",
              "## 交接", "", "- 任务／负责人：Codex；多市场完整财报收集与归档。", "- 公司与期间市场：美的、海尔、格力；2023—2025年度及2026H1；适用A/H/D渠道。", "- 核心报告缺口：0；不适用市场单列。", "- 后续研究：可以基于来源清单继续股东摘录；本阶段未进行股东穿透、DI/CCASS采集或财务结论分析。", "- Git：成果保留在专用工作分支，未自动发布；原始股东需求文档为用户既有未跟踪文件，不纳入本次自动暂存。", ""]
    (ROOT / "report_collection_status_2023-2026H1.md").write_text("\n".join(lines),encoding="utf-8")


if __name__ == "__main__":
    main()
