# AI Govern Dashboard — 一级页面（首页总览）设计 V1

本文档是首页（一级页面）的完整设计参考：产品定位、方法论、全站设计原则、站点地图与导航、首页布局、8 个领域的关键指标（L1 KPI）及实施口径、以及一级页面与二级页面的关系设计。

每个领域的二级页面设计参见独立文档 `design-L2-domain-{n}-*.md`。

---

## 1. 产品定位

面向企业 AI governance / AI security 团队的 **AI Control Tower**，不是文档门户，也不是报表仓库。

核心目标：
1. 用最少点击让管理者看到**哪个治理领域最需要关注**
2. 首页只做**跨领域总览与导航**
3. 详细分析放到二级页面中完成

---

## 2. 方法论与输入依据

| 输入 | 作用 |
|---|---|
| **NIST AI RMF** | 提供 Govern / Map / Measure / Manage 的治理框架视角 |
| **NIST AI 600-1** | 提供 GenAI 风险与治理重点 |
| **OWASP Top 10 for LLM Applications** | 提供 AI 应用安全风险清单 |
| **Microsoft 平台能力** | 作为本期主要可落地数据源与实现基础 |

关键判断：
- NIST AI 600-1 不直接翻译成栏目——它是方法论，不是 dashboard 架构
- 一级栏目按**管理对象 + 治理闭环位置**拆分，避免重叠
- 首页指标必须是 **decision-useful metrics**，不接受伪指标

---

## 3. 数据来源策略

优先使用 Microsoft 平台原生数据：Azure、Microsoft 365、Microsoft Entra、Microsoft Purview、Microsoft Defender、Microsoft Sentinel、Azure DevOps、Dataverse / SharePoint Online。自动化成熟度不足的内容可先作为后置或样例数据处理。

---

## 4. 当前确认的 8 个一级领域

| # | 中文名称 | 英文名称 | 设计定位 |
|---|---|---|---|
| 1 | AI 资产台账 | AI Asset Inventory | 定义治理对象总体范围，回答"我们到底在管什么" |
| 2 | AI 安全防护 | AI Security Protection | 管理 AI 运行面、接口面、身份面与防护姿态 |
| 3 | 数据与隐私 | Data and Privacy | 管理 AI 使用数据的识别、分类、暴露与隐私风险 |
| 4 | 输出可信与内容溯源 | Output Trustworthiness and Content Provenance | 管理输出可信性、合成内容标识与 provenance / disclosure |
| 5 | 第三方与供应链 | Third-Party and Supply Chain | 管理外部模型、API、开源组件、skill/agent 等依赖面 |
| 6 | 验证、审计与合规保证 | Validation, Audit, and Compliance Assurance | 管理 assurance baseline、formal validation、audit evidence 与 findings |
| 7 | 运行事件、响应与整改 | Operational Incidents, Response, and Remediation | 管理 AI 相关事件、处置时效与整改闭环 |
| 8 | 治理监督与控制执行 | Governance Oversight and Control Execution | 管理治理动作执行、例外、风险接受与监督机制 |

---

## 5. 全站设计原则

### 5.1 产品与页面原则

1. **决策优先** — 先回答"哪里有风险、哪里要行动"，不把首页做成制度清单
2. **一级页面总览，二级页面下钻** — 一级页面只放 8 张领域卡片，每张卡片只放 1-2 个最重要的指标
3. **真实数据优先，假数据补位** — 能接微软真实数据的优先真数据；事件、治理类允许先用 sample data 占位
4. **默认周视图** — 趋势相关图形默认按周表达

### 5.2 首页 UI 原则

1. **首页只保留顶部状态条 + 8 张领域卡片** — 已删除全局摘要区和重点行动区；顶部状态条只保留 Time 与 Last Updated
2. **卡片布局强调可扫读** — 大屏优先 4 张卡/行；增大边距与间距；每张卡片中的 2 个指标左右并排
3. **状态语义优先** — 右上 badge 使用：**High Risk** / **Attention** / **Low Risk**；`Sample Data` 为单独中性说明
4. **文案控制** — 不使用自动生成难度高的 narrative issue text；删除 `Why it matters`；指标说明采用短词组
5. **图形按含义选型**：
   - 覆盖率 / 占比 → donut（首页 donut 统一采用**上文下图**）
   - 结构分布 → stacked composition bar
   - 积压 / 趋势 → 大数字 + sparkline
   - 周事件趋势 + 来源拆分 → 大数字 + stacked weekly bars

---

## 6. 站点地图

