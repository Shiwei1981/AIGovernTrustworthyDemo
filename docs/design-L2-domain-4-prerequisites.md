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
| RAG Service（知识检索问答服务） | Evaluation + Red Teaming + App Insights + Blob evidence | 是 |
| Azure AI Foundry 原生模型 | Evaluation + Tracing + Red Teaming | 是 |
| Azure AI Foundry fine-tune 模型 | Evaluation + Tracing + Red Teaming | 是 |
| Azure AI Foundry 自定义 Agent | Evaluation + Red Teaming | 是 |
| Copilot Studio 自定义 Agent | Evaluation + Red Teaming | 是 |
| VM 中从 Hugging Face 下载并部署的自建模型 | 红队外部调用（PyRIT） + shared-observability 留痕 | 是 |
| Tier 1 Consumer App（AI 服务直接调用方） | App Insights（完整调用链） + shared-observability + Blob evidence + Evaluation + Red Teaming | 是 |
| Tier 2 Consumer App（通过 Tier 1 间接使用 AI） | App Insights（平台 trace 上下文透传） + shared-observability + Blob evidence + 间接 AI 使用追踪 | 是 |

**约束**：本领域仅覆盖**文本类模型**，不含图像生成、视频、语音等多模态输出。

### 2.2 报表展示拆分原则

Domain 4 的二级页面在展示 coverage、failure rate、red teaming、model identity 等指标时，必须按以下测试对象类型分别展示，不能把不同对象混在一个总数里：

1. RAG Service（知识检索问答服务）
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

### 2.4 APIM / Foundry tracing / shared-observability / Blob / Application Insights 统一观测设计

> 本节是统一 observability 设计的 L2 摘要。  
> 监控、链路、日志、evidence archive、字段字典、写入责任与写入时机的主规范见：`docs/design-L3-domain-4-monitoring-tracing-logging.md`

Domain 4 本期采用“平台 tracing 为主，Python 证据记录为辅”的统一观测方案。统一 AI Governance 证据链由五部分组成：

1. `Azure API Management (APIM)`：所有可代理 HTTP hop 的默认 tracing 入口。
2. `Azure AI Foundry tracing`：Foundry Agent / Hosted Agent 内部 span，以及使用 Foundry SDK / 平台原生 tracing 的模型调用链。
3. `packages/shared-observability/`：跨应用共享 Python 组件，仅负责记录 Python 侧 LLM 调用证据，并写入薄索引事件。
4. `Application Insights / Azure Monitor Logs`：APIM tracing、适用时的 Foundry tracing、AOAI 平台诊断、Python evidence 事件的统一查询入口。
5. `Blob archive`：统一保存每次 LLM 调用的完整 `input`、`output`、`metadata`。

设计原则：

1. 在所有可以开启 APIM 的情况下，开启 APIM tracing。
2. 对于 LLM 调用，使用 Python 代码级 log 保存完整输入输出证据。
3. 对于 Foundry 目标，优先启用平台原生 tracing；其中 APIM → AOAI REST 代理链路的主平台证据由 APIM diagnostics + AOAI 平台诊断承担，不单独要求 Foundry Studio span。
4. 统一查询以 App Insights / Azure Monitor Logs 为主，Blob 只作为证据打开位置。
5. shared-observability 不再负责自建统一 tracing 系统，也不再要求生成 `correlation_id`。
6. 所有自定义字段命名尽可能向 Foundry tracing 与 APIM tracing 原生命名靠拢。

#### 2.4.1 统一记录路径

| 对象 | 统一记录路径 |
|---|---|
| App 2 -> App 1 | APIM tracing + App 原生遥测 + 调用方 evidence |
| App 1 -> RAG / AOAI native model / VM API | APIM tracing（若可代理）+ Web App / Python evidence；其中 APIM → AOAI REST 额外依赖 AOAI 平台诊断 |
| App 1 -> Foundry Agent / Hosted Agent API | APIM tracing（若可代理）+ Python evidence；Agent 内部 hop 由 Foundry tracing 记录 |
| Foundry Agent / Hosted Agent 内部 span | Foundry tracing |
| Python 代码中的实际 LLM 调用 | Python evidence + Blob archive |
| Evaluation / PyRIT 结果 | 结果事件 + 关联的 `trace_id` / `response_id` |

#### 2.4.2 组件职责矩阵

| 层 | 责任 |
|---|---|
| APIM | 记录所有可代理 HTTP hop 的 tracing、diagnostics、gateway/backends 信息 |
| Azure AI Foundry tracing | 记录 Foundry 内部 spans，以及 SDK / 平台支持的 Foundry tracing 路径；不覆盖所有 APIM → AOAI REST hop |
| shared-observability Python 包 | 记录 Python LLM 调用完整证据，并写入薄索引事件 |
| Application Insights | APIM tracing、适用时的 Foundry tracing、AOAI 平台诊断、Python evidence 的统一查询面 |
| Blob archive | 保存完整 `input.json`、`output.json`、`metadata.json` |
| Log Analytics | 复用现有工作区，承接 Application Insights 与 APIM 诊断查询 |

#### 2.4.3 统一基础字段

所有受管调用必须尽量提供以下字段，用于后续 Domain 4 报表与交叉检索：

