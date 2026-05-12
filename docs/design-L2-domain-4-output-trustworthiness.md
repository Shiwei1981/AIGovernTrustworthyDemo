# Domain 4 · 输出可信与内容溯源 — 二级页面设计 V1

## 1. 领域定位

**英文名**：Output Trustworthiness and Content Provenance
**设计定位**：管理 AI 输出的可信度、内容溯源能力与行为健康状态
**治理对象范围**：AI 应用、AI Agent、Azure AI Foundry 中的模型、VM 中部署的模型（文本类模型）
**本期实现**：设计已完成，待实施

---

## 2. 首页关键指标（L1 KPI）

本领域在首页展示以下 2 个关键指标（详细实施口径见 `design-L1-overview.md` §10）：

| 指标 | 图形 | 状态 |
|---|---|---|
| Grounded Response Rate | donut | 已确认 |
| Model Identity Capture Gaps | plain number | 已确认 |

**关键设计决定**：
- `Grounded Response Rate`：当前无 RAG 系统，显示 N/A；待 RAG 系统就位后自动生效
- `Model Identity Capture Gaps`：替换原 `Synthetic Content Labeling Gaps`，因其覆盖所有文本模型（含 VM），不依赖内部 tracing，是可执行的治理抓手
- 当 Grounded Response Rate = N/A 时，首页该 Domain 的主要 governance 信号来自 Model Identity Capture Gaps

---

## 3. 治理范围与平台说明

| 治理对象 | 治理策略 | 备注 |
|---|---|---|
| Azure AI Foundry 托管模型 | Evaluation + Tracing + Red Teaming | 全面覆盖 |
| Azure AI Foundry Agent | Evaluation + Red Teaming | 暂无内部 tracing 依赖 |
| AI 应用（App Service / Function） | Evaluation + Red Teaming + App Insights | 需配置 response_id、model_name、model_version |
| VM 中自建模型 | 红队外部调用（PyRIT） + APIM 身份捕获 | 不在 VM 内部做 tracing；APIM 为可选配置 |

**文本模型范围说明**：本领域仅覆盖文本类模型，不包括图像生成、视频、语音等多模态输出。

---

## 4. 二级页面指标结构

### 4.1 输出质量基线与评估覆盖

| 指标 | 图形 | 是否本期实现 | 设计确认状态 | 指标解释 | 指标数据来源 |
|---|---|---|---|---|---|
| Evaluation Coverage by Target Type | stacked bar | 是 | 已确认 | 按治理对象类型（AI App / Agent / Azure 模型 / VM 模型）分拆的已评估覆盖率 | Azure AI Foundry Evaluations、Azure DevOps Test Plans |
| Groundedness / Citation Rate | donut | 是 | 已确认 | 输出中成功命中检索证据或批准来源的比例（无 RAG 时显示 N/A） | Azure AI Foundry Evaluations、Azure AI Search 检索日志 |
| Safety Evaluator Failure Rate | donut + number | 是 | 已确认 | 安全评测中判定失败的输出占比；显示失败率和对应绝对数量 | Azure AI Foundry Evaluations（Safety Evaluator） |

**数据来源**：
- Azure AI Foundry Evaluations API：`GET /evaluations`，字段 `target_type`、`groundedness_score`、`safety_pass_rate`
- Azure DevOps Work Items：红队与评估发现记录

**计算逻辑**：
- Evaluation Coverage = 本周期内已完成至少一次 evaluation 的 target 数 / 纳管 target 总数，按 target_type 拆分
- Groundedness = grounded_citations / total_responses，仅当有 RAG 上下文时计算；否则返回 N/A
- Safety Failure Rate = safety_fail_count / total_evaluated_responses

---

### 4.2 内容溯源与可追溯性

| 指标 | 图形 | 是否本期实现 | 设计确认状态 | 指标解释 | 指标数据来源 |
|---|---|---|---|---|---|
| Traceable Output Rate | donut | 是 | 已确认 | 已附带 response_id 或等效追踪标识的输出占比（仅 Azure 托管，VM 不计） | Application Insights（response_id 字段）、Azure AI Foundry Tracing |
| Source Attribution Rate | donut | 是 | 已确认 | 输出中包含来源引用的比例（无 RAG 时显示 N/A） | Azure AI Foundry Evaluations、Azure AI Search 检索日志 |
| Model Identity Capture Rate | donut / stacked bar | 是 | 已确认 | 已附带 model_name + model_version 的调用占比；按平台（Azure / VM via APIM）分拆 | Application Insights（model_name、model_version 字段）、Azure APIM 日志 |

**数据来源**：
- Application Insights：自定义属性 `response_id`、`model_name`、`model_version`（需要应用侧配置）
- Azure AI Foundry Tracing：`GET /traces`
- Azure API Management 日志：后端调用记录，含 VM 模型的 model_name、version

**计算逻辑**：
- Traceable Output Rate = 含 response_id 的 response 数 / Azure 托管模型 total response 数；VM 排除在外
- Source Attribution Rate = 含 source citation 的 response 数 / RAG response 总数；无 RAG 时 N/A
- Model Identity Capture Rate = 含 model_name + model_version 的调用数 / 全部受管模型调用总数；按 Azure / VM 分拆

**约束说明**：
- `Traceable Output Rate` 仅适用于 Azure 托管模型；VM 模型不统计此指标
- `Source Attribution Rate` 当前无 RAG → 显示 N/A
- `Model Identity Capture Rate` 依赖 App Insights 配置，VM 通过 APIM（可选配置；未配置时 VM 组显示 0%）