```text
登录
└── 首页总览（一级页面）
    ├── 1. AI 资产台账（二级页面）
    ├── 2. AI 安全防护（二级页面）
    ├── 3. 数据与隐私（二级页面）
    ├── 4. 输出可信与内容溯源（二级页面）
    ├── 5. 第三方与供应链（二级页面）
    ├── 6. 验证、审计与合规保证（二级页面）
    ├── 7. 运行事件、响应与整改（二级页面）
    └── 8. 治理监督与控制执行（二级页面）
```

当前页面分层：**一级页面** = 首页总览；**二级页面** = 每个领域的领域页面。暂不建议在二级页面之外增加大量三级独立页面；更合适的方式是在二级页面内用页面内分区承载二级目录。

---

## 7. 全站导航

| 区域 | 建议内容 |
|---|---|
| 顶部导航 | 首页总览、8 个一级栏目、全局搜索、用户菜单 |
| 全局筛选 | 时间（默认周）、环境等真正需要驱动全页联动的筛选项 |
| 页面内导航 | 二级页面右侧或页内 anchor，跳转到各二级目录区块 |
| 全局状态条 | 最近更新时间，以及必要时保留的少量全局状态信息 |

---

## 8. 首页布局骨架

### 8.1 页面结构

1. **顶部状态条** — 时间范围、最近更新时间
2. **一级栏目卡片区（8 张卡）**
   - 每张卡只展示：领域名称、1-2 个首页指标、必要的短说明、一个状态色
   - 单击进入该领域 dashboard
   - 大屏宽度下优先保持 4 张卡/行

### 8.2 一级目录设计原则

1. 一级目录按治理对象与治理闭环位置拆分，避免同一问题在多个栏目重复解释
2. 首页只展示每个一级目录最重要的 1-2 个指标，用于快速判断哪个领域需要关注
3. 点击一级页面中的某一领域卡片，将进入只对应这个领域的二级页面
4. 优先使用可自动化、可持续获取的数据

---

## 9. 首页关键指标设计结果（8 个领域）

默认统计周期**最近 4 周**；趋势型指标按**周**聚合。

| 领域 | 指标 1 | 指标 2 | 状态 |
|---|---|---|---|
| 1. AI 资产台账 | Key Azure AI Resources | Asset Type Mix | 已确认 |
| 2. AI 安全防护 | AI Resources in Unhealthy State | Open High/Critical Defender Recommendations | 已确认 |
| 3. 数据与隐私 | Purview Classification Coverage | Sensitive Data Exposure Alerts | 已确认 |
| 4. 输出可信与内容溯源 | Grounded Response Rate | Model Identity Capture Gaps | 已确认 |
| 5. 第三方与供应链 | 3rd-Party Dependencies | Critical Open-Source Findings | 已确认 |
| 6. 验证、审计与合规保证 | Required Validation Coverage | Open High-Risk Findings | 已确认 |
| 7. 运行事件、响应与整改 | AI Incidents This Week | Average Closure Time | 待确认（Sample Data） |
| 8. 治理监督与控制执行 | On-Time Governance Actions | Open Exceptions / Risk Acceptances | 待确认（Sample Data） |

---

## 10. 一级页面 KPI 实施口径（开发参考）

说明：以下口径覆盖当前一级页面已确认的 1-6 域 KPI。默认统计周期**最近 4 周**；趋势型指标按**周**聚合。7-8 域当前仍是 sample data，不在本节展开。

### 10.1 Key Azure AI Resources（Domain 1）

**设计逻辑**：先让管理者看到当前主要有哪些 Azure AI 资源类型及其数量，而不是只给一个总数。

- **来源系统**：Azure Resource Graph、Azure AI Foundry / AML Registry、Microsoft Entra ID、Dataverse / SharePoint 资产台账
- **关键字段**：asset id / resource id、asset type、asset name、lifecycle state
- **计算逻辑**：按 Azure resource type 聚合数量，首页显示按数量排序的关键 resource type，最多展示 4 类
- **当前实现（2026-05-09）**：`GET /api/metrics/ai-asset-inventory`；只自动发现 Resource Graph 直接返回的 AI 资产及带 `AI` tag 的 `microsoft.web/sites`；采用资源清单直连方案。

### 10.2 Asset Type Mix（Domain 1）

**设计逻辑**：在总量之外给管理者结构视图，快速知道当前 AI 资产以什么类型为主。

- **来源系统**：Azure Resource Graph、Azure AI Foundry / AML Registry、Dataverse / SharePoint 资产台账
- **关键字段**：asset id、normalized asset type
- **计算逻辑**：以去重后资产全集为输入，按 Azure resource type 聚合，输出 stacked composition bar
- **当前资源类型拆分**：`microsoft.cognitiveservices/accounts`、`microsoft.aiservices/accounts`、`microsoft.machinelearningservices/workspaces`、`microsoft.machinelearningservices/registries`、`microsoft.botservice/botservices`、`microsoft.databricks/workspaces`、带 `AI` tag 的 `microsoft.web/sites`

