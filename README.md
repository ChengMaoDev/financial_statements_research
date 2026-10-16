# 白色家电企业财务报表分析

围绕美的集团（000333.SZ）、海尔智家（600690.SH）和格力电器（000651.SZ），结合商业模式、会计政策、财务报表与行业环境开展横向比较，重点解释盈利质量、现金流和经营差异的成因。

研究期间为 **2023—2025 年度及 2026 年半年度**。仓库保留原始材料，并提供方便 AI 检索和程序处理的 Markdown、CSV 副本。现有分析文档和比较表属于研究输入，引用其中的结论与数字前仍需核对来源。

## 从哪里开始

- [Prompt.md](Prompt.md)：任务范围、研究阶段与预期交付物。
- [分析内容概述.md](分析内容概述.md)：三家公司定位及已有分析概览。
- [年度报告/](年度报告/)：按公司、期间命名的报告文本，供检索与定位。
- [财务比较/](财务比较/)：年度及半年度指标比较，附来源和口径说明。
- [空调ASP与大宗商品成本传导.md](空调ASP与大宗商品成本传导.md)：空调平均售价、原材料成本与毛利率的专项分析。
- [空调ASP与大宗商品数据/](空调ASP与大宗商品数据/)：对应数据、情景假设、敏感性分析和来源链接。

## 目录结构

```text
.
├── origin/                       # 原始材料：12 PDF、3 DOCX、2 XLSX
│   ├── 年度报告/                 # 三家公司各四个报告期间
│   └── *.docx / *.xlsx
├── 年度报告/                     # 12 份报告的 Markdown 文本
├── Prompt.md
├── 分析内容概述.md
├── 空调ASP与大宗商品成本传导.md
├── 财务比较/                     # 每张工作表一个 CSV
├── 空调ASP与大宗商品数据/         # 每张工作表一个 CSV
├── scripts/
│   ├── convert_to_text.py         # 原始材料转换
│   └── verify_conversion.py       # 转换内容校验
├── AGENTS.md                     # AI 协作核心约定
└── README.md
```

## 阅读与引用

优先用根目录下的 Markdown 和 CSV 检索、提取与计算；遇到关键数字、表格结构或口径疑问，回到 `origin/` 中的原件核实。

- PDF 文本以 `## Page N` 标记原文件的第 N 页；这是 PDF 文件页序，可能与报告印刷页码不同。
- CSV 按原工作表拆分，使用 UTF-8 BOM 编码，跳过全空行；单位、期间和口径沿用原表，未统一标准化。
- 引用关键数字时记录公司、指标、数值、单位、期间、合并口径，以及原文件路径和页码或表名。区分披露值、计算值、估算和分析判断。

## 转换与校验

在仓库根目录运行，需已安装 Python、`uv` 和 Poppler（提供 `pdftotext`）。Python 依赖通过 `uv` 临时环境提供。

先输出到独立目录试转，不覆盖仓库现有文件：

```sh
uv run --with python-docx --with openpyxl python3 scripts/convert_to_text.py --output-dir /path/to/conversion-preview
uv run --with python-docx --with openpyxl python3 scripts/verify_conversion.py --output-dir /path/to/conversion-preview
```

检查试转结果后，才覆盖根目录中的转换件：

```sh
uv run --with python-docx --with openpyxl python3 scripts/convert_to_text.py --overwrite
uv run --with python-docx --with openpyxl python3 scripts/verify_conversion.py
```

转换脚本默认拒绝覆盖已有文件；只有明确传入 `--overwrite` 才会替换。若转换件有人工修订，先备份或单独保存。支持 `--only pdf|docx|xlsx` 对单类文件试转。

转换与校验的范围：

- **PDF**：使用 `pdftotext -layout` 保留接近原页面的列间距，并用等宽文本块和 PDF 实际页序标记；报告印刷页码可能不同。校验页数和提取文本。复杂表格没有强行重建成 Markdown 表格，关键数字仍须对照原 PDF 页面。
- **DOCX**：按原文顺序输出段落与表格，保留标题样式和列表标记；校验逐项检查正文/表格文字及其顺序。图片、字体、颜色和精确分页不转换。
- **XLSX**：每个工作表输出一个 CSV；公式原文不会丢失，缓存结果会注明，缺失缓存明确标出。校验逐单元格检查值与公式；不重算公式。CSV 不保留单元格格式、合并区域或图表，口径/单位须对照原工作簿及表头核实。

校验通过表示内容和来源顺序符合上述检查，不代表版面完全等价，也不验证原始数字或研究结论。任何分析引用仍以 `origin/` 原件为准。

## 协作

保留 `origin/` 原件不变，通过脚本和可追溯的来源记录支持研究。按任务建立分支，经 PR 合并到 `main`；具体分析、证据和协作约定见 [AGENTS.md](AGENTS.md)。
