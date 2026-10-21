"""提取三家年报中引用的第三方行业数据与自身产销量。

年报「行业情况」章节会转引权威机构数据，这些引用：
- 原始来源可靠（奥维云网、产业在线、GfK 中怡康、海关总署、国家统计局、Euromonitor）
- 免费可获取（已写在年报里，无需购买付费数据库）
- 可与付费库口径对照

同时提取公司自己披露的产销量（A 级一手数据）。

用法：
    uv run python3 scripts/extract_industry_data.py --all
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "年度报告"
OUT_INDUSTRY = ROOT / "市场数据" / "行业数据_年报引用.csv"
OUT_VOLUME = ROOT / "市场数据" / "公司产销量.csv"

REPORTS = {
    "美的集团": ["美的2023.pdf", "美的2024.pdf", "美的2025.pdf"],
    "海尔智家": ["海尔2023.pdf", "海尔2024.pdf", "海尔2025.pdf"],
    "格力电器": ["格力2023.pdf", "格力2024.pdf", "格力2025.pdf"],
}

# 机构 → 在正文中的称谓
SOURCES = [
    ("奥维云网", ["奥维云网（AVC）", "奥维云网", "奥维统计", "奥维数据", "AVC"]),
    ("产业在线", ["产业在线"]),
    ("GfK中怡康", ["GfK 中怡康", "GfK中怡康", "中怡康"]),
    ("海关总署", ["海关总署"]),
    ("国家统计局", ["国家统计局"]),
    ("Euromonitor", ["Euromonitor", "欧睿"]),
]


def pdf_text(pdf: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    return result.stdout


def flatten(text: str) -> str:
    """压平换行，保留句读，便于整句抽取。"""
    text = re.sub(r"\d+ / \d+\s*", " ", text)
    text = re.sub(
        r"[\u4e00-\u9fa5]{2,12}(?:股份有限公司|集团股份有限公司)\s*\d{4}\s*年(?:半)?年度报告(?:全文)?",
        " ",
        text,
    )
    return re.sub(r"\s+", " ", text)


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[。；]", text) if len(s.strip()) >= 12]


def extract_industry(text: str, company: str, year: str) -> list[dict[str, str]]:
    """抓含机构名且含数字的句子。"""
    flat = flatten(text)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for sentence in split_sentences(flat):
        if not re.search(r"\d", sentence):
            continue
        for label, aliases in SOURCES:
            if not any(alias in sentence for alias in aliases):
                continue
            key = re.sub(r"\s", "", sentence)[:80]
            if key in seen:
                break
            seen.add(key)
            # 抽出句子里的所有数值+单位，便于结构化引用
            metrics = re.findall(
                r"(\d[\d,]*\.?\d*)\s*(亿元|万台|亿台|亿美元|个百分点|%|元)", sentence
            )
            rows.append(
                {
                    "公司": company,
                    "年度": year,
                    "数据来源": label,
                    "原文": sentence[:300],
                    "数值个数": str(len(metrics)),
                    "数据性质": "第三方引用",
                }
            )
            break
    return rows


def extract_volume(text: str, company: str, year: str) -> list[dict[str, str]]:
    """公司自披露产销量。"""
    flat = flatten(text)
    rows: list[dict[str, str]] = []

    # 美的/海尔式：销售量 万台/套 X Y Z%
    for metric in ["销售量", "生产量", "库存量"]:
        match = re.search(
            rf"{metric}\s+万台/套\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+(-?[\d.]+)%",
            flat,
        )
        if match:
            rows.append(
                {
                    "公司": company,
                    "年度": year,
                    "指标": metric,
                    "本期": match.group(1).replace(",", ""),
                    "上期": match.group(2).replace(",", ""),
                    "同比": match.group(3),
                    "单位": "万台/套",
                    "口径": "家用电器行业合计",
                    "数据性质": "披露值",
                }
            )

    # 海尔式：家用电器 万台/套 生产量 销售量 库存量 三个同比
    if not rows:
        match = re.search(
            r"家用电器\s+万台/套\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)",
            flat,
        )
        if match:
            for index, metric in enumerate(["生产量", "销售量", "库存量"]):
                rows.append(
                    {
                        "公司": company,
                        "年度": year,
                        "指标": metric,
                        "本期": match.group(index + 1).replace(",", ""),
                        "上期": "",
                        "同比": match.group(index + 4),
                        "单位": "万台/套",
                        "口径": "家用电器",
                        "数据性质": "披露值",
                    }
                )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all", action="store_true", default=True, help="默认执行全部；保留该开关用于兼容旧命令"
    )
    args = parser.parse_args()
    if not args.all:  # 默认 True；仅显式 --no-all 时才打印帮助
        parser.print_help()
        return 1

    industry: list[dict[str, str]] = []
    volume: list[dict[str, str]] = []
    for company, files in REPORTS.items():
        for filename in files:
            pdf = PDF_DIR / filename
            if not pdf.exists():
                print(f"  缺少 {filename}", file=sys.stderr)
                continue
            year_match = re.search(r"(20\d{2})", filename)
            if not year_match:
                continue
            year = year_match.group(1)
            text = pdf_text(pdf)
            industry_rows = extract_industry(text, company, year)
            volume_rows = extract_volume(text, company, year)
            industry.extend(industry_rows)
            volume.extend(volume_rows)
            sources = {}
            for row in industry_rows:
                sources[row["数据来源"]] = sources.get(row["数据来源"], 0) + 1
            print(
                f"  {company} {year}: 行业引用 {len(industry_rows)} 条 {sources}, 产销量 {len(volume_rows)} 条"
            )

    OUT_INDUSTRY.parent.mkdir(parents=True, exist_ok=True)
    with OUT_INDUSTRY.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["公司", "年度", "数据来源", "原文", "数值个数", "数据性质"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(industry)
    print(f"\n写入 {OUT_INDUSTRY.relative_to(ROOT)}: {len(industry)} 行")

    with OUT_VOLUME.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["公司", "年度", "指标", "本期", "上期", "同比", "单位", "口径", "数据性质"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(volume)
    print(f"写入 {OUT_VOLUME.relative_to(ROOT)}: {len(volume)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
