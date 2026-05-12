# Domain 4 · 前置条件环境与依赖设计

## 1. 文档定位

本文件用于跟踪 `L2-domain-4-output-trustworthiness` 的实施前置条件、环境准备项、依赖系统、配置要求、后续操作步骤、脚本与开发产物。

当前阶段先维护"要做的事情列表"，后续逐步补充每一项的：
- 具体需求
- 设计说明
- 操作步骤
- 云上配置
- 需要开发的脚本
- 需要纳入本项目的代码与接口

---

## 2. 设计约束（非步骤，供所有步骤参考）

> 以下内容是 Domain 4 的设计要求与边界，不是可执行的操作步骤。后续每个步骤的实施都必须符合这些约束。

### 2.1 纳管范围

| 纳管对象 / 报表展示对象 | 治理策略 | 是否需要预先准备 |
|---|---|---|
| AI 应用（App Service） | Evaluation + Red Teaming + App Insights | 是 |
| Azure AI Foundry 原生模型 | Evaluation + Tracing + Red Teaming | 是 |
| Azure AI Foundry fine-tune 模型 | Evaluation + Tracing + Red Teaming | 是 |
| Azure AI Foundry 自定义 Agent | Evaluation + Red Teaming | 是 |
| Copilot Studio 自定义 Agent | Evaluation + Red Teaming | 是 |
| VM 中从 Hugging Face 下载并部署的自建模型 | 红队外部调用（PyRIT） + APIM 身份捕获 | 是 |
| Tier 1 Consumer App（AI 服务直接调用方） | App Insights（完整调用链） + Evaluation + Red Teaming | 是 |
| Tier 2 Consumer App（通过 Tier 1 间接使用 AI） | App Insights（correlation_id 透传，间接 AI 使用追踪） | 是 |

**约束**：本领域仅覆盖**文本类模型**，不含图像生成、视频、语音等多模态输出。

### 2.2 报表展示拆分原则

Domain 4 的二级页面在展示 coverage、failure rate、red teaming、model identity 等指标时，必须按以下测试对象类型分别展示，不能把不同对象混在一个总数里：

1. AI 应用（App Service）
2. Azure AI Foundry 原生模型
3. Azure AI Foundry fine-tune 模型
4. Azure AI Foundry 自定义 Agent
5. Copilot Studio 自定义 Agent
6. VM 中从 Hugging Face 下载并部署的自建模型
7. Tier 1 Consumer App（直接调用 AI 服务）
8. Tier 2 Consumer App（经 Tier 1 间接使用 AI 服务）

### 2.3 本期治理指标列表

| 指标 | 来源区块 | 状态 |
|---|---|---|
| Evaluation Coverage by Target Type | 4.1 | 本期实现 |
| Groundedness / Citation Rate | 4.1 | 无 RAG 时显示 N/A |
| Safety Evaluator Failure Rate | 4.1 | 本期实现 |
| Traceable Output Rate | 4.2 | 仅 Azure 托管；VM 不计 |
| Source Attribution Rate | 4.2 | 无 RAG 时显示 N/A |
| Model Identity Capture Rate / Gaps | 4.2 | 本期实现（L1 主指标） |
| Red Teaming Coverage by Target Type | 4.3 | 本期实现 |
| Attack Success Rate by Target Type | 4.3 | 本期实现 |
| Open High-Risk Red Team Findings | 4.3 | 本期实现 |

**后置指标（不在本期实现）**：AI Disclosure Label Coverage、Unlabeled AI-Generated Text Outputs、输出波动率、人工复核推翻率、偏差样本率。

### 2.4 APIM / API / Application Insights 监控设计

Domain 4 中 APIM 的定位不是替代应用侧遥测，也不是强制接管所有 Azure 原生 endpoint；APIM 是**可控调用入口、统一检测入口、VM / 自建模型身份捕获入口**。Application Insights 是**应用内遥测、端到端 correlation、response / model identity / citation 证据的落地位置**。

设计原则：

1. 凡是由本项目建设或可控的 AI 应用 / 模型 API，优先通过 APIM 暴露给检测程序和外部调用方。
2. Azure AI Foundry / Azure OpenAI 原生 endpoint 可以直接调用；如需统一检测、限流、审计和字段注入，可在 APIM 中建立代理 API。
3. VM 中从 Hugging Face 下载并部署的模型必须经 APIM 代理，除非仅用于临时内网验证。
4. Copilot Studio Agent 如通过 Direct Line / 自定义连接器暴露，优先通过 APIM 包一层统一检测入口；如果通道限制导致无法代理，则由检测脚本将调用日志写入 Application Insights。
5. APIM 负责记录 gateway 视角：谁调用、调用哪个 target、请求/响应状态、耗时、model identity、test run id。
6. Application Insights 负责记录应用 / 模型调用视角：`response_id`、`model_name`、`model_version`、`target_type`、`target_id`、`citations`、trace / dependency correlation。
7. 检测程序（Evaluation / PyRIT / 自定义 smoke test）应优先调用 APIM URL，而不是直接调用后端 endpoint，除非该目标无法被 APIM 代理。

#### 2.4.1 被测试系统需要暴露的 API