| 字段 | 含义 |
|---|---|
| `target_type` | `rag_service`、`foundry_native_model`、`foundry_finetune_model`、`foundry_agent`、`copilot_studio_agent`、`vm_huggingface_model`、`tier1_consumer`、`tier2_consumer` |
| `target_id` | 目标对象唯一标识，如 deployment name、agent id、bot id、VM model service name |
| `model_name` | 模型名称 |
| `model_version` | 模型版本；如无法从平台获得，需要在 target registry 中维护 |
| `trace_id` | 平台 tracing 的主关联键 |
| `span_id` | 当前 span 标识 |
| `test_tool` | `evaluation`、`pyrit`、`smoke_test`、`manual`、`dashboard` |
| `test_run_id` | 一次 evaluation / red teaming / smoke test 的运行 ID |
| `response_id` | 后端 response id；优先使用原生 `gen_ai.response.id` 或等效值 |
| `archive_id` | Blob 证据归档目录主键 |
| `payload_ref` | Blob archive 中本次调用归档位置 |
| `status` | `succeeded`、`failed` |

#### 2.4.4 Blob archive 结构

统一 Blob 容器：`ai-invocation-archive`

统一路径规则：

`aigoverntrustworthy/{yyyy}/{mm}/{dd}/{service_name}/{target_type}/{archive_id}/{input|output|metadata}.json`

其中：

- `input.json`：完整请求体、prompt、上游上下文、必要的 header 摘要
- `output.json`：完整响应体、模型输出、错误响应体
- `metadata.json`：基础字段 + 扩展字段 + blob hash / size / token / citation 等信息

#### 2.4.5 Application Insights 管理边界

Application Insights 的管理对象分为三类：

1. **平台 tracing**：APIM tracing 和 Foundry tracing 是调用链观测的主来源；对 APIM 代理 AOAI REST 的 hop，AOAI 平台诊断作为补充证据。
2. **LLM evidence**：RAG Web App、Tier 1 / Tier 2、VM API、runner、脚本在每次实际 LLM 调用后写一条薄 evidence 事件，并保留 Blob 索引。
3. **结果事件**：Evaluation / PyRIT / smoke test 等脚本在 run 完成后写结果事件，必要时保留 `trace_id` / `response_id`。

建议统一事件名：

| 事件名 | 使用场景 |
|---|---|
| `AIGovernTrustworthyLLMEvidence` | 每次实际 LLM 调用的 Blob 索引事件 |
| `AIGovernTrustworthyEvaluationRun` | 每次 evaluation run 汇总 |
| `AIGovernTrustworthyRedTeamRun` | 每次 PyRIT / red team run 汇总 |
| `AIGovernTrustworthyFindingCreated` | 写入 Azure DevOps finding 时记录 |

#### 2.4.6 统一查询与关联策略

未来查询统一发生在 App Insights / Azure Monitor Logs。

最小关联策略如下：

1. `trace_id` 是平台 tracing 的主关联键。
2. `response_id` 是具体模型或 Agent 响应的主定位键。
3. `archive_id` 与 `payload_ref` 用于把 App Insights 查询结果跳转到 Blob 证据。
4. 对可疑调用，例如 jailbreak 尝试，最小查询路径是：
   - 先通过 `trace_id` 或 `response_id` 查 evidence 事件
   - 再按同一 `trace_id` 查 APIM / Foundry 原生日志
   - 最后通过 `payload_ref` 打开 Blob 中的完整输入输出

#### 2.4.7 检测工具依赖矩阵

| 检测工具 / 程序 | 调用目标方式 | 是否依赖 shared-observability | 是否写入 App Insights | 是否写入 Blob archive | 关键关联字段 |
|---|---|---|---|---|---|
| Smoke test script | 直连或经 APIM 访问目标 endpoint | 是 | 是 | 是 | `trace_id`、`response_id`、`payload_ref` |
| Azure AI Foundry Evaluations | Foundry target / endpoint 直连 | 是，用于补写 evidence | 是 | 是 | `test_run_id`、`trace_id`、`response_id` |
| PyRIT Red Teaming | 直连 target registry 记录的 endpoint | 是 | 是 | 是 | `test_run_id`、`trace_id`、`response_id`、`severity` |
| Dashboard metric collector | 读取 App Insights / Blob | 否 | 否 | 否 | `target_type`、`target_id`、`model_name`、`model_version` |

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

### 步骤总览

| 步骤 | 名称 | 状态 | 涉及系统 / 对象 | 执行主体 | 主要产物 |
|---|---|---|---|---|---|
| 1 | 准备观测基础设施 | ✅ 已完成 | Log Analytics、App Insights、APIM、Blob | Copilot + 用户授权 | 环境检查脚本、KQL 验证 |
| 2 | 建立 RAG 服务 | ✅ 已完成 | Azure Web App、APIM、AOAI、Blob | Copilot + 用户授权 | Web App 代码（v1.0.4）、PDF 目录、轻量级检索实现、APIM `/rag` |
| 3 | Foundry 原生模型部署 | ✅ 已完成 | Azure OpenAI、APIM | Copilot + 用户授权 | 模型 deployment、APIM `/native-model`、target registry、验证命令 |
| 4 | Foundry fine-tune 模型 | ✅ 已完成 | Azure AI Foundry | Copilot + 用户授权 | fine-tune job、deployment、APIM `/finetune-model`、5000 Q&A 归档、target registry |
| 5 | VM Hugging Face 模型 + API | ✅ 已完成 | Azure VM、App Insights | Copilot + deploy SPN | 安装脚本、API 服务代码、遥测配置 |
| 6 | Agent（Foundry 自定义 Agent + Copilot Studio Agent） | 🟡 部分完成；Copilot Studio Agent POC 暂停于正式 license 阻塞点 | Azure AI Foundry、Copilot Studio、SharePoint、Direct Line、APIM | Copilot + 用户 Portal / UI | Agent 清单、端点记录、调用验证脚本、身份授权说明 |
| 7 | Consumer Apps（Tier 1 + Tier 2） | ✅ 已完成 | App Service、APIM、全部 AI 后端、Tier 1 | Copilot + 用户授权 | Tier 1/Tier 2 API 代码、forwarding API、部署脚本、KQL 追踪验证 |
| 8 | App Insights 遥测字段配置 | 🟡 部分完成；剩余能力暂时跳过 | App Insights、Workbook、步骤 7 Trace Chain UI | Copilot + 用户授权 | App Insights Workbook 报表、KQL 查询、展示边界说明 |
| 9 | Foundry Tracing 能力 | ⏭ 暂时跳过 | Azure AI Foundry、App Insights | Copilot + 用户 Portal | tracing 配置说明、适用范围表 |
| 10 | Foundry Evaluations 能力 | ⬜ 待开始 | Azure AI Foundry Evaluations | Copilot + 用户授权 | target 清单、评估脚本 |
| 11 | Red Teaming 环境（PyRIT） | ⬜ 待开始 | PyRIT、全部目标 endpoint | Copilot + 用户授权 | connector 代码、攻击集 |
| 12 | 指标状态语义定义 | ⬜ 待开始 | Domain 4 报表、API | Copilot + 用户确认阈值 | 状态语义表、字段定义 |
| 13 | 首页与二级页指标映射校准 | ⬜ 待开始 | L1/L2 页面、Domain 4 API | Copilot + 用户确认 | 页面设计、API 设计、开发任务清单 |

