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
| RAG Service（知识检索问答服务） | Evaluation + Red Teaming + App Insights | 是 |
| Azure AI Foundry 原生模型 | Evaluation + Tracing + Red Teaming | 是 |
| Azure AI Foundry fine-tune 模型 | Evaluation + Tracing + Red Teaming | 是 |
| Azure AI Foundry 自定义 Agent | Evaluation + Red Teaming | 是 |
| Copilot Studio 自定义 Agent | Evaluation + Red Teaming | 是 |
| VM 中从 Hugging Face 下载并部署的自建模型 | 红队外部调用（PyRIT） + shared-observability 留痕 | 是 |
| Tier 1 Consumer App（AI 服务直接调用方） | App Insights（完整调用链） + Evaluation + Red Teaming | 是 |
| Tier 2 Consumer App（通过 Tier 1 间接使用 AI） | App Insights（平台 trace 上下文透传，间接 AI 使用追踪） | 是 |
| Tier 2 Consumer App（通过 Tier 1 间接使用 AI） | App Insights（平台 trace 上下文透传，间接 AI 使用追踪） | 是 |

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

Domain 4 本期采用“平台 tracing 为主，Python 证据记录为辅”的统一观测方案。统一 AI Governance 证据链由五部分组成：

1. `Azure API Management (APIM)`：所有可代理 HTTP hop 的默认 tracing 入口。
2. `Azure AI Foundry tracing`：Foundry 原生模型、fine-tune 模型、Foundry Agent 的平台内部 tracing。
3. `packages/shared-observability/`：跨应用共享 Python 组件，仅负责记录 Python 侧 LLM 调用证据，并写入薄索引事件。
4. `Application Insights`：APIM tracing、Foundry tracing、Python evidence 事件的统一查询入口。
5. `Blob archive`：统一保存每次 LLM 调用的完整 `input`、`output`、`metadata`。

设计原则：

1. 在所有可以开启 APIM 的情况下，开启 APIM tracing。
2. 对于 LLM 调用，使用 Python 代码级 log 保存完整输入输出证据。
3. 对于 Foundry 目标，全面开启 Foundry tracing。
4. 统一查询以 App Insights / Azure Monitor Logs 为主，Blob 只作为证据打开位置。
5. shared-observability 不再负责自建统一 tracing 系统，也不再要求生成 `correlation_id`。
6. 所有自定义字段命名尽可能向 Foundry tracing 与 APIM tracing 原生命名靠拢。

#### 2.4.1 统一记录路径

| 对象 | 统一记录路径 |
|---|---|
| App 2 -> App 1 | APIM tracing + App 原生遥测 |
| App 1 -> RAG / Foundry model / Foundry Agent / VM API | APIM tracing（若可代理）+ Python evidence |
| Foundry Agent 内部 span | Foundry tracing |
| Python 代码中的实际 LLM 调用 | Python evidence + Blob archive |
| Evaluation / PyRIT 结果 | 结果事件 + 关联的 `trace_id` / `response_id` |

#### 2.4.2 组件职责矩阵

| 层 | 责任 |
|---|---|
| APIM | 记录所有可代理 HTTP hop 的 tracing、diagnostics、gateway/backends 信息 |
| Azure AI Foundry tracing | 记录 Foundry 模型与 Agent 内部 spans |
| shared-observability Python 包 | 记录 Python LLM 调用完整证据，并写入薄索引事件 |
| Application Insights | APIM tracing、Foundry tracing、Python evidence 的统一查询面 |
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

1. **平台 tracing**：APIM tracing 和 Foundry tracing 是调用链观测的主来源。
2. **Python evidence**：RAG Service、Tier 1 / Tier 2、VM API、runner、脚本在每次实际 LLM 调用后写一条薄 evidence 事件，并保留 Blob 索引。
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
| Dashboard metric collector | 读取 App Insights / Blob / ADO | 否 | 否 | 否 | `target_type`、`target_id`、`model_name`、`model_version` |

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