| 测试对象 | 应暴露的 API | 是否建议通过 APIM | App Insights 管理方式 |
|---|---|---|---|
| RAG Service（App Service） | `GET /health`；`POST /rag/query`；`POST /v1/chat/completions`；`GET /metadata` | 是 | 应用代码写入 request / dependency / custom event；记录 response、model、citation、retrieval metadata |
| Azure AI Foundry 原生模型 | Azure OpenAI / Foundry 原生推理 endpoint；可选 APIM 代理 endpoint：`POST /foundry/native/{deployment}/chat/completions` | 可选；用于统一检测和审计时建议代理 | Foundry tracing + 调用脚本 / APIM 日志；记录 deployment、model、response id |
| Azure AI Foundry fine-tune 模型 | 原生 fine-tuned deployment endpoint；可选 APIM 代理 endpoint：`POST /foundry/finetune/{deployment}/chat/completions` | 可选；用于统一检测和审计时建议代理 | Foundry tracing + 调用脚本 / APIM 日志；必须与原生模型分开标记 target type |
| VM Hugging Face 模型 | `GET /health`；`POST /v1/chat/completions`；`GET /metadata` | 是，正式检测必须经 APIM | VM API 写入 App Insights 或由 APIM gateway 记录；APIM policy 注入 `deployment_type=vm_huggingface` |
| Azure AI Foundry 自定义 Agent | Agent invocation endpoint；可选 APIM 代理 endpoint：`POST /agents/foundry/{agent_id}/invoke` | 可选；如果 endpoint 支持代理则建议代理 | Foundry 记录 + 调用脚本 / APIM 日志；记录 agent id、project、model |
| Copilot Studio 自定义 Agent | Direct Line / Custom Connector endpoint；可选 APIM 代理 endpoint：`POST /agents/copilot-studio/{bot_id}/invoke` | 条件支持；可代理时建议代理 | 调用脚本或 APIM 记录 conversation id、bot id、environment id |
| Evaluation runner / PyRIT runner（如后续开发为服务） | `POST /runs`；`GET /runs/{run_id}`；`GET /health` | 可选；需要集中触发检测时建议代理 | runner 应写入 App Insights，并把结果写入 Azure DevOps Work Items |

#### 2.4.2 APIM 应监控的 API 范围

APIM 应优先纳管以下 API：

1. 所有本项目建设的 AI 应用 API：RAG Service、后续 demo app、测试 runner。
2. 所有 VM / 自建模型 API：尤其是 Hugging Face LLM 的 OpenAI-compatible endpoint。
3. 所有需要统一红队或评估入口的 target API：Foundry 原生模型、Foundry fine-tune 模型、Foundry Agent、Copilot Studio Agent。
4. 所有会被 PyRIT / Evaluation / smoke test 调用的 endpoint，只要技术上可代理，都优先通过 APIM。

APIM 不应作为主监控入口的范围：

1. Azure Resource Manager、Foundry 管理面、DevOps Work Items 等 control plane API；这些由脚本通过 SPN / 用户权限直接调用，并在脚本日志中记录。
2. 只能通过平台内部机制访问且无法稳定代理的 endpoint；这类目标由检测脚本补充写入 Application Insights。
3. 纯 UI 操作，不经过可调用 API 的系统；仅记录操作结果和资产状态，不纳入调用级指标。

#### 2.4.3 APIM 必须记录 / 注入的字段

APIM policy 或调用方必须尽量提供以下字段，用于后续 Domain 4 报表：

| 字段 | 含义 |
|---|---|
| `target_type` | `ai_app`、`foundry_native_model`、`foundry_finetune_model`、`foundry_agent`、`copilot_studio_agent`、`vm_huggingface_model` |
| `target_id` | 目标对象唯一标识，如 deployment name、agent id、bot id、VM model service name |
| `model_name` | 模型名称 |
| `model_version` | 模型版本；如无法从平台获得，需要在 target registry 中维护 |
| `deployment_type` | `app_service`、`foundry`、`copilot_studio`、`vm_huggingface` |
| `test_tool` | `evaluation`、`pyrit`、`smoke_test`、`manual`、`dashboard` |
| `test_run_id` | 一次 evaluation / red teaming / smoke test 的运行 ID |
| `response_id` | 后端 response id；若后端无原生 id，则由 gateway / app 生成等效 id |
| `correlation_id` | 贯穿 APIM、App Insights、evaluation result、DevOps work item 的关联 ID |

#### 2.4.4 Application Insights 管理边界

Application Insights 的管理对象分为三类：

1. **应用内遥测**：RAG Service、VM API、runner service 等可改代码的应用，必须直接写入 App Insights。
2. **网关遥测**：APIM gateway 日志必须进入 Log Analytics / Application Insights，用于覆盖不可改代码或外部托管目标。
3. **检测脚本遥测**：Evaluation / PyRIT / smoke test 脚本需要在每次调用后写入统一事件，补齐 target、run、result、failure reason。

建议统一事件名：

| 事件名 | 使用场景 |
|---|---|
| `Domain4TargetInvocation` | 每次 target 调用 |
| `Domain4EvaluationRun` | 每次 evaluation run 汇总 |
| `Domain4RedTeamRun` | 每次 PyRIT / red team run 汇总 |
| `Domain4ModelIdentityObserved` | 成功捕获 model identity |
| `Domain4CitationObserved` | 成功捕获 citation / source attribution |
| `Domain4FindingCreated` | 写入 Azure DevOps finding 时记录 |

#### 2.4.5 初始 API 命名建议

APIM 中建议按 target type 分 product / API，便于权限、限流和报表映射：