---

### 步骤 1：准备观测基础设施（已完成）

- **状态**：已完成。

1. 使用 `.env.local` 中的订阅、资源组、SPN 参数查询现有 Application Insights、Log Analytics workspace、APIM 实例，以及 observability Blob archive 资源。
2. 如果资源已存在，记录 resource id、workspace id、connection string、diagnostic setting 状态。
3. 如果资源缺失，先设计命名、区域、保留周期、权限，再用脚本或 Portal 创建。
4. 为 APIM 开启 diagnostics 与 Application Insights / Log Analytics 集成。
5. 为 App Service、Azure AI 相关资源配置 diagnostic settings，日志统一进入同一个查询面。
6. 按 §2.4 确认 Blob archive 容器、shared-observability 组件配置和 App Insights 连接参数。
7. 用 KQL 查询验证 APIM、Foundry、Python evidence 三类日志表可读。

- **Copilot 可执行**：Azure CLI / REST 查询、创建脚本、APIM/诊断设置脚本、KQL 验证脚本。
- **可能需要用户操作**：如果 SPN 权限不足，需要用户登录 Azure CLI 或在 Portal 中授予权限。
- **产物**：`scripts/` 下的环境检查与配置脚本；本文档中的资源清单、APIM 配置顺序与 KQL 验证语句。

### 步骤 2：建立 RAG 服务（已完成）

> 详细需求设计见：`docs/design-L3-domain-4-rag-governance-service.md`

- **当前状态（2026-05-14）**：`AIGovernTrustworthyRAGApp` v1.0.4 已部署；APIM `/rag` 已配置并联通；`/rag/responses` 和 `/rag/health` 可用；APIM 全链路 trace_id 验证通过。

1. 复用现有 App Service Plan `AIGovernDemoASP`，创建 RAG Web App `AIGovernTrustworthyRAGApp`。
2. 将 AI Governance 行业标准 PDF 放入仓库中的 `apps/rag-service/knowledge-base/`，随应用部署或启动时加载。
3. 在 Web App 内实现轻量级代码式 RAG：PDF 解析、文本切块、进程内检索、模型调用、answer + citations 返回。
4. 默认不依赖 Foundry Hosted Agent、ACR、Foundry file_search / vector store、Azure AI Search 或独立 embedding 资源。
5. 在 Web App 真实模型调用处记录 `response_id`、`model_name`、`model_version`、`citations_count`，并写 Blob evidence。
6. 将 evidence 索引事件写入 Application Insights；RAG 路径以 APIM tracing + Web App telemetry + Blob evidence 组成证据链。
7. 将 APIM `/rag` 后端配置到 RAG Web App `/responses` endpoint；RAG Web App 自带的手动测试 UI 通过服务端代理调用 `L4_RAG_SERVICE_URL`（默认指向 APIM `/rag`），而不是让浏览器直接访问 Internal APIM。
8. 将 RAG Service 作为 Tier 1 App 的 AI 服务后端，同时作为 Domain 4 可评估目标。
9. 如后续需要新增 embedding、vector store、AI Search 等资源，必须先经用户确认。

- **Copilot 可执行**：Web App 代码与部署脚本、Azure 资源查询、PDF 目录约定、轻量级检索实现、APIM 配置脚本。
- **可能需要用户操作**：如果创建 Web App、配置应用设置或补充 AOAI / Blob / App Service 权限需要 Portal 授权，由用户按步骤完成。
- **产物**：RAG Service 需求设计、Web App 代码、PDF 目录约定、APIM `/rag` 配置、App Insights 遥测字段说明。
- **注意**：本步骤只建设 RAG 服务，不包含消费端应用；Tier 1 Consumer App 在步骤 7 中开发。

### 步骤 3：Foundry 原生模型部署（已完成）

> 详细需求设计见：`docs/design-L3-domain-4-foundry-native-model.md`

1. 查询当前 Azure AI Foundry / Azure OpenAI 可用模型部署。
2. 选择一个基础文本模型作为原生模型目标。
3. 如果未部署，通过脚本或 Portal 创建模型 deployment。
4. 记录模型名称、deployment 名称、版本、endpoint、project 信息。
5. 在可代理场景下通过 APIM 暴露该 endpoint，并保留 APIM diagnostics / AOAI 平台诊断；如后续引入 Foundry SDK tracing 路径，再补充对应 Foundry tracing。
6. 验证推理端点可调用。
7. 将该模型作为独立 target type 写入后续 evaluation / red teaming / dashboard 设计。