---

### 4.3 Red Teaming 与模型行为健康

| 指标 | 图形 | 是否本期实现 | 设计确认状态 | 指标解释 | 指标数据来源 |
|---|---|---|---|---|---|
| Red Teaming Coverage by Target Type | stacked bar | 是 | 已确认 | 按治理对象类型分拆的已完成 red teaming 覆盖率 | Azure DevOps Work Items（PyRIT 结果存储）、Azure AI Foundry Red Teaming |
| Attack Success Rate by Target Type | stacked bar | 是 | 已确认 | 按治理对象类型分拆的攻击成功率（越低越好） | Azure AI Foundry Red Teaming（PyRIT）、Azure DevOps Work Items |
| Open High-Risk Red Team Findings | plain number + sparkline | 是 | 已确认 | 当前未关闭的高危/严重红队发现数量及趋势 | Azure DevOps Work Items（标签 `red-team`、严重度 High/Critical） |

**数据来源**：
- Azure AI Foundry Red Teaming（内置）：Azure 托管模型和 Agent
- PyRIT（外部调用）：VM 模型 OpenAI-compatible 推理端点，零 VM 侧改动；结果写入 Azure DevOps Work Items
- Azure DevOps Work Items：`GET /wit/workitems?$filter=type='Bug'&tags='red-team'`

**计算逻辑**：
- Red Teaming Coverage = 本周期内已完成至少一次 red teaming 的 target 数 / 纳管 target 总数，按 target_type 分拆
- Attack Success Rate = 成功绕过安全控制的攻击数 / 总攻击场景数，按 target_type 分拆
- Open High-Risk Findings = Azure DevOps Work Items 中状态为 Open / Active，severity = High / Critical，tag 含 `red-team` 的数量

**VM 模型 Red Teaming 策略**：
- PyRIT 通过 VM 模型的 OpenAI-compatible REST 端点发起外部调用
- 不需要在 VM 内安装任何 agent 或修改模型配置
- 需要 VM 推理端点可从红队执行环境访问（可通过 APIM 或直接网络路由实现）

---

### 4.4 文本合成内容 Disclosure（完全后置 / 当前隐藏）

> **状态：后置。当前 disclosure scope 未定义，不展示此目录。**

| 指标 | 图形 | 是否本期实现 | 设计确认状态 | 指标解释 | 指标数据来源 |
|---|---|---|---|---|---|
| AI Disclosure Label Coverage | donut | 否（当前隐藏） | 后置 | 已明确披露 AI 生成来源的文本输出占比 | Application Insights、自定义 disclosure 元数据 |
| Unlabeled AI-Generated Text Outputs | plain number + sparkline | 否（当前隐藏） | 后置 | 缺少 AI 生成标识的文本输出数量 | Application Insights、自定义 disclosure 元数据 |

---

### 4.5 偏差 / 稳定性 / 人机协同（完全后置）

> **状态：后置。当前不具备支撑此类指标的数据基础。**

| 指标 | 图形 | 是否本期实现 | 设计确认状态 | 指标解释 | 指标数据来源 |
|---|---|---|---|---|---|
| 输出波动率 | plain number + sparkline | 否 | 后置 | 相同输入下输出结果不稳定的程度 | Azure AI Foundry Evaluations、Application Insights |
| 人工复核推翻率 | donut | 否 | 后置 | 人工复核后被推翻的输出占比 | Dataverse 人工复核队列、Power BI 评测结果集 |
| 偏差样本率 | donut | 否 | 后置 | 评测样本中触发偏差判定的比例 | Azure AI Foundry Evaluations、Power BI 评测结果集 |

---

## 5. 数据约束与配置依赖

| 约束项 | 当前状态 | 处理方式 |
|---|---|---|
| RAG 系统 | 当前无 | Groundedness / Source Attribution Rate 显示 N/A；RAG 就绪后自动生效 |
| App Insights model_name / model_version 字段 | 尚未确认是否已配置 | 若支持，用户可增加配置；Model Identity Capture Rate 依赖此字段 |
| VM 模型通过 APIM 暴露 | 可选配置 | 未配置时 VM 组 Model Identity Capture Rate 显示 0%；建议配置 |
| PyRIT 结果存储 | 可设计 | 建议：PyRIT 执行后结果写入 Azure DevOps Work Items（tag: `red-team`） |
| Disclosure scope | 未定义 | 4.4 目录完全后置，不展示 |

---

## 6. API 端点设计（开发参考）

```
GET /api/metrics/domain4/evaluation-coverage
  → { by_target_type: [{type, total, evaluated, coverage_pct}], total_coverage_pct }

GET /api/metrics/domain4/groundedness
  → { rate: null | float, n/a_reason: "no_rag" | null, sample_count: int }

GET /api/metrics/domain4/safety-evaluator-failure
  → { failure_rate: float, failure_count: int, total_evaluated: int }

GET /api/metrics/domain4/traceable-output-rate
  → { rate: float, traceable: int, total: int, scope: "azure_hosted_only" }

GET /api/metrics/domain4/model-identity-capture
  → { overall_rate: float, by_platform: [{platform, rate, captured, total}] }

GET /api/metrics/domain4/red-teaming-coverage
  → { by_target_type: [{type, total, red_teamed, coverage_pct}] }

GET /api/metrics/domain4/attack-success-rate
  → { by_target_type: [{type, success_rate, attacks, successes}] }

GET /api/metrics/domain4/open-red-team-findings
  → { count: int, sparkline: [int] }
```