| APIM API | 后端目标 |
|---|---|
| `/domain4/rag-demo/*` | RAG Service（App Service） |
| `/domain4/foundry/native/*` | Azure AI Foundry 原生模型 deployment |
| `/domain4/foundry/finetune/*` | Azure AI Foundry fine-tune 模型 deployment |
| `/domain4/vm-huggingface/*` | VM Hugging Face 模型 API |
| `/domain4/agents/foundry/*` | Azure AI Foundry 自定义 Agent |
| `/domain4/agents/copilot-studio/*` | Copilot Studio 自定义 Agent |
| `/domain4/tier1/*` | Tier 1 Consumer App（App Service，直接 AI 服务调用方） |
| `/domain4/tier2/*` | Tier 2 Consumer App（App Service，通过 Tier 1 间接使用 AI） |
| `/domain4/test-runs/*` | Evaluation / PyRIT runner service（后续如开发） |

#### 2.4.6 API / APIM / Application Insights 总览矩阵

本表用于持续跟踪每类被测对象需要暴露的 API、是否纳入 APIM、是否由 Application Insights 管理，以及当前设计状态。后续每完成一个 target，就在本表中补充实际 endpoint、resource id、状态和验证结果。

| 关联步骤 | 被测对象 | API / Endpoint | 后端承载 | APIM 管理 | APIM API 建议 | App Insights 管理 | 当前状态 |
|---|---|---|---|---|---|---|---|
| 2 | RAG Service | `GET /health`；`POST /rag/query`；`POST /v1/chat/completions`；`GET /metadata` | App Service | 必须 | `/domain4/rag-demo/*` | 必须；应用代码直接写入 | 待建设 |
| 3 | Azure AI Foundry 原生模型 | Foundry / Azure OpenAI 原生推理 endpoint；可选 OpenAI-compatible proxy | Azure AI Foundry / Azure OpenAI | 可选；如用于统一检测则纳入 | `/domain4/foundry/native/*` | 必须；Foundry tracing + APIM / 调用脚本补充 | 待确认现有 deployment |
| 4 | Azure AI Foundry fine-tune 模型 | Fine-tuned deployment endpoint；可选 OpenAI-compatible proxy | Azure AI Foundry / Azure OpenAI | 可选；如用于统一检测则纳入 | `/domain4/foundry/finetune/*` | 必须；Foundry tracing + APIM / 调用脚本补充 | 待建设 |
| 5-6 | VM Hugging Face 模型 | `GET /health`；`POST /v1/chat/completions`；`GET /metadata` | Azure VM | 必须 | `/domain4/vm-huggingface/*` | 必须；VM API 或 APIM gateway 写入 | 待建设 |
| 7 | Azure AI Foundry 自定义 Agent | Agent invocation endpoint；可选代理 API | Azure AI Foundry Agent | 可选；如 endpoint 可代理则纳入 | `/domain4/agents/foundry/*` | 必须；Foundry / APIM / 调用脚本补充 | 待建设 |
| 8 | Copilot Studio 自定义 Agent | Direct Line / Custom Connector endpoint；可选代理 API | Copilot Studio / Dataverse | 条件支持；可代理则纳入 | `/domain4/agents/copilot-studio/*` | 必须；APIM 或调用脚本写入 | 待建设，需 UI 操作 |
| 9 | Tier 1 Consumer App | `GET /health`；`POST /query`；`GET /metadata` | App Service | 必须 | `/domain4/tier1/*` | 必须；应用代码直接写入 | 待建设 |
| 10 | Tier 2 Consumer App | `GET /health`；`POST /request`；`GET /metadata` | App Service | 必须 | `/domain4/tier2/*` | 必须；应用代码直接写入 | 待建设 |
| 11 | Evaluation runner | `POST /runs`；`GET /runs/{run_id}`；`GET /health` | 后续 runner service | 可选；需要集中触发时纳入 | `/domain4/test-runs/evaluations/*` | 必须；runner 写入 run / result 事件 | 后续设计 |
| 13 | PyRIT runner | `POST /runs`；`GET /runs/{run_id}`；`GET /health` | 后续 runner service / 脚本 | 可选；需要集中触发时纳入 | `/domain4/test-runs/pyrit/*` | 必须；runner 写入 run / finding 事件 | 后续设计 |

#### 2.4.7 APIM 监控字段矩阵

本表用于定义 APIM gateway 必须记录或注入的字段。字段优先从调用方 header / query / request body 传入；缺失时由 APIM policy 或后端 target registry 补齐。