- **Copilot 可执行**：资源查询、调用验证、部署脚本草案、模型清单文档。
- **可能需要用户操作**：模型部署配额、区域选择或 Portal 内模型部署授权。
- **产物**：步骤 3 专用需求设计文档、模型 deployment 清单、验证命令、报表对象映射。
- **当前状态（2026-05-17 → 已更新）**：旧 deployment `AIGovernTrustworthyDemoNativeModel` 已删除；当前 live deployment 为 `aigoverntrustworthyfoundry` account 下的 `AIGovernTrustworthyDemoNativeModelGPT5.4mini`（`gpt-5.4-mini` `2026-03-17`）；APIM `/native-model` 已切换到 cognitiveservices 直连路径，MSI scope 为 `https://cognitiveservices.azure.com`；实测返回 200，模型标识 `gpt-5.4-mini-2026-03-17`。

### 步骤 4：Foundry fine-tune 模型

> 详细需求设计见：`docs/design-L3-domain-4-foundry-finetune-model.md`

- **当前状态（2026-05-17）**：步骤 4 已完成自动化闭环：`aigoverntrustworthydemo-finetune` container 已创建，5000 行 AI Governance 训练 JSONL 已生成并归档到 `docs/finetune-qa-archive/`，训练文件已上传到 Storage；fine-tune job `ftjob-ae456ec3dc4d468b87ecb8512ad33f86` 已在 `aigoverntrustworthyfoundry` account endpoint 上成功完成，并生成 fine-tuned model `gpt-4.1-2025-04-14.ft-ae456ec3dc4d468b87ecb8512ad33f86-aigovtrustdemo`；deployment `AIGovernTrustworthyDemoFineTuneModel` 已创建；APIM `/finetune-model` 已切换到 `AIGovernTrustworthyRAGProject/openai/v1` project-backed 路径，并已验证带 `model` 和不带 `model` 的两种请求形态都返回 200。早先 `invalidPayload: The specified base model does not support fine-tuning.` 已确认为自动化调用缺少 `trainingType=GlobalStandard` 且 endpoint 选择不一致导致。
- **执行约束（2026-05-14）**：步骤 4 的正式实施固定为**全程 AI 自动化**；除用户已明确批准的 3 个创建动作外，AI 不得创建或删除其他云资源。当前已批准：在 `aigoverntrustworthysa` 下创建 `aigoverntrustworthydemo-finetune` container、创建 fine-tune job、创建 `AIGovernTrustworthyDemoFineTuneModel` deployment；并允许使用 SPN 为所需账号授权。训练文件上传必须复用 `.env.local.L4` 中现有 storage 变量，中间 Q&A 还需在 `docs/finetune-qa-archive/` 下保留一份归档副本。

1. 明确 fine-tune 的测试目标：只为 Domain 4 测试提供一个可治理对象，不追求业务效果最大化。
2. 设计最小训练数据格式和样例数据来源。
3. 准备训练数据清洗、格式转换和上传脚本。
4. 提交 fine-tune job，并记录 job id、基础模型、输出模型信息。
5. 部署 fine-tuned model 到可调用 endpoint。
6. 在可代理场景下通过 APIM 暴露该 endpoint，并在支持的平台 / SDK 路径启用 Foundry tracing。
7. 验证 endpoint 可调用，并纳入 evaluation / red teaming / dashboard 独立展示。

- **Copilot 可执行**：在既有资源与权限满足前提下，自动化完成 PDF -> Q&A -> JSONL -> Storage 上传、APIM 配置脚本、验证脚本与文档归档设计。
- **前置阻塞**：若 fine-tune 权限、配额、Storage / APIM / AOAI / Foundry / App Insights 访问不足，或实施中发现还需创建未获批准的其他类型云资源，则不得继续推进。
- **产物**：fine-tune 需求设计、训练数据格式、实施前预置条件清单、Q&A 归档路径设计、job / 部署 / APIM 自动化脚本设计。

### 步骤 5：VM Hugging Face 模型 + API

1. 确认 VM 操作系统、最低成本可用的 CPU 规格、磁盘、网络、安全组、Python 版本。
2. 选择小型可运行的 Hugging Face 文本模型，优先选择资源消耗低、许可清晰的模型。
3. 编写 VM 初始化脚本：安装最小运行时依赖，优先采用能直接提供 OpenAI-compatible API 的方案。
4. 下载模型到 VM 本地目录或挂载磁盘。
5. 提供 OpenAI-compatible 推理 API，尽可能贴近通用 LLM API 格式。
6. 在 VM 模型服务自身集成 App Insights / OpenTelemetry，承接 `traceparent` 并记录统一字段。
7. 配置 systemd / supervisor 启动服务。
8. 验证 API 在内网可访问，并确认 App Insights 中可查询到 trace 记录。
9. 在可代理场景下将 VM API 放到 APIM 后面，由 APIM 承接平台 tracing。
10. VM 服务自身只负责轻量遥测与 trace 承接，不在服务内嵌入 shared-observability；对 VM 模型的完整 `input` / `output` / `metadata` evidence 统一由后续调用方（Tier 1 / Evaluation / PyRIT / connector 脚本）写入 Blob archive 与 App Insights。

- **Copilot 可执行**：VM 检查脚本、安装脚本、API 服务代码、启动服务配置。
- **可能需要用户操作**：如果需要 SSH 登录、开端口、分配 GPU、调整 NSG，需要用户协助或授权登录 session。
- **产物**：VM 部署设计、安装脚本、API 代码、服务配置、App Insights 遥测设计、验证命令。

### 步骤 6：Agent（Foundry 自定义 Agent + Copilot Studio Agent）