| 步骤 | 名称 | 涉及系统 / 对象 | 执行主体 | 主要产物 |
|---|---|---|---|---|
| 1 | 准备观测基础设施（已完成） | Log Analytics、App Insights、APIM、Blob | Copilot + 用户授权 | 环境检查脚本、KQL 验证 |
| 2 | 建立 RAG 服务 | Azure AI Search、Azure OpenAI/Foundry、App Service | Copilot + 用户授权 | RAG API 代码、索引脚本 |
| 3 | Foundry 原生模型部署 | Azure AI Foundry | Copilot + 用户授权 | 模型清单、验证命令 |
| 4 | Foundry fine-tune 模型 | Azure AI Foundry | Copilot + 用户授权 | fine-tune 脚本、部署清单 |
| 5 | VM Hugging Face 模型 + API | Azure VM | Copilot + 用户 SSH | 安装脚本、API 服务代码 |
| 6 | VM 模型接入 shared-observability（步骤 5 扩展） | VM API、Blob、App Insights | Copilot + 用户授权 | observability 接入代码、验证脚本 |
| 7 | Foundry 自定义 Agent | Azure AI Foundry | Copilot + 用户 Portal | Agent 清单、调用脚本 |
| 8 | Copilot Studio Agent | Copilot Studio、Direct Line | 用户 UI + Copilot 验证 | UI 操作指南、验证脚本 |
| 9 | Tier 1 Consumer App | App Service、APIM、全部 AI 后端 | Copilot + 用户授权 | API 代码、connector、部署脚本 |
| 10 | Tier 2 Consumer App | App Service、APIM、Tier 1 | Copilot + 用户授权 | API 代码、KQL 追踪验证 |
| 11 | App Insights 遥测字段配置 | shared-observability、App Insights | Copilot + 用户授权 | 字段规范、KQL 验证语句 |
| 12 | Foundry Tracing 能力 | Azure AI Foundry、App Insights | Copilot + 用户 Portal | tracing 配置说明、适用范围表 |
| 13 | Foundry Evaluations 能力 | Azure AI Foundry Evaluations | Copilot + 用户授权 | target 清单、评估脚本 |
| 14 | Azure DevOps Work Items | Azure DevOps | Copilot + 用户 PAT | ADO 字段设计、写入脚本 |
| 15 | Red Teaming 环境（PyRIT） | PyRIT、全部目标 endpoint | Copilot + 用户授权 | connector 代码、攻击集 |
| 16 | 指标状态语义定义 | Domain 4 报表、API | Copilot + 用户确认阈值 | 状态语义表、字段定义 |
| 17 | 首页与二级页指标映射校准 | L1/L2 页面、Domain 4 API | Copilot + 用户确认 | 页面设计、API 设计、开发任务清单 |

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

### 步骤 2：建立 RAG 服务

1. 确认 Azure AI Search、Azure OpenAI / Azure AI Foundry 模型部署是否存在。
2. 设计最小 RAG 索引 schema：`id`、`content`、`source`、`page`、`content_vector`。
3. 使用仓库内 NIST AI 600-1 PDF 作为初始知识材料，后续可加入公司 AI 政策文档。
4. 开发文档切分、embedding、上传到 Azure AI Search 的脚本。
5. 开发 RAG Service API：`retrieve → prompt → generate → return answer + citations`。
6. 在可代理场景下将 RAG API 暴露到 APIM 后面。
7. 在每次实际 LLM 调用中记录 `trace_id`、`response_id`、`model_name`、`model_version`、`citations`，并写 Blob evidence。
8. 将 evidence 索引事件写入 Application Insights。
9. 将 RAG Service 部署到 App Service，作为 Tier 1 App 的 AI 服务后端，同时作为 Domain 4 可评估目标。

- **Copilot 可执行**：代码与脚本开发、Azure 资源查询、索引创建、App Service 部署脚本。
- **可能需要用户操作**：如果 Search / Azure OpenAI 创建或模型部署需要 Portal 权限，由用户按步骤完成。
- **产物**：RAG Service 需求设计、索引 schema、ingestion 脚本、RAG Service API 代码、App Insights 遥测字段说明。
- **注意**：本步骤只建设 RAG 服务，不包含消费端应用；Tier 1 Consumer App 在步骤 9 中开发。

### 步骤 3：Foundry 原生模型部署

1. 查询当前 Azure AI Foundry / Azure OpenAI 可用模型部署。
2. 选择一个基础文本模型作为原生模型目标。
3. 如果未部署，通过脚本或 Portal 创建模型 deployment。
4. 记录模型名称、deployment 名称、版本、endpoint、project 信息。
5. 在可代理场景下通过 APIM 暴露该 endpoint，并开启 Foundry tracing。
6. 验证推理端点可调用。
7. 将该模型作为独立 target type 写入后续 evaluation / red teaming / dashboard 设计。

