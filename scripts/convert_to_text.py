"""Create structure-aware, source-traceable text derivatives of project files.

PDF uses Poppler's layout-preserving text extraction, with explicit page markers.
DOCX preserves paragraph/table order. XLSX exports each sheet and never drops formulas.
Originals remain untouched. By default outputs go to repo root; --output-dir supports
safe pilot runs. Existing targets are refused unless --overwrite is supplied.
"""
from __future__ import annotations

import argparse
import csv
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, time
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "origin"


def write_text(path: Path, text: str, overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite {path}; use --overwrite after review")
    path.write_text(text, encoding="utf-8")


def safe_sheet_name(name: str) -> str:
    return re.sub(r"[^\w\-\u4e00-\u9fff]+", "_", name).strip("_") or "sheet"


def convert_pdf(src: Path, dst: Path, overwrite: bool) -> None:
    if shutil.which("pdftotext") is None:
        raise RuntimeError("pdftotext (Poppler) is required for layout-preserving PDF extraction")
    result = subprocess.run(
        ["pdftotext", "-layout", str(src), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    pages = result.stdout.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    out = [
        f"# {src.stem}\n",
        f"> Source: `{src.relative_to(ROOT)}`\n",
        "> PDF page text extracted with Poppler `-layout`; spaces approximate original columns.\n",
        "> Tables are not reconstructed as Markdown tables. Verify important figures against the source PDF.\n",
    ]
    for number, page in enumerate(pages, 1):
        lines = [line.rstrip() for line in page.splitlines()]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        text = "\n".join(lines)
        out.extend([f"\n---\n\n## PDF page {number}\n\n```text\n{text}\n```\n"])
    write_text(dst, "\n".join(out), overwrite)
    print(f"PDF {src.name}: {len(pages)} layout-preserved pages")


def escape_cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def paragraph_markdown(paragraph: object, document: object) -> str:
    from docx.oxml.ns import qn

    text = paragraph.text.strip()
    if not text:
        return ""
    style = (paragraph.style.name or "").lower()
    if style.startswith("heading"):
        match = re.search(r"(\d+)$", style)
        level = min(int(match.group(1)), 6) if match else 2
        return f"{'#' * level} {text}"
    if "list bullet" in style:
        return f"- {text}"
    if "list number" in style:
        return f"1. {text}"
    properties = paragraph._p.pPr
    numbering = properties.numPr if properties is not None else None
    if numbering is not None and numbering.numId is not None:
        number_id = numbering.numId.val
        level_id = numbering.ilvl.val if numbering.ilvl is not None else 0
        numbering_root = document.part.numbering_part.element
        number = next((item for item in numbering_root.num_lst if item.numId == number_id), None)
        abstract_id = number.abstractNumId.val if number is not None else None
        abstract = next(
            (item for item in numbering_root.xpath("./w:abstractNum")
             if item.get(qn("w:abstractNumId")) == str(abstract_id)),
            None,
        )
        levels = [
            level for level in abstract.findall(qn("w:lvl"))
            if level.get(qn("w:ilvl")) == str(level_id)
        ] if abstract is not None else []
        formats = levels[0].findall(qn("w:numFmt")) if levels else []
        number_format = formats[0].get(qn("w:val")) if formats else "bullet"
        return f"1. {text}" if number_format == "decimal" else f"- {text}"
    return text


def convert_docx(src: Path, dst: Path, overwrite: bool) -> None:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(src)
    out = [f"# {src.stem}\n", f"> Source: `{src.relative_to(ROOT)}`\n"]
    paragraph_count = 0
    table_count = 0
    for child in doc.element.body.iterchildren():
        if child.tag.endswith("}p"):
            paragraph = Paragraph(child, doc)
            rendered = paragraph_markdown(paragraph, doc)
            if rendered:
                out.append(rendered)
                paragraph_count += 1
        elif child.tag.endswith("}tbl"):
            table = Table(child, doc)
            table_count += 1
            table_lines = [f"**Table {table_count} (source order)**", ""]
            rows = [[escape_cell(cell.text.strip()) for cell in row.cells] for row in table.rows]
            width = max((len(row) for row in rows), default=0)
            for row_index, row in enumerate(rows):
                row += [""] * (width - len(row))
                table_lines.append("| " + " | ".join(row) + " |")
                if row_index == 0:
                    table_lines.append("| " + " | ".join(["---"] * width) + " |")
            out.append("\n".join(table_lines))
    write_text(dst, "\n\n".join(out) + "\n", overwrite)
    print(f"DOCX {src.name}: {paragraph_count} paragraphs, {table_count} tables in source order")


def cell_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return str(value)


def convert_xlsx(src: Path, outdir: Path, overwrite: bool) -> None:
    import openpyxl

    values = openpyxl.load_workbook(src, data_only=True, read_only=False)
    formulas = openpyxl.load_workbook(src, data_only=False, read_only=False)
    for ws_value, ws_formula in zip(values.worksheets, formulas.worksheets):
        safe = safe_sheet_name(ws_value.title)
        csv_path = outdir / f"{safe}.csv"
        if not overwrite and csv_path.exists():
            raise FileExistsError(f"Refusing to overwrite worksheet outputs for {src.name}[{ws_value.title}]")
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        formulas_found = 0
        no_cache = 0
        output_rows: list[list[str]] = []
        for row_value, row_formula in zip(ws_value.iter_rows(), ws_formula.iter_rows()):
            row: list[str] = []
            for value_cell, formula_cell in zip(row_value, row_formula):
                formula = formula_cell.value
                value = value_cell.value
                if isinstance(formula, str) and formula.startswith("="):
                    formulas_found += 1
                    cached = cell_value(value)
                    if value is None:
                        no_cache += 1
                        row.append(f"FORMULA (cached result unavailable): {formula}")
                    else:
                        row.append(f"FORMULA: {formula} | CACHED VALUE: {cached}")
                else:
                    row.append(cell_value(value))
            if any(item.strip() for item in row):
                output_rows.append(row)
        with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
            csv.writer(stream, lineterminator="\n").writerows(output_rows)
        print(f"XLSX {src.name}[{ws_value.title}]: {len(output_rows)} rows, {formulas_found} formulas ({no_cache} without cached result)")
    values.close()
    formulas.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT, help="Output root (default: repository root)")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing existing converted files")
    parser.add_argument("--only", choices=["all", "pdf", "docx", "xlsx"], default="all")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output_dir.resolve()
    pdfs: Iterable[Path] = sorted((SRC / "年度报告").glob("*.pdf")) if args.only in ("all", "pdf") else []
    docxs: Iterable[Path] = sorted(SRC.glob("*.docx")) if args.only in ("all", "docx") else []
    xlsxs: Iterable[Path] = sorted(SRC.glob("*.xlsx")) if args.only in ("all", "xlsx") else []
    try:
        for src in pdfs:
            convert_pdf(src, output / "年度报告" / f"{src.stem}.md", args.overwrite)
        for src in docxs:
            convert_docx(src, output / f"{src.stem}.md", args.overwrite)
        for src in xlsxs:
            convert_xlsx(src, output / src.stem, args.overwrite)
    except (FileExistsError, OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Conversion stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