| 关联步骤 | APIM API | 必填字段 | 推荐字段 | 字段来源 | 主要用途 |
|---|---|---|---|---|---|
| 2 | `/domain4/rag-demo/*` | `target_type=ai_app`；`target_id`；`test_tool`；`correlation_id` | `response_id`；`model_name`；`model_version`；`citations_count`；`test_run_id` | RAG Service response + APIM policy | Groundedness、Source Attribution、Traceable Output、Model Identity |
| 3 | `/domain4/foundry/native/*` | `target_type=foundry_native_model`；`target_id`；`model_name`；`model_version`；`correlation_id` | `test_tool`；`test_run_id`；`response_id` | target registry + Foundry response + APIM policy | Evaluation coverage、Safety failure、Model Identity |
| 4 | `/domain4/foundry/finetune/*` | `target_type=foundry_finetune_model`；`target_id`；`model_name`；`model_version`；`correlation_id` | `base_model_name`；`fine_tune_job_id`；`test_tool`；`test_run_id` | fine-tune registry + APIM policy | Fine-tune model 单独展示、Evaluation coverage、Red Teaming |
| 5-6 | `/domain4/vm-huggingface/*` | `target_type=vm_huggingface_model`；`target_id`；`deployment_type=vm_huggingface`；`model_name`；`model_version`；`correlation_id` | `response_id`；`test_tool`；`test_run_id`；`backend_latency_ms` | APIM policy + VM API `/metadata` | VM 模型身份捕获、APIM 侧可追溯、Red Teaming |
| 7 | `/domain4/agents/foundry/*` | `target_type=foundry_agent`；`target_id`；`agent_id`；`correlation_id` | `model_name`；`model_version`；`project_id`；`test_tool`；`test_run_id` | Foundry Agent metadata + APIM policy | Agent coverage、Red Teaming、Evaluation |
| 8 | `/domain4/agents/copilot-studio/*` | `target_type=copilot_studio_agent`；`target_id`；`bot_id`；`environment_id`；`correlation_id` | `conversation_id`；`test_tool`；`test_run_id` | Copilot Studio channel response + APIM policy | Copilot Studio Agent 单独展示、Red Teaming |
| 9 | `/domain4/tier1/*` | `target_type=tier1_consumer`；`correlation_id`；`target_id` | `downstream_target_type`；`downstream_target_id`；`response_id`；`test_run_id` | 应用层透传 + APIM policy | Traceable Output、Model Identity、间接 AI 使用追踪入口 |
| 10 | `/domain4/tier2/*` | `target_type=tier2_consumer`；`correlation_id` | `downstream_app=tier1`；`session_id`；`test_run_id` | 应用层生成 + APIM policy | 调用链起点标记、间接 AI 使用入口 |
| 11 / 13 | `/domain4/test-runs/*` | `test_tool`；`test_run_id`；`correlation_id`；`target_type`；`target_id` | `scenario_id`；`severity`；`result_status`；`finding_id` | runner service / script | 串联 APIM、App Insights、Azure DevOps Work Items |

#### 2.4.8 Application Insights 遥测矩阵

本表用于定义哪些应用 / API 必须由 Application Insights 管理，以及主要记录哪些字段。原则是：可改代码的应用直接写；不可改代码的托管目标由 APIM 或检测脚本补写；Foundry 支持 tracing 的目标同时读取 Foundry tracing。

| 关联步骤 | 应用 / API | App Insights 管理方式 | 主要事件 / 表 | 必须字段 | 推荐字段 | 用于指标 |
|---|---|---|---|---|---|---|
| 2 | RAG Service（App Service） | 应用代码直接写入 | `requests`；`dependencies`；`customEvents: Domain4TargetInvocation`；`Domain4CitationObserved` | `response_id`；`model_name`；`model_version`；`target_type`；`target_id`；`citations`；`correlation_id` | `retrieved_document_count`；`retrieval_latency_ms`；`prompt_tokens`；`completion_tokens` | Groundedness、Source Attribution、Traceable Output、Model Identity |
| 3 | Azure AI Foundry 原生模型 | Foundry tracing + 调用脚本补写 | Foundry trace；`customEvents: Domain4TargetInvocation` | `target_type=foundry_native_model`；`target_id`；`model_name`；`model_version`；`response_id`；`correlation_id` | `deployment_name`；`project_id`；`prompt_tokens`；`completion_tokens` | Evaluation Coverage、Safety Failure、Model Identity |
| 4 | Azure AI Foundry fine-tune 模型 | Foundry tracing + 调用脚本补写 | Foundry trace；`customEvents: Domain4TargetInvocation` | `target_type=foundry_finetune_model`；`target_id`；`model_name`；`model_version`；`correlation_id` | `base_model_name`；`fine_tune_job_id`；`deployment_name` | Fine-tune 单独报表、Evaluation、Red Teaming |
| 5-6 | VM Hugging Face API | VM API 直接写入；或由 APIM gateway 补写 | `requests`；`dependencies`；`customEvents: Domain4TargetInvocation`；`Domain4ModelIdentityObserved` | `response_id`；`model_name`；`model_version`；`target_type=vm_huggingface_model`；`target_id`；`correlation_id` | `backend_latency_ms`；`gpu_type`；`model_path`；`api_version` | Model Identity、Attack Success Rate、Red Teaming Coverage |
| 6 / 9 | APIM gateway | Diagnostic settings 写入 Log Analytics / App Insights | `AzureDiagnostics` / APIM gateway logs；`requests`（如启用） | `target_type`；`target_id`；`operation_name`；`status_code`；`duration_ms`；`correlation_id` | `subscription_id`；`caller_app`；`test_tool`；`test_run_id` | 所有经 APIM 的调用覆盖、错误率、model identity gap |
| 7 | Azure AI Foundry 自定义 Agent | Foundry trace / Agent logs + 调用脚本补写 | Foundry trace；`customEvents: Domain4TargetInvocation` | `target_type=foundry_agent`；`target_id`；`agent_id`；`correlation_id` | `project_id`；`model_name`；`model_version` | Agent coverage、Red Teaming、Safety Failure |
| 8 | Copilot Studio 自定义 Agent | APIM 或检测脚本补写 | `customEvents: Domain4TargetInvocation` | `target_type=copilot_studio_agent`；`target_id`；`bot_id`；`environment_id`；`correlation_id` | `conversation_id`；`channel_id`；`topic_name` | Agent Red Teaming、Attack Success Rate |
| 9 | Tier 1 Consumer App | 应用代码直接写入 | `requests`；`dependencies`；`customEvents: Domain4TargetInvocation` | `response_id`；`model_name`；`model_version`；`target_type=tier1_consumer`；`target_id`；`correlation_id`；`downstream_target_type`；`downstream_target_id` | `citations`；`prompt_tokens`；`completion_tokens`；`downstream_latency_ms` | Model Identity Capture、Traceable Output、间接 AI 使用调用链 |
| 10 | Tier 2 Consumer App | 应用代码直接写入 | `requests`；`dependencies`；`customEvents: Domain4TargetInvocation` | `target_type=tier2_consumer`；`correlation_id`；`upstream_app`；`target_id` | `session_id`；`user_id`；`scenario_id` | 间接 AI 使用追踪、调用链起点、覆盖率分母 |
| 11 | Evaluation runner | runner 直接写入 | `customEvents: Domain4EvaluationRun`；`Domain4TargetInvocation` | `test_tool=evaluation`；`test_run_id`；`target_type`；`target_id`；`result_status`；`correlation_id` | `evaluator_name`；`score`；`threshold`；`dataset_id` | Evaluation Coverage、Groundedness、Safety Failure |
| 13 | PyRIT runner | runner 直接写入 | `customEvents: Domain4RedTeamRun`；`Domain4FindingCreated` | `test_tool=pyrit`；`test_run_id`；`target_type`；`target_id`；`attack_scenario_id`；`result_status` | `severity`；`finding_id`；`ado_work_item_id`；`prompt_template_id` | Red Teaming Coverage、Attack Success Rate、Open Findings |

