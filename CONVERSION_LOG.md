# Conversion log (2026-10-16 11:52 UTC)

Method: `scripts/convert_to_text.py` (pdfplumber page text; python-docx headings/paras/tables; openpyxl cached values per sheet).
Originals unchanged. Units/signs/scopes NOT normalized here; verify against filings before quoting.

- Found 12 PDFs, 3 DOCX, 2 XLSX.
- PDF 格力2023.pdf: 249 pages, 240813 chars, 0 empty.
- PDF 格力2024.pdf: 248 pages, 248856 chars, 0 empty.
- PDF 格力2025.pdf: 219 pages, 230192 chars, 0 empty.
- PDF 格力2026半年度.pdf: 190 pages, 184245 chars, 0 empty.
- PDF 海尔2023.pdf: 243 pages, 237157 chars, 0 empty.
- PDF 海尔2024.pdf: 247 pages, 248144 chars, 0 empty.
- PDF 海尔2025.pdf: 245 pages, 246152 chars, 0 empty.
- PDF 海尔2026半年度.pdf: 192 pages, 194400 chars, 0 empty.
- PDF 美的2023.pdf: 291 pages, 270681 chars, 0 empty.
- PDF 美的2024.pdf: 295 pages, 274859 chars, 0 empty.
- PDF 美的2025.pdf: 276 pages, 253471 chars, 0 empty.
- PDF 美的2026半年度.pdf: 205 pages, 198218 chars, 0 empty.
- DOCX Prompt.docx: 105 paras, 0 tables.
- DOCX 分析内容概述.docx: 94 paras, 3 tables.
- DOCX 空调ASP与大宗商品成本传导.docx: 65 paras, 8 tables.
- XLSX 空调ASP与大宗商品数据.xlsx [ASP_结论]: 4 non-empty rows -> ASP_结论.csv (5 formula cells; saved cached values, NOT verified)
- XLSX 空调ASP与大宗商品数据.xlsx [ASP_单匹情景]: 10 non-empty rows -> ASP_单匹情景.csv (9 formula cells; saved cached values, NOT verified)
- XLSX 空调ASP与大宗商品数据.xlsx [ASP_行业校验]: 6 non-empty rows -> ASP_行业校验.csv
- XLSX 空调ASP与大宗商品数据.xlsx [ASP_财报口径限制]: 4 non-empty rows -> ASP_财报口径限制.csv
- XLSX 空调ASP与大宗商品数据.xlsx [大宗商品_年度]: 5 non-empty rows -> 大宗商品_年度.csv
- XLSX 空调ASP与大宗商品数据.xlsx [大宗商品_月度原始]: 46 non-empty rows -> 大宗商品_月度原始.csv
- XLSX 空调ASP与大宗商品数据.xlsx [大宗商品_同比]: 8 non-empty rows -> 大宗商品_同比.csv
- XLSX 空调ASP与大宗商品数据.xlsx [成本暴露与库存]: 4 non-empty rows -> 成本暴露与库存.csv
- XLSX 空调ASP与大宗商品数据.xlsx [毛利率敏感性]: 4 non-empty rows -> 毛利率敏感性.csv
- XLSX 空调ASP与大宗商品数据.xlsx [来源链接]: 12 non-empty rows -> 来源链接.csv
- XLSX 空调ASP与大宗商品数据.xlsx [README]: 7 non-empty rows -> README.csv
- XLSX 财务比较.xlsx [年度财务对比]: 10 non-empty rows -> 年度财务对比.csv
- XLSX 财务比较.xlsx [2026H1]: 4 non-empty rows -> 2026H1.csv
- XLSX 财务比较.xlsx [指标口径与局限]: 9 non-empty rows -> 指标口径与局限.csv
- XLSX 财务比较.xlsx [来源]: 19 non-empty rows -> 来源.csv

## 2026-10-16 restructure
- Originals moved to `origin/` (git mv, history preserved); converted files mirrored at repo root.
- Script updated: inputs from `origin/`, outputs at root.

## 2026-10-16 verification (`scripts/verify_conversion.py`)
- 17 files checked, 0 mismatches: 12 PDF (page counts + full page text), 3 DOCX (paras + table cells), 2 XLSX x 15 sheets (cell-by-cell cached values).
- Note: XLSX compared against cached values; 14 formula cells NOT re-evaluated. Verifier itself fixed once (table-cell regex skipped alternate cells).