> 详细需求设计见：`docs/design-L3-domain-4-agents.md`

本步骤一次性完成两类 Agent 的建设与纳管，但两者在治理口径上仍保持独立 target type，不合并统计。

- **当前设计状态（2026-05-17）**：步骤 6 的 Foundry Agent 部分已完成设计、资源确认和 APIM `/foundry-agent` 接入；可作为步骤 7 Tier 1 / Tier 2 的下游 target。Copilot Studio Agent 已创建并选择 `SalesTeamSite` 作为知识源，但发布仍被正式 Copilot Studio license 阻塞，因此 Copilot Studio / Direct Line / APIM `/copilot-studio` 收尾仍暂停。
- **官方文档依据（2026-05-17）**：Microsoft Learn `Assign licenses and manage access to Copilot Studio` 明确要求同时具备 `Copilot Studio` tenant license 与 `Copilot Studio User License`；trial license 可创建和测试 agent，但不能 publish。当前 tenant 仅发现 `CCIBOTS_PRIVPREV_VIRAL` trial SKU，不能满足发布前置。
- **当前已确认的方案**：
  - Foundry Agent：复用现有 AOAI model deployment，在 Foundry 中创建一个 Agent，并上传现有 5 份 AI Governance PDF，使其可基于这 5 份材料回答问题。
  - Copilot Studio Agent：采用最简单可落地方案，创建一个 Agent，使其可读取同 tenant 的 SharePoint site `SalesTeamSite` 上指定文件的信息并回答问题。
  - 两个 Agent 自身都**不要求接入 shared-observability 或写 Blob 级 LLM evidence**；步骤 6 先依赖平台侧日志与 APIM tracing。后续如 Tier 1、evaluation runner、PyRIT runner 调用这两个 Agent，则调用方仍需按统一规范记录 Agent API evidence。
  - 两个 Agent 的外部 API 都必须挂到 APIM 后端；不接受长期绕开 APIM 的直连方案。
  - Foundry Agent 应优先启用平台原生 tracing，并自动把平台日志送到 App Insights；Copilot Studio Agent 若存在可用的 App Insights / Azure Monitor 集成能力，则应尽量配置，否则至少保留 APIM tracing + 调用方 evidence。

1. 明确两类 Agent 的最小场景：
   - Foundry 自定义 Agent：基于现有 AOAI deployment 和 5 份 AI Governance PDF 的知识问答 Agent。
   - Copilot Studio Agent：可读取同 tenant SharePoint site `SalesTeamSite` 指定文件信息的最小知识型 Agent。
2. Foundry Agent 的固定知识源为以下 5 个文档，不再抽象写作“可复用 RAG Service 知识材料”：
   - `NIST.AI.100-1.pdf`
   - `NIST.AI.600-1.pdf`
   - `OJ_L_202401689_EN_TXT.pdf`
   - `OWASP-Top-10-for-LLMs-v2025.pdf`
   - `sgmodelaigovframework2.pdf`
3. 在 Azure AI Foundry 中创建 Foundry Agent 时，必须复用步骤 3/4 已存在的 AOAI model deployment，不再为步骤 6 额外新建平行模型资源；并把上述 5 份 PDF 作为 Agent knowledge source 上传到 Foundry。
4. 在 Copilot Studio 中创建最小自定义 Agent 时，优先采用最简单的 tenant 内知识接入方式，使 Agent 可读取 SharePoint site `SalesTeamSite` 上目标文件的信息并完成问答；当前以用户提供的目标文件链接为实施锚点。
5. 为 Foundry Agent 获取可调用 endpoint 或 invocation 方式，并通过 APIM `/foundry-agent` 暴露为统一治理入口；在平台支持的路径开启 Foundry tracing，并确保日志进入 App Insights / Azure Monitor 查询面。
6. 为 Copilot Studio Agent 启用可被外部调用的通道，当前默认优先 Direct Line；并通过 APIM `/copilot-studio` 暴露为统一治理入口，保留 bot id、environment id、channel / connector 信息。
7. 分别验证 Foundry Agent 与 Copilot Studio Agent 可被外部脚本调用，并验证经 APIM 调用时可以在 App Insights 中查询到对应平台日志或平台侧证据。
8. 两类 Agent 的日志边界固定如下：
   - Foundry Agent：不要求 Agent 自身接入 shared-observability；依赖 Foundry tracing + App Insights / Azure Monitor 自动日志 + APIM tracing。
   - Copilot Studio Agent：不要求 Agent 自身接入 shared-observability；若产品能力允许则尽量接入 App Insights / Azure Monitor，否则依赖 APIM tracing，后续再由调用方补齐 evidence。
9. 两类 Agent 的 Entra 运行身份与授权原则固定如下：
   - Foundry Agent：当前**不把“绑定任意自定义 SPN 作为 Agent runtime principal”视为默认可行方案**。正式设计基线是优先使用 Foundry Project / Agent 平台管理身份，或 Agent 所依赖 connection 的实际运行身份；若后续产品能力证明确实支持绑定指定 SPN，再作为增量设计补充。
   - Copilot Studio Agent：当前**不把“绑定任意自定义 SPN 作为 Copilot Studio Agent runtime principal”视为默认可行方案**。访问 SharePoint 知识源时，优先基于 Copilot Studio / Power Platform connection 的实际身份运行；如不支持 app-only/SPN，则使用专用 Entra 用户账户或 service account 作为 connection owner，并授予目标 SharePoint site / 文件读取权限。
   - 因此，步骤 6 的重点不是先创建两个新的运行时 SPN，而是先识别这两个 Agent 在租户内真正使用的后台身份，再把相应读权限 / 模型调用权限赋给该身份。
