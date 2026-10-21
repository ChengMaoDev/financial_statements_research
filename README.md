# 白色家电企业财务报表分析

围绕美的集团（000333.SZ）、海尔智家（600690.SH）和格力电器（000651.SZ），结合商业模式、会计政策、财务报表与行业环境开展横向比较，重点解释盈利质量、现金流和经营差异的成因。

研究期间为 **2017—2025 年度及 2026 年半年度**。仓库只保存原始材料与结构化数据，不保留文本转换产物；需要阅读原文时通过 `markitdown` MCP 工具即时转换。

## 从哪里开始

- [数据源分级.md](数据源分级.md)：**先读这个**。四级可靠性标准、已发现的口径陷阱、引用规范。
- [Prompt.docx](Prompt.docx)：任务范围、研究阶段与预期交付物。
- [分析内容概述.docx](分析内容概述.docx)：三家公司定位及已有分析概览。
- [年度报告/](年度报告/)：12 份年报与半年报 PDF，审计后的一手材料。
- [定期报告/](定期报告/)：105 份定期报告的完整索引（2017 年度—2026 Q1），含 PDF 直链。
- [财务数据/](财务数据/)：结构化财务数据，三张报表、核心指标、分红、股东户数、治理披露。
- [财务数据/三家对比_2025.csv](财务数据/三家对比_2025.csv)：核心指标横向对比（营收、利润、ROE、研发、人效、估值）。
- [财务数据/分季度经营.csv](财务数据/分季度经营.csv)：2023—2025 年逐季收入与归母净利润，来自年报披露。
- [财务数据/营运效率与现金流.csv](财务数据/营运效率与现金流.csv)：现金转换周期、净现比、自由现金流。
- [财务数据/成本结构与费用率.csv](财务数据/成本结构与费用率.csv)：毛利率到净利率的完整漏斗，四项费用率分项。
- [财务数据/股东回报.csv](财务数据/股东回报.csv)：历年分红、股息率、估值分位。
- [财务数据/关键审计事项.csv](财务数据/关键审计事项.csv)：审计师认定的最重要事项与审计费用。
- [财务数据/分部报告.csv](财务数据/分部报告.csv)：分部收入、利润、资产、负债；海尔的全球地区拆分。
- [财务数据/员工构成.csv](财务数据/员工构成.csv)：三家专业构成、教育程度、人均薪酬。
- [财务数据/客户供应商集中度.csv](财务数据/客户供应商集中度.csv)：前五大客户/供应商金额、占比、关联方占比。
- [财务数据/供应商客户集中度时序.csv](财务数据/供应商客户集中度时序.csv)：2019—2025 七年集中度与关联购销依赖度。
- [财务数据/存货明细.csv](财务数据/存货明细.csv)：原材料/在产品/库存商品/开发成本，含跌价准备计提率。
- [财务数据/存货跌价准备变动.csv](财务数据/存货跌价准备变动.csv)：计提、转回、转销三者的年度变动。
- [财务数据/会计政策对比.csv](财务数据/会计政策对比.csv)：折旧年限、存货计价、坏账计提、研发资本化、销售返利。
- [财务数据/应收账款质量.csv](财务数据/应收账款质量.csv)：账面余额、坏账准备、整体计提率（已与报表对平）。
- [财务数据/利润质量.csv](财务数据/利润质量.csv)：扣非净利润、非经常性损益、政府补助、减值、商誉。
- [财务数据/渠道返利与占款.csv](财务数据/渠道返利与占款.csv)：销售返利规模与上下游净占款。
- [财务数据/有息负债与偿债能力.csv](财务数据/有息负债与偿债能力.csv)：有息负债结构、净现金、净负债率、利息保障倍数。
- [财务数据/现金流结构.csv](财务数据/现金流结构.csv)：经营/投资/筹资三大现金流、自由现金流、资本开支强度。
- [财务数据/分季度盈利能力.csv](财务数据/分季度盈利能力.csv)：单季毛利率与净利率，由累计数反推。
- [财务数据/关联交易.csv](财务数据/关联交易.csv)：关联采购/销售金额与对成本/收入依赖度。
- [财务数据/商誉明细.csv](财务数据/商誉明细.csv)：按资产组拆分的商誉原值、减值准备与账面价值。
- [财务数据/汇兑损益.csv](财务数据/汇兑损益.csv)：汇兑损益及对归母净利润的影响，符号已统一。
- [财务数据/政府补助与其他收益.csv](财务数据/政府补助与其他收益.csv)：政府补助与增值税加计抵减拆分。
- [财务数据/渠道结构.csv](财务数据/渠道结构.csv)：线上/线下、直销/经销收入与毛利率。
- [财务数据/家电主业占比.csv](财务数据/家电主业占比.csv)：统一口径后的家电主业与非家电收入占比。
- [财务数据/担保与诉讼.csv](财务数据/担保与诉讼.csv)：担保余额、占净资产比例、重大诉讼结论。
- [财务数据/三家对比_2026H1.csv](财务数据/三家对比_2026H1.csv)：2026 年半年报 33 项横向对比。
- [财务数据/收现质量.csv](财务数据/收现质量.csv)：收现比、海外占比、含税还原后收现比。
- [财务数据/研发人员结构.csv](财务数据/研发人员结构.csv)：研发人员学历/年龄结构与披露覆盖度。
- [财务数据/中期分红.csv](财务数据/中期分红.csv)：2026 年中期分红方案，现金派息与回购拆开列示。
- [财务数据/受限资产.csv](财务数据/受限资产.csv)：受限资产明细、占总资产比例与受限原因。
- [财务数据/股份支付.csv](财务数据/股份支付.csv)：股份支付费用、扣除后净利润与反推影响，区分披露值/计算值。
- [财务数据/所得税与税收优惠.csv](财务数据/所得税与税收优惠.csv)：所得税调整表全项、母公司起点税率与有效税率。
- [财务数据/投资收益结构.csv](财务数据/投资收益结构.csv)：权益法与非权益法二分，识别可持续与一次性收益。
- [财务数据/少数股东损益与权益.csv](财务数据/少数股东损益与权益.csv)：少数股东损益、权益变动与归母净利润差额。
- [财务数据/财务净收益.csv](财务数据/财务净收益.csv)：利息收入/费用、汇兑损益，统一为「正=收益」。
- [财务数据/长期股权投资回报.csv](财务数据/长期股权投资回报.csv)：长投规模、权益法收益与回报率（期末/平均双口径）。
- [财务数据/减值明细.csv](财务数据/减值明细.csv)：资产减值与信用减值分项，统一为「正=损失」。
- [财务数据/其他综合收益.csv](财务数据/其他综合收益.csv)：汇率折算、套期储备等不经利润表的盈亏，含 2026H1 冲击。
- [财务数据/递延所得税.csv](财务数据/递延所得税.csv)：销售返利形成的递延税资产、未确认 DTA 与抵销口径。
- [财务数据/净利润调节经营现金流.csv](财务数据/净利润调节经营现金流.csv)：净利润到经营现金流的逐项调节，格力「其他」拆解。
- [财务数据/类现金与金融资产.csv](财务数据/类现金与金融资产.csv)：货币资金与各类金融投资合计，净类现金占净资产比。
- [财务数据/商誉减值测试假设.csv](财务数据/商誉减值测试假设.csv)：三家商誉资产组的折现率、永续增长率与安全垫。
- [财务数据/无形资产明细.csv](财务数据/无形资产明细.csv)：分类别原值/摊销/减值，含使用寿命不确定项。
- [财务数据/子公司与合并范围.csv](财务数据/子公司与合并范围.csv)：企业集团构成、持股比例、合并范围变动。
- [财务数据/固定资产与在建工程.csv](财务数据/固定资产与在建工程.csv)：原值/累计折旧/减值/变动表/在建工程明细/使用权资产。
- [财务数据/票据与应收结构.csv](财务数据/票据与应收结构.csv)：票据/应收/应收款项融资三分，含背书贴现终止确认口径。
- [财务数据/租赁与承诺事项.csv](财务数据/租赁与承诺事项.csv)：使用权资产/租赁负债/未折现付款额/资本承诺。
- [财务数据/职工薪酬与税费明细.csv](财务数据/职工薪酬与税费明细.csv)：薪酬四段变动表与应交税费明细。
- [财务数据/套期保值.csv](财务数据/套期保值.csv)：三家衍生品投资表（期货/外汇/利率），期末金额与占净资产比。
- [财务数据/原材料价格指数.csv](财务数据/原材料价格指数.csv)：铜/铝/锌/钢/铁矿石/塑料年度均价与同比。
- [市场数据/](市场数据/)：行业数据、公司产销量、电商快照、股权与资金面数据。
- [市场数据/电商/](市场数据/电商/)：京东联盟 30 天引单量（10 品类 816 组）+ 淘宝/拼多多搜索页快照。
- [市场数据/结构化/原材料价格.csv](市场数据/结构化/原材料价格.csv)：8 种原材料期货日线（近 5 年，11,224 行，含热卷）。
- [市场数据/结构化/房地产景气指数.csv](市场数据/结构化/房地产景气指数.csv)：国房景气指数，1998-01 起月度，326 期。
- [市场数据/结构化/汇率.csv](市场数据/结构化/汇率.csv)：人民币兑美元中间价、中行汇买/汇卖价。
- [市场数据/行业数据_年报引用.csv](市场数据/行业数据_年报引用.csv)：三家年报转引的奥维云网、产业在线、GfK 中怡康等第三方数据。
- [财务比较.xlsx](财务比较.xlsx)：年度及半年度指标比较，附来源和口径说明。
- [空调ASP与大宗商品成本传导.docx](空调ASP与大宗商品成本传导.docx)：空调平均售价、原材料成本与毛利率的专项分析。
- [空调ASP与大宗商品数据.xlsx](空调ASP与大宗商品数据.xlsx)：对应数据、情景假设、敏感性分析和来源链接。

