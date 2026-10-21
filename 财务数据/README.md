# 财务数据

从公开数据库采集的结构化财务数据，均为人民币原值。可靠性分级见 [`../数据源分级.md`](../数据源分级.md)。

## 文件

### 原始采集（akshare，B 级）

| 文件 | 内容 | 规模 |
|---|---|---|
| `主要财务指标.csv` | 14 项核心指标 × 全部报告期（长表） | 3,975 行 |
| `资产负债表.csv` | 全量科目（长表） | 19,912 行 |
| `利润表.csv` | 全量科目（长表） | 11,612 行 |
| `现金流量表.csv` | 全量科目（长表） | 11,632 行 |
| `财务分析指标.csv` | 杜邦分解、周转率、偿债能力 | 114 行（38 期 × 3 家） |
| `主营构成.csv` | 分产品/分地区收入、成本、毛利率 | 600 条 |
| `分红送配.csv` | 分红方案、派息比例、除权日 | 82 条 |
| `股东户数.csv` | 股东户数变化、户均持股 | 151 条 |
| `公司概况.csv` | 市值、行业、上市时间 | 3 条 |

### 年报提取（A 级）

| 文件 | 内容 | 规模 |
|---|---|---|
| `治理与经营披露.csv` | 研发投入、审计意见、会计师事务所、员工人数 | 9 行（3 家 × 3 年） |
| `关键审计事项.csv` | 审计师认定的最重要事项、审计费用 | 16 行 |
| `分季度经营.csv` | 2023—2025 年逐季营业收入与归母净利润 | 72 行 |
| `分部报告.csv` | 分部收入/成本/利润/资产/负债，海尔含全球地区拆分 | 180 行 |
| `员工构成.csv` | 专业构成、教育程度、人均薪酬 | 92 行 |
| `客户供应商集中度.csv` | 前五大客户/供应商金额、占比、关联方占比 | 28 行 |
| `供应商客户集中度时序.csv` | 2019—2025 前五大客户/供应商 + 关联购销依赖度 | 322 行 |
| `存货明细.csv` | 原材料/在产品/库存商品/开发成本等，含跌价准备 | 32 行 |
| `存货跌价准备变动.csv` | 期初/计提/转回或转销/期末，含外币折算 | 39 行 |
| `会计政策对比.csv` | 折旧年限、存货计价、坏账计提、研发资本化、销售返利 | 24 行 |
| `应收账款质量.csv` | 账面余额、坏账准备、整体计提率，与报表对平 | 3 行 |
| `关联交易.csv` | 关联采购/销售金额、占成本/收入比例、口径说明 | 6 行（3 家 × 2 年） |
| `商誉明细.csv` | 按资产组拆分的商誉原值、减值准备、账面价值 | 18 行（含合计与校验行） |
| `汇兑损益.csv` | 汇兑损益及占归母净利润比例，符号统一为「正=收益」 | 6 行 |
| `政府补助与其他收益.csv` | 政府补助与增值税加计抵减拆分、占利润总额比例 | 30 行 |
| `渠道结构.csv` | 线上/线下、直销/经销收入与毛利率 | 7 行 |
| `担保与诉讼.csv` | 担保余额、占净资产比例、重大诉讼结论 | 6 行 |
| `研发人员结构.csv` | 研发人员学历/年龄结构，含披露覆盖度 | 31 行 |

### 计算与汇总（计算值）