#### 2.4.9 检测工具依赖矩阵

本表用于跟踪检测工具依赖 APIM、Application Insights、Azure DevOps 的方式。后续新增检测工具时，应先在本表登记，再开发 connector 或脚本。

| 关联步骤 | 检测工具 / 程序 | 调用目标方式 | 是否依赖 APIM | 是否写入 App Insights | 是否读取 App Insights | 是否写入 Azure DevOps | 依赖字段 |
|---|---|---|---|---|---|---|---|
| 9 | APIM diagnostic job | APIM gateway diagnostic logs | 是 | 是，作为日志来源 | 是 | 否 | `operation_name`、`target_type`、`target_id`、`duration_ms`、`status_code` |
| 11 | Smoke test script | 优先 APIM；无法代理时直连 endpoint | 是，优先 | 是 | 可选，用于验证落日志 | 否 | `target_type`、`target_id`、`correlation_id`、`status_code` |
| 11 | Azure AI Foundry Evaluations | Foundry target / APIM proxy / endpoint 直连 | 条件依赖；用于统一入口时依赖 | 是，通过 runner 或脚本补写 | 可选，用于合并 trace 与分数 | 可选，仅失败或高风险时写入 | `test_run_id`、`target_type`、`target_id`、`score`、`evaluator_name` |
| 12 | Azure DevOps finding sync | ADO REST API | 否 | 是，记录 sync 状态 | 可选 | 是 | `finding_id`、`ado_work_item_id`、`severity`、`status`、`target_type` |
| 13 | PyRIT Red Teaming | connector 默认调用 APIM URL | 是，优先 | 是 | 可选，用于确认 target invocation | 是，高风险或成功攻击写入 | `test_run_id`、`attack_scenario_id`、`severity`、`target_type`、`target_id` |
| 15 | Dashboard metric collector | 读取 API / Log Analytics / App Insights / ADO | 否，通常不调用 target | 否 | 是 | 是，读取 findings | `target_type`、`target_id`、`model_name`、`model_version`、`result_status` |

---

## 3. 执行原则

1. 优先使用 `.env.local` 中已有参数和 SPN 权限执行 Azure / Microsoft 365 操作。
2. 如果某项操作必须使用用户交互权限，则开启登录 session，由用户完成登录或授权。
3. 我可以代为执行的操作，必须沉淀为脚本、命令记录或设计文档，避免只做一次性手工操作。
4. 必须通过 UI 完成的操作，需要在本文档中写清楚用户操作路径、输入项和验证方式。
5. 需要需求与设计后才能开发的内容，先补充需求和接口设计，再进入代码实现。
6. Microsoft 365 Copilot（企业版）没有可供外部程序调用的推理端点，当前不作为 Domain 4 的可测试目标；M365 Copilot 资产由 Domain 1 资产台账覆盖。

---

## 4. 前置条件与准备步骤列表

1. 准备 Log Analytics / Application Insights / APIM 日志落地
   - 操作步骤：
     1. 使用 `.env.local` 中的订阅、资源组、SPN 参数查询现有 Application Insights、Log Analytics workspace、APIM 资源。
     2. 如果资源已存在，记录 resource id、workspace id、connection string、diagnostic setting 状态。
     3. 如果资源缺失，先设计命名、区域、保留周期、权限，再用脚本创建。
     4. 为 App Service、APIM、Azure AI 相关资源配置 diagnostic settings，日志统一进入 Log Analytics。
     5. 按 §2.4 确认 APIM 是否已有可承载 Domain 4 API 的 product / API 命名空间。
     6. 用 KQL 查询验证日志表可读。
   - 我可以执行：Azure CLI / REST 查询、创建脚本、诊断设置脚本、KQL 验证脚本。
   - 可能需要用户操作：如果 SPN 权限不足，需要用户登录 Azure CLI 或在 Portal 中授予权限。
   - 产物：`scripts/` 下的环境检查与配置脚本；本文档中的资源清单与 KQL 验证语句。