## 目录结构

```text
.
├── 年度报告/                         # 三家公司各四个报告期间的 PDF（一手，已审计）
├── 定期报告/                         # 105 份定期报告索引 + 港股公告索引
├── 财务数据/                         # 三表、指标、治理、分季度、会计政策、债务、返利、利润质量
├── 市场数据/                         # 行业数据、产销量、电商快照、结构化行情与资金面
│   ├── 结构化/                       # 十大股东、估值、行情、融资融券、北向、原材料、汇率、房地产景气
│   ├── 电商/                         # 京东联盟与拼多多清洗后的面板（原始导出在 .playwright-mcp/，已 ignore）
│   └── 快照/                         # 电商反爬探测的原始响应文本
├── scripts/                          # 采集、校验、清洗脚本（pdf_util.py 为共享 PDF 工具）
│   └── _pdd_inbox/                   # 拼多多原始 TSV 导出，build_pdd_csv.py 的输入（不可删）
├── 数据源分级.md                     # 四级可靠性标准与口径陷阱
├── Prompt.docx
├── 分析内容概述.docx
├── 空调ASP与大宗商品成本传导.docx
├── 财务比较.xlsx
├── 空调ASP与大宗商品数据.xlsx
├── .gitignore
└── README.md
```

## 数据来源