- **Copilot 可执行**：资源查询、调用验证、部署脚本草案、模型清单文档。
- **可能需要用户操作**：模型部署配额、区域选择或 Portal 内模型部署授权。
- **产物**：模型 deployment 清单、验证命令、报表对象映射。

### 步骤 4：Foundry fine-tune 模型

1. 明确 fine-tune 的测试目标：只为 Domain 4 测试提供一个可治理对象，不追求业务效果最大化。
2. 设计最小训练数据格式和样例数据来源。
3. 准备训练数据清洗、格式转换和上传脚本。
4. 提交 fine-tune job，并记录 job id、基础模型、输出模型信息。
5. 部署 fine-tuned model 到可调用 endpoint。
6. 在可代理场景下通过 APIM 暴露该 endpoint，并开启 Foundry tracing。
7. 验证 endpoint 可调用，并纳入 evaluation / red teaming / dashboard 独立展示。

- **Copilot 可执行**：训练数据样例、格式转换脚本、提交 job 脚本、验证脚本。
- **可能需要用户操作**：如果 fine-tune 权限、配额或 Portal 审批不足，需要用户授权或手工启动。
- **产物**：fine-tune 需求设计、训练数据格式、job 操作脚本、部署清单。

### 步骤 5：VM Hugging Face 模型 + API

1. 确认 VM 操作系统、GPU / CPU、磁盘、网络、安全组、Python 版本。
2. 选择小型可运行的 Hugging Face 文本模型，优先选择资源消耗低、许可清晰的模型。
3. 编写 VM 初始化脚本：安装 Python、venv、transformers / vLLM / llama.cpp 等依赖。
4. 下载模型到 VM 本地目录或挂载磁盘。
5. 开发 OpenAI-compatible 推理 API。
6. 配置 systemd / supervisor 启动服务。
7. 验证 API 在内网可访问。

- **Copilot 可执行**：VM 检查脚本、安装脚本、API 服务代码、启动服务配置。
- **可能需要用户操作**：如果需要 SSH 登录、开端口、分配 GPU、调整 NSG，需要用户协助或授权登录 session。
- **产物**：VM 部署设计、安装脚本、API 代码、服务配置、验证命令。

### 步骤 6：VM 模型接入 shared-observability（步骤 5 扩展）

1. 确认 VM API 内网地址、shared-observability 依赖包和 Blob / App Insights 连接参数。
2. 在可代理场景下将 VM API 放到 APIM 后面。
3. 在 VM API 中为 `/v1/chat/completions`、`/metadata` 接入 shared-observability。
4. 记录 `trace_id`、`response_id`、`model_name`、`model_version`、`deployment_type=vm_huggingface`。
5. 写入完整 input / output / metadata 到 Blob archive。
6. 将 evidence 事件写入 Application Insights / Log Analytics。
7. 验证直接调用 VM 模型成功，并确认 Blob 与 App Insights 双写成功。

- **Copilot 可执行**：observability helper 接入、验证脚本、KQL 查询、Blob 校验脚本。
- **可能需要用户操作**：如果 VM 网络或权限不足，需要用户协助或授权。
- **产物**：VM API observability 接入代码、字段映射、验证脚本。

### 步骤 7：Foundry 自定义 Agent

1. 明确 Agent 的最小场景，例如基于治理知识库的问答 Agent。
2. 在 Azure AI Foundry 创建 Agent project / Agent。
3. 绑定可用模型和知识源（可复用 RAG Service 知识材料）。
4. 发布 Agent 并获取可调用 endpoint 或 invocation 方式。
5. 在可代理场景下通过 APIM 暴露 Agent invocation endpoint，并开启 Foundry tracing。
6. 验证 Agent 可被外部脚本调用。
7. 记录 Agent id、endpoint、project、模型信息，作为独立报表对象。

- **Copilot 可执行**：需求设计、调用验证脚本、Agent 清单文档。
- **可能需要用户操作**：Foundry Portal 中创建 / 发布 Agent 如无法脚本化，由用户按步骤完成。
- **产物**：Agent 设计说明、调用示例、纳管清单。

### 步骤 8：Copilot Studio Agent

1. 在 Copilot Studio 创建最小自定义 Agent。
2. 配置知识源或 topic，使其能回答固定治理问题。
3. 发布 Agent。
4. 启用可被外部调用的通道，例如 Direct Line 或 Custom Connector。
5. 获取 endpoint、bot id、环境 id，并验证脚本可调用。
6. 与 Domain 1 Dataverse `bots` 资产发现结果对齐，作为独立报表对象。