### 10.3 AI Resources in Unhealthy State（Domain 2）

- **来源系统**：Microsoft Defender for Cloud / AI security posture、Azure Resource Graph
- **计算逻辑**：`unhealthy AI resources / total AI-scoped resources`；首页以 donut 呈现占比

### 10.4 Open High/Critical Defender Recommendations（Domain 2）

- **来源系统**：Microsoft Defender for Cloud recommendations、Azure Resource Graph
- **计算逻辑**：过滤 AI-scoped + severity in (High, Critical) + 未关闭；统计总数；按周聚合生成 sparkline

### 10.5 Purview Classification Coverage（Domain 3）

**API 路由**：`GET /api/metrics/purview-classification-coverage?time_range=4w|12w`

- **数据来源**：Microsoft Purview Data Map Search API；端点 `POST https://{PURVIEW_ACCOUNT_NAME}.purview.azure.com/datamap/api/search/query?api-version=2023-09-01-preview`；认证：MSAL client credentials，scope `https://purview.azure.net/.default`
- **计算口径（已确认）**：优先查询列级实体 `azure_sql_column`；若 total = 0 则 fallback 到 `azure_sql_table` + `azure_sql_view`；覆盖率 = `round(classified_count / total_count × 100)`
- **响应结构**：`{"coverage_pct": 59, "classified_count": 10, "total_count": 17, "asset_level": "column"}`

### 10.6 Sensitive Data Exposure Alerts（Domain 3）

**API 路由**：`GET /api/metrics/sensitive-data-exposure-alerts?time_range=4w|12w`

- **数据来源**：Office 365 Management Activity API — DLP.All 订阅；认证：MSAL client credentials，scope `https://manage.office.com/.default`
- **计算口径（已确认）**：数据窗口仅最近 7 天；dedup key `alertId`；排除 Dismissed；只计 SharePoint / OneDrive / Exchange；周聚合按 UTC 自然周（周一起始）
- **响应结构**：`{"total": 3, "weeks": [{"label":"W1","count":0},...], "data_window_days": 7}`

### 10.7 Grounded Response Rate（Domain 4）

**设计逻辑**：比"幻觉率"更稳定，更符合 trustworthiness 的治理表达。仅适用于文本类模型。

- **来源系统**：Azure AI Foundry Evaluations、Azure AI Search 检索日志、Application Insights / Log Analytics
- **关键字段**：evaluation id、groundedness score / citation result、output time
- **计算逻辑**：`grounded outputs / evaluated outputs`；首页以 donut 呈现

### 10.8 Model Identity Capture Gaps（Domain 4）

**设计逻辑**：检测 AI 输出缺少模型身份记录的缺口，覆盖 Azure-hosted 与 VM 部署模型，不依赖内部 tracing。

- **来源系统**：Application Insights（Azure 托管模型）、Blob archive metadata + Application Insights（VM 模型）
- **关键字段**：response id、model_name、model_version、deployment_type
- **计算逻辑**：`outputs missing model identity record / total outputs`；按 deployment type 拆分；首页以 number + sparkline 呈现

### 10.9 3rd-Party Dependencies（Domain 5）

- **来源系统**：APIM API / backend 配置、Azure AI Foundry 模型与 connection 清单、target registry、Azure Resource Graph
- **计算逻辑**：汇总外部模型、API、软件包；去重后统计总数；按主要类型聚合生成分类结构

### 10.10 Critical Open-Source Findings（Domain 5）

- **来源系统**：Microsoft Defender for DevOps、Defender Vulnerability Management、Azure Artifacts、Azure Container Registry
- **计算逻辑**：过滤开源组件 + severity = Critical + status != Closed；统计总数；按周聚合生成 sparkline

### 10.11 Required Validation Coverage（Domain 6）

- **来源系统**：Azure AI Foundry Evaluations、Azure DevOps Test Plans / Work Items、Purview Compliance Manager、Defender for Cloud Regulatory Compliance
- **计算逻辑**：`systems with completed required baseline / systems requiring baseline`；首页以 donut 呈现

### 10.12 Open High-Risk Findings（Domain 6）

- **来源系统**：Azure DevOps Work Items、Purview Compliance Manager、Defender for Cloud Regulatory Compliance、审计发现台账
- **计算逻辑**：过滤 formal assurance 来源 + High / Severe / Major + 未关闭；统计总数；按周聚合生成 sparkline

---

## 11. 一级页面与二级页面关系设计

### 11.1 基本规则