按可靠性分为四级，详见 [数据源分级.md](数据源分级.md)：

| 级别 | 来源 | 用途 |
|---|---|---|
| A | 巨潮资讯网、港交所披露易、年报 PDF | 法定披露，可直接引用 |
| B | akshare、Longbridge | 结构化数据，须与 A 级交叉校验 |
| C | 奥维云网、GfK、券商研报、商务部 | 行业数据，须标注预测/实际 |
| D | 电商平台展示值 | 仅方向性参考，不可用于定量结论 |

## 采集与校验

依赖由 `pyproject.toml` 声明，首次使用先 `uv sync`。电商采集另需 `uv sync --extra ecommerce`。

**额外前置**：解析 PDF 需要 `pdftotext`（poppler），27 个 `extract_*.py` 都依赖它。
`uv sync` 不会装它，必须单独安装：

```sh
brew install poppler          # macOS
sudo apt install poppler-utils # Debian/Ubuntu
```

缺它时脚本会给出中文提示，`verify_all.py` 第 37 条也会检查。

```sh
# 定期报告索引（巨潮，A 级）
uv run python3 scripts/fetch_cninfo_index.py

# 港股公告索引（港交所，A 级）
uv run python3 scripts/fetch_hkex_index.py

# 结构化财务数据（akshare，B 级）
uv run python3 scripts/fetch_akshare.py --all
uv run python3 scripts/fetch_akshare_extended.py --all
uv run python3 scripts/fetch_segments.py

# 市场与资金面（akshare，B 级）
uv run python3 scripts/fetch_market_data.py --all
uv run python3 scripts/fetch_capital_flow.py --all
uv run python3 scripts/fetch_commodity.py      # 原材料期货（含热卷）+ 汇率
uv run python3 scripts/fetch_real_estate.py    # 国房景气指数

# 从年报 PDF 提取治理披露与行业引用（A 级）
uv run python3 scripts/fetch_pdf_disclosures.py --all
uv run python3 scripts/extract_industry_data.py --all
uv run python3 scripts/extract_audit_kam.py --all
uv run python3 scripts/extract_segments_note.py --all
uv run python3 scripts/build_quarterly.py

# 从年报附注逐项提取（A 级，每个脚本对应一张表）
uv run python3 scripts/extract_related_party.py --all
uv run python3 scripts/extract_goodwill.py --all
uv run python3 scripts/extract_fx.py --all
uv run python3 scripts/extract_gov_subsidy.py --all
uv run python3 scripts/extract_channels.py --all
uv run python3 scripts/extract_guarantees.py --all
uv run python3 scripts/extract_rd_staff.py --all
uv run python3 scripts/extract_interim_dividend.py --all
uv run python3 scripts/extract_restricted_assets.py --all
uv run python3 scripts/extract_share_payment.py --all
uv run python3 scripts/extract_tax_reconciliation.py --all
uv run python3 scripts/extract_investment_income.py --all
uv run python3 scripts/extract_finance_income.py --all
uv run python3 scripts/extract_impairment.py --all
uv run python3 scripts/extract_oci.py --all
uv run python3 scripts/extract_deferred_tax.py --all
uv run python3 scripts/extract_cash_reconciliation.py --all
uv run python3 scripts/build_financial_assets.py --all
uv run python3 scripts/extract_goodwill_assumptions.py --all
uv run python3 scripts/extract_fixed_assets.py --all
uv run python3 scripts/extract_intangibles.py --all
uv run python3 scripts/extract_subsidiaries.py --all
uv run python3 scripts/extract_bills_receivables.py --all
uv run python3 scripts/extract_leases_commitments.py --all
uv run python3 scripts/extract_payroll_tax_payable.py --all
uv run python3 scripts/extract_hedging.py --all
uv run python3 scripts/extract_accounting_policy.py --all
uv run python3 scripts/extract_concentration.py --all
uv run python3 scripts/extract_supply_chain_concentration.py --all
uv run python3 scripts/extract_employees.py --all
uv run python3 scripts/extract_inventory.py --all
uv run python3 scripts/extract_inventory_provision.py --all
uv run python3 scripts/extract_receivables.py --all

# 汇总计算（输入为上面两类）
uv run python3 scripts/build_business_mix.py
uv run python3 scripts/build_comparison.py
uv run python3 scripts/build_comparison_h1.py
uv run python3 scripts/build_efficiency.py
uv run python3 scripts/build_cost_structure.py
uv run python3 scripts/build_shareholder_return.py
uv run python3 scripts/build_cashflow_structure.py
uv run python3 scripts/build_quarterly_margin.py
uv run python3 scripts/build_earnings_quality.py
uv run python3 scripts/build_debt_structure.py
uv run python3 scripts/build_channel_float.py
uv run python3 scripts/build_cash_collection.py
uv run python3 scripts/build_commodity_index.py
uv run python3 scripts/build_minority_interest.py
uv run python3 scripts/build_equity_investment.py

# 电商快照（D 级，需持久化登录）
# 注意：京东联盟与拼多多的原始导出（jdunion-*.csv / pdd-*.tsv）没有生成脚本，
# 靠 Playwright 驱动已登录浏览器手工操作产生，落地在 .playwright-mcp/（已 gitignore）。
# 仓储只保证「已采到的快照」可清洗复现，不保证从零可重采。详见各数据说明 md 的「复现」段。
uv run python3 scripts/probe_ecommerce.py
uv run python3 scripts/fetch_national_day.py
uv run python3 scripts/clean_jd_snapshot.py
uv run python3 scripts/build_jdunion_panel.py    # jdunion-*.csv → 组级面板 + SKU 明细
uv run python3 scripts/parse_taobao.py           # taobao-*.csv 解析 + --audit 校验
uv run python3 scripts/collect_pinduoduo.py      # 拼多多 CDP 监听采集（需在 Playwright 上下文内调用，见脚本说明）
uv run python3 scripts/build_pdd_csv.py          # pdd-*.tsv → pdd-*.csv

# 校验
uv run python3 scripts/verify_against_pdf.py
uv run python3 scripts/verify_all.py

# 公共模块（不是脚本，无需运行）
#   scripts/pdf_util.py   统一封装 pdftotext 调用与依赖检查，被所有 extract_*.py 引用
```

