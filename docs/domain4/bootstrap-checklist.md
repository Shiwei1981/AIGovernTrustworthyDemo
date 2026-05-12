# Domain 4 Bootstrap Checklist

本清单用于将 README 中的规划信息转成可执行的落地步骤，便于持续记录完成状态、回填变量，并作为后续脚本化的依据。

## 目标

- 优先完成会阻塞后续 target 接入的基础资源。
- 把资源创建结果同步回填到 `.env.local.L4`。
- 为每个 target 保留 API、APIM 和可观测性验证位置。

## Phase 1: 优先手动创建

| 优先级 | 资源 | 名称 | 说明 | 输出 |
| --- | --- | --- | --- | --- |
| P0 | API Management | `AIGovernDomain4APIM` | 创建耗时最长，建议最先开始 | `L4_APIM_ENDPOINT`、`L4_APIM_SUBSCRIPTION_KEY` |
| P0 | 资源组 | `AIGovernDomain4RG` | 后续资源统一落在此资源组 | `L4_RESOURCE_GROUP` |
| P0 | App Service Plan | `AIGovernDomain4ASP` | RAG / Tier1 / Tier2 统一承载 | `L4_APP_SERVICE_PLAN_NAME` |
| P1 | Web App | `AIGovernRAGService` | 承载 RAG Service | `L4_RAG_SERVICE_URL` |
| P1 | Web App | `AIGovernTier1App` | 承载 Tier 1 Consumer App | `L4_TIER1_APP_URL` |
| P1 | Web App | `AIGovernTier2App` | 承载 Tier 2 Consumer App | `L4_TIER2_APP_URL` |
| P2 | Copilot Studio Agent | `AIGovernDomain4CopilotAgent` | 需 Portal / UI 操作 | `L4_COPILOT_STUDIO_BOT_ID`、`L4_COPILOT_STUDIO_DIRECTLINE_SECRET` |

## Phase 2: 脚本自动创建

| 优先级 | 资源 | 名称 | 工具 / 命令 | 输出 |
| --- | --- | --- | --- | --- |
| P1 | SPN | `AIGovernDomain4-App` | `az ad sp create-for-rbac` | `L4_APP_CLIENT_ID`、`L4_APP_CLIENT_SECRET` |
| P1 | SPN | `AIGovernDomain4-Eval` | `az ad sp create-for-rbac` | `L4_EVAL_CLIENT_ID`、`L4_EVAL_CLIENT_SECRET` |
| P1 | Azure AI Search | `aigovernl4search` | `az search service create` | `L4_AI_SEARCH_ADMIN_KEY`、`L4_AI_SEARCH_QUERY_KEY` |
| P1 | Storage Account | `aigovernl4storage` | `az storage account create` | `L4_STORAGE_CONNECTION_STRING` |
| P2 | Storage Containers | `rag-documents`、`finetune-data` | `az storage container create` | 无 |
| P2 | Azure VM | `AIGovernDomain4VM` | `az vm create` | `L4_VM_PRIVATE_IP` |
| P2 | VM 模型安装 | `Phi-3-mini via ollama` | SSH + 初始化脚本 | 无 |
| P2 | RBAC 角色授权 | Deploy SPN + App SPN | `az role assignment create` | 无 |

## Phase 3: 复用现有资源确认

| 资源 | 名称 | 资源组 | 变量 |
| --- | --- | --- | --- |
| Azure OpenAI | `contosoaigovdemo` | `AOAIRG` | `OPENAI_ENDPOINT`、`OPENAI_DEPLOYMENT` |
| AI Foundry Hub | `aigoverndemofoundryhub` | `AOAIRG` | `L4_AI_FOUNDRY_HUB_NAME` |
| AI Foundry Project | `aigoverndemofoundryproject` | `AOAIRG` | `L4_AI_FOUNDRY_PROJECT_NAME` |
| Application Insights | 现有实例 | `AIGovernDemoRG` | `APPLICATIONINSIGHTS_CONNECTION_STRING` |
| Log Analytics Workspace | `aiexvddh5zbxgtg` | `AIGovernDemoRG` | `LOG_ANALYTICS_WORKSPACE_ID` |

## Target 验证记录模板

后续每完成一个 target，请补充以下信息：

| Target | 实际 Endpoint | Resource ID | 是否纳入 APIM | App Insights 接入方式 | 当前状态 | 验证结果 |
| --- | --- | --- | --- | --- | --- | --- |
| RAG Service |  |  |  |  |  |  |
| Foundry 原生模型 |  |  |  |  |  |  |
| Foundry fine-tune 模型 |  |  |  |  |  |  |
| VM Hugging Face 模型 |  |  |  |  |  |  |
| Foundry Agent |  |  |  |  |  |  |
| Copilot Studio Agent |  |  |  |  |  |  |
| Tier 1 Consumer App |  |  |  |  |  |  |
| Tier 2 Consumer App |  |  |  |  |  |  |
| Evaluation runner |  |  |  |  |  |  |
| PyRIT runner |  |  |  |  |  |  |
