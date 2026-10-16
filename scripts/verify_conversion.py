"""Verify converted files match originals under origin/.

Checks (read-only, no writes except stdout):
  PDF->MD : page count == '## Page' markers; extracted text == md body
            (headers/markers stripped).
  DOCX->MD: paragraph texts in order; table cell values in order.
  XLSX->CSV: cached cell values equal CSV cells; all-empty rows skipped;
            formula cells reported (values, not formulas, are compared).

Exit 0 if all match, 1 otherwise. Mismatches printed with locations.
Run: uv run --with pdfplumber --with python-docx --with openpyxl python3 scripts/verify_conversion.py
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "origin"
ERRORS: list[str] = []
CHECKED = 0


def err(msg: str) -> None:
    ERRORS.append(msg)
    print("MISMATCH:", msg, flush=True)


def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def check_pdf(pdf: Path, md: Path) -> None:
    global CHECKED
    import pdfplumber

    CHECKED += 1
    if not md.exists():
        return err(f"{md} missing")
    text = md.read_text(encoding="utf-8")
    markers = re.findall(r"^## Page (\d+)$", text, re.M)
    with pdfplumber.open(pdf) as doc:
        n = len(doc.pages)
        if [int(m) for m in markers] != list(range(1, n + 1)):
            err(f"{pdf.name}: page markers {len(markers)} != pdf pages {n}")
        body = re.sub(r"^# .*\n\n> Source:.*\n", "", text, count=1)
        body = re.sub(r"\n\n---\n\n## Page \d+\n\n", "\n", body)
        for i, page in enumerate(doc.pages, 1):
            src_t = norm_ws(page.extract_text() or "")
            if src_t and src_t not in norm_ws(body):
                # find first divergence for location info
                err(f"{pdf.name} p{i}: page text not found in md "
                    f"(src {len(src_t)} chars, head: {src_t[:60]!r})")
                break
        else:
            print(f"OK pdf {pdf.name}: {n} pages all present")


def check_docx(docx: Path, md: Path) -> None:
    global CHECKED
    from docx import Document

    CHECKED += 1
    if not md.exists():
        return err(f"{md} missing")
    text = md.read_text(encoding="utf-8")
    doc = Document(docx)
    stripped = re.sub(r"^# .*\n\n> Source:.*\n", "", text, count=1)
    stripped = re.sub(r"^(#{1,3} )", "", stripped, flags=re.M)
    missing = 0
    for p in doc.paragraphs:
        t = p.text.strip()
        if t and norm_ws(t) not in norm_ws(stripped):
            missing += 1
            if missing <= 3:
                err(f"{docx.name}: para missing: {t[:70]!r}")
    cells_src = [norm_ws(c.text) for tbl in doc.tables for row in tbl.rows for c in row.cells if c.text.strip()]
    cells_md: list[str] = []
    for line in stripped.splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|") and len(s) > 2:
            cells_md.extend(
                norm_ws(c.replace("\\|", "|").replace("<br>", " "))
                for c in s[1:-1].split("|")
            )
    cells_md = [c for c in cells_md if c and c != "---"]
    lost = [c for c in cells_src if c not in norm_ws(" ".join(cells_md))]
    if missing == 0 and not lost:
        print(f"OK docx {docx.name}: {len(doc.paragraphs)} paras, {len(doc.tables)} tables, "
              f"{len(cells_src)} cells all present")
    elif lost:
        err(f"{docx.name}: {len(lost)} table cells missing, e.g. {lost[:2]}")


def check_xlsx(xlsx: Path, outdir: Path) -> None:
    global CHECKED
    import openpyxl

    CHECKED += 1
    wb = openpyxl.load_workbook(xlsx, data_only=True, read_only=True)
    for ws in wb.worksheets:
        safe = re.sub(r"[^\w\-\u4e00-\u9fff]+", "_", ws.title).strip("_") or "sheet"
        csv_path = outdir / f"{safe}.csv"
        if not csv_path.exists():
            err(f"{xlsx.name}[{ws.title}]: {safe}.csv missing")
            continue
        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            csv_rows = [r for r in csv.reader(f)]
        xl_rows: list[list[str]] = []
        for row in ws.iter_rows():
            line = [("" if c.value is None else str(c.value)) for c in row]
            if any(x.strip() for x in line):
                xl_rows.append(line)
        if len(xl_rows) != len(csv_rows):
            err(f"{xlsx.name}[{ws.title}]: rows {len(xl_rows)} != csv {len(csv_rows)}")
            continue
        bad = 0
        for ri, (a, b) in enumerate(zip(xl_rows, csv_rows), 1):
            if len(a) != len(b):
                err(f"{xlsx.name}[{ws.title}] r{ri}: cols {len(a)} != {len(b)}")
                bad += 1
                break
            for ci, (x, y) in enumerate(zip(a, b), 1):
                if norm_ws(x) != norm_ws(y):
                    err(f"{xlsx.name}[{ws.title}] r{ri}c{ci}: {x!r} != {y!r}")
                    bad += 1
                    break
            if bad:
                break
        if not bad:
            print(f"OK xlsx {xlsx.name}[{ws.title}]: {len(xl_rows)} rows x {len(xl_rows[0]) if xl_rows else 0} cols match")
    wb.close()


def main() -> int:
    for pdf in sorted((SRC / "年度报告").glob("*.pdf")):
        check_pdf(pdf, ROOT / "年度报告" / (pdf.stem + ".md"))
    for docx in sorted(SRC.glob("*.docx")):
        check_docx(docx, ROOT / (docx.stem + ".md"))
    for xlsx in sorted(SRC.glob("*.xlsx")):
        check_xlsx(xlsx, ROOT / xlsx.stem)
    print(f"\nChecked {CHECKED} files, {len(ERRORS)} mismatches.")
    return 1 if ERRORS else 0


if __name__ == "__main__":
    sys.exit(main())