校验结果（`verify_all.py`，432 项通过 / 13 项已归因，共 51 类）：

| # | 校验项 | 通过 | 差异 | 差异原因/备注 |
|---|---|---|---|---|
| 1 | 季度合计 vs 利润表全年 | 15 | 3 | 海尔 2024 年同一控制下合并物流业务，追溯重述 2023 年可比数 |
| 2 | 分产品合计 vs 营业收入 | 53 | 1 | 海尔 2018 年报分产品披露粒度不足（94.02%） |
| 3 | 年报研发投入 vs 利润表研发费用 | 9 | 0 | — |
| 4 | 产销量平衡：生产 + 期初库存 - 期末库存 ≈ 销售 | 0 | 3 | 美的销售量大于生产量，差额来自外购/代工 |
| 5 | 分部报告对外交易收入合计 vs 利润表营业总收入 | 6 | 2 | 海尔 2023/2024 同前，物流业务重述 |
| 6 | 员工构成合计 vs 治理披露员工人数 | 9 | 0 | — |
| 7 | 存货明细分项合计 vs 资产负债表存货 | 5 | 1 | 海尔 2024 合同履约成本重分类 1.46 亿 |
| 8 | 前五大客户：金额 / 占比 反推营业收入 | 8 | 1 | 海尔 2023 营收重述（同第一项） |
| 9 | 应收账款：余额 − 坏账准备 vs 资产负债表 | 3 | 0 | — |
| 10 | 主要财务指标「营业成本」= 利润表「营业总成本」（不是「营业成本」） | 9 | 0 | — |
| 11 | 商誉明细合计 vs 资产负债表商誉 | 3 | 0 | — |
| 12 | 政府补助明细合计 vs 利润表「其他收益」 | 6 | 0 | — |
| 13 | 关联交易：金额为正、占比可重算 | 6 | 0 | — |
| 14 | 2026H1：分地区收入合计 vs 营业收入（已剔除「其中:」子项） | 6 | 0 | — |
| 16 | 担保余额/归母净资产 vs 年报披露的占净资产比例 | 3 | 0 | — |
| 17 | 研发人员数 = 员工构成「技术人员」；学历/年龄覆盖不超总数 | 3 | 0 | — |
| 18 | 收现比 = 销售商品收到的现金 / 营业收入 | 21 | 0 | — |
| 19 | 2026H1 中期分红：现金分红/归母净利润 vs 年报披露比例 | 1 | 0 | — |
| 20 | 受限资产：明细相加 vs 年报合计，占总资产比例可复算 | 1 | 0 | — |
| 21 | 股份支付：扣除后净利润 − 净利润 = 反推影响 | 1 | 0 | — |
| 22 | 所得税调整表：起点税率 + 各调整项 = 所得税费用 | 6 | 0 | — |
| 23 | 投资收益：分项合计 = 利润表，权益法占比可复算 | 6 | 0 | — |
| 24 | 少数股东损益：净利润 − 归母净利润 = 少数股东损益 | 21 | 0 | — |
| 25 | 财务净收益：明细合计 = −利润表财务费用 | 6 | 0 | — |
| 26 | 减值明细：资产减值 + 信用减值 = −利润表两项之和 | 6 | 0 | — |
| 27 | 其他综合收益：分项合计 = 归母，归母 + 少数 = 税后净额 | 15 | 0 | — |
| 28 | 递延所得税：分项合计 = 表内合计，未抵销 − 抵销 = 资产负债表 | 3 | 0 | — |
| 29 | 净利润调节表：调节后合计 = 现金流量表经营净额 | 6 | 0 | — |
| 30 | 类现金与金融资产：明细相加 = 合计，隐含收益率 = 利息/平均类现金 | 6 | 0 | — |
| 31 | 商誉减值假设：安全垫倍数可复算 | 3 | 0 | — |
| 32 | 固定资产与在建工程：变动表勾稽 + 与报表对平 | 17 | 1 | 海尔 2024 附注 375.19 亿 vs 报表 376.13 亿，差 0.94 亿为同一控制下企业合并追溯重述 |
| 33 | 票据与应收：原值−坏账=账面价值，三分合计与报表勾稽 | 6 | 0 | — |
| 34 | 租赁与承诺：使用权资产与租赁负债对平 | 6 | 0 | — |
| 35 | 职工薪酬与应交税费：明细合计 = 资产负债表科目 | 6 | 0 | — |
| 36 | 存货跌价准备变动：期初 + 计提 − 转回/转销 = 期末，且与存货明细对平 | 3 | 0 | — |
| 37 | 供应链集中度：前五名金额 ÷ 占比 反推的分母 vs 营业收入/成本 | 21 | 0 | — |
| 38 | 无形资产：原值 − 累计摊销 − 减值 = 账面价值，且与报表对平 | 6 | 0 | — |
| 39 | 子公司：持股比例区间合法，结构统计与明细家数一致 | 6 | 0 | — |
| 40 | 品牌归一：短别名不跨品牌误命中，食品品牌不进家电面板 | 9 | 0 | — |
| 41 | 主键唯一性：长表不得有重复的复合主键 | 5 | 0 | — |
| 42 | 分部报告闭合：各分部相加 = 合计 | 26 | 0 | — |
| 43 | 费用漏斗闭合：收入 × (1 − 各成本率之和) ≈ 营业利润 | 15 | 0 | — |
| 44 | 非经常性损益：归母净利润 − 扣非净利润，占比可复算 | 21 | 0 | — |
| 45 | 外部工具链：pdftotext（poppler）可用性 | 1 | 0 | — |
| 46 | 结构完整性：CSV 表头列数 = 数据列数 | 20 | 0 | — |
| 47 | 京东联盟排序有效性：原始导出 o30 是否降序 | 0 | 1 | 已记录数据缺陷：15/15 文件非降序，样本不能称「高引单前 120 条」 |
| 48 | 套期保值：三家均提取到数据，期末金额与净资产占比同向 | 13 | 0 | — |
| 49 | 房地产景气指数：月份连续、取值合理 | 2 | 0 | — |
| 50 | 数据性质一致性：CSV 的 actual/forecast 与来源登记不矛盾 | 2 | 0 | — |
| 51 | 跨检索词去重：同一 SKU 跨关键词重复入库的规模 | 1 | 0 | — |