- **Copilot 可执行**：调用验证脚本、Dataverse 发现对齐脚本、记录字段设计。
- **必须用户操作**：Copilot Studio UI 创建、发布、通道开启通常需要用户在 UI 中完成。
- **产物**：UI 操作指南、Agent 端点记录、调用验证脚本。

### 步骤 9：Tier 1 Consumer App

代表"合规使用 AI 服务"的标准消费者应用。调用 RAG Service、Foundry 原生模型、Foundry fine-tune 模型、VM Hugging Face 模型、Foundry Agent、Copilot Studio Agent 等全部 AI 服务后端。

1. 设计 Tier 1 App 的 API 接口：`POST /query`（接收用户请求并路由到对应 AI 服务）；`GET /health`；`GET /metadata`。
2. 在接收请求时继承平台 trace 上下文，不要求自建 `correlation_id`。
3. 对每类 AI 服务分别实现 connector：RAG Service、Foundry endpoint、VM Hugging Face endpoint、Foundry Agent、Copilot Studio Direct Line。
4. 对所有可代理的下游调用统一改为走 APIM。
5. 在每次实际 LLM 调用后记录 `trace_id`、`response_id`、`model_name`、`model_version`、`target_type`、`target_id`、`citations`（若调用 RAG），并写 Blob evidence。
6. 将 Tier 1 App 部署到 App Service，并接入 shared-observability。
7. 验证从外部调用 Tier 1 可成功触发下游 AI 服务，并确认 APIM / Foundry / Python evidence 三层链路完整。

- **Copilot 可执行**：接口设计、connector 代码、遥测 helper、Blob / App Insights 写入代码、部署脚本。
- **可能需要用户操作**：如 AI 服务 endpoint 权限不足，需要用户授权。
- **产物**：Tier 1 App 需求设计、API 代码、connector 代码、遥测 helper、部署脚本。

### 步骤 10：Tier 2 Consumer App

代表通过"AI 服务平台层"间接调用 AI 的上游业务应用。Tier 2 不直接调用 AI 服务，只调用 Tier 1，体现"间接 AI 使用"的治理追踪场景。

1. 设计 Tier 2 App 的 API 接口：`POST /request`（接收用户输入并转发到 Tier 1）；`GET /health`；`GET /metadata`。
2. 在接收请求时继承平台 trace 上下文，不要求自建 `correlation_id`。
3. 通过 APIM 暴露的 Tier 1 endpoint 调用 Tier 1，并透传当前 trace context。Tier 1 与 Tier 2 都必须保留平台 trace 关联能力。
4. 在 Tier 2 自身请求前后写入 App Insights 原生遥测；对于真正发生的 LLM 调用，由下游 Python 代码写 Blob evidence。
5. 将 Tier 2 App 部署到 App Service。
6. 验证：通过 KQL 可以从 Tier 2 请求的 `trace_id` 追踪到最终 AI 服务调用（Tier 2 / APIM / Tier 1 / Foundry 或 VM evidence），证明间接 AI 使用可追溯。

- **Copilot 可执行**：接口设计、转发代码、遥测 helper、部署脚本、KQL 验证查询。
- **可能需要用户操作**：如果 App Service 权限不足，需要用户授权。
- **产物**：Tier 2 App 需求设计、API 代码、部署脚本、KQL 追踪验证查询。

### 步骤 11：App Insights 遥测字段配置

1. 按 §2.4.3 定义统一字段：`trace_id`、`span_id`、`response_id`、`model_name`、`model_version`、`target_type`、`target_id`、`payload_ref`。
2. 在 shared-observability 写出的 evidence 事件中，优先使用贴近 Foundry / OTel 的字段命名。
3. 对不可直接埋点的目标，记录来自 Foundry / 调用脚本的等效字段。
4. 按 §2.4.5 定义统一事件名，并编写 KQL 查询验证 APIM、Foundry、Python evidence 的字段覆盖率。

- **Copilot 可执行**：遥测 helper、KQL 查询、字段覆盖率验证脚本。
- **可能需要用户操作**：如果 App Insights 权限不足，需要用户授权。
- **产物**：遥测字段规范、代码 helper、KQL 验证语句。

### 步骤 12：Foundry Tracing 能力