2. 建立 RAG 服务基础设施（AI RAG 服务，供 Tier 1 App 调用）
   - 操作步骤：
     1. 确认 Azure AI Search、Azure OpenAI / Azure AI Foundry 模型部署是否存在。
     2. 设计最小 RAG 索引 schema：`id`、`content`、`source`、`page`、`content_vector`。
     3. 使用仓库内 NIST AI 600-1 PDF 作为初始知识材料，后续可加入公司 AI 政策文档。
     4. 开发文档切分、embedding、上传到 Azure AI Search 的脚本。
     5. 开发 RAG Service API：`retrieve → prompt → generate → return answer + citations`。
     6. 在每次调用中记录 `response_id`、`model_name`、`model_version`、`citations`。
     7. 将调用日志写入 Application Insights。
     8. 将 RAG Service 部署到 App Service，作为 Tier 1 App 的 AI 服务后端，同时作为 Domain 4 可评估目标。
   - 我可以执行：代码与脚本开发、Azure 资源查询、索引创建、App Service 部署脚本。
   - 可能需要用户操作：如果 Search / Azure OpenAI 创建或模型部署需要 Portal 权限，由用户按步骤完成。
   - 产物：RAG Service 需求设计、索引 schema、ingestion 脚本、RAG Service API 代码、App Insights 遥测字段说明。
   - 注意：本步骤只建设 RAG 服务，不包含消费端应用；Tier 1 Consumer App 在步骤 9 中开发。

3. 准备 Azure AI Foundry 原生模型部署（Azure AI Foundry 原生模型类目标）
   - 操作步骤：
     1. 查询当前 Azure AI Foundry / Azure OpenAI 可用模型部署。
     2. 选择一个基础文本模型作为原生模型目标。
     3. 如果未部署，通过脚本或 Portal 创建模型 deployment。
     4. 记录模型名称、deployment 名称、版本、endpoint、project 信息。
     5. 验证推理端点可调用。
     6. 将该模型作为独立 target type 写入后续 evaluation / red teaming / dashboard 设计。
   - 我可以执行：资源查询、调用验证、部署脚本草案、模型清单文档。
   - 可能需要用户操作：模型部署配额、区域选择或 Portal 内模型部署授权。
   - 产物：模型 deployment 清单、验证命令、报表对象映射。

4. 准备 Azure AI Foundry fine-tune 模型（Azure AI Foundry fine-tune 模型类目标）
   - 操作步骤：
     1. 明确 fine-tune 的测试目标：只为 Domain 4 测试提供一个可治理对象，不追求业务效果最大化。
     2. 设计最小训练数据格式和样例数据来源。
     3. 准备训练数据清洗、格式转换和上传脚本。
     4. 提交 fine-tune job，并记录 job id、基础模型、输出模型信息。
     5. 部署 fine-tuned model 到可调用 endpoint。
     6. 验证 endpoint 可调用，并纳入 evaluation / red teaming / dashboard 独立展示。
   - 我可以执行：训练数据样例、格式转换脚本、提交 job 脚本、验证脚本。
   - 可能需要用户操作：如果 fine-tune 权限、配额或 Portal 审批不足，需要用户授权或手工启动。
   - 产物：fine-tune 需求设计、训练数据格式、job 操作脚本、部署清单。

5. 在 VM 里下载、安装、配置 Hugging Face 上的模型（LLM），并开发 API（VM Hugging Face 模型类目标）
   - 操作步骤：
     1. 确认 VM 操作系统、GPU / CPU、磁盘、网络、安全组、Python 版本。
     2. 选择小型可运行的 Hugging Face 文本模型，优先选择资源消耗低、许可清晰的模型。
     3. 编写 VM 初始化脚本：安装 Python、venv、transformers / vLLM / llama.cpp 等依赖。
     4. 下载模型到 VM 本地目录或挂载磁盘。
     5. 开发 OpenAI-compatible 推理 API。
     6. 配置 systemd / supervisor 启动服务。
     7. 验证 API 在内网可访问。
   - 我可以执行：VM 检查脚本、安装脚本、API 服务代码、启动服务配置。
   - 可能需要用户操作：如果需要 SSH 登录、开端口、分配 GPU、调整 NSG，需要用户协助或授权登录 session。
   - 产物：VM 部署设计、安装脚本、API 代码、服务配置、验证命令。

6. 为 VM Hugging Face 模型接入 Azure API Management（步骤 5 的扩展）
   - 操作步骤：
     1. 确认 APIM 实例、网络可达性、VM API 内网地址。
     2. 在 APIM 中创建 `/domain4/vm-huggingface/*` API / operation，代理 VM 模型推理端点。
     3. 配置 APIM policy，注入或记录 `model_name`、`model_version`、`deployment_type=vm_huggingface`。
     4. 配置 `target_type`、`target_id`、`test_tool`、`test_run_id`、`correlation_id` 字段透传或生成。
     5. 配置 APIM diagnostic settings，将 gateway log 写入 Application Insights / Log Analytics。
     6. 验证从 APIM 调用 VM 模型成功。
   - 我可以执行：APIM 配置脚本、policy XML、验证脚本。
   - 可能需要用户操作：APIM 网络 / VNet / private endpoint 配置若需 Portal 操作，由用户完成。
   - 产物：APIM policy、API 配置脚本、日志字段映射。

