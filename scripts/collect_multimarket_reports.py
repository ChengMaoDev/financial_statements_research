"""Utilities for the 2023-2026H1 official full-report collection.

Downloads are staged separately. Inspect/review their content before archiving.
No original or existing derivative is overwritten. Uses only the Python standard
library and Poppler; document review decisions are recorded in the collection plan.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
WORK = Path(tempfile.gettempdir()) / "financial-report-collection-20261017"
RECORDS = ROOT / "H股披露"
sys.dont_write_bytecode = True


def stamp():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pages(path):
    run = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"], check=True, capture_output=True, encoding="utf-8"
    )
    result = run.stdout.split("\f")
    if result and not result[-1].strip():
        result.pop()
    return result


PATTERNS = {
    "business": r"管理[层層].{0,5}(?:[讨討][论論]|分析)|[业業][务務]回[顾顧]|[经經][营營]情[况況]|Management Discussion|Business Review",
    "governance": r"公司治理|企[业業]管治|Corporate Governance|董事[会會][报報]告|Report of the Directors|其他[资資]料|Other Information",
    "shareholders": r"[股權权][东東本益].{0,9}(?:[变變][动動]|[情资資]?[况況料]|持股)|主要股[东東]|SUBSTANTIAL SHAREHOLDER|SHARE CAPITAL|Shareholders|Interests in Shares",
    "statements": r"[资資][产產][负負][债債]表|[财財][务務][状狀][况況]表|[现現]金流量表|Statement of Financial Position|Statement of Cash Flows|Balance Sheet",
    "notes": r"[财財][务務][报報]表附[注註]|[财財][务務][报報]告附[注註]|中期[财財][务務][资資]料附[注註]|[报報]表[项項]目[注註][释釋]|重要[会會][计計]政策|Notes\s+to[\s\S]{0,130}Financial\s+(?:Statements|Information)|Notes to the Consolidated|IMPORTANT ACCOUNTING POLICIES|GENERAL INFORMATION OF THE COMPANY",
    "audit": r"[审審][计計][报報]告|[核數数][數数]?[師师][报報]告|Independent Auditor|Audit Report",
    "IFRS": r"International Financial Reporting Standards|IFRS Accounting Standards|國際財務報告準則|国际财务报告准则",
    "CAS": r"企业会计准则|企業會計準則|China Accounting Standards|Accounting Standards for Business Enterprises",
}


def inspect(path, output):
    texts = pages(path)
    compact = [re.sub(r"[ \t]+", "", t) for t in texts]
    matches = {}
    for label, pattern in PATTERNS.items():
        rx = re.compile(pattern, re.I)
        hits = []
        for number, (text, squeezed) in enumerate(zip(texts, compact, strict=True), 1):
            match = rx.search(text) or rx.search(squeezed)
            if match:
                hits.append({"pdf_page": number, "match": match.group(0)[:100]})
        matches[label] = hits
    info = subprocess.run(
        ["pdfinfo", str(path)], capture_output=True, encoding="utf-8", errors="replace"
    )
    value = {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
        "pages": len(texts),
        "pdfinfo": info.stdout,
        "pdfinfo_exit": info.returncode,
        "front": "\n\f\n".join(texts[:5])[:18000],
        "last_page": texts[-1][-4000:],
        "matches": matches,
        "inspected_at": stamp(),
    }
    last = next(((i, t) for i, t in reversed(list(enumerate(texts, 1))) if t.strip()), (0, ""))
    value["last_nonblank_page"] = last[0]
    value["last_nonblank_excerpt"] = last[1][-2000:]
    save(output, value)
    print(
        json.dumps(
            {
                "file": path.name,
                "pages": len(texts),
                "bytes": value["bytes"],
                "categories": {k: [v["pdf_page"] for v in vals[:8]] for k, vals in matches.items()},
                "inspection": str(output),
            },
            ensure_ascii=False,
        )
    )


def fetch(url, name, is_pdf):
    WORK.mkdir(parents=True, exist_ok=True)
    target = WORK / name
    if target.exists():
        print(f"REUSE STAGED {target}")
        return
    parsed = urlsplit(url)
    encoded_url = urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            quote(parsed.path, safe="/%:@"),
            quote(parsed.query, safe="=&%:+,;/?"),
            "",
        )
    )
    request = Request(
        encoded_url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; academic report collection)",
            "Accept": "*/*",
        },
    )
    partial = target.with_suffix(target.suffix + ".part")
    with urlopen(request, timeout=60) as response:
        headers = dict(response.headers)
        final = response.url
        status = response.status
        with partial.open("xb") as dest:
            shutil.copyfileobj(response, dest)
    if is_pdf and not partial.read_bytes()[:1024].lstrip().startswith(b"%PDF-"):
        raise ValueError(f"Not a PDF: {url}; staged for rejection at {partial}")
    partial.rename(target)
    save(
        WORK / (name + ".http.json"),
        {
            "requested_url": url,
            "final_url": final,
            "downloaded_at": stamp(),
            "status": status,
            "headers": headers,
            "bytes": target.stat().st_size,
            "sha256": sha(target),
        },
    )
    print(
        json.dumps(
            {"path": str(target), "bytes": target.stat().st_size, "final_url": final},
            ensure_ascii=False,
        )
    )
    if is_pdf:
        inspect(target, WORK / (name + ".inspection.json"))


def snapshot():
    target = RECORDS / "original_files_sha256_before.json"
    if target.exists():
        raise FileExistsError("Baseline already exists; will not overwrite")
    files = list((ROOT / "origin" / "年度报告").glob("*.pdf")) + list(
        (ROOT / "年度报告").glob("*.md")
    )
    save(
        target,
        {"created_at": stamp(), "files": {str(p.relative_to(ROOT)): sha(p) for p in sorted(files)}},
    )
    print(f"Saved baseline for {len(files)} existing files")


def links(path, base, pattern):
    class Anchors(HTMLParser):
        def __init__(self):
            super().__init__()
            self.current = None
            self.found = []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "a":
                self.current = [attrs.get("href", ""), attrs.get("title", "")]

        def handle_data(self, data):
            if self.current is not None:
                self.current[1] += " " + data.strip()

        def handle_endtag(self, tag):
            if tag == "a" and self.current is not None:
                self.found.append(self.current)
                self.current = None

    parser = Anchors()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    for href, text in parser.found:
        if re.search(pattern, href + " " + text, re.I):
            print(
                json.dumps(
                    {"url": urljoin(base, href), "text": re.sub(r"\s+", " ", text).strip()},
                    ensure_ascii=False,
                )
            )


def verify_baseline():
    value = json.loads((RECORDS / "original_files_sha256_before.json").read_text(encoding="utf-8"))
    bad = [
        path
        for path, digest in value["files"].items()
        if not (ROOT / path).exists() or sha(ROOT / path) != digest
    ]
    print(json.dumps({"original_files": len(value["files"]), "changed": bad}, ensure_ascii=False))
    if bad:
        raise ValueError("Original files changed")


def compare(local, official, output):
    local = local.resolve()
    left, right = pages(local), pages(official)

    def normalize(value):
        return re.sub(r"\s+", "", value)

    a, b = list(map(normalize, left)), list(map(normalize, right))
    offset = next((i for i in range(max(0, len(b) - len(a) + 1)) if b[i : i + len(a)] == a), None)
    local_label = str(local.relative_to(ROOT)) if local.is_relative_to(ROOT) else local.name
    result = {
        "local": local_label,
        "official_staged_name": official.name,
        "local_sha256": sha(local),
        "official_sha256": sha(official),
        "local_pages": len(a),
        "official_pages": len(b),
        "binary_identical": sha(local) == sha(official),
        "all_page_texts_match": offset is not None,
        "official_page_range": [offset + 1, offset + len(a)] if offset is not None else None,
        "method": "Remove Unicode whitespace, compare every page in order; image contents are not compared",
        "checked_at": stamp(),
    }
    if offset is None:
        result["same_numbered_page_matches"] = sum(x == y for x, y in zip(a, b, strict=False))
    save(output, result)
    print(json.dumps(result, ensure_ascii=False))


def cninfo(code, query, date_range):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.cninfo.com.cn/",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }
    request = Request(
        "https://www.cninfo.com.cn/new/information/topSearch/query",
        data=urlencode({"keyWord": code, "maxNum": 10}).encode(),
        headers=headers,
    )
    with urlopen(request, timeout=40) as response:
        identities = json.load(response)
    issuer = next(x for x in identities if x.get("code") == code)
    values = {
        "pageNum": 1,
        "pageSize": 30,
        "tabName": "fulltext",
        "column": "sse" if code.startswith("6") else "szse",
        "stock": code + "," + issuer["orgId"],
        "searchkey": query,
        "secDate": date_range,
        "isHLtitle": "true",
    }
    request = Request(
        "https://www.cninfo.com.cn/new/hisAnnouncement/query",
        data=urlencode(values).encode(),
        headers=headers,
    )
    with urlopen(request, timeout=40) as response:
        value = json.load(response)
    WORK.mkdir(parents=True, exist_ok=True)
    save(
        WORK / (code + "_" + query + ".cninfo.json"),
        {"query": values, "at": stamp(), "response": value},
    )
    for item in value.get("announcements") or []:
        print(
            json.dumps(
                {
                    "title": re.sub("<[^>]*>", "", item["announcementTitle"]),
                    "url": urljoin("https://static.cninfo.com.cn/", item["adjunctUrl"]),
                    "announcement_id": item["announcementId"],
                    "time": item["announcementTime"],
                },
                ensure_ascii=False,
            )
        )


def diagnose_mirrors():
    results = []
    for source in sorted((ROOT / "origin" / "年度报告").glob("*.pdf")):
        mirror = ROOT / "年度报告" / (source.stem + ".md")
        original = pages(source)
        extracted = re.findall(
            r"^## PDF page (\d+)\n\n```text\n(.*?)\n```$",
            mirror.read_text(encoding="utf-8"),
            re.M | re.S,
        )
        if len(extracted) != len(original):
            raise ValueError(f"Existing mirror page count differs: {mirror}")
        differences = []
        for i, ((number, old), current) in enumerate(zip(extracted, original, strict=True), 1):
            if int(number) != i:
                raise ValueError("Existing page sequence differs")

            def norm(value):
                return re.sub(r"\s+", " ", value).strip()

            if norm(old) == norm(current):
                continue
            a, b = re.sub(r"\s+", "", old), re.sub(r"\s+", "", current)
            kind = (
                "whitespace_only"
                if a == b
                else "reading_order_only"
                if Counter(a) == Counter(b)
                else "character_content_difference"
            )
            differences.append(
                {
                    "pdf_page": i,
                    "classification": kind,
                    "character_count_old": len(a),
                    "character_count_current": len(b),
                }
            )
        result = {
            "source": source.relative_to(ROOT).as_posix(),
            "mirror": mirror.relative_to(ROOT).as_posix(),
            "pages": len(original),
            "mismatched_pages": len(differences),
            "differences": differences,
        }
        results.append(result)
        print(
            json.dumps(
                {
                    "file": source.name,
                    "mismatched_pages": len(differences),
                    "classifications": dict(Counter(d["classification"] for d in differences)),
                },
                ensure_ascii=False,
            )
        )
    save(
        RECORDS / "validation" / "existing_mirror_differences.json",
        {
            "method": "Same page mapping as verify_conversion.py; classify normalized text differences without changing files",
            "warning": "Equal character multisets identify order differences, not correct paragraph/table semantics; original mirror tool version is unknown",
            "documents": results,
        },
    )


def convert(source, target):
    from convert_to_text import convert_pdf
    from verify_conversion import ERRORS, check_pdf

    preview = WORK / "preview" / source.parent.name / (source.stem + ".md")
    if not preview.exists():
        convert_pdf(source, preview, False)
    check_pdf(source, preview)
    if ERRORS:
        raise ValueError(str(ERRORS))
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes() != preview.read_bytes():
            raise FileExistsError(f"Different mirror already exists: {target}")
    else:
        with target.open("xb") as dest:
            dest.write(preview.read_bytes())
    print(f"VERIFIED MIRROR {target.relative_to(ROOT)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("snapshot")
    sub.add_parser("verify-baseline")
    sub.add_parser("diagnose-mirrors")
    dl = sub.add_parser("fetch")
    dl.add_argument("url")
    dl.add_argument("name")
    dl.add_argument("--html", action="store_true")
    ins = sub.add_parser("inspect")
    ins.add_argument("path", type=Path)
    ins.add_argument("output", type=Path)
    cv = sub.add_parser("convert")
    cv.add_argument("source", type=Path)
    cv.add_argument("target", type=Path)
    lk = sub.add_parser("links")
    lk.add_argument("path", type=Path)
    lk.add_argument("base")
    lk.add_argument("pattern")
    cp = sub.add_parser("compare")
    cp.add_argument("local", type=Path)
    cp.add_argument("official", type=Path)
    cp.add_argument("output", type=Path)
    cn = sub.add_parser("cninfo")
    cn.add_argument("code")
    cn.add_argument("query")
    cn.add_argument("date_range")
    args = parser.parse_args()
    if args.command == "snapshot":
        snapshot()
    elif args.command == "verify-baseline":
        verify_baseline()
    elif args.command == "fetch":
        fetch(args.url, args.name, not args.html)
    elif args.command == "inspect":
        inspect(args.path, args.output)
    elif args.command == "convert":
        convert(args.source, args.target)
    elif args.command == "links":
        links(args.path, args.base, args.pattern)
    elif args.command == "compare":
        compare(args.local, args.official, args.output)
    elif args.command == "cninfo":
        cninfo(args.code, args.query, args.date_range)
    elif args.command == "diagnose-mirrors":
        diagnose_mirrors()


if __name__ == "__main__":
    main()
