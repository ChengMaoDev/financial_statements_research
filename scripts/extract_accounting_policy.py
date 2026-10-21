"""提取三家公司的关键会计政策，用于横向可比性判断。

为什么这张表必读：
同样的收入、同样的资产，会计政策不同，毛利率和净利润就不可比。本表聚焦
四个对家电企业影响最大的政策：

1. 存货计价方法 —— 铜价 2026 年上涨 28.6%，先进先出（美的）会更快把
   高价铜计入成本，加权平均（海尔、格力）则有平滑效果。
2. 固定资产折旧年限 —— 格力机器设备 6–10 年，美的 2–25 年、海尔 4–20 年。
   折旧年限越短，当期成本越高、利润越保守。
3. 应收账款坏账计提 —— 格力 3 年以上计提 97.81%，海尔 64.56%，美的按
   组合模型（境内 3.89% / 境外 1.07%），口径完全不同。
4. 研发支出资本化 —— 海尔部分资本化，美的、格力全部费用化。

文字类政策无法用正则可靠抽取，采用「关键词存在性校验 + 人工确认取值」：
脚本会断言每个结论对应的关键词确实出现在当年年报中，防止张冠李戴。

用法：
    uv run python3 scripts/extract_accounting_policy.py --all
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
OUT = ROOT / "财务数据" / "会计政策对比.csv"

REPORTS = {"美的集团": "美的2025.pdf", "海尔智家": "海尔2025.pdf", "格力电器": "格力2025.pdf"}

# (类别, 折旧年限正则模板) —— 通过类名定位，再取该行内的年数区间
DEPRECIATION = {
    "美的集团": [
        ("房屋及建筑物", r"房屋及建筑物\s*(\d+)-(\d+)\s*年"),
        ("机器设备", r"机器设备\s*(\d+)-(\d+)\s*年"),
        ("运输工具", r"运输工具\s*(\d+)-(\d+)\s*年"),
        ("电子设备及其他", r"电子设备及其他\s*(\d+)-(\d+)\s*年"),
    ],
    "海尔智家": [
        ("房屋建筑物", r"房屋建筑物\s*年限平均法\s*(\d+)-(\d+)"),
        ("机器设备", r"机器设备\s*年限平均法\s*(\d+)-(\d+)"),
        ("运输设备", r"运输设备\s*年限平均法\s*(\d+)-(\d+)"),
        ("办公及其他设备", r"办公及其他设备\s*年限平均法\s*(\d+)-(\d+)"),
    ],
    "格力电器": [
        ("房屋、建筑物", r"房屋、建筑物\s*5\.00\s*(\d+)\.00\s*"),
        ("机器设备", r"机器设备\s*5\.00\s*(\d+)\.00-(\d+)\.00"),
        ("电子设备", r"电子设备\s*5\.00\s*(\d+)\.00-(\d+)\.00"),
        ("运输设备", r"运输设备\s*5\.00\s*(\d+)\.00-(\d+)\.00"),
    ],
}

# 文字类政策：结论 + 必须在年报中出现的关键词（用于自动校验）
# forbidden：必须【不】出现的关键词，用于验证「全部费用化」这类否定结论
POLICY = {
    "美的集团": [
        ("存货计价方法", "先进先出法", ["先进先出法"], []),
        (
            "应收账款坏账计提方法",
            "组合预期信用损失模型（境内 3.89%、境外 1.07%）",
            ["境内业务组合", "境外业务组合"],
            [],
        ),
        (
            "研发支出资本化",
            "全部费用化（年报未披露本期资本化研发投入）",
            ["研发投入"],
            ["本期资本化研发投入"],
        ),
        ("销售返利", "附注单列「预提销售返利」", ["预提销售返利"], []),
    ],
    "海尔智家": [
        ("存货计价方法", "加权平均法", ["加权平均法"], []),
        (
            "应收账款坏账计提方法",
            "账龄组合（1 年以内 1.24%，3 年以上 64.56%）",
            ["应收账款按账龄披露"],
            [],
        ),
        (
            "研发支出资本化",
            "部分资本化（2025 年资本化率 5.79%）",
            ["本期资本化研发投入", "研发投入资本化的比重"],
            [],
        ),
        ("销售返利", "仅披露计提政策，不单列金额", ["销售返利的计提"], []),
    ],
    "格力电器": [
        ("存货计价方法", "月末一次加权平均法", ["月末一次加权平均法"], []),
        (
            "应收账款坏账计提方法",
            "账龄组合（1 年以内 3.34%，3 年以上 97.81%）",
            ["按账龄组合计提坏账准备"],
            [],
        ),
        (
            "研发支出资本化",
            "全部费用化（年报未披露本期资本化研发投入）",
            ["研发投入"],
            ["本期资本化研发投入"],
        ),
        ("销售返利", "附注单列「销售返利」", ["销售返利"], []),
    ],
}


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
    text = re.sub(r"\b\d{1,3}\s*/\s*\d{1,3}\b", " ", text)
    text = re.sub(
        r"[\u4e00-\u9fa5（）()]+股份有限公司\s*\d{4}\s*年(?:半)?年度报告(?:全文)?", " ", text
    )
    text = re.sub(r"(?m)^\s*\d{2,3}\s*$", " ", text)
    return re.sub(r"\s+", " ", text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all", action="store_true", default=True, help="默认执行全部；保留该开关用于兼容旧命令"
    )
    args = parser.parse_args()
    if not args.all:  # 默认 True；仅显式 --no-all 时才打印帮助
        parser.print_help()
        return 1

    rows: list[dict[str, str]] = []
    for company, filename in REPORTS.items():
        pdf = PDF_DIR / filename
        if not pdf.exists():
            print(f"  缺少 {filename}", file=sys.stderr)
            continue
        flat = flatten(pdf_text(pdf))

        # 折旧年限
        for category, pattern in DEPRECIATION[company]:
            match = re.search(pattern, flat)
            if not match:
                print(f"  {company} 未匹配折旧：{category}", file=sys.stderr)
                continue
            groups = [g for g in match.groups() if g is not None]
            span = f"{groups[0]}–{groups[1]} 年" if len(groups) >= 2 else f"{groups[0]} 年"
            rows.append(
                {
                    "公司": company,
                    "政策类别": "固定资产折旧年限",
                    "明细": category,
                    "取值": span,
                    "来源": filename,
                    "数据性质": "披露值",
                }
            )

        # 文字类政策（含关键词校验）
        for category, conclusion, keywords, forbidden in POLICY[company]:
            missing = [k for k in keywords if k not in flat]
            present = [k for k in forbidden if k in flat]
            if missing or present:
                print(
                    f"  {company} 「{category}」校验失败：缺 {missing} / 不应出现 {present}，已跳过",
                    file=sys.stderr,
                )
                continue
            rows.append(
                {
                    "公司": company,
                    "政策类别": category,
                    "明细": "",
                    "取值": conclusion,
                    "来源": filename,
                    "数据性质": "披露值",
                }
            )

    fields = ["公司", "政策类别", "明细", "取值", "来源", "数据性质"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n{'公司':<8}{'政策':<22}{'明细':<14}{'取值'}")
    print("-" * 90)
    for row in rows:
        print(f"{row['公司']:<8}{row['政策类别']:<22}{row['明细']:<14}{row['取值']}")
    print(f"\n写入 {OUT.relative_to(ROOT)}: {len(rows)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
