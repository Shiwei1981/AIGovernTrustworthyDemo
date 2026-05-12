# AIGovernTrustworthyDemo

本项目用于构建一系列演示程序和系统，以展示企业在 AI Trustworthy 领域的 Governance 实践。

当前仓库的目标不是一次性落地所有演示对象，而是先建设这些演示所需的前置条件、资源规划和治理基线，便于后续逐步补齐每个 target 的实现、接入、监控与验证。

## 项目目标

- 建立 Trustworthy AI Governance 演示所需的基础资源与依赖关系。
- 统一梳理各类被测对象的 API 暴露方式、APIM 纳管策略和 Application Insights 观测要求。
- 明确哪些资源需要手动创建、哪些资源由脚本自动创建、哪些资源可以直接复用。
- 为后续 RAG、Foundry、Agent、Consumer App、Evaluation Runner 和 PyRIT Runner 的实现提供执行基线。

## 当前范围

当前优先覆盖以下内容：

1. 2.4.6 API / APIM / Application Insights 总览矩阵
2. 资源创建方式总览
3. `.env.local.L4` 所需变量的来源对齐
4. 多应用项目骨架与跨应用统一宪章落位

配套文件：

- 环境变量配置：`.env.local.L4`
- 设计文档目录：`docs/`
- 跨应用统一宪章目录：`docs/charters/`
- Dashboard 设计工作区：`AIGovernDashboardDesign/`
- Domain 4 前置条件设计：`docs/design-L2-domain-4-prerequisites.md`
- Domain 4 低级别设计：`docs/design-L2-domain-4-prerequisites-lowleveldesign.md`
- Domain 4 输出可信设计：`docs/design-L2-domain-4-output-trustworthiness.md`

## 目录框架

当前仓库按“跨应用规则、设计工作区、应用实现、共享能力、基础设施”分层：

- `docs/`：权威需求、设计约束、跨应用统一宪章
- `AIGovernDashboardDesign/`：Dashboard 的调研、方法论、信息架构、KPI、原型与决策记录
- `apps/`：各个独立应用，例如 dashboard、RAG service、Tier1、Tier2、runner
- `packages/`：多个应用共享的数据契约与观测能力
- `infra/`：Azure、APIM、监控等基础设施脚本与配置

## 2.4.6 API / APIM / Application Insights 总览矩阵

本表用于持续跟踪每类被测对象需要暴露的 API、是否纳入 APIM、是否由 Application Insights 管理，以及当前设计状态。后续每完成一个 target，就在本表中补充实际 endpoint、resource id、状态和验证结果。

| 关联步骤 | 被测对象 | API / Endpoint | 后端承载 | APIM 管理 | APIM API 建议 | App Insights 管理 | 当前状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
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

## 6. 资源创建方式总览

### 6A. 手动创建资源

用户在 Azure Portal 完成创建，完成后填入 `.env.local.L4`。

| # | 资源类型 | 资源名 | 资源组 | SKU / 规格 | Tag: AI= | 完成后填入变量 |
| --- | --- | --- | --- | --- | --- | --- |
| M1 | 资源组 | `AIGovernTrustworthyDemoRG` | N/A | - | `AIGovernTrustworthyDemo-ResourceGroup` | `L4_RESOURCE_GROUP` |
| M2 | API Management | `AIGovernTrustworthyDemoAPIM` | `AIGovernTrustworthyDemoRG` | Developer，canadaeast | `AIGovernTrustworthyDemo-APIM` | `L4_APIM_ENDPOINT`、`L4_APIM_SUBSCRIPTION_KEY` |
| M3 | App Service Plan | `AIGovernTrustworthyDemoASP` | `AIGovernTrustworthyDemoRG` | B2，Linux，canadaeast | `AIGovernTrustworthyDemo-AppServicePlan` | `L4_APP_SERVICE_PLAN_NAME` |
| M4 | RAG Service Web App | `AIGovernTrustworthyDemoRAGService` | `AIGovernTrustworthyDemoRG` | Python 3.11，使用 M3 | `AIGovernTrustworthyDemo-RAGService` | `L4_RAG_SERVICE_URL` |
| M5 | Tier 1 App Web App | `AIGovernTrustworthyDemoTier1App` | `AIGovernTrustworthyDemoRG` | Python 3.11，使用 M3 | `AIGovernTrustworthyDemo-Tier1App` | `L4_TIER1_APP_URL` |
| M6 | Tier 2 App Web App | `AIGovernTrustworthyDemoTier2App` | `AIGovernTrustworthyDemoRG` | Python 3.11，使用 M3 | `AIGovernTrustworthyDemo-Tier2App` | `L4_TIER2_APP_URL` |
| M7 | Copilot Studio Agent | `AIGovernTrustworthyDemoCopilotStudioAgent` | Copilot Studio（Power Platform） | - | N/A | `L4_COPILOT_STUDIO_BOT_ID`、`L4_COPILOT_STUDIO_DIRECTLINE_SECRET` |

> APIM 创建耗时约 30-45 分钟，建议优先开始。创建时选择 Developer SKU、canadaeast，Publisher 使用自己的邮箱。