10. 实际创建完成后，必须分别记录：
   - Foundry Agent：agent id、project、endpoint / run API、复用的 model deployment、knowledge file 清单、平台实际运行身份或 connection 身份、App Insights / tracing 配置状态
   - Copilot Studio Agent：bot id、environment id、Direct Line / connector 信息、SharePoint site / 文件来源、connection owner 身份、App Insights / tracing 配置状态
11. 与 Domain 1 Dataverse `bots` 资产发现结果对齐，并把两类 Agent 作为独立报表对象纳管。
12. 实施前的关键前置条件如下：
   - Foundry Agent：既有 Foundry Project 可访问、既有 AOAI deployment 可复用、5 个 PDF 已准备齐全、APIM MSI 具备或可补齐 Foundry 数据面访问权限、创建后回填 `L4_FOUNDRY_AGENT_ID`
   - Copilot Studio Agent：Copilot Studio 环境可创建 Agent、`SalesTeamSite` 目标文件可访问、knowledge connection 的实际身份已确认并具备 SharePoint 读取权限、Direct Line 可启用并回填 `L4_COPILOT_STUDIO_DIRECTLINE_SECRET`
13. 当前已确认的 Foundry Agent 实施结果如下：
   - Agent 名称 = `AIGovernTrustworthyDemoFoundryAgent`
   - `agent_id = asst_qPEQxZ6Gc894gcxQjaIOkdF6`
   - 实际创建 project = `AIGovernTrustworthyRAGProject`
   - model deployment = `AIGovernTrustworthyDemoNativeModelGPT5.4mini`（`gpt-5.4-mini` `2026-03-17`）
   - 旧 Hosted Agent `aigovern-rag-agent` 已删除；deploy SPN 视角下 `/agents` 列表为空，`/assistants` 列表仅包含上述 Foundry Agent
   - APIM `/foundry-agent` 已接到 `AIGovernTrustworthyRAGProject` project-level assistants / threads / messages / runs API，并已完成端到端 smoke test
   - Project UI 可见 tracing / monitoring / diagnostics 入口；真实调用已能通过 APIM 完成，平台 trace 查询仍以后续 dashboard / evidence 联调为准
14. 当前已确认的 Copilot Studio 实施 / 阻塞结果如下：
   - Agent 名称 = `AIGovernTrustworthyDemoCopilotStudioAgent`
   - Environment = `Default-7d3389c6-5b33-43be-b0fd-d7c303755fb5` / `Contoso (default)`
   - Dataverse URL = `https://org1fb702ee.crm.dynamics.com/`
   - UI 已接受 `SalesTeamSite` 站点级知识源选择；未暴露单文件 URL 字段或 connection owner 字段
   - 当前作者 `weishi@MngEnvMCAP029189.onmicrosoft.com` 已具备 `Basic User`、`Environment Maker`、`Bot Author`
   - `Bot Author` 通过已有 Dataverse System Administrator application user `devdeployspn` / `AZ_DEPLOY_CLIENT_ID` 分配并验证
   - Publish 仍阻塞于正式 Copilot Studio license；Direct Line secret 尚未生成
   - 结论：Copilot Studio Agent POC 当前到此为止；等待 license 补齐与用户后续指令后再继续 Direct Line 与 `/copilot-studio` 收尾

- **Copilot 可执行**：需求设计、调用验证脚本、Agent 清单文档、Dataverse 发现对齐脚本。
- **可能需要用户操作**：
  - Foundry Portal 中创建 / 发布 Agent、上传知识文件、确认平台 tracing / monitoring，如无法脚本化，由用户按步骤完成。
   - Copilot Studio UI 创建、发布、知识源连接、Direct Line 开启通常需要用户在 UI 中完成；其中 publish 需要先补齐正式 Copilot Studio tenant / user license。
  - 若产品界面中无法明确看到后台运行身份或 connection owner，需要用户配合在 Portal / Power Platform 管理界面确认实际身份。
- **产物**：Foundry Agent 清单、Copilot Studio Agent 端点记录、调用验证脚本、纳管清单、运行身份 / 授权说明。

### 步骤 7：Consumer Apps（Tier 1 + Tier 2）（已完成）

> 详细需求设计见：`docs/design-L3-domain-4-consumer-apps.md`

- **状态**：已完成。

本步骤一次性完成 Tier 1 与 Tier 2 两类 Consumer App 的整体设计与开发，但两者在治理口径上仍保持独立 target type，不合并统计。

#### 7.1 Tier 1 Consumer App

代表"合规使用 AI 服务"的标准消费者应用。调用 RAG Service、Foundry 原生模型、Foundry fine-tune 模型、VM Hugging Face 模型、Foundry Agent、Copilot Studio Agent 等全部 AI 服务后端。