7. 使用 Azure AI Foundry 开发并部署一个自定义 Agent（Azure AI Foundry Agent 类目标）
   - 操作步骤：
     1. 明确 Agent 的最小场景，例如基于治理知识库的问答 Agent。
     2. 在 Azure AI Foundry 创建 Agent project / Agent。
     3. 绑定可用模型和知识源（可复用 RAG Service 知识材料）。
     4. 发布 Agent 并获取可调用 endpoint 或 invocation 方式。
     5. 验证 Agent 可被外部脚本调用。
     6. 记录 Agent id、endpoint、project、模型信息，作为独立报表对象。
   - 我可以执行：需求设计、调用验证脚本、Agent 清单文档。
   - 可能需要用户操作：Foundry Portal 中创建 / 发布 Agent 如无法脚本化，由用户按步骤完成。
   - 产物：Agent 设计说明、调用示例、纳管清单。

8. 使用 Copilot Studio 创建并发布一个自定义 Agent（Copilot Studio Agent 类目标）
   - 操作步骤：
     1. 在 Copilot Studio 创建最小自定义 Agent。
     2. 配置知识源或 topic，使其能回答固定治理问题。
     3. 发布 Agent。
     4. 启用可被外部调用的通道，例如 Direct Line 或 Custom Connector。
     5. 获取 endpoint、bot id、环境 id，并验证脚本可调用。
     6. 与 Domain 1 Dataverse `bots` 资产发现结果对齐，作为独立报表对象。
   - 我可以执行：调用验证脚本、Dataverse 发现对齐脚本、记录字段设计。
   - 必须用户操作：Copilot Studio UI 创建、发布、通道开启通常需要用户在 UI 中完成。
   - 产物：UI 操作指南、Agent 端点记录、调用验证脚本。

9. 开发 Tier 1 Consumer App（直接 AI 服务调用方）
   - 定位：代表"合规使用 AI 服务"的标准消费者应用。调用 RAG Service、Foundry 原生模型、Foundry fine-tune 模型、VM Hugging Face 模型、Foundry Agent、Copilot Studio Agent 等全部 AI 服务后端。
   - 操作步骤：
     1. 设计 Tier 1 App 的 API 接口：`POST /query`（接收用户请求并路由到对应 AI 服务）；`GET /health`；`GET /metadata`。
     2. 在接收请求时生成或接受 `correlation_id`，并在所有下游 AI 服务调用中透传此 ID。
     3. 对每类 AI 服务分别实现 connector：RAG Service、Foundry endpoint、VM Hugging Face APIM URL、Foundry Agent、Copilot Studio Direct Line。
     4. 在每次调用后记录 `response_id`、`model_name`、`model_version`、`target_type`、`target_id`、`citations`（若调用 RAG）、`correlation_id` 到 Application Insights。
     5. 将 Tier 1 App 部署到 App Service，并通过 APIM 暴露（`/domain4/tier1/*`）。
     6. 验证从外部调用 Tier 1 可成功触发下游 AI 服务，并确认日志链路完整。
   - 我可以执行：接口设计、connector 代码、遥测 helper、APIM API 配置、部署脚本。
   - 可能需要用户操作：如 AI 服务 endpoint 权限不足，需要用户授权。
   - 产物：Tier 1 App 需求设计、API 代码、connector 代码、遥测 helper、APIM 配置、部署脚本。

10. 开发 Tier 2 Consumer App（通过 Tier 1 间接使用 AI 服务）
    - 定位：代表通过"AI 服务平台层"间接调用 AI 的上游业务应用。Tier 2 不直接调用 AI 服务，只调用 Tier 1，体现"间接 AI 使用"的治理追踪场景。
    - 操作步骤：
      1. 设计 Tier 2 App 的 API 接口：`POST /request`（接收用户输入并转发到 Tier 1）；`GET /health`；`GET /metadata`。
      2. 在接收请求时生成 `correlation_id`（作为本次业务请求的唯一 ID）。
      3. 通过 APIM URL `/domain4/tier1/query` 调用 Tier 1（不直连 Tier 1 App Service），并在请求 header 中透传 `correlation_id`。这样 APIM 会同时记录 Tier 2 → Tier 1 的调用，使该段调用链也具备可追溯性。
      4. 在每次请求前后写入 App Insights：`correlation_id`、`target_type=tier2_consumer`、`upstream=tier1_app`、`target_id`。
      5. 将 Tier 2 App 部署到 App Service，并通过 APIM 暴露（`/domain4/tier2/*`）。
      6. 验证：通过 KQL 可以从 Tier 2 请求的 `correlation_id` 追踪到最终 AI 服务调用（经 APIM log → Tier 1 log → AI 服务 log），证明间接 AI 使用可追溯。
    - 我可以执行：接口设计、转发代码、遥测 helper、APIM API 配置、部署脚本、KQL 验证查询。
    - 可能需要用户操作：如果 App Service / APIM 权限不足，需要用户授权。
    - 产物：Tier 2 App 需求设计、API 代码、APIM 配置、部署脚本、KQL 追踪验证查询。