### 6B. 脚本自动创建资源

通过 `AZ_DEPLOY_CLIENT_ID` 对应的 SPN 执行。

| # | 资源类型 | 资源名 | 资源组 | 工具 / 命令 | Tag: AI= | 完成后填入变量 |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | SPN | `AIGovernTrustworthyDemoRAGServiceSPN` | N/A（AAD 对象） | `az ad sp create-for-rbac` | N/A | `L4_RAG_SERVICE_CLIENT_ID`、`L4_RAG_SERVICE_CLIENT_SECRET` |
| A2 | SPN | `AIGovernTrustworthyDemoTier1AppSPN` | N/A（AAD 对象） | `az ad sp create-for-rbac` | N/A | `L4_TIER1_APP_CLIENT_ID`、`L4_TIER1_APP_CLIENT_SECRET` |
| A3 | SPN | `AIGovernTrustworthyDemoTier2AppSPN` | N/A（AAD 对象） | `az ad sp create-for-rbac` | N/A | `L4_TIER2_APP_CLIENT_ID`、`L4_TIER2_APP_CLIENT_SECRET` |
| A4 | SPN | `AIGovernTrustworthyDemoEvaluationRunnerSPN` | N/A（AAD 对象） | `az ad sp create-for-rbac` | N/A | `L4_EVALUATION_RUNNER_CLIENT_ID`、`L4_EVALUATION_RUNNER_CLIENT_SECRET` |
| A5 | SPN | `AIGovernTrustworthyDemoPyRITRunnerSPN` | N/A（AAD 对象） | `az ad sp create-for-rbac` | N/A | `L4_PYRIT_RUNNER_CLIENT_ID`、`L4_PYRIT_RUNNER_CLIENT_SECRET` |
| A6 | Azure AI Search | `aigoverntrustworthysearch` | `AIGovernTrustworthyDemoRG` | `az search service create` | `AIGovernTrustworthyDemo-RAGSearch` | `L4_AI_SEARCH_ADMIN_KEY`、`L4_AI_SEARCH_QUERY_KEY` |
| A7 | AI Search 索引 | `aigoverntrustworthydemo-rag-index` | - | Python ingestion 脚本 | N/A | `L4_AI_SEARCH_INDEX_NAME`（已知） |
| A8 | Storage Account | `aigoverntrustworthydemostorage` | `AIGovernTrustworthyDemoRG` | `az storage account create` | `AIGovernTrustworthyDemo-Storage` | `L4_STORAGE_CONNECTION_STRING` |
| A9 | Storage Container | `aigoverntrustworthydemo-rag-docs` | - | `az storage container create` | N/A | - |
| A10 | Storage Container | `aigoverntrustworthydemo-finetune` | - | `az storage container create` | N/A | - |
| A11 | Azure VM | `AIGovernTrustworthyDemoVM` | `AIGovernTrustworthyDemoRG` | `az vm create` | `AIGovernTrustworthyDemo-HuggingFaceVM` | `L4_VM_PRIVATE_IP` |
| A12 | VM 模型安装 | `Phi-3-mini via ollama` | VM 内部 | SSH + 初始化脚本 | N/A | - |
| A13 | RBAC 角色授权 | Deploy SPN + 各应用运行时 SPN | 各资源作用域 | `az role assignment create` | N/A | - |

### 6C. 复用现有资源

以下资源无需重复创建，可直接复用。

| 资源类型 | 资源名 | 资源组 | 已填入变量 |
| --- | --- | --- | --- |
| Azure OpenAI | `contosoaigovdemo` | `AOAIRG` | `OPENAI_ENDPOINT`、`OPENAI_DEPLOYMENT` |
| AI Foundry Hub | `aigoverndemofoundryhub` | `AOAIRG` | `L4_AI_FOUNDRY_HUB_NAME` |
| AI Foundry Project | `aigoverndemofoundryproject` | `AOAIRG` | `L4_AI_FOUNDRY_PROJECT_NAME` |
| Application Insights | 现有（`InstrumentationKey=01f866fb...`） | `AIGovernDemoRG` | `APPLICATIONINSIGHTS_CONNECTION_STRING` |
| Log Analytics Workspace | `aiexvddh5zbxgtg` | `AIGovernDemoRG` | `LOG_ANALYTICS_WORKSPACE_ID` |

## 实施建议

1. 优先手动创建 APIM、App Service Plan 和 3 个 Web App，避免后续阻塞 API 接入与监控校验。
2. 完成 Portal 资源后，立即统一回填 `.env.local.L4`，避免变量来源分散。
3. 在每个 target 完成时，回填该 target 的实际 endpoint、resource id、部署状态和验证结果。
4. 对可选纳入 APIM 的目标，按是否需要统一检测入口来决定是否代理，而不是一开始全部接入。

## 后续计划

后续会在本仓库中逐步补充：

- 各模块的实现代码
- Azure 资源自动化脚本
- 部署说明和环境变量模板
- 运行、验证与评估脚本
- 观测与治理检查清单