| 文件 | 内容 | 规模 |
|---|---|---|
| `三家对比_2025.csv` | 42 项核心指标横向对比 | 42 行 |
| `三家对比_2026H1.csv` | 2026 年半年报 33 项横向对比（未年化） | 33 行 |
| `家电主业占比.csv` | 统一口径的家电/非家电/其他业务收入占比 | 26 行（2017—2025） |
| `成本结构与费用率.csv` | 毛利率到净利率的漏斗、四项费用率 | 15 行 |
| `营运效率与现金流.csv` | DSO/DIO/DPO/现金转换周期、净现比、自由现金流 | 15 行 |
| `股东回报.csv` | 历年每股派息、股息率、分红方案 | 71 行 |
| `原材料价格指数.csv` | 铜/铝/锌/钢/铁矿石/塑料的年度均价与同比 | 42 行 |
| `有息负债与偿债能力.csv` | 有息负债结构、净现金、净负债率、利息保障倍数 | 21 行 |
| `利润质量.csv` | 扣非净利润、非经常性损益、其他收益、投资收益、减值、商誉 | 21 行 |
| `投资收益结构.csv` | 权益法/非权益法二分，细项与占利润总额比 | 46 行 |
| `少数股东损益与权益.csv` | 少数股东损益、权益、权益变动与归母差额 | 123 行 |
| `长期股权投资回报.csv` | 长投规模、权益法收益、期末/平均回报率 | 95 行 |
| `渠道返利与占款.csv` | 销售返利规模、上下游净占款 | 21 行 |
| `分季度盈利能力.csv` | 单季毛利率与净利率（累计数反推） | 30 行 |
| `现金流结构.csv` | 经营/投资/筹资三大现金流、自由现金流、资本开支强度 | 21 行 |
| `收现质量.csv` | 收现比、海外占比、含税还原后收现比（估算） | 21 行 |
| `中期分红.csv` | 2026 年中期分红方案，现金派息与回购分列 | 6 行 |
| `受限资产.csv` | 受限资产明细、占总资产比例、受限原因 | 13 行 |
| `股份支付.csv` | 股份支付费用、扣除后净利润、反推影响 | 7 行 |
| `所得税与税收优惠.csv` | 所得税调整表全项、母公司税率、有效税率 | 44 行 |
| `财务净收益.csv` | 利息收入/费用、汇兑损益，统一符号 | 40 行 |
| `减值明细.csv` | 资产减值与信用减值分项、统一为「正=损失」 | 84 行 |
| `其他综合收益.csv` | 不能重分类/将重分类两段全部明细项 | 255 行 |
| `其他综合收益冲击.csv` | 归母 OCI 占净利润/净资产、余额变动校验 | 15 行 |
| `递延所得税.csv` | 未抵销 DTA/DTL 分项、未确认 DTA | 45 行 |
| `递延所得税勾稽.csv` | 抵销金额与资产负债表的对应关系 | 3 行 |
| `净利润调节经营现金流.csv` | 净利润→经营现金流逐项调节，含格力「其他」拆解 | 83 行 |
| `类现金与金融资产.csv` | 货币资金、金融投资合计，净类现金占净资产 | 84 行 |
| `商誉减值测试假设.csv` | 各商誉资产组的折现率、永续增长率、安全垫 | 39 行 |
| `固定资产与在建工程.csv` | 原值/折旧/减值/变动表/在建工程/使用权资产 | 385 行 |
| `票据与应收结构.csv` | 应收票据/应收账款/应收款项融资三分、背书贴现 | 231 行 |
| `租赁与承诺事项.csv` | 使用权资产/租赁负债/资本承诺/对外担保 | 211 行 |
| `职工薪酬与税费明细.csv` | 短期薪酬/离职后福利/辞退福利变动表、应交税费明细 | 111 行 |
| `套期保值.csv` | 衍生品投资表：期货/外汇/利率，期末金额与占净资产比 | 96 行 |

## 覆盖范围

- 报告期：1990 年至 2026 年半年度
- 三家公司：美的集团（000333）、海尔智家（600690）、格力电器（000651）
- 报表期数：美的 79 期、海尔 119 期、格力 113 期
- 分季度：2023—2025 年，共 3 年 × 4 季 × 2 指标 × 3 家 = 72 条

## 核心指标

`主要财务指标.csv` 收录 14 项：营业总收入、营业成本、归母净利润、扣非净利润、净利润、经营现金流量净额、股东权益合计、毛利率、销售净利率、ROE、资产负债率、基本每股收益、每股净资产、商誉。

注意 akshare 的 `营业总收入` 含其他业务收入，与年报 `营业收入` 有 0.4%–0.5% 差异。详见 `数据源分级.md`。

