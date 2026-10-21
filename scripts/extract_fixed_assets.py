"""固定资产与在建工程结构：折旧政策差异如何落到报表上。

为什么重要：
三家 2025 年固定资产账面价值 449.83 / 403.53 / 343.85 亿元（美的/海尔/格力），
占总资产 10%–14%，是家电企业最大的非流动资产。但**同一个「固定资产」科目，三家的
折旧口径差 2–3 倍**（口径陷阱 27/28）：

| 公司 | 房屋及建筑物 | 机器设备 | 电子设备 |
|---|---|---|---|
| 美的 | 15–50 年 | **2–25 年** | 2–20 年 |
| 海尔 | 8–40 年 | 4–20 年 | 3–10 年（办公及其他） |
| 格力 | 20 年 | **6–10 年** | **2–3 年** |

美的机器设备上限 25 年、格力下限 6 年，同样一台注塑机的年折旧率可以差 4 倍。
三家的毛利率、净利率**不是同一把尺子量出来的**：格力毛利率里含着最保守的折旧，
美的含着最宽松的。只看利润表会把这部分会计选择误读成经营能力。

但**折旧政策保守 ≠ 当期折旧率高**，2025 年的实测正好相反：

| 公司 | 计提折旧 | 期初原值 | 当期折旧率 | 累计折旧/原值 |
|---|---|---|---|---|
| 美的 | 51.17 亿 | 666.64 亿 | 7.68% | 44.1% |
| 海尔 | 52.90 亿 | 692.85 亿 | 7.64% | 45.9% |
| 格力 | 44.88 亿 | 762.66 亿 | **5.88%** | **54.8%** |

格力当期折旧率最低、累计折旧率最高——因为它的资产**更老**（大量设备已提足折旧、
不再计提），不是因为折旧慢。把「当期折旧率低」读成「折旧政策宽松」会得到完全
相反的结论。这也解释了格力毛利率为何仍能维持：老资产的历史成本低、折旧包袱轻。

第二个用途是**资本开支的时点判断**。在建工程是「已经花钱、还没转固、因此还不提
折旧」的蓄水池。美的在建工程账面价值从 2024 年 53.64 亿降到 2025 年 30.55 亿
（-43%），同期固定资产原值增加 142.12 亿——扩产在收尾。格力在建工程从 30.76 亿
降到 13.38 亿，但其中 11.55 亿已计提减值（格力钛工程不再建设），真实在建规模只剩
13.38 亿。

八个陷阱：

1. **单位不同**：美的年报附注用「千元」，海尔/格力用「元」。美的固定资产原值
   80,976,643 是千元（809.77 亿），不是元（8.10 亿）。本脚本对美的乘 1000。
2. **「固定资产」报表数与附注数不等**：格力资产负债表 343.96 亿包含「固定资产清理」
   0.11 亿，附注 21 的固定资产是 343.85 亿。美的/海尔没有固定资产清理。直接取
   资产负债表数会把格力高估 0.03%。
3. **在建工程的「余额」是账面余额，不是账面价值**：格力 2025 年期末在建工程余额
   24.93 亿、减值准备 11.55 亿、账面价值只有 13.38 亿。只报余额会把格力的在建规模
   高估 86%，也会让毛利率分析忽略格力钛工程那 11.42 亿的一次性减值。
4. **列在跨页处会重排**：海尔固定资产表第 181–183 页分两段，第一段是「房屋及建筑物/
   生产设备/运输设备」，第二段「办公设备/其他/合计」。按「每行取最后三个数」解析，
   会把第二段的合计列当成「其他」，海尔固定资产虚增 40 倍（74,742,864,410.65 vs
   1,554,864,455.86）。本脚本按**数字右边界聚类**定位列，每页重新聚类。
5. **格力的行标签被金额劈成三段**：「（2）投资性房地」/ 金额 / 「产转入」，
   「（3）在建工程转」/ 金额 / 「入」，「（1）处置或报」/ 金额 / 「废」。按行解析
   会得到「投资性房地」这种残缺标签，或把金额行当成无标签的合计。本脚本用
   carry + open_tail 拼接（见 `page_rows`），拼完必须命中 `FULL`。
6. **变动表的列数逐年变，且明细行会缺列**：格力 2025 年 7 列（期初/增加/转入固定资产/
   转入投资性房地产/处置/期末/利息资本化），2024 年也是 7 列但第二列是「本期合并
   范围变动」。明细行经常缺列（「格力钛工程」没有转入投资性房地产），按明细行聚类
   会少识别一列，把「处置」读成「期末」。本脚本只从**合计行**按顺序取变动表。
7. **变动表的明细行不能写死清单**：标签拼得对，不代表写进了 CSV。旧版 `emit_flow`
   只按一张固定清单（购置/在建工程转入/企业合并增加/计提/处置/汇率）落库，
   格力 2025 的「（2）投资性房地产转入 1.92 亿」「转至投资性房地产 −1.05 亿」解析
   正确却被整行丢掉：CSV 明细只有 26.82 亿，`本期增加` 却是 28.73 亿，
   762.66 + 16.48 = 779.14 ≠ 表内期末 780.00（差 0.86 亿）。现在明细行与
   「本期增加/减少」都从 `INCREASE`/`DECREASE` 同一份登记表派生，且表里出现未登记
   的标签、或解析到却没落库，都会在自校验里报出来，不再静默丢行。
8. **附注合计 ≠ 资产负债表「固定资产净额」**：两家报表口径不同。格力资产负债表把
   「固定资产清理」单列（2025 年 0.11 亿），本脚本比的是**不含清理**的「固定资产
   净额」343.85 亿，与附注 21 一致。海尔 2024 差 0.94 亿则是**追溯重述**：2025 年报
   因同一控制下企业合并（卡奥斯模具（青岛）有限公司，2025 年 3 月合并）重述了 2024
   年可比数，2024 年报的固定资产 37,518,645,325.08 + 卡奥斯模具上期期末固定资产
   94,570,444.38 = 37,613,215,769.46，正是 2025 年报的期初数（在建工程同理：
   57.08 + 0.06 = 57.14）。所以「附注数来自 2024 年报、资产负债表数来自 2025 年报
   的可比数」，差额不是取数错误。已登记在 `BOOK_GAP`，逐年核对金额。

自校验（stderr 报告）：
- 各类别账面价值相加 = 账面价值合计
- 原值 − 累计折旧 − 减值准备 = 账面价值（逐类别 + 合计）
- 变动表：期初 + 增加 − 减少 + 汇率变动 = 期末（原值、累计折旧、在建工程）
- 变动表明细行相加 = 本期增加 / 本期减少（逐公司逐年，防「解析到了却没写进 CSV」）
- 附注「账面价值合计」− 资产负债表「固定资产净额」= 0，或命中 `BOOK_GAP` 已登记口径差
- 2025 年报的期初 = 2024 年报的期末（跨年勾稽）

未取到的项：三家均未披露在建工程的「预算数」和「工程进度」（美的只写「与预算金额
匹配」，海尔/格力只给资金来源）。CSV 中以「数据性质=未披露」单列一行，不填 0。

用法：
    uv run python3 scripts/extract_fixed_assets.py --all
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "年度报告"
FIN = ROOT / "财务数据"
CACHE = Path("/tmp/fsr")
OUT = FIN / "固定资产与在建工程.csv"

# 固定资产按类别表的列布局。海尔跨页重排成「办公设备/其他/合计」，所以分两段。
FA_LAYOUT: dict[str, list[list[str]]] = {
    "美的集团": [["房屋及建筑物", "境外土地", "机器设备", "运输工具", "电子设备及其他", "合计"]],
    "海尔智家": [["房屋及建筑物", "生产设备", "运输设备"], ["办公设备", "其他", "合计"]],
    "格力电器": [["房屋及建筑物", "机器设备", "运输设备", "电子设备", "其他设备", "合计"]],
}

ROU_LAYOUT: dict[str, list[list[str]]] = {
    "美的集团": [["房屋及建筑物", "机器设备", "土地使用权及其他", "合计"]],
    "海尔智家": [["房屋及建筑物", "生产设备", "运输设备"], ["办公设备", "其他", "合计"]],
    "格力电器": [["房屋建筑物", "其他设备", "合计"]],
}

# 在建工程变动表：**合计行**的数字从左到右就是这些列。格力 2024 年第二列是
# 「本期合并范围变动」，语义与 2025 年不同，所以按 (公司, 年度) 分开给。
CWIP_COLS: dict[tuple[str, str], list[str]] = {
    ("美的集团", "2025"): [
        "期初余额",
        "本期增加",
        "转入固定资产",
        "其他减少",
        "汇率变动",
        "期末余额",
    ],
    ("美的集团", "2024"): [
        "期初余额",
        "本期增加",
        "转入固定资产",
        "其他减少",
        "汇率变动",
        "期末余额",
    ],
    ("海尔智家", "2025"): [
        "期初余额",
        "本期增加",
        "转入固定资产",
        "其他减少",
        "汇率变动",
        "期末余额",
    ],
    ("海尔智家", "2024"): [
        "期初余额",
        "本期增加",
        "转入固定资产",
        "其他减少",
        "汇率变动",
        "期末余额",
    ],
    ("格力电器", "2025"): [
        "期初余额",
        "本期增加",
        "转入固定资产",
        "转入投资性房地产",
        "处置",
        "期末余额",
        "利息资本化",
    ],
    ("格力电器", "2024"): [
        "期初余额",
        "合并范围变动",
        "本期增加",
        "转入固定资产",
        "处置",
        "期末余额",
        "利息资本化",
    ],
}

# 公司 → 年度 → (PDF, 千元→元, 固定资产附注, 在建工程附注, 使用权资产附注)
SOURCES: dict[str, dict[str, tuple[str, int, str, str, str]]] = {
    "美的集团": {
        "2025": ("美的2025.pdf", 1_000, "附注四(17)", "附注四(18)", "附注四(19)"),
        "2024": ("美的2024.pdf", 1_000, "附注四(18)", "附注四(19)", "附注四(20)"),
    },
    "海尔智家": {
        "2025": ("海尔2025.pdf", 1, "附注七、17", "附注七、18", "附注七、19"),
        "2024": ("海尔2024.pdf", 1, "附注七、17", "附注七、18", "附注七、19"),
    },
    "格力电器": {
        "2025": ("格力2025.pdf", 1, "附注五、21", "附注五、22", "附注五、23"),
        "2024": ("格力2024.pdf", 1, "附注五、21", "附注五、22", "附注五、23"),
    },
}

# 附注「固定资产账面价值合计」与资产负债表「固定资产净额」的已登记口径差。
# (公司, 年度) → (差额(亿元, 报表 − 附注), 原因)。差得对不上就报错，避免把新差异
# 用旧解释盖掉。
BOOK_GAP: dict[tuple[str, str], tuple[float, str]] = {
    ("海尔智家", "2024"): (
        0.94,
        "追溯重述：2025 年报因同一控制下企业合并（卡奥斯模具（青岛）有限公司，"
        "2025 年 3 月合并）重述了 2024 年可比数——2024 年报固定资产 37,518,645,325.08"
        " + 卡奥斯模具合并日上期期末固定资产 94,570,444.38 = 37,613,215,769.46，"
        "正是 2025 年报的期初数；本表分类别明细取自 2024 年报，资产负债表 2025 年报"
        "可比数，故差 0.94 亿。非取数错误",
    ),
}

TITLES = {"fa": "固定资产", "cwip": "在建工程", "rou": "使用权资产"}
STOPS = {"fa": ("在建工程", "使用权资产"), "cwip": ("使用权资产", "无形资产"), "rou": ("无形资产",)}
UNIFY = {"生产设备": "机器设备", "运输设备": "运输工具", "其他设备": "电子设备及其他"}

# 披露标签 → 规范名。不做这层映射，「处置」会同时命中「处置」和「处置、报废及其他」，
# 同一行被算两次（美的 2025 原值减少虚增一倍：-78.37 亿 vs 实际 -39.18 亿）。
CANON = {
    "账面原值": "原值",
    "原价": "原值",
    "企业合并增加": "企业合并增加",
    "非同一控制下企业合并": "企业合并增加",
    "处置或报废": "处置",
    "处置、报废及其他": "处置",
    "处置子公司": "处置子公司",
    "处置": "处置",
    "报废": "处置",
    "转至投资性房地产": "投资性房地产转出",
    "转为投资性房地产": "投资性房地产转出",
    "转入投资性房地产": "投资性房地产转出",
    "外币报表折算差额": "汇率变动",
    "外币报表折算": "汇率变动",
    "汇率变动及其他": "汇率变动",
    "本期增加金额": "本期增加",
    "本年增加": "本期增加",
    "本期减少金额": "本期减少",
    "本年减少": "本期减少",
}

# 变动表「本期增加 / 本期减少」的明细登记表：(表内标签, CSV 项目名)。
# `increase`/`decrease` 求和、`emit_flow` 落库、`check_movement` 校验都只认这一份，
# 三处不可能再走偏。旧版 `emit_flow` 单独写死一张清单，格力 2025 的「投资性房地产
# 转入 +1.91 亿 / 转至投资性房地产 −1.05 亿」解析对了却没落库，本期增加 28.73 亿
# 与明细 26.82 亿对不上，变动表差 0.86 亿。
INCREASE: dict[str, tuple[tuple[str, str], ...]] = {
    "原值": (
        ("购置", "购置"),
        ("在建工程转入", "在建工程转入"),
        ("企业合并增加", "企业合并增加"),
        ("投资性房地产转入", "投资性房地产转入"),
        ("其他", "其他增加"),
    ),
    "累计折旧": (
        ("计提", "计提"),
        ("企业合并增加", "企业合并增加"),
        ("投资性房地产转入", "投资性房地产转入"),
        ("其他", "其他增加"),
    ),
}
DECREASE: tuple[tuple[str, str], ...] = (
    ("处置", "处置或报废"),
    ("投资性房地产转出", "转至投资性房地产"),
    ("处置子公司", "处置子公司"),
    ("转入持有待售", "转入持有待售"),
)
# 变动表里不属于「增加/减少」明细的行
BASE_LABELS = ("期初余额", "期末余额", "本期增加", "本期减少", "汇率变动")

DATE = re.compile(r"^\s*\d{4}\s*年(?:\s*\d{1,2}\s*月)?(?:\s*\d{1,2}\s*日)?")
# 前后不能是字母数字，否则「库卡 B04」会被拆出 04
NUM = re.compile(
    r"(?<![A-Za-z0-9.,])\(-?[\d,]+(?:\.\d+)?\)"
    r"|(?<![A-Za-z0-9.,])-?\d[\d,]*(?:\.\d+)?(?![A-Za-z0-9])"
    r"|(?<=\s)-(?=\s|$)"
)
LEAD = re.compile(r"^\s*(?:[（(]\s*\d+\s*[）)]|\d+\s*[、.])")
PAREN_NO = re.compile(r"[（(]\s*\d+\s*[）)](?=\s*[\u4e00-\u9fa5A-Za-z])")
SECTION = re.compile(r"^[一二三四]\s*、\s*(账面原值|累计折旧|减值准备|账面价值)[：:]?$")
PAGE = re.compile(r"^\s*(?:\d{1,4}\s*/\s*\d{1,4}|\d{1,4})\s*$")

# 表内项目名。附注正文里也有数字（「计提的折旧金额为 5,117,232,000 元」），
# 只留命中这些前缀的行，否则正文会被当成表格行。
KEEP = (
    "期初余额",
    "期末余额",
    "期初账面价值",
    "期末账面价值",
    "本期增加",
    "本期减少",
    "本年增加",
    "本年减少",
    "购置",
    "在建工程转入",
    "企业合并增加",
    "非同一控制下企业合并",
    "投资性房地产转入",
    "转为投资性房地产",
    "转至投资性房地产",
    "转入投资性房地产",
    "转入持有待售",
    "处置或报废",
    "处置、报废及其他",
    "处置子公司",
    "报废",
    "处置",
    "其他",
    "计提",
    "汇率变动及其他",
    "外币报表折算",
    "合计",
)
# 完整的项目名：这类行单独成行（本年无发生额），不是被劈断的碎片
COMPLETE = (
    "购置",
    "在建工程转入",
    "企业合并增加",
    "非同一控制下企业合并",
    "投资性房地产转入",
    "转至投资性房地产",
    "转入投资性房地产",
    "转为投资性房地产",
    "转入持有待售",
    "处置或报废",
    "处置、报废及其他",
    "处置子公司",
    "报废",
    "处置",
    "其他",
    "计提",
    "汇率变动及其他",
    "外币报表折算差额",
    "本期增加金额",
    "本期减少金额",
    "本年增加",
    "本年减少",
)
# 「投资性房地」+ 金额 +「产转入」这类被劈断的标签，拼接后必须命中其中之一
FULL = (
    "投资性房地产转入",
    "转至投资性房地产",
    "转入投资性房地产",
    "转为投资性房地产",
    "在建工程转入",
    "处置或报废",
    "处置、报废及其他",
    "外币报表折算差额",
    "汇率变动及其他",
    "企业合并增加",
    "非同一控制下企业合并",
)


def text_of(pdf: Path) -> str:
    """优先用 /tmp/fsr 的 pdftotext -layout 缓存，缺了才重新转 PDF。"""
    cached = CACHE / f"{pdf.stem}.txt"
    if cached.exists():
        return cached.read_text(encoding="utf-8")
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    return result.stdout


def number(token: str) -> float:
    token = token.strip()
    if token == "-":
        return 0.0
    if token.startswith("(") and token.endswith(")"):
        return -float(token[1:-1].replace(",", ""))
    return float(token.replace(",", ""))


def clean(text: str) -> str:
    text = re.sub(r"\s+", "", text)
    return text.replace("其中：", "").replace("其中:", "").strip("：:")


def is_boundary(stripped: str) -> bool:
    """页码 / 页眉 / 「- 224 -」：跨页处列宽会重排，必须在这里切页。"""
    if PAGE.match(stripped):
        return True
    if "股份有限公司" in stripped and ("年度报告" in stripped or "财务报表附注" in stripped):
        return True
    return bool(re.match(r"^[-—–]\s*\d{1,4}\s*[-—–]$", stripped))


@dataclass
class Row:
    label: str
    values: list[float] = field(default_factory=list)
    ends: list[int] = field(default_factory=list)


@dataclass
class Table:
    header: list[str]
    rows: list[Row] = field(default_factory=list)

    def last(self, label: str) -> Row | None:
        """同名行会出现多次（日期行 + 文末合计行），取最后一个。

        label 会先过 CANON 映射，所以「处置、报废及其他」也能用「处置」取到。
        """
        name = CANON.get(label, label)
        hits = [row for row in self.rows if CANON.get(row.label, row.label) == name]
        return hits[-1] if hits else None

    def at(self, label: str, column: int | None = None) -> float | None:
        row = self.last(label)
        if row is None or not row.values:
            return None
        index = len(self.header) - 1 if column is None else column
        # 变动表把期初…期末压成单值行，这时只有第 0 个值，回落到它
        return row.values[index] if index < len(row.values) else row.values[-1]


def page_rows(lines: list[str], year: str, valued: bool, keep_only: bool = True) -> list[Row]:
    """一页 → [(标签, 数字, 右边界)]。valued 标明当前段是不是「账面价值」。

    格力的标签会被金额劈成三段：「（2）投资性房地」/ 金额 / 「产转入」。所以
    遇到半截标签时要记住它，等后续的尾巴行拼完整，规则是：
    - 纯文字行且是某个完整项目名的**真前缀** → 存为 carry，等下一行的数字；
    - 带数字的行如果标签仍是半截（`_is_prefix`）→ 记在 row 上，等尾巴行补全；
    - 尾巴行只在「上一行的标签确实是半截」时拼接，否则「在建工程转入」+
      「企业合并增加」会被误拼成一个标签。
    """
    rows: list[Row] = []
    carry = ""
    open_tail = False
    for raw in lines:
        stripped = raw.strip()
        if not stripped or is_boundary(stripped):
            continue
        stamp = DATE.search(raw)
        masked = DATE.sub(lambda m: " " * len(m.group()), raw.rstrip())
        # 「其中：（1）处置或报」的前缀会挡住 LEAD 的剥离，先把「其中：」抹成等长空格。
        masked = re.sub(r"其中[：:]", lambda m: " " * len(m.group()), masked)
        masked = PAREN_NO.sub(lambda m: " " * len(m.group()), masked)
        masked = LEAD.sub(lambda m: " " * len(m.group()), masked)
        found = [(m.group(), m.end()) for m in NUM.finditer(masked)]
        # 「美的总部 08 地块项目」里的 08 会被当成金额。1–2 位纯整数不可能是报表金额
        # （美的千元表最小也是 4 位数），一律丢掉。
        found = [item for item in found if not re.fullmatch(r"\d{1,2}", item[0])]
        label = clean(masked[: found[0][1] - len(found[0][0])] if found else masked)

        if not found:
            if not label:
                continue
            if open_tail and rows and _joins(rows[-1].label, label):
                rows[-1].label += label  # 「投资性房地」+ 金额 +「产转入」
                open_tail = False
            elif _is_prefix(label) and label not in FULL:
                # 半截标签（「处置或报」「转至投资性」「在建工程转」）。
                # 必须先判半截再判完整：`_complete("处置或报")` 会因
                # startswith("处置") 返回 True，半截标签就被丢掉了。
                carry = label
            elif _complete(label):
                carry = ""  # 「（3）企业合并增加」本身完整，本行无发生额
            else:
                carry = ""
            continue

        if stamp:
            # 「2024 年 12 月 31 日 28,356,572 …」是整行，不带项目名
            head = "期末" if stamp.group().strip().startswith(year) else "期初"
            label = f"{head}账面价值" if valued else f"{head}余额"
        elif carry:
            label, carry = carry + label, ""

        if not label:
            # 金额行无标签：只有整行没有其他文字时才是美的的「合计」行，
            # 否则是附注正文折行（「4,078,675,000 元)，其中计入营业成本…」）。
            if re.search(r"[\u4e00-\u9fa5]", masked[found[-1][1] :]):
                continue
            label = "合计"
        open_tail = _is_prefix(label)
        rows.append(Row(label, [number(v) for v, _ in found], [e for _, e in found]))

    # 过滤放在拼接之后：「投资性房地」+金额+「产转入」拼完才是「投资性房地产转入」。
    if keep_only:
        # 只要明细行。合计**行**不要（本表读的是「合计」列），而且附注后面紧跟的
        # 「固定资产清理」小表也有一行「合计」，留着会被当成固定资产合计。
        rows = [
            row
            for row in rows
            if row.label != "合计" and any(row.label.startswith(keep) for keep in KEEP)
        ]
    return rows


def _complete(text: str) -> bool:
    return bool(text) and any(text == name or text.startswith(name) for name in COMPLETE)


def _is_prefix(text: str) -> bool:
    return bool(text) and any(full.startswith(text) for full in FULL)


def _joins(head: str, tail: str) -> bool:
    """head 是不是某个完整项目名被金额劈断的前半截（「投资性房地」+「产转入」）。

    必须要求 head 是**真前缀**：否则「在建工程转入」+「企业合并增加」会被拼成
    「在建工程转入企业合并增加」（因为后者本身就以「企业合并增加」结尾），
    海尔 2025 年原值增加项因此少算 7.19 亿在建工程转入。
    """
    if not head or not tail or len(tail) > 6 or re.match(r"^[（(]", tail):
        return False
    merged = head + tail
    return any(full.startswith(head) and len(head) < len(full) for full in FULL) and any(
        merged == full or full.startswith(merged) for full in FULL
    )


def cluster(ends: list[int], count: int) -> list[float]:
    """数字右边界聚类：同列结尾相差 ≤2 字符。簇多于目标数时合并最近的两个。"""
    groups: list[list[int]] = []
    for end in sorted(set(ends)):
        if groups and end - groups[-1][-1] <= 2:
            groups[-1].append(end)
        else:
            groups.append([end])
    while len(groups) > count:
        gaps = [groups[i + 1][0] - groups[i][-1] for i in range(len(groups) - 1)]
        index = gaps.index(min(gaps))
        groups[index] = groups[index] + groups.pop(index + 1)
    if len(groups) != count:
        raise ValueError(f"只识别到 {len(groups)} 列，期望 {count} 列")
    return [sum(group) / len(group) for group in groups]


def pages(lines: list[str]) -> list[list[str]]:
    out: list[list[str]] = [[]]
    for raw in lines:
        if is_boundary(raw.strip()):
            out.append([])
        else:
            out[-1].append(raw)
    return [page for page in out if page]


def spread(rows: list[Row], count: int, hint: str) -> list[Row]:
    """把一页的行按列聚类摊到 count 列上。先算完再赋值，失败时不留半成品。"""
    if not rows:
        return []
    edges = cluster([end for row in rows for end in row.ends], count)
    out: list[Row] = []
    for row in rows:
        cells = [0.0] * count
        for value, end in zip(row.values, row.ends, strict=True):
            slot = min(range(len(edges)), key=lambda i: abs(edges[i] - end))
            if abs(edges[slot] - end) > 8:
                raise ValueError(f"{hint}: 「{row.label}」的 {value} 落不进列")
            cells[slot] = value
        out.append(Row(row.label, cells))
    return out


def _fit(rows: list[Row], count: int, hint: str) -> list[Row]:
    """摊列。若这一页实际只有 1 列数字（格力 2024 使用权资产），就按 1 列收，
    把值放进最后一列——那是合计列，与表头「房屋建筑物/其他设备/合计」的语义一致。"""
    if not rows:
        return []
    width = max(len(row.values) for row in rows)
    if width == 1 and count > 1:
        return [Row(row.label, [0.0] * (count - 1) + [row.values[0]]) for row in rows]
    return spread(rows, count, hint)


def sections(lines: list[str], company: str) -> list[tuple[str, list[str]]]:
    """切成 (原值/累计折旧/减值准备/账面价值, 行)。"""
    marks: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        flat = re.sub(r"\s+", "", line)
        if company == "美的集团" and flat in ("原价", "累计折旧", "减值准备", "账面价值"):
            marks.append((i, "原值" if flat == "原价" else flat))
        elif match := SECTION.match(flat):
            marks.append((i, "原值" if match.group(1) == "账面原值" else match.group(1)))
    out = []
    for index, (line_no, name) in enumerate(marks):
        stop = marks[index + 1][0] if index + 1 < len(marks) else len(lines)
        out.append((name, lines[line_no + 1 : stop]))
    return out


def note(lines: list[str], kind: str) -> list[str]:
    """截取附注正文：起点是「固定资产」等标题，终点是下一个相关附注。

    同一标题出现两次——会计政策章节（美的 (14)、海尔 16、格力 20）和合并报表项目
    附注（美的 (17)、海尔 17、格力 21）。只有后者紧跟着表格表头，所以取那一个。
    """
    title = TITLES[kind]
    marks = [
        i
        for i, line in enumerate(lines)
        if re.match(rf"^(?:\(\d+\)|\d+、){title}", re.sub(r"\s+", "", line))
    ]
    start = next((i for i in marks if _has_table(lines[i : i + 40], kind)), None)
    if start is None:
        return []
    for i in range(start + 1, min(start + 900, len(lines))):
        match = re.match(r"^(?:\(\d+\)|\d+、)(.+)$", re.sub(r"\s+", "", lines[i]))
        if match and match.group(1).startswith(STOPS[kind]):
            return lines[start:i]
    return lines[start : start + 900]


def _has_table(lines: list[str], kind: str = "fa") -> bool:
    """标题后 40 行内是否出现该表独有的表头，用来区分会计政策章节与报表附注章节。"""
    heads = {
        "fa": ("原价", "账面原值"),
        "cwip": ("项目列示", "在建工程情况", "账面余额"),
        "rou": ("原价", "账面原值"),
    }[kind]
    for line in lines:
        flat = re.sub(r"\s+", "", line)
        if any(head in flat for head in heads):
            return True
    return False


def statement(
    lines: list[str], company: str, layout, year: str, keep_only: bool = True
) -> dict[str, Table]:
    """固定资产/使用权资产：返回 {段名: 表}。

    海尔的续表里同名段出现两次（先是「房屋及建筑物/生产设备/运输设备」，再是
    「办公设备/其他/合计」），两块表按列向拼成宽表。同名同标签的行合并不覆盖——
    「期初余额」在两段里各有一份，后者是「办公设备/其他/合计」那三列。
    """
    hint = f"{company} {year}"
    out: dict[str, Table] = {}
    seen: dict[str, int] = {}
    for name, chunk in sections(lines, company):
        index = seen.get(name, 0)
        seen[name] = index + 1
        names = layout[min(index, len(layout) - 1)]
        offset = sum(len(part) for part in layout[:index])
        valued = name == "账面价值"
        rows: list[Row] = []
        try:
            for page in pages(chunk):
                parsed = page_rows(page, year, valued, keep_only)
                rows.extend(_fit(parsed, len(names), hint))
        except ValueError as error:
            print(f"  ✗ {error}", file=sys.stderr)
            continue
        if name not in out:
            out[name] = Table([n for part in layout for n in part])
        table = out[name]
        for row in rows:
            wide = [0.0] * len(table.header)
            wide[offset : offset + len(names)] = row.values
            existing = next((item for item in table.rows if item.label == row.label), None)
            if existing is None:
                table.rows.append(Row(row.label, wide))
            else:
                # 同名行只在**本段覆盖的那几列**上被替换，前一段的列保留
                existing.values[offset : offset + len(names)] = row.values
    return out


def cwip(lines: list[str], company: str, year: str) -> tuple[Table | None, Table | None]:
    """在建工程 → (分项目明细, 变动表)。变动表只从合计行取，理由见 docstring 陷阱 5。"""
    flow_at = next(
        (i for i, line in enumerate(lines) if "变动情况" in re.sub(r"\s+", "", line)), None
    )
    if flow_at is None:
        # 美的的标题是「(a) 重大在建工程项目变动」，没有「情况」二字
        flow_at = next(
            (i for i, line in enumerate(lines) if "工程项目变动" in re.sub(r"\s+", "", line)), None
        )
    detail = _detail(lines[1:flow_at] if flow_at else lines[1:], f"{company} {year}")
    flow = None
    if flow_at is not None:
        names = CWIP_COLS[(company, year)]
        for page in pages(lines[flow_at + 1 : flow_at + 40]):
            rows = page_rows(page, year, valued=False, keep_only=False)
            total = next(
                (row for row in rows if row.label == "合计" and len(row.values) == len(names)),
                None,
            )
            if total is not None:
                flow = Table(
                    names,
                    [Row(name, [value]) for name, value in zip(names, total.values, strict=True)],
                )
                break
        if flow is None:
            print(f"  ✗ {company}{year} 在建工程变动表合计行取不到", file=sys.stderr)
    return detail, flow


def _detail(lines: list[str], hint: str) -> Table | None:
    """在建工程分项目明细（项目 / 账面余额 / 减值准备 / 账面价值 × 期末+期初）。

    两个坑：
    1. 项目名会折行，且方向不固定：海尔「青岛制冷电器项」在金额行**之前**，紧接着的
       「目」在金额行**之后**；「美国 GE」在前、「Appliances 项目」在后。用「上一行
       是不是无标签金额行」判断：是 → 这段文字是上一行的后缀，否则是下一行的前缀。
    2. 表头里的「项目」二字是每个项目名都有的，不能拿它判断表头。只有整行**完全由
       表头词组成**才算表头。
    """
    start = next(
        (
            i
            for i, line in enumerate(lines)
            if all(
                word in re.sub(r"\s+", "", line) for word in ("账面余额", "减值准备", "账面价值")
            )
        ),
        None,
    )
    if start is None:
        return None
    rows: list[Row] = []
    pending = ""
    open_tail = False
    for raw in lines[start + 1 :]:
        stripped = raw.strip()
        if not stripped or is_boundary(stripped) or _company_header(stripped):
            continue
        masked = LEAD.sub(lambda m: " " * len(m.group()), raw.rstrip())
        masked = PAREN_NO.sub(lambda m: " " * len(m.group()), masked)
        found = [(m.group(), m.end()) for m in NUM.finditer(masked)]
        found = [item for item in found if not re.fullmatch(r"\d{1,2}", item[0])]
        text = clean(masked[: found[0][1] - len(found[0][0])] if found else masked)
        if not found:
            if not text:
                continue
            if open_tail and rows:
                rows[-1].label += text  # 「青岛制冷电器项」/ 金额 /「目」
                open_tail = False
                continue
            # 「项目」单独成行是表头；但项目名本身也常以「项目」结尾
            # （海尔「青岛水生态科技」+「项目」），有 pending 时不当表头。
            if text == "项目" and not pending:
                continue
            if _header_only(text) and not pending:
                continue
            pending += text
            continue
        if not text and len(found) == 6 and rows and not pending:
            # 美的的合计行没有标签，整行 6 个数
            rows.append(Row("合计", [number(v) for v, _ in found], [e for _, e in found]))
            break
        if text.startswith("合计"):
            rows.append(Row("合计", [number(v) for v, _ in found], [e for _, e in found]))
            break
        if _header_only(text):
            continue
        if not text and "金额单位" in clean(masked):
            break  # 「(除特别注明外，金额单位为人民币千元)」，明细表已结束
        # 同一行可能同时带前缀和后缀：「Appliances 项    255,332,644.93 … 目」
        # 文本完全在数字左边的是前缀，数字右边还有文字的是后缀（属于上一行）。
        label = pending + text
        pending = ""
        tail = clean(masked[found[-1][1] :])
        if tail and _is_name_tail(tail):
            label += tail
            open_tail = False
        else:
            open_tail = not text
        rows.append(Row(label, [number(v) for v, _ in found], [e for _, e in found]))
    if not rows:
        return None
    # 空格单元格在报表里是**空白**（不是「-」），所以不能按顺序取数：
    # 「武汉模具工程」只有 4 个数（期末余额/账面价值 + 期初余额/账面价值），
    # 按顺序会把期初账面价值读成减值准备。必须按数字右边界定位列。
    return Table(["账面余额", "减值准备", "账面价值"] * 2, spread(rows, 6, hint))


def _header_only(text: str) -> bool:
    """整行只由表头词组成（「项目」「账面余额」「期末余额」「单位：元 币种：人民币」）。"""
    if not text:
        return False
    residue = text
    for word in (
        "项目",
        "账面余额",
        "减值准备",
        "账面价值",
        "期末余额",
        "期初余额",
        "单位：元币种：人民币",
        "币种：人民币",
        "单位：元",
    ):
        residue = residue.replace(word, "")
    return not residue


def _is_name_tail(text: str) -> bool:
    """数字右侧的文字是不是项目名的尾巴（「Appliances 项 … 目」）。

    只在很短、且不含表格结构词时才算，避免把「（2）本期由在建工程转入…元」
    这类附注正文当成项目名。
    """
    return 0 < len(text) <= 4 and not _header_only(text) and "元" not in text


def _company_header(text: str) -> bool:
    """跨页时的公司抬头（「美的集团股份有限公司」/「2025 年度财务报表附注」）。"""
    return (
        "股份有限公司" in text
        or "财务报表附注" in text
        or bool(re.fullmatch(r"\d{4}年度财务报表附注", text))
    )


def add(rows, company, year, kind, item, value, factor, source, nature="披露值") -> None:
    if value is None:
        return
    # 「-0.00」是舍入产物（海尔 2024 累计折旧的处置子公司只有 29 万元），
    # 保留负号会让下游按符号分类时把它当成一笔减少额。
    scaled = value * factor / 1e8
    if abs(scaled) < 0.005:
        scaled = 0.0
    rows.append([company, year, kind, item, f"{scaled:.2f}", nature, source])


def emit_fa(rows, company, year, factor, note_no, fa) -> None:
    names = [n for part in FA_LAYOUT[company] for n in part]
    for column, name in enumerate(names):
        item = UNIFY.get(name, name)
        for kind, key, label in (
            ("固定资产-原值", "原值", "期末余额"),
            ("固定资产-累计折旧", "累计折旧", "期末余额"),
            ("固定资产-减值准备", "减值准备", "期末余额"),
            ("固定资产-账面价值", "账面价值", "期末账面价值"),
        ):
            table = fa.get(key)
            add(
                rows,
                company,
                year,
                kind,
                item,
                table.at(label, column) if table else None,
                factor,
                note_no,
            )


def emit_flow(rows, company, year, factor, kind, note_no, table) -> set[str]:
    """原值/累计折旧变动表。返回实际写入 CSV 的项目名，供 `check_movement` 核对。

    本期增加、本期减少在各家报表里是**空标题**（只有子项、没有合计数），所以由
    子项相加得到，数据性质标「计算值」。其余是披露值。

    明细行与增加/减少额都从 `INCREASE`/`DECREASE` 派生：旧版把明细写成固定清单，
    报表里解析到但不在清单上的子项（格力的「投资性房地产转入」）会被静默丢掉，
    落库的明细就凑不回本期增加。现在漏项会在 `check_movement` 里报错。
    """
    lines_only = kind == "累计折旧变动表"
    increases = INCREASE["累计折旧" if lines_only else "原值"]
    flow: list[tuple[str, float | None, str]] = [
        ("期初余额", table.at("期初余额"), "披露值"),
        ("本期增加", increase(table, "累计折旧" if lines_only else "原值"), "计算值"),
    ]
    flow += [(name, table.at(label), "披露值") for label, name in increases]
    flow.append(("本期减少", decrease(table), "计算值"))
    flow += [(name, _negative(table.at(label)), "披露值") for label, name in DECREASE]
    flow += [
        ("汇率变动", table.at("折算差额") or table.at("汇率变动"), "披露值"),
        ("期末余额", table.at("期末余额"), "披露值"),
    ]
    written: set[str] = set()
    for item, value, nature in flow:
        if value is None:
            continue
        add(rows, company, year, kind, item, value, factor, note_no, nature)
        written.add(item)
    return written


def increase(table: Table, kind: str = "原值") -> float | None:
    """本期增加 = 各明细子项相加。

    三家的「本期增加金额」都是**空标题**（行里没有合计数），所以要累加子项。
    子项按表的性质不同：原值的增加是购置/在建工程转入/企业合并/投资性房地产转入；
    累计折旧的增加是计提/企业合并/投资性房地产转入/其他。登记表是 `INCREASE`。

    只能用规范名（CANON 之后的名字）各取一次：美的/海尔的「非同一控制下企业合并」
    也被 CANON 映射成「企业合并增加」，两个名字一起查会把 36.47 亿算两遍。
    """
    found = [table.at(label) for label, _ in INCREASE[kind]]
    found = [value for value in found if value is not None]
    return sum(found) if found else None


def _negative(value: float | None) -> float | None:
    """统一「减少」的符号为负。美的印括号负数，海尔/格力印正数。"""
    return None if value is None else -abs(value)


def decrease(table: Table) -> float | None:
    """本期减少 = 各明细子项相加，**统一取负**。登记表是 `DECREASE`。

    美的把减少印成括号数（`(985,923)`），海尔/格力印正数（`386,400,388.28`）。
    不取负，海尔 2025 原值的勾稽差会正好是两倍的减少额（+66.52 亿 = 2 × 33.26 亿）。
    """
    found = [table.at(label) for label, _ in DECREASE]
    found = [abs(value) for value in found if value is not None]
    return -sum(found) if found else None


def emit_rou(rows, company, year, factor, note_no, rou) -> None:
    """使用权资产：只取本年（期末）的合计列，用列下标而不是标签名。

    两个坑：
    1. 「租赁变更及其他」在原值和累计折旧里各出现两次（增加一次、减少一次），
       按标签取会命中减少的那一行；
    2. 2025 年报的表里同时印「2025 年 12 月 31 日」和「2024 年 12 月 31 日」两行，
       但 2024 年的值已由 2024 年报提供，这里只写本年度，避免同一数字写两遍。
    """
    for kind, label in (
        ("原值", "期末余额"),
        ("累计折旧", "期末余额"),
        ("账面价值", "期末账面价值"),
    ):
        table = rou.get(kind)
        if table is None:
            continue
        add(
            rows,
            company,
            year,
            "使用权资产",
            kind,
            table.at(label, len(table.header) - 1),
            factor,
            note_no,
        )


def _record(name: str, found: list[str], problems: list[str], passes: list[str]) -> None:
    """把一组校验结果记入「通过」或「问题」。"""
    if found:
        problems.extend(found)
    else:
        passes.append(name)


def check_movement(company, year, table, kind, written: set[str]) -> list[str]:
    """变动表：解析到的每一行都必须真的写进 CSV，且明细能凑回本期增加/减少。

    这条对应真实缺陷：`emit_flow` 旧版按固定清单落库，格力 2025 的
    「（2）投资性房地产转入」被 `page_rows` 正确拼成标签、也读出了金额
    （原值 1.92 亿、累计折旧 0.98 亿），但清单里没有这个名字，整行被静默丢掉，
    CSV 的明细只有 26.82 亿而「本期增加」是 28.73 亿，变动表差 0.86 亿。

    所以这里不只看登记表，还要看 `written`（`emit_flow` 实际产出的项目名）：
    - 表里有、CSV 里没有 → 丢行；
    - 表里没有、CSV 里有 → 凭空多行（例如同一项被两个名字写两遍）；
    - 明细相加 ≠ 本期增加/减少 → 落库的明细不闭合。
    今后年报多出新项目（或 `CANON` 漏映射），会直接报出来，不再静默。
    """
    known = {CANON.get(label, label) for label, _ in INCREASE[kind]}
    known |= {CANON.get(label, label) for label, _ in DECREASE}
    known |= set(BASE_LABELS)
    parsed = {CANON.get(row.label, row.label) for row in table.rows}
    out: list[str] = []
    missing = sorted(parsed - known)
    if missing:
        out.append(f"{company}{year} {kind} 有未登记的明细行（未写入 CSV）：{missing}")
    # 登记表两侧对照：表内标签（CANON 后）↔ 落库项目名，两边都得真的出现。
    # 一个表内标签可能对应一个落库名（「处置」→「处置或报废」），所以用映射比对，
    # 不能直接拿两套字符串集合相减。
    for label, name in INCREASE[kind] + DECREASE:
        key = CANON.get(label, label)
        if key in parsed and name not in written:
            out.append(f"{company}{year} {kind} 表里有「{label}」但 CSV 里没写「{name}」")
        if name in written and key not in parsed:
            out.append(f"{company}{year} {kind} 写入了「{name}」，但表里没有「{label}」")

    lines_only = kind == "累计折旧变动表"
    increase_rows = INCREASE["累计折旧" if lines_only else "原值"]
    detail_plus = sum(value for label, _ in increase_rows if (value := table.at(label)) is not None)
    detail_minus = sum(
        abs(value) for label, _ in DECREASE if (value := table.at(label)) is not None
    )
    for name, detail, stated in (
        ("本期增加", detail_plus, increase(table, "累计折旧" if lines_only else "原值")),
        ("本期减少", -detail_minus, decrease(table)),
    ):
        if stated is None:
            continue
        if abs(detail - stated) > 1:
            out.append(
                f"{company}{year} {kind} 明细相加 {detail / 1e8:.2f} 亿"
                f" ≠ {name} {stated / 1e8:.2f} 亿"
            )
    return out


def check_book(company, year, factor, fa, balance) -> tuple[list[str], str]:
    """附注「固定资产账面价值合计」vs 资产负债表「固定资产净额」。

    返回 (问题, 已登记差异的说明)。说明会打在通过行上——口径差必须一直可见，
    否则下一个人会以为这里是零差异。

    口径先分清，再谈差异：
    - 格力资产负债表把「固定资产清理」单列（2025 年 0.11 亿），「固定资产净额」
      343.85 亿不含它，与附注 21 一致；「固定资产及清理合计」才是 343.96 亿。
      拿错行会把格力高估 0.03%，也会让「附注 ≠ 报表」的假差异掩盖真差异。
    - 海尔 2024 的 0.94 亿是**追溯重述**，不是取数错误，见 `BOOK_GAP`。
    """
    book = fa.get("账面价值")
    if book is None or balance is None:
        return [f"{company}{year} 附注账面价值或资产负债表固定资产净额缺失"], ""
    stated = book.at("期末账面价值", len(book.header) - 1)
    if stated is None:
        return [f"{company}{year} 附注账面价值合计行缺失"], ""
    # 附注单位随公司变（美的千元、海尔/格力元），统一换到亿元再比
    stated_yi = abs(stated) * factor / 1e8
    balance_yi = balance / 1e8
    gap_yi = balance_yi - stated_yi
    expected, reason = BOOK_GAP.get((company, year), (0.0, ""))
    if abs(gap_yi - expected) <= 0.02:
        return [], reason
    return [
        f"{company}{year} 附注账面价值 {stated_yi:.2f} 亿"
        f" ≠ 资产负债表固定资产净额 {balance_yi:.2f} 亿"
        f"（差 {gap_yi:+.2f} 亿，登记的是 {expected:+.2f}）"
        f"{'：' + reason if reason else '，且未登记口径差'}"
    ], ""


def balance_sheet() -> dict[tuple[str, str], float]:
    """资产负债表「固定资产净额」（元），按 (公司, 年度)。

    **不要**用「固定资产及清理合计」：格力把「固定资产清理」单列（2025 年 0.11 亿），
    那一行含清理、对不上附注 21。也不用「固定资产净值」——那是原值−累计折旧、
    没扣减值准备。
    """
    path = FIN / "资产负债表.csv"
    if not path.exists():
        return {}
    out: dict[tuple[str, str], float] = {}
    with path.open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["科目"] != "固定资产净额" or not row["报告期"].endswith("1231"):
                continue
            try:
                out[(row["公司"], row["报告期"][:4])] = float(row["数值"])
            except ValueError:
                continue
    return out


def check(company, year, factor, fa) -> list[str]:
    """自校验（逐公司逐年，四项）：

    1. 逐类别：原值 − 累计折旧 − 减值准备 = 账面价值
    2. 逐类别账面价值相加 = 账面价值合计
    3. 逐类别原值相加 = 原值合计
    4. 逐类别累计折旧相加 = 累计折旧合计
    """
    out: list[str] = []
    names = [n for part in FA_LAYOUT[company] for n in part]
    origin, accum, impair, book = (fa.get(k) for k in ("原值", "累计折旧", "减值准备", "账面价值"))
    if not all((origin, accum, impair, book)):
        return [f"{company}{year} 固定资产四段不全：{sorted(k for k in fa)}"]
    for column, name in enumerate(names):
        parts = [
            origin.at("期末余额", column),
            accum.at("期末余额", column),
            impair.at("期末余额", column),
            book.at("期末账面价值", column),
        ]
        if None in parts:
            out.append(f"{company}{year} {name} 有缺项 {parts}")
            continue
        gap = parts[0] - abs(parts[1]) - abs(parts[2]) - parts[3]
        if abs(gap) > 1:
            out.append(
                f"{company}{year} {name}：原值−折旧−减值−账面 = {gap * factor / 1e8:+.4f} 亿"
            )
    total = len(names) - 1
    for kind, table, label in (
        ("账面价值", book, "期末账面价值"),
        ("原值", origin, "期末余额"),
        ("累计折旧", accum, "期末余额"),
    ):
        sums = sum(abs(table.at(label, c) or 0.0) for c in range(total))
        stated = table.at(label, total)
        if stated is None:
            out.append(f"{company}{year} {kind}合计行缺失")
        elif abs(sums - abs(stated)) > 2:
            out.append(
                f"{company}{year} 分类别{kind}相加 {sums * factor / 1e8:.2f} 亿"
                f" ≠ 披露合计 {abs(stated) * factor / 1e8:.2f} 亿"
            )
    return out


def check_flow(company, year, factor, table, label) -> list[str]:
    out: list[str] = []
    begin, end = table.at("期初余额"), table.at("期末余额")
    plus = increase(table, "累计折旧" if label == "累计折旧" else "原值")
    minus = decrease(table)
    fx = table.at("折算差额") or table.at("汇率变动") or 0.0
    if None in (begin, end, plus, minus):
        return [f"{company}{year} {label}变动表有缺项"]
    gap = begin + plus + minus + fx - end
    if abs(gap) > 1:
        out.append(
            f"{company}{year} {label}：期初+增加−减少+汇率−期末 = {gap * factor / 1e8:+.4f} 亿"
        )
    return out


def check_cwip(company, year, factor, flow, cols) -> list[str]:
    if flow is None:
        return [f"{company}{year} 在建工程变动表未解析"]
    values = {name: flow.at(name) for name in flow.header}
    missing = [name for name, value in values.items() if value is None]
    if missing:
        return [f"{company}{year} 在建工程变动表缺列：{missing}"]
    begin, end = values["期初余额"], values["期末余额"]
    plus = values["本期增加"]
    merge = values.get("合并范围变动") or 0.0
    fx = values.get("汇率变动") or 0.0
    out_flow = sum(
        abs(values.get(name) or 0.0)
        for name in ("转入固定资产", "转入投资性房地产", "处置", "其他减少")
    )
    gap = begin + plus + merge + fx - out_flow - end
    if abs(gap) > 1:
        return [
            f"{company}{year} 在建工程：期初+增加+汇率−转出−期末 = {gap * factor / 1e8:+.4f} 亿"
        ]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all",
        action="store_true",
        default=True,
        help="提取三家 2024/2025 全部固定资产与在建工程数据（默认执行，保留开关兼容旧命令）",
    )
    if not parser.parse_args().all:  # 默认 True；仅显式关闭才打印帮助
        parser.print_help()
        return 1

    rows: list[list[str]] = []
    problems: list[str] = []
    passes: list[str] = []
    sheet = balance_sheet()
    for company, years in SOURCES.items():
        for year, (filename, factor, fa_note, cwip_note, rou_note) in years.items():
            pdf = PDF_DIR / filename
            if not pdf.exists():
                problems.append(f"缺少 {filename}")
                continue
            lines = text_of(pdf).splitlines()
            fa = statement(note(lines, "fa"), company, FA_LAYOUT[company], year)
            if not fa.get("原值"):
                problems.append(f"{company}{year} 固定资产未解析")
                continue
            emit_fa(rows, company, year, factor, fa_note, fa)
            for label, kind in (("原值", "固定资产变动表"), ("累计折旧", "累计折旧变动表")):
                if label in fa:
                    written = emit_flow(rows, company, year, factor, kind, fa_note, fa[label])
                    _record(
                        f"{company}{year} {kind} 勾稽（期初+增加−减少+汇率=期末）",
                        check_flow(company, year, factor, fa[label], label),
                        problems,
                        passes,
                    )
                    _record(
                        f"{company}{year} {kind} 明细全部落库（无静默丢行）",
                        check_movement(company, year, fa[label], label, written),
                        problems,
                        passes,
                    )
            emit_rou(
                rows,
                company,
                year,
                factor,
                rou_note,
                statement(note(lines, "rou"), company, ROU_LAYOUT[company], year, False),
            )
            detail, flow = cwip(note(lines, "cwip"), company, year)
            emit_cwip(rows, company, year, factor, cwip_note, detail, flow)
            _cwip_undisclosed(rows, company, year, cwip_note)
            _record(
                f"{company}{year} 在建工程勾稽（期初+增加+汇率=转出+期末）",
                check_cwip(company, year, factor, flow, CWIP_COLS[(company, year)]),
                problems,
                passes,
            )
            _record(
                f"{company}{year} 固定资产 原值−折旧−减值=账面 / 分类别相加=合计",
                check(company, year, factor, fa),
                problems,
                passes,
            )
            book_problems, book_note = check_book(
                company, year, factor, fa, sheet.get((company, year))
            )
            _record(
                f"{company}{year} 附注账面价值 = 资产负债表固定资产净额"
                + (f"（已登记口径差：{book_note}）" if book_note else ""),
                book_problems,
                problems,
                passes,
            )
            print(
                f"  {company} {year}: 固定资产 {len(fa)} 段，在建工程明细 "
                f"{len(detail.rows) if detail else 0} 行"
            )

    _record("跨年勾稽（2024 期末 = 2025 期初）", cross_year(rows), problems, passes)
    fields = ["公司", "年度", "类别", "项目", "金额(亿元)", "数据性质", "来源"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)
    print(f"写入 {OUT.relative_to(ROOT)}: {len(rows)} 行", file=sys.stderr)
    print(f"\n自校验通过 {len(passes)} 项：", file=sys.stderr)
    for name in passes:
        print(f"  ✓ {name}", file=sys.stderr)
    if problems:
        print(f"\n自校验问题 {len(problems)} 项：", file=sys.stderr)
        for problem in problems:
            print(f"  ! {problem}", file=sys.stderr)
    summary(rows)
    return 0


def emit_cwip(rows, company, year, factor, note_no, detail, flow) -> None:
    """在建工程：变动表给期初/增加/转固/期末（毛额），明细表给分项目账面价值。

    口径要分清：变动表和明细表的「余额」都是**账面余额**（已减在建工程减值前的数）。
    格力 2025 年期末账面余额 24.93 亿、减值准备 11.55 亿、账面价值仅 13.38 亿——
    只报 24.93 会把格力钛工程的 11.42 亿减值漏掉。所以账面价值单列。
    """
    if flow is not None:
        for name in flow.header:
            add(rows, company, year, "在建工程", name, flow.at(name), factor, note_no)
    if detail is None:
        return
    total = next((row for row in detail.rows if row.label == "合计"), None)
    if total is not None and len(total.values) >= 3:
        # 减值准备统一为「正 = 已计提」。美的把减值印成括号负数，海尔/格力印正数。
        add(rows, company, year, "在建工程", "减值准备", abs(total.values[1]), factor, note_no)
        add(rows, company, year, "在建工程", "账面价值", total.values[2], factor, note_no)
        if flow is None:
            add(rows, company, year, "在建工程", "期末余额", total.values[0], factor, note_no)
    for row in detail.rows:
        if row.label == "合计" or len(row.values) < 3:
            continue
        add(rows, company, year, "在建工程明细", row.label, row.values[2], factor, note_no)


def _cwip_undisclosed(rows, company: str, year: str, note_no: str) -> None:
    """三家都没有披露在建工程的「预算数」和「工程进度」。

    美的只写「在建工程支出与预算金额匹配，工程正在按进度开展」，海尔/格力只给
    「资金来源=自筹」。按要求写成「数据性质=未披露」的一行，不填 0——
    填 0 会被下游当成「预算为零」，意思完全不同。
    """
    for item in ("预算数", "工程进度"):
        rows.append([company, year, "在建工程明细", item, "", "未披露", note_no])


def cross_year(rows: list[list[str]]) -> list[str]:
    """2025 年报的期初应等于 2024 年报的期末。

    已知唯一例外：海尔 2025 年发生同一控制下企业合并（优瑾上海），按准则**重述**了
    2024 年可比数，所以 2025 年报的期初在建工程 57.14 亿比 2024 年报的期末 57.08 亿
    多 0.06 亿。这是口径差异，不是取数错误。
    """
    out: list[str] = []
    index = {(r[0], r[1], r[2], r[3]): float(r[4]) for r in rows if r[4]}
    for company in SOURCES:
        for kind, a, b in (
            ("固定资产-账面价值", "期末账面价值", "期初账面价值"),
            ("固定资产-原值", "期末余额", "期初余额"),
            ("在建工程", "期末余额", "期初余额"),
        ):
            now = index.get((company, "2024", kind, a))
            later = index.get((company, "2025", kind, b))
            if now is None or later is None or abs(now - later) <= 0.02:
                continue
            note = "（同一控制下企业合并重述，非取数错误）" if company == "海尔智家" else ""
            out.append(
                f"{company} {kind} 跨年勾稽：2024 期末 {now:.2f} ≠ 2025 期初 {later:.2f}{note}"
            )
    return out


def summary(rows: list[list[str]]) -> None:
    """横向对比用**账面价值**（已扣在建工程减值），不是账面余额。

    格力 2025 年在建工程余额 24.93 亿里有 11.55 亿减值（格力钛工程），账面价值只
    13.38 亿；用余额对比会把格力的在建规模高估 86%。
    """
    print(f"\n{'公司':<10}{'固定资产':>10}{'在建工程':>10}{'使用权':>9}   2025 年末（亿元）")
    print("-" * 50)
    for company in SOURCES:
        pick = {(r[2], r[3]): r[4] for r in rows if r[0] == company and r[1] == "2025"}
        print(
            f"{company:<10}{pick.get(('固定资产-账面价值', '合计'), '-'):>10}"
            f"{pick.get(('在建工程', '账面价值'), '-'):>10}"
            f"{pick.get(('使用权资产', '账面价值'), '-'):>9}"
        )


if __name__ == "__main__":
    sys.exit(main())
