"""共享的 PDF 转文本工具。

原先 27 个 `extract_*.py` 各自复制了一份 `pdf_text()`，都直接
`subprocess.run(["pdftotext", ...])` 且不检查可执行文件是否存在。
在没装 poppler 的机器上，这会抛裸的 `FileNotFoundError`，看不出是缺依赖。

本模块把「调用 pdftotext」和「检查依赖」放在一处，并统一剥离页眉。

依赖：`pdftotext`（macOS: `brew install poppler`；Debian: `apt install poppler-utils`）。
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

# 页眉正则在 19 个脚本里各写过一遍，都只匹配「年年度报告」，
# 导致半年报的「2026 年半年度报告」页眉残留，进而被当成金额解析
# （实测会让 extract_goodwill 在格力半年报上多出一行 2026.0）。
_HEADER = re.compile(
    r"[\u4e00-\u9fa5（）()]+(?:股份有限公司|集团股份有限公司)"
    r"\s*\d{4}\s*年(?:半)?年度报告(?:全文)?"
)


class PdfToolMissingError(RuntimeError):
    """缺少 pdftotext 可执行文件。"""


def require_pdftotext() -> str:
    """返回 pdftotext 路径；缺失时给出可执行的安装提示。"""
    found = shutil.which("pdftotext")
    if found:
        return found
    raise PdfToolMissingError(
        "缺少 pdftotext，无法解析 PDF。\n"
        "  macOS : brew install poppler\n"
        "  Ubuntu: sudo apt install poppler-utils\n"
        "  conda : conda install -c conda-forge poppler"
    )


def pdf_text(pdf: Path | str, layout: bool = True, timeout: int = 300) -> str:
    """把 PDF 转为文本。缺失 poppler 时抛 `PdfToolMissingError`。"""
    binary = require_pdftotext()
    cmd = [binary]
    if layout:
        cmd.append("-layout")
    cmd += [str(pdf), "-"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext 失败（{pdf}）：{result.stderr.strip()[:300]}")
    return result.stdout


def report_pdf(root: Path, stem: str) -> Path:
    """只接受原始 PDF；历史报告可预置于 /tmp/fsr/pdf_hist，绝不读取旧 txt。"""
    candidates = (root / "年度报告" / f"{stem}.pdf", Path("/tmp/fsr/pdf_hist") / f"{stem}.pdf")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"缺少原始报告 {stem}.pdf；请按定期报告/定期报告清单.csv 下载至年度报告/"
        "或 /tmp/fsr/pdf_hist/，不能以无来源的文本缓存代替"
    )


def strip_headers(text: str) -> str:
    """删除跨页页眉，避免页眉里的年份/公司名被当作表格数据。"""
    return _HEADER.sub(" ", text)


def flatten(text: str) -> str:
    """pdf_text + 删页眉。多数提取脚本需要的就是这一步。"""
    return strip_headers(text)


def fail_fast() -> int:
    """在脚本入口调用，缺依赖时打印中文提示并返回非零退出码。"""
    try:
        require_pdftotext()
    except PdfToolMissingError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0