## 采集与校验

```sh
# 采集主要指标与公司概况
uv run --with akshare python3 scripts/fetch_akshare.py --all

# 采集三张报表、分红、股东户数、分析指标
uv run python3 scripts/fetch_akshare_extended.py --all

# 采集主营构成（分产品/分地区）
uv run python3 scripts/fetch_segments.py --all

# 从年报 PDF 提取治理披露、关键审计事项、分季度
uv run python3 scripts/fetch_pdf_disclosures.py --all
uv run python3 scripts/extract_audit_kam.py --all
uv run python3 scripts/extract_segments_note.py --all
uv run python3 scripts/build_quarterly.py
uv run python3 scripts/extract_employees.py --all
uv run python3 scripts/extract_concentration.py --all
uv run python3 scripts/extract_inventory.py --all
uv run python3 scripts/extract_accounting_policy.py --all
uv run python3 scripts/extract_receivables.py --all
uv run python3 scripts/extract_related_party.py --all
uv run python3 scripts/extract_goodwill.py --all
uv run python3 scripts/extract_fx.py --all
uv run python3 scripts/extract_gov_subsidy.py --all
uv run python3 scripts/extract_channels.py --all
uv run python3 scripts/extract_guarantees.py --all
uv run python3 scripts/extract_rd_staff.py --all
uv run python3 scripts/extract_interim_dividend.py --all
uv run python3 scripts/extract_restricted_assets.py --all
uv run python3 scripts/extract_impairment.py --all
uv run python3 scripts/extract_investment_income.py --all
uv run python3 scripts/extract_finance_income.py --all
uv run python3 scripts/extract_tax_reconciliation.py --all
uv run python3 scripts/extract_deferred_tax.py --all
uv run python3 scripts/extract_share_payment.py --all
uv run python3 scripts/extract_oci.py --all
uv run python3 scripts/extract_cash_reconciliation.py --all
uv run python3 scripts/extract_goodwill_assumptions.py --all
uv run python3 scripts/extract_fixed_assets.py --all
uv run python3 scripts/extract_hedging.py --all

# 生成计算类汇总表
uv run python3 scripts/build_comparison.py
uv run python3 scripts/build_cost_structure.py
uv run python3 scripts/build_efficiency.py
uv run python3 scripts/build_shareholder_return.py
uv run python3 scripts/build_commodity_index.py
uv run python3 scripts/build_debt_structure.py
uv run python3 scripts/build_earnings_quality.py
uv run python3 scripts/build_channel_float.py
uv run python3 scripts/build_cash_collection.py
uv run python3 scripts/build_business_mix.py
uv run python3 scripts/build_comparison_h1.py
uv run python3 scripts/build_quarterly_margin.py
uv run python3 scripts/build_cashflow_structure.py
uv run python3 scripts/build_minority_interest.py
uv run python3 scripts/build_equity_investment.py
uv run python3 scripts/build_financial_assets.py

# 交叉校验（必须执行）
uv run python3 scripts/verify_against_pdf.py
uv run python3 scripts/verify_all.py
```

校验脚本会自动识别年报的单位（美的用千元，海尔/格力用元），并区分「完全一致」与「口径差」。

## 使用限制

- 本目录数据为**二次加工**的结构化数据（B 级），关键结论须回溯到 `年度报告/` 的 PDF 原文。
- 长表格式（公司/报告期/科目/数值）便于筛选，但跨公司对比前需确认科目名称一致。
- `财务分析指标.csv` 中的比率由 akshare 按自身口径计算，与年报披露的加权平均 ROE 等可能存在小数位差异。
- **akshare 返回的是最新重述口径**（见 `数据源分级.md` 第 20 条）。2023、2024 年的营业成本、营业收入等科目，与当年年报原披露值不同。做时间序列分析用本目录数据（内部一致），引用「当时披露」用年报 PDF。
- 计算类文件（`三家对比_2025.csv` 起的四个）的数值由脚本从上述原始数据推导，可随时重跑复现，不应手工编辑。