0. Tier 1 是一个包含前端、前端对应后端和独立 API 的网页程序；前端与独立 API 可由同一个 FastAPI 应用承载。
1. 设计 Tier 1 App 的 API 接口：按 tab 分离的 forwarding API（例如 `POST /api/chat/rag`、`POST /api/chat/native-model` 等）；同时提供 `GET /health`、`GET /ui/bootstrap`。
2. 在接收请求时继承平台 trace 上下文，不要求自建 `correlation_id`。
3. 对当前 5 类目标分别实现独立 forwarding route：RAG Service、Foundry Agent、VM Hugging Face endpoint、Foundry Native Model、Foundry Fine-tune Model。
4. 对所有可代理的下游调用统一改为走 APIM。
5. 在每次实际 LLM 调用后记录 `trace_id`、`response_id`、`model_name`、`model_version`、`target_type`、`target_id`、`citations`（若调用 RAG），并写 Blob evidence。
6. 将 Tier 1 App 部署到 App Service，并接入 shared-observability。
7. Native Model 与 Fine-tune Model 在底层仍属于 AOAI deployment，但步骤 7 的 consumer app 需求要求优先通过 `AIGovernTrustworthyRAGProject` project endpoint 调用，以利用该 Project 的 tracing 能力。
8. 验证从外部调用 Tier 1 可成功触发下游 AI 服务，并确认 APIM / Foundry / Python evidence 三层链路完整。
9. Tier 1 前端页面与外部程序调用其独立 API 时，若二者都能发起下游调用，则两条入口路径都必须满足同样的 evidence 记录要求。
10. 对 VM Hugging Face 模型的调用由 Tier 1 forwarding route 负责写入 `input` / `output` / `metadata` evidence，并保留 `trace_id`、`response_id`、`model_name`、`model_version`、`target_type=vm_huggingface_model`、`target_id`。
11. Tier 1 自带的 Trace Chain API 必须由 Tier 1 Web App 自己使用运行时 SPN 直接读取 observability Blob archive；不得依赖本地 blob viewer 或额外的第三个 Web App 才能展开 archive payload。

- **Copilot 可执行**：接口设计、forwarding 代码、遥测 helper、Blob / App Insights 写入代码、部署脚本。
- **可能需要用户操作**：如 AI 服务 endpoint 权限不足，需要用户授权。
- **产物**：Tier 1 App 需求设计、API 代码、forwarding 代码、遥测 helper、部署脚本。

#### 7.2 Tier 2 Consumer App

代表通过"AI 服务平台层"间接调用 AI 的上游业务应用。Tier 2 不直接调用 AI 服务，只调用 Tier 1，体现"间接 AI 使用"的治理追踪场景。

0. Tier 2 是一个包含前端和前端对应后端的网页程序；其前后端由同一个 FastAPI 应用承载。
1. 设计 Tier 2 App 的 API 接口：按 tab 分离的 forwarding API（例如 `POST /api/chat/rag`、`POST /api/chat/native-model` 等）；同时提供 `GET /health`、`GET /ui/bootstrap`。
2. 在接收请求时继承平台 trace 上下文，不要求自建 `correlation_id`。
3. 通过 APIM 暴露的 Tier 1 endpoint 调用 Tier 1，并透传当前 trace context。Tier 1 与 Tier 2 都必须保留平台 trace 关联能力。
4. 在 Tier 2 自身请求前后写入 App Insights 原生遥测；Tier 2 后端在调用 Tier 1 API 时，也必须调用 shared-observability，把这条间接 AI 使用入口调用写入 Blob evidence 与 App Insights thin event。
5. 将 Tier 2 App 部署到 App Service。
6. 验证：通过 KQL 可以从 Tier 2 请求的 `trace_id` 追踪到最终 AI 服务调用（Tier 2 / APIM / Tier 1 / Foundry 或 VM evidence），证明间接 AI 使用可追溯。
7. Tier 2 前端页面触发的调用必须与 Tier 2 后端写出的 evidence 对齐，不能把“前端发起页面请求”和“后端调用 Tier 1 API”混成一条无法区分的记录。
8. Tier 2 -> Tier 1 服务间调用固定使用 app-only token，而不是透传浏览器用户 token；对应的 Entra API exposure、权限授予与 admin consent 属于实现前置条件。
9. Tier 2 Trace Chain 必须由 Tier 2 Web App 自己查询 App Insights 和 Blob archive，不能把 Trace Chain 后端汇总责任代理给 Tier 1，也不能额外依赖 blob viewer 进程或独立 blob viewer Web App。

- **Copilot 可执行**：接口设计、转发代码、遥测 helper、部署脚本、KQL 验证查询。
- **可能需要用户操作**：如果 App Service 权限不足，需要用户授权。
- **产物**：Tier 2 App 需求设计、API 代码、部署脚本、KQL 追踪验证查询。

### 步骤 8：App Insights 遥测字段配置（部分完成，剩余能力暂时跳过）

> 详细需求设计见：`docs/design-L3-domain-4-app-insights-telemetry-fields.md`

1. 当前步骤 8 标记为 **部分完成**。
2. 已完成的范围仅包括：App Insights / Azure Monitor Logs 查询设计、Workbook 报表部署、基础统计图与单 trace 调用链图尝试。
3. 当前 App Insights Workbook 展示不全面，调用链图可读性与稳定性仍存在风险；不再把它作为唯一 tracing chain 展示入口。
4. tracing chain 的正式演示入口改为使用 **步骤 7 已开发的 Tier 1 / Tier 2 Trace Chain UI**。
5. Foundry UI tracing、完整 troubleshooting 字段治理、字段主合同收敛、runner/evidence 全覆盖等步骤 8 其他能力 **暂时跳过**，后续如有明确需求再单独恢复。

- **Copilot 已完成**：App Insights tracing query 设计、Workbook 报表部署、Foundry UI tracing 可行性研究、展示边界说明。
- **暂不继续推进**：Foundry UI tracing 深入集成、App Insights 图形继续美化、troubleshooting 字段治理、写入方字段统一。
- **当前产物**：`infra/monitoring/domain4-step8-tracing.workbook.json`、`infra/monitoring/deploy-step8-tracing-workbook.sh`、步骤 8 L3 设计说明。

### 步骤 9：Foundry Tracing 能力（暂时跳过）

**当前状态**：⏭ 暂时跳过。

原因：步骤 8 实测发现，通过 instrumented SDK 写入 App Insights 的 fine-tuned model trace 无法在 Foundry UI Tracing 页面显示；Foundry UI Tracing 显示需要满足 Foundry SDK / OpenTelemetry 特定语义约束，当前项目通过 APIM 网关的调用路径无法自动满足该约束。后续如有明确展示需求再单独恢复。