11. 配置 Application Insights 遥测字段
   - 操作步骤：
     1. 按 §2.4.3 定义统一字段：`response_id`、`model_name`、`model_version`、`target_type`、`target_id`、`citations`、`test_tool`、`test_run_id`、`correlation_id`。
     2. 在 RAG Service、VM API、APIM policy、可控的测试调用脚本中写入这些字段。
     3. 对不可直接埋点的目标，记录来自 Foundry / APIM / 调用脚本的等效字段。
     4. 按 §2.4.4 定义统一事件名，并编写 KQL 查询验证字段覆盖率。
   - 我可以执行：遥测 helper、APIM policy、KQL 查询、字段覆盖率验证脚本。
   - 可能需要用户操作：如果 App Insights 权限不足，需要用户授权。
   - 产物：遥测字段规范、代码 helper、KQL 验证语句。

12. 准备 Azure AI Foundry Tracing 能力
   - 操作步骤：
     1. 确认哪些目标支持 Foundry Tracing：Foundry 原生模型、fine-tune 模型、Foundry Agent。
     2. 在 Foundry 项目中开启 tracing / monitoring。
     3. 连接 Application Insights / Log Analytics。
     4. 触发测试调用，验证 trace 记录生成。
     5. 明确 VM Hugging Face 模型不走 Foundry tracing，由 APIM + App Insights 记录。
   - 我可以执行：tracing 状态检查、调用验证脚本、KQL 查询。
   - 可能需要用户操作：Foundry Portal 中开启 tracing 或连接资源。
   - 产物：Tracing 配置说明、验证查询、适用范围表。

13. 准备 Azure AI Foundry Evaluations 能力
   - 操作步骤：
     1. 设计 evaluation target schema：target type、endpoint、auth、input、expected behavior。
     2. 为 RAG Service、Foundry 原生模型、fine-tune 模型、Foundry Agent、Copilot Studio Agent、VM Hugging Face 模型分别建立 target 记录。
     3. 准备最小 evaluation 数据集。
     4. 配置 groundedness / citation / safety evaluator。
     5. 运行一次评估并导出结果。
     6. 将结果字段映射到 Domain 4 指标。
   - 我可以执行：target 配置文件、评估数据集样例、运行脚本、结果解析脚本。
   - 可能需要用户操作：Foundry UI 中创建 evaluation 或授权 evaluator。
   - 产物：evaluation 需求设计、target 清单、样例数据集、结果解析脚本。

14. 准备 Azure DevOps Work Items / Test Plans
   - 操作步骤：
     1. 确认 Azure DevOps organization / project。
     2. 设计 work item 类型、tag、severity、target_type、target_id 字段使用方式。
     3. 创建或确认用于 red teaming / evaluation findings 的查询和 board。
     4. 编写脚本，将 evaluation / PyRIT 结果写入 Work Items。
     5. 验证 high / critical 未关闭发现可查询。
   - 我可以执行：ADO REST 脚本、work item 创建脚本、查询脚本。
   - 可能需要用户操作：如果 PAT / OAuth / project 权限不足，需要用户授权。
   - 产物：ADO 字段设计、写入脚本、查询脚本。

15. 准备 Red Teaming 执行环境（PyRIT）
   - 操作步骤：
     1. 选择执行环境：本地、开发 VM、GitHub Actions 或 Azure VM。
     2. 安装 PyRIT 和必要依赖。
     3. 为每类目标编写 connector：RAG Service、Foundry 模型、fine-tune 模型、Foundry Agent、Copilot Studio Agent、VM Hugging Face 模型。
     4. connector 默认优先调用 APIM URL；仅当目标无法代理时才直连后端 endpoint。
     5. 准备最小攻击场景集。
     6. 执行 smoke test，确认每类目标可调用。
     7. 将结果写入 Application Insights 和 Azure DevOps Work Items。
   - 我可以执行：PyRIT 环境脚本、connector 代码、最小攻击集、ADO 写入脚本。
   - 可能需要用户操作：目标 endpoint 权限、Copilot Studio 通道密钥、网络访问授权。
   - 产物：PyRIT 配置、connector 代码、攻击集、结果写入脚本。

16. 定义 Domain 4 指标状态语义
   - 操作步骤：
     1. 定义 `N/A`、`Not Configured`、`No Data`、真实 `0` 的差异。
     2. 为每个指标指定适用对象和不适用对象。
     3. 定义首页 L1 状态 badge 规则。
     4. 定义二级页每个 target type 的状态显示规则。
   - 我可以执行：状态语义设计、API 响应字段设计、前端展示规则草案。
   - 可能需要用户操作：确认业务接受的风险阈值。
   - 产物：状态语义表、阈值规则、API 字段定义。

17. 校准首页与二级页指标映射
   - 操作步骤：
     1. 对照 `design-L2-domain-4-output-trustworthiness.md` 更新 L1/L2 指标映射。
     2. 明确首页显示 `Grounded Response Rate` 和 `Model Identity Capture Gaps` 的数据来源。
     3. 明确二级页按 6 类对象分开展示：AI 应用、Foundry 原生模型、Foundry fine-tune 模型、Foundry Agent、Copilot Studio Agent、VM Hugging Face 模型。
     4. 设计 Domain 4 API endpoint、响应结构和前端卡片布局。
     5. 后续进入代码开发，实现页面、API 和指标加载。
   - 我可以执行：设计文档更新、API 设计、页面草图、后续代码实现。
   - 可能需要用户操作：确认首页是否继续保留 `Grounded Response Rate`，以及各指标阈值。
   - 产物：更新后的 Domain 4 页面设计、API 设计、开发任务清单。