1. 确认哪些目标支持 Foundry Tracing：Foundry 原生模型、fine-tune 模型、Foundry Agent。
2. 在 Foundry 项目中开启 tracing / monitoring。
3. 连接 Application Insights / Log Analytics。
4. 触发测试调用，验证 trace 记录生成。
5. 明确 VM Hugging Face 模型不走 Foundry tracing，由 APIM（若可代理）+ Python evidence 记录。

- **Copilot 可执行**：tracing 状态检查、调用验证脚本、KQL 查询。
- **可能需要用户操作**：Foundry Portal 中开启 tracing 或连接资源。
- **产物**：Tracing 配置说明、验证查询、适用范围表。

### 步骤 13：Foundry Evaluations 能力

1. 设计 evaluation target schema：target type、endpoint、auth、input、expected behavior。
2. 为 RAG Service、Foundry 原生模型、fine-tune 模型、Foundry Agent、Copilot Studio Agent、VM Hugging Face 模型分别建立 target 记录。
3. 准备最小 evaluation 数据集。
4. 配置 groundedness / citation / safety evaluator。
5. 运行一次评估并导出结果。
6. 将结果字段映射到 Domain 4 指标。

- **Copilot 可执行**：target 配置文件、评估数据集样例、运行脚本、结果解析脚本。
- **可能需要用户操作**：Foundry UI 中创建 evaluation 或授权 evaluator。
- **产物**：evaluation 需求设计、target 清单、样例数据集、结果解析脚本。

### 步骤 14：Azure DevOps Work Items

1. 确认 Azure DevOps organization / project。
2. 设计 work item 类型、tag、severity、target_type、target_id 字段使用方式。
3. 创建或确认用于 red teaming / evaluation findings 的查询和 board。
4. 编写脚本，将 evaluation / PyRIT 结果写入 Work Items。
5. 验证 high / critical 未关闭发现可查询。

- **Copilot 可执行**：ADO REST 脚本、work item 创建脚本、查询脚本。
- **可能需要用户操作**：如果 PAT / OAuth / project 权限不足，需要用户授权。
- **产物**：ADO 字段设计、写入脚本、查询脚本。

### 步骤 15：Red Teaming 环境（PyRIT）

1. 选择执行环境：本地、开发 VM、GitHub Actions 或 Azure VM。
2. 安装 PyRIT 和必要依赖。
3. 为每类目标编写 connector：RAG Service、Foundry 模型、fine-tune 模型、Foundry Agent、Copilot Studio Agent、VM Hugging Face 模型。
4. connector 默认调用 target registry 记录的 endpoint；统一通过 shared-observability 写入证据链。
5. 准备最小攻击场景集。
6. 执行 smoke test，确认每类目标可调用。
7. 将结果写入 Application Insights 和 Azure DevOps Work Items。

- **Copilot 可执行**：PyRIT 环境脚本、connector 代码、最小攻击集、ADO 写入脚本。
- **可能需要用户操作**：目标 endpoint 权限、Copilot Studio 通道密钥、网络访问授权。
- **产物**：PyRIT 配置、connector 代码、攻击集、结果写入脚本。

### 步骤 16：指标状态语义定义

1. 定义 `N/A`、`Not Configured`、`No Data`、真实 `0` 的差异。
2. 为每个指标指定适用对象和不适用对象。
3. 定义首页 L1 状态 badge 规则。
4. 定义二级页每个 target type 的状态显示规则。

- **Copilot 可执行**：状态语义设计、API 响应字段设计、前端展示规则草案。
- **可能需要用户操作**：确认业务接受的风险阈值。
- **产物**：状态语义表、阈值规则、API 字段定义。

### 步骤 17：首页与二级页指标映射校准

1. 对照 `design-L2-domain-4-output-trustworthiness.md` 更新 L1/L2 指标映射。
2. 明确首页显示 `Grounded Response Rate` 和 `Model Identity Capture Gaps` 的数据来源。
3. 明确二级页按 6 类对象分开展示：AI 应用、Foundry 原生模型、Foundry fine-tune 模型、Foundry Agent、Copilot Studio Agent、VM Hugging Face 模型。
4. 设计 Domain 4 API endpoint、响应结构和前端卡片布局。
5. 后续进入代码开发，实现页面、API 和指标加载。

- **Copilot 可执行**：设计文档更新、API 设计、页面草图、后续代码实现。
- **可能需要用户操作**：确认首页是否继续保留 `Grounded Response Rate`，以及各指标阈值。
- **产物**：更新后的 Domain 4 页面设计、API 设计、开发任务清单。