原始计划步骤（保留供参考）：
1. 确认哪些目标支持 Foundry Tracing：Foundry 原生模型、fine-tune 模型、Foundry Agent。
2. 在 Foundry 项目中开启 tracing / monitoring。
3. 连接 Application Insights / Log Analytics。
4. 触发测试调用，验证 trace 记录生成。
5. 明确 VM Hugging Face 模型不走 Foundry tracing，由 APIM + Python evidence 记录。

### 步骤 10：Foundry Evaluations 能力

> 详细需求设计见：`docs/design-L3-domain-4-foundry-evaluations.md`

1. 设计 evaluation target schema：target type、endpoint、auth、input、expected behavior。
2. 为 RAG Service、Foundry 原生模型、fine-tune 模型、Foundry Agent、VM Hugging Face 模型分别建立 target 记录；Copilot Studio Agent 当前未开发完成，不作为 Foundry Evaluations 测试对象。
3. 准备完整可对比 evaluation 数据集；项目目录只作为编辑工作区，最终测试数据注册为 Foundry project dataset。`quality_general`、`rag_pdf_groundedness`、`safety_baseline` 当前尚未创建，后续按用户指令创建。
4. 配置 groundedness / citation / safety evaluator；独立 judge/scoring deployment `AIGovernTrustworthyEvaluationJudgeModel` 已创建，judge model 选择以评分准确性优先，不复用被测 target deployment。若具体 evaluator 要求内置安全模型或区域能力，则在 Foundry 中单独验证。
5. 在已创建的 `AIGovernTrustworthyEvaluationDashboard` 中按 `target_id × test_item` 手动触发评估；该 Web App 复用现有 App Service Plan，网络 / VNet access 和自身 App logging 已配置。Foundry Evaluations 测试不经过 APIM，不写入 tracing-chain telemetry / LLM evidence，以免干扰步骤 7 / 8 tracing chain 输出。官方评分结果进入 Foundry evaluation run；dashboard 通过 SDK / API 动态读取 Foundry run，并默认选取每个 `target_id × test_item` 的最新 completed run 做横向对比。
6. 将结果字段映射到 Domain 4 指标。
7. 对 VM Hugging Face 模型的 evaluation 调用，直连 `http://10.1.1.8:11434/v1/chat/completions`；runner 将 VM 输出整理为 Foundry dataset evaluation 输入，并运行完整适用数据集。Blob 复用现有 `aigoverntrustworthysa` / `ai-invocation-archive`，只保存 Foundry run 不覆盖但有解释价值的 supplemental data：target response text、citation metadata、source document match、target direct-call error。Evaluation runner 身份使用 `.env.local.L4` 中的 `L4_EVALUATION_RUNNER_SPN_DISPLAY_NAME`。

- **Copilot 可执行**：target 配置文件、评估数据集样例、运行脚本、结果解析脚本。
- **可能需要用户操作**：Foundry UI 中创建 evaluation 或授权 evaluator。
- **产物**：evaluation 需求设计、target 清单、样例数据集、runner / dashboard Web App、Foundry run 链接、supplemental data schema。

### 步骤 11：Red Teaming 环境（PyRIT）

1. 选择执行环境：本地、开发 VM、GitHub Actions 或 Azure VM。
2. 安装 PyRIT 和必要依赖。
3. 为每类目标编写 connector：RAG Service、Foundry 模型、fine-tune 模型、Foundry Agent、Copilot Studio Agent、VM Hugging Face 模型。
4. connector 默认调用 target registry 记录的 endpoint；统一通过 shared-observability 写入证据链。
5. 准备最小攻击场景集。
6. 执行 smoke test，确认每类目标可调用。
7. 将结果写入 Application Insights，作为后续状态语义与报表映射的数据来源。

- **Copilot 可执行**：PyRIT 环境脚本、connector 代码、最小攻击集、结果解析脚本。
- **可能需要用户操作**：目标 endpoint 权限、Copilot Studio 通道密钥、网络访问授权。
- **产物**：PyRIT 配置、connector 代码、攻击集、结果写入脚本。

### 步骤 12：指标状态语义定义

1. 定义 `N/A`、`Not Configured`、`No Data`、真实 `0` 的差异。
2. 为每个指标指定适用对象和不适用对象。
3. 定义首页 L1 状态 badge 规则。
4. 定义二级页每个 target type 的状态显示规则。

- **Copilot 可执行**：状态语义设计、API 响应字段设计、前端展示规则草案。
- **可能需要用户操作**：确认业务接受的风险阈值。
- **产物**：状态语义表、阈值规则、API 字段定义。

### 步骤 13：首页与二级页指标映射校准

1. 对照 `design-L2-domain-4-output-trustworthiness.md` 更新 L1/L2 指标映射。
2. 明确首页显示 `Grounded Response Rate` 和 `Model Identity Capture Gaps` 的数据来源。
3. 明确二级页按 8 类对象分开展示：RAG Service、AI 应用、Foundry 原生模型、Foundry fine-tune 模型、Foundry Agent、Copilot Studio Agent、VM Hugging Face 模型、Tier 2 间接 AI 应用。
4. 设计 Domain 4 API endpoint、响应结构和前端卡片布局。
5. 后续进入代码开发，实现页面、API 和指标加载。

- **Copilot 可执行**：设计文档更新、API 设计、页面草图、后续代码实现。
- **可能需要用户操作**：确认首页是否继续保留 `Grounded Response Rate`，以及各指标阈值。
- **产物**：更新后的 Domain 4 页面设计、API 设计、开发任务清单。