三家 2025 年度归母净利润与年报**逐位一致**；海尔总资产 295,795,068,591.57 与年报逐位一致。

## 阅读与引用

PDF、DOCX、XLSX 不可由模型直接理解，需先转为文本：通过 `markitdown` MCP 工具逐个转换后阅读。该工具一次只接受单个文件，不支持目录批量处理。

引用关键数字时记录公司、指标、数值、单位、期间、合并口径，以及原文件路径。区分披露值、计算值、估算和分析判断。

## 局限

- 转换结果不落盘、不经校验，直接来自 `markitdown` 单次解析；合并单元格与跨页表格可能错位。
- PDF 无页码锚点，定位具体页需回到原件人工核对。
- 复杂表格的数值归属须对照原 PDF 页面确认，不得仅依据转换文本下结论。
- 单份年报转换后可达数十万字符，超出上下文容量，需分章取用。
- 电商「已售」为累计口径且区间化取整，同型号在多店铺重复计数，不能当作档期销量或直接求和。
- **品牌级、单品级的节假日销量在公开渠道不存在**，属奥维云网、GfK 中怡康付费库。详见 `市场数据/国庆数据可获得性实测.md`。
- 京东联盟「30 天引单量」虽是官方滚动口径，但**≥100 时只有 1 位有效数字**（100…900、
  1000…40000；<100 为精确整数），且是**店铺 × 系列**聚合值而非 SKU 级，
  不能求和、不能做倍数表述。详见 `市场数据/电商/京东联盟数据说明.md`。
- 淘宝 `sort=sale-desc` URL 参数无效，必须点「销量」tab；价格被打码（可读率 1%–30%），
  不能算均价。详见 `市场数据/电商/淘宝数据说明.md`。
- 拼多多的 `sort_type=_sales` 参数传了但不生效，且 API `sales` 字段与页面展示不一致，
  **排序位次不可用**。详见 `市场数据/电商/拼多多数据说明.md`。

## 协作

原始材料保持原样。按任务建立分支，经 PR 合并到 `main`。