1. 一级页面中的 **2 个关键指标**，必须在对应二级页面的完整指标集合中被覆盖
2. 二级页面不要求把这 2 个指标原样重复显示为单独的顶部卡片
3. 二级页面可以用**不同的图形**或**不同的组织形式**来表达相同的基础数据
4. 必要时，一级页面中的 1 个指标可以在二级页面中拆分为多个更细的指标

### 11.2 各领域 L1/L2 覆盖方式

| 领域 | L1 两个关键指标 | 二级页面覆盖方式 |
|---|---|---|
| 1. AI 资产台账 | Key Azure AI Resources；Asset Type Mix | 在资产总览 / 资产结构相关指标中覆盖 |
| 2. AI 安全防护 | AI Resources in Unhealthy State；Open High/Critical Defender Recommendations | 在 Defender posture / recommendation 相关指标中覆盖，可按更细粒度展开 |
| 3. 数据与隐私 | Purview Classification Coverage；Sensitive Data Exposure Alerts | Classification Coverage 作为 3.2 的输入基础；Exposure Alerts 由 3.3 承接 |
| 4. 输出可信与内容溯源 | Grounded Response Rate；Model Identity Capture Gaps | 在 4.1 评估覆盖 / 4.2 内容溯源相关指标中覆盖 |
| 5. 第三方与供应链 | 3rd-Party Dependencies；Critical Open-Source Findings | 在依赖面、开源与基础组件等指标中覆盖 |
| 6. 验证、审计与合规保证 | Required Validation Coverage；Open High-Risk Findings | 在 validation / audit / compliance 相关指标中覆盖 |
| 7. 运行事件、响应与整改 | AI Incidents This Week；Average Closure Time | 应覆盖事件数量与关闭时效（当前工作版本） |
| 8. 治理监督与控制执行 | On-Time Governance Actions；Open Exceptions / Risk Acceptances | 应覆盖治理动作执行与例外/风险接受存量（当前工作版本） |

---

## 12. 二级页面统一骨架

所有二级页面使用同一版式，降低学习成本。

### 12.1 页面结构

1. **顶部状态条** — 时间范围、最近更新时间
2. **领域页头卡片** — 栏目名称、页面定位说明、风险/状态、**← Dashboard** 返回按钮
   > **确认决策（已实施验证）**：所有域页面必须包含此按钮，位于页头左上方；样式 Bootstrap `btn btn-sm btn-outline-secondary`；目标 `/`（首页）。已在 Data and Privacy 域页面首次实施并验证，后续所有域页面沿用此模式。
3. **二级目录分区** — 每个二级目录一个内容区块（1-4 个图表）：
   - 每个区块保留一句"管理意义说明"
   - 应覆盖该领域的全部相关指标，不只覆盖首页的 2 个指标
   - 每个指标/图形卡片应带自己的数据来源说明
   - 当指标需要治理核查明细时，卡片内可包含**默认折叠**的 resource list / comparison table
   - 区块标题不再显示 `Current Phase` / `Phase 2` 之类的 phase 标签
4. **底部行动区** — 待处理项、关联事件/关联整改、页面级口径/新鲜度说明

### 12.2 图表数量控制

| 页面层级 | 建议图表数量 |
|---|---|
| 首页 | 不超过 10-12 个可见图形对象 |
| 二级页面 | 通常控制在 6-10 个图表/卡片 |
| 单个二级目录区块 | 1-4 个图表 |

### 12.3 本期实现策略

本期真数据重点栏目：Domain 1-6。本期假数据占位栏目：Domain 7-8。

对于当前阶段不准备展示、但仍需保留设计位置的二级目录区块，原型中可直接**隐藏**，而不强制显示为弱化卡片。

### 12.4 页面交互

| 场景 | 交互建议 |
|---|---|
| 首页进入二级页面 | 单击卡片进入，不增加中间层 |
| 页面内查看明细 | 图表支持 hover tooltip + 右侧说明文本 |
| 时间趋势切换 | 默认周视图，支持 4 周 / 12 周 |
| 数据可信度提示 | 对假数据或样例区块显式标注 "Sample Data" |

---

## 13. 已明确后置的话题

| 话题 | 当前归属 |
|---|---|
| 责任与风险分级 | 8.3 / 8.4 |
| 知识产权 | 3.6 |
| 滥用防护 | 2.4 |
| CI/CD、上线 gate、go/no-go | 6.5 |
| 人机协同、偏差、稳定性 | 4.5 |

---

## 14. 当前状态

### 已确认
1. 网站定位与方法论方向
2. 8 个一级栏目
3. 首页整体骨架
4. 首页卡片设计原则
5. Domain 1-6 的首页指标与主要图形方式

### 待继续确认
1. Domain 7-8 的首页指标
2. 各一级栏目页的区块与图表组合
3. 状态色规则与阈值
4. `AI scope`、`unique alert case` 等统计口径
