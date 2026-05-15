# Domain 4 · 前置条件环境 · 低级别设计（LLD）

## 1. 文档定位

本文件是 `design-L2-domain-4-prerequisites.md` 的低级别设计伴随文档，记录：

- 所有需要建立的 SPN 及对应权限
- 所有需要创建的 Azure 资源及关键配置
- `.env.local.L4` 环境变量设计（含复用变量和新增变量）
- 数据结构待确认项（⚠️ 停止点）

**约定**：
- 部署操作统一使用 `AZ_DEPLOY_CLIENT_ID`（SPN `227dcc2d-bea0-4156-a65b-0ea91a746203`）
- 所有 Domain 4 新建资源统一放入新资源组 `AIGovernTrustworthyRG`
- Tenant / Subscription 沿用现有：`7d3389c6-5b33-43be-b0fd-d7c303755fb5` / `47da4b42-0493-49ff-b3c8-45df3ae06821`
- Location 沿用 `canadaeast`
- Azure AI Foundry Hub / Project（旧 AzureML workspace 后端）：**保留复用**，用于既有 Foundry 资源、模型治理与非 RAG Web App 场景
  - Hub：`aigoverndemoaihub`（AIGovernDemoRG）
  - Project：`aigovenaihubproject`（AIGovernDemoRG）
- Microsoft Foundry Account / Project（新后端）：步骤 2 **不再作为 RAG 主路径依赖**；如后续其他步骤需要，再单独设计
- **Azure OpenAI Service（Domain 4 专用）**：**已创建 `AIGovernTrustworthyAOAI`**（`AIGovernTrustworthyRG`），用于原生模型 / fine-tune / 兼容性验证；RAG Web App 直接调用其模型 deployment
- App Insights：**复用现有实例**（`APPLICATIONINSIGHTS_CONNECTION_STRING`），不新建
- App Service Plan：**复用现有 `AIGovernDemoASP`**，不再新建 Domain 4 专用 Plan
- API Management：**新建 `AIGovernTrustworthyDemoAPIM`**，作为所有可代理 HTTP hop 的统一入口与 tracing 网关
- Azure Web App（RAG / Tier1 / Tier2）：由用户在 Portal 手动创建；RAG Service 使用 Web App `AIGovernTrustworthyRAGApp`
- Azure Container Registry：步骤 2 当前方案不依赖
- Observability Blob Archive：新建专用 Storage Account + Container，用于统一保存 AI 调用的完整 input / output / metadata
- 所有关键参数名（SPN 名、App 名等）写入 `.env.local.L4`，用户可手动修改
- 所有新建 Azure 资源必须附加以下 Tag：
  - `AI` = 资源用途描述（如 `AIGovernTrustworthyDemo-RAGSearch`）
  - `Owner` = `weishi@MngEnvMCAP029189.onmicrosoft.com`

---

## 2. 新建资源组

> **✅ 当前状态**：资源组 `AIGovernTrustworthyRG` 已存在（eastus2）。

| 项目 | 值 |
|---|---|
| 资源组名 | `AIGovernTrustworthyRG` |
| Subscription | `47da4b42-0493-49ff-b3c8-45df3ae06821` |
| Location | `eastus2` |
| Tags | `project=AIGovern`，`domain=aigoverntrustworthy`，`env=demo` |

```bash
# RG 已存在；仅供参考
az group create \
  --name AIGovernTrustworthyRG \
  --location eastus2 \
  --subscription 47da4b42-0493-49ff-b3c8-45df3ae06821 \
  --tags project=AIGovern domain=aigoverntrustworthy env=demo \
         AI=AIGovernTrustworthyDemo-ResourceGroup Owner=weishi@MngEnvMCAP029189.onmicrosoft.com
```

---

## 3. SPN 设计与权限清单

### 3.1 现有 SPN（复用）

| SPN 名称 / 用途 | Client ID | 环境变量 | 说明 |
|---|---|---|---|
| 部署 SPN（Deploy） | `227dcc2d-bea0-4156-a65b-0ea91a746203` | `AZ_DEPLOY_CLIENT_ID` | 用于所有 Azure 资源的创建、配置、CI/CD 部署 |
| 应用运行时 SPN（现有 App） | `c8d13a9c-dbba-4bb9-b9c5-9a3d10e64ab4` | `PROD_AZURE_CLIENT_ID` | 现有 AIGovernApp 使用，不做 Domain 4 新增授权 |

#### 3.1.1 需要为部署 SPN 补充的新权限（针对 AIGovernTrustworthyRG）

| 权限 | 作用域 | 原因 |
|---|---|---|
| `Contributor` | `AIGovernTrustworthyRG` | 创建和管理所有 Domain 4 资源 |
| `User Access Administrator` | `AIGovernTrustworthyRG` | 为新 SPN 分配 RBAC 角色 |
| `Cognitive Services Contributor` | `AIGovernTrustworthyRG` | 创建 Azure OpenAI / AI Foundry 资源 |
| `Azure AI Project Manager` | `AIGovernTrustworthyRG` / Foundry Project | 用于未来 Foundry Project / Agent 管理场景；不再是步骤 2 的前置 |
| `Azure AI Owner` | RAG Foundry Account / Project（按需） | 创建 Foundry project / agent resources 与调试期间的数据面管理 |
| `Search Service Contributor` | `AIGovernTrustworthyRG` | 创建和管理 Azure AI Search |
| `Storage Blob Data Contributor` | `AIGovernTrustworthyRG` | 上传 fine-tune 训练数据和 RAG 文档 |

```bash
# 授权部署 SPN 对新资源组的 Contributor + User Access Administrator
az role assignment create \
  --assignee 227dcc2d-bea0-4156-a65b-0ea91a746203 \
  --role Contributor \
  --scope /subscriptions/47da4b42-0493-49ff-b3c8-45df3ae06821/resourceGroups/AIGovernTrustworthyRG

az role assignment create \
  --assignee 227dcc2d-bea0-4156-a65b-0ea91a746203 \
  --role "User Access Administrator" \
  --scope /subscriptions/47da4b42-0493-49ff-b3c8-45df3ae06821/resourceGroups/AIGovernTrustworthyRG
```

---

### 3.2 新建 SPN

部署使用现有 SPN `AZ_DEPLOY_CLIENT_ID`。所有应用程序的运行时身份都单独新建，不共用一个运行时 SPN。所有会写统一 AI 调用证据链的运行时身份，都必须具备 observability Blob archive 的写入权限。所有新增 SPN 统一加入 `aigoverndemogroup`，统一使用 client secret 认证；应用对象与对应 service principal 统一写入标签 `AI:SPN`、`Owner:ITBob@MngEnvMCAP029189.onmicrosoft.com`。

#### 3.2.1 RAG Service 运行时 SPN（primary）

| 属性 | 值 |
|---|---|
| 建议显示名 | `AIGovernTrustworthyDemoRAGServiceSPN` |
| 用途 | RAG Web App 运行时身份（调用 AOAI、写 Blob evidence、写 App Insights） |
| 环境变量 | `L4_RAG_SERVICE_CLIENT_ID` / `L4_RAG_SERVICE_CLIENT_SECRET` |

| 权限 | 作用域 | 原因 |
|---|---|---|
| `Cognitive Services OpenAI User` | Azure OpenAI resource | Web App 调用推理 API |
| `Monitoring Metrics Publisher` | `AIGovernTrustworthyRG` | 写入 App Insights 自定义事件 |
| `Storage Blob Data Contributor` | Observability Blob Storage Account | 写入 AI 调用归档 |

> **当前结论**：`AIGovernTrustworthyDemoRAGServiceSPN` 是当前 RAG Web App 的首选运行时身份，不再作为 Hosted Agent fallback。

#### 3.2.2 Tier 1 App 运行时 SPN

| 属性 | 值 |
|---|---|
| 建议显示名 | `AIGovernTrustworthyDemoTier1AppSPN` |
| 用途 | Tier 1 Consumer App 运行时身份 |
| 环境变量 | `L4_TIER1_APP_CLIENT_ID` / `L4_TIER1_APP_CLIENT_SECRET` |

| 权限 | 作用域 | 原因 |
|---|---|---|
| `Cognitive Services OpenAI User` | AI Foundry / Azure OpenAI resource | 调用推理 API |
| `Monitoring Metrics Publisher` | `AIGovernTrustworthyRG` | 写入调用链与自定义事件 |
| `Storage Blob Data Contributor` | Observability Blob Storage Account | 写入 AI 调用归档 |

#### 3.2.3 Tier 2 App 运行时 SPN

| 属性 | 值 |
|---|---|
| 建议显示名 | `AIGovernTrustworthyDemoTier2AppSPN` |
| 用途 | Tier 2 Consumer App 运行时身份 |
| 环境变量 | `L4_TIER2_APP_CLIENT_ID` / `L4_TIER2_APP_CLIENT_SECRET` |

| 权限 | 作用域 | 原因 |
|---|---|---|
| `Monitoring Metrics Publisher` | `AIGovernTrustworthyRG` | 写入调用链与自定义事件 |
| `Storage Blob Data Contributor` | Observability Blob Storage Account | 写入 AI 调用归档 |

#### 3.2.4 Evaluation Runner 运行时 SPN

| 属性 | 值 |
|---|---|
| 建议显示名 | `AIGovernTrustworthyDemoEvaluationRunnerSPN` |
| 用途 | Evaluation runner 调用身份 |
| 环境变量 | `L4_EVALUATION_RUNNER_CLIENT_ID` / `L4_EVALUATION_RUNNER_CLIENT_SECRET` |

| 权限 | 作用域 | 原因 |
|---|---|---|
| `Azure AI User` | AI Foundry Project | 提交 Evaluation job，读取结果 |
| `Cognitive Services OpenAI User` | AI Foundry / Azure OpenAI resource | 调用裁判模型 |
| `Monitoring Metrics Publisher` | `AIGovernTrustworthyRG` | 写入 Evaluation 结果到 App Insights |
| `Storage Blob Data Contributor` | Observability Blob Storage Account | 写入 evaluation payload 归档 |

#### 3.2.5 PyRIT Runner 运行时 SPN

| 属性 | 值 |
|---|---|
| 建议显示名 | `AIGovernTrustworthyDemoPyRITRunnerSPN` |
| 用途 | PyRIT runner 调用身份 |
| 环境变量 | `L4_PYRIT_RUNNER_CLIENT_ID` / `L4_PYRIT_RUNNER_CLIENT_SECRET` |

| 权限 | 作用域 | 原因 |
|---|---|---|
| `Monitoring Metrics Publisher` | `AIGovernTrustworthyRG` | 写入 PyRIT 结果到 App Insights |
| `Storage Blob Data Contributor` | Observability Blob Storage Account | 写入 red teaming payload 归档 |

---

## 4. Azure 资源清单与关键配置

### 4.1 复用的现有资源（跨 RG，只读 / 调用）

| 资源 | 名称 / 端点 | 用途 | 环境变量 |
|---|---|---|---|
| AI Foundry Hub（旧） | `aigoverndemoaihub` | 既有 Foundry / AzureML workspace 资源 | `L4_AI_FOUNDRY_HUB_NAME` |
| AI Foundry Project（旧） | `aigovenaihubproject` | 既有 Foundry 资源；不作为当前 RAG Web App 的运行后端 | `L4_AI_FOUNDRY_PROJECT_NAME` |
| Application Insights | `appinsights` | 复用连接串（不在 L4 创建独立实例） | `APPLICATIONINSIGHTS_CONNECTION_STRING` |
| Log Analytics Workspace | `aiexvddh5zbxgtg` | 复用诊断日志汇集目标 | `LOG_ANALYTICS_WORKSPACE_NAME` |
| App Service Plan（现有，复用） | `AIGovernDemoASP`（canadaeast，B3） | 当前步骤 2 的 RAG Web App 直接复用 | `L4_APP_SERVICE_PLAN_NAME` |
| ACR | `AIGovernDemoACR`（`aigoverndemoacr.azurecr.io`） | 当前步骤 2 不依赖 | `PROD_ACR_LOGIN_SERVER` |

---

### 4.2 新建资源（均在 `AIGovernTrustworthyRG`）

#### 4.2.1 Application Insights

> **✅ 已确认（S5）**：复用现有实例，不新建。直接使用 `.env.local` 中的 `APPLICATIONINSIGHTS_CONNECTION_STRING`。

| 属性 | 值 |
|---|---|
| 实例 | 现有（见 `APPLICATIONINSIGHTS_CONNECTION_STRING`） |
| 操作 | 无需新建；在 `.env.local.L4` 中直接引用现有连接串 |
| 关联 Log Analytics | `aiexvddh5zbxgtg`（现有） |

---

#### 4.2.2 Azure AI Foundry Hub + Project（旧后端，复用）

> **✅ 已确认**：复用现有实例，已通过 SPN 查询到以下资源，信息已填入 `.env.local.L4`。该 Project endpoint 供既有 Foundry 场景使用，不作为当前 RAG Web App 的运行后端。

| 属性 | 值 |
|---|---|
| Hub 名称 | `aigoverndemoaihub` |
| Hub 资源组 | `AIGovernDemoRG` |
| Project 名称 | `aigovenaihubproject` |
| Project 资源组 | `AIGovernDemoRG` |
| Project Workspace ID | `3fd0a0f0-4511-48e9-aa5e-f0249e996cca` |
| Project Endpoint | `https://0ccc5150-37cd-4136-8f18-02728d0b38b7.workspace.eastus2.api.azureml.ms` |
| MLflow URI | `azureml://0ccc5150-37cd-4136-8f18-02728d0b38b7.workspace.eastus2.api.azureml.ms/mlflow/v1.0/.../AIGovernDemoRG/.../aigovenaihubproject` |

> **用途边界**：保留给步骤 3 / 4 / 7 的既有 Foundry 资源。当前步骤 2 的 RAG Web App 不依赖下一节的新后端 Foundry Account / Project。

---

#### 4.2.2A Azure Web App（RAG Service）

> **当前选定方案**：步骤 2 使用 Azure Web App `AIGovernTrustworthyRAGApp`，部署到**现有** App Service Plan `AIGovernDemoASP`。不再使用 Hosted Agent、ACR、Foundry vector store 作为默认路径。

| 属性 | 值 |
|---|---|
| Web App 名称 | `AIGovernTrustworthyRAGApp` |
| 资源组 | `AIGovernTrustworthyRG` |
| App Service Plan | `AIGovernDemoASP`（复用，资源组 `AIGovernDemoRG`） |
| Runtime | Python 3.11 |
| 对外入口 | 通过 APIM `/rag` 统一暴露 |
| 直接站点 URL | `https://AIGovernTrustworthyRAGApp.azurewebsites.net` |
| 运行时身份 | `L4_RAG_SERVICE_CLIENT_ID` / `L4_RAG_SERVICE_CLIENT_SECRET` |
| 环境变量 | `L4_RAG_APP_NAME`、`L4_RAG_APP_URL`、`L4_APP_SERVICE_PLAN_NAME` |

**实现原则**：

- PDF 知识材料随应用部署，或在启动时从受控目录读取。
- 应用内完成 PDF 解析、文本切块、轻量级检索和模型调用。
- 默认不创建 embedding、vector store、Azure AI Search 或额外检索云资源。
- 如后续需要新增 embedding / vector 资源，先暂停并征得用户同意。

---

#### 4.2.3 Azure OpenAI Service（Domain 4 专用）

> **✅ 已确认（S6，步骤 3 已完成）**：`AIGovernTrustworthyAOAI` 已创建并用于步骤 3。当前已验证 native deployment `AIGovernTrustworthyDemoNativeModel` 可直连调用，APIM `/native-model` 已通过 MSI 代理该 deployment，AOAI 平台诊断中可见 deployment / model / version。

| 属性 | 值 |
|---|---|
| 资源名 | `AIGovernTrustworthyAOAI` |
| 资源组 | `AIGovernTrustworthyRG` |
| Location | `canadaeast`（或与 Foundry Hub 同 region） |
| SKU | `S0` |
| 访问控制 | `disableLocalAuth = true`（仅 Entra token，不用 API Key） |
| Foundry Connection 名 | `AIGovernTrustworthyAOAI`（如需在 Foundry Hub / Project 中使用，可按连接资源方式添加） |
| 环境变量 | `L4_AOAI_ENDPOINT`，`L4_AOAI_SERVICE_NAME` |

**模型 Deployment（在此资源下创建）**：

| Deployment 名 | 模型 | 用途 |
|---|---|---|
| `AIGovernTrustworthyDemoNativeModel` | `gpt-5.4-nano` | Native Model（步骤 3）；同时作为 RAG Web App 默认生成模型 |
| `AIGovernTrustworthyDemoFineTuneModel` | Fine-tune 结果 | Fine-tune 部署（步骤 4） |

**📋 Portal 重建步骤（仅在需要重建时）**：
1. Portal → Azure OpenAI → **Create** → 资源组 `AIGovernTrustworthyRG`，名称 `AIGovernTrustworthyAOAI`，Location `canadaeast`，SKU S0
2. 创建后，在资源 Overview 记录 Endpoint URL → 填入 `L4_AOAI_ENDPOINT`
3. 将此资源作为 **Connection** 添加到 Foundry Hub `aigoverndemoaihub`：
   - Portal → AI Foundry Hub → Settings → Connected Resources → Add → Azure OpenAI → 选 `AIGovernTrustworthyAOAI`
4. 在该 AOAI 资源下，创建 model deployment `AIGovernTrustworthyDemoNativeModel`（gpt-5.4-nano）

---

#### 4.2.4 Azure AI Search（RAG fallback，可选）

> **状态调整**：RAG 主路径改为应用内代码式检索，不再以 Azure AI Search 作为必须资源。以下设计仅保留为 fallback：当内存检索在规模、相关性或管理性上不足时，再经用户确认启用。

| 属性 | 值 |
|---|---|
| 资源名 | `aigoverntrustworthysearch` |
| SKU | `Basic`（够用于 Demo，可升级） |
| Location | `canadaeast` |
| 索引名 | `aigoverntrustworthydemo-rag-index` |

```bash
az search service create \
  --name aigoverntrustworthysearch \
  --resource-group AIGovernTrustworthyRG \
  --location canadaeast \
  --sku Basic \
  --tags AI=AIGovernTrustworthyDemo-RAGSearch Owner=weishi@MngEnvMCAP029189.onmicrosoft.com
# fallback 才需要记录 admin key → L4_AI_SEARCH_ADMIN_KEY
# fallback 才需要记录 endpoint → L4_AI_SEARCH_ENDPOINT
```

> **S1 调整**：该 schema 仍可作为 Azure AI Search fallback 的最简 POC schema；当前 Web App 主路径不依赖它。

#### AI Search 索引 Schema（`aigoverntrustworthydemo-rag-index`）

| 字段名 | 类型 | 属性 | 说明 |
|---|---|---|---|
| `id` | `Edm.String` | key, filterable | 唯一 chunk ID，格式 `{source_name}_{chunk_index}` |
| `content` | `Edm.String` | searchable（`en.microsoft`） | 切分后的文本块 |
| `title` | `Edm.String` | searchable, filterable | 文档 / 文章标题 |
| `source_type` | `Edm.String` | filterable | `standard` \| `news` \| `product_solution` |
| `source_name` | `Edm.String` | filterable | 如 `NIST AI 600-1`、`ISO/IEC 42001`、`Microsoft Defender for AI` |
| `url` | `Edm.String` | — | 来源 URL（可为空） |
| `chunk_index` | `Edm.Int32` | sortable | 在原文档中的块顺序 |
| `ingested_at` | `Edm.String` | filterable | ISO 8601 摄取时间 |
| `content_vector` | `Collection(Edm.Single)` | searchable（向量，dims=1536） | `text-embedding-3-small` 输出 |

**知识库内容来源规划**（由应用程序自动填充）：

| source_type | 来源示例 | 填充方式 |
|---|---|---|
| `standard` | NIST AI RMF、NIST AI 600-1、ISO/IEC 42001、ISO/IEC 23894、OWASP LLM Top 10 | PDF 下载 → 切分 → ingestion 脚本 |
| `news` | AI Security 新闻（RSS / Bing News API） | 定期拉取摘要 → ingestion 脚本 |
| `product_solution` | Microsoft Defender for AI、Azure AI Content Safety、Purview AI Hub、合作伙伴方案 | 官方文档页面抓取 → ingestion 脚本 |

**Embedding 变量（fallback）**：`L4_EMBEDDING_MODEL_DEPLOYMENT=text-embedding-3-small`（仅在用户批准启用 embedding 方案时使用）

---

#### 4.2.5 Storage Account（复用；fine-tune 数据 + RAG 文档上传）

| 属性 | 值 |
|---|---|
| 资源名 | `aigoverntrustworthysa` |
| SKU | `Standard_LRS` |
| Location | `canadaeast` |
| Container（blob）| `aigoverntrustworthydemo-rag-docs`（RAG 原始文档），`aigoverntrustworthydemo-finetune`（fine-tune 训练集） |

```bash
az storage account create \
  --name aigoverntrustworthysa \
  --resource-group AIGovernTrustworthyRG \
  --location canadaeast \
  --sku Standard_LRS \
  --kind StorageV2 \
  --tags AI=AIGovernTrustworthyDemo-Storage Owner=weishi@MngEnvMCAP029189.onmicrosoft.com

az storage container create --account-name aigoverntrustworthysa --name aigoverntrustworthydemo-rag-docs
az storage container create --account-name aigoverntrustworthysa --name aigoverntrustworthydemo-finetune
# 记录 connection string → L4_STORAGE_CONNECTION_STRING
```

> **当前执行约束（2026-05-14）**：以上 `create` 命令主要作为现有资源来源的历史记录。当前步骤 4 已获得例外授权，可由 AI 自动化在 `aigoverntrustworthysa` 中创建 `aigoverntrustworthydemo-finetune` container；此外还允许创建 fine-tune job 与 `AIGovernTrustworthyDemoFineTuneModel` deployment。若执行中还需要创建其他类型云资源，应视为新的前置阻塞并先请求用户确认。

> **✅ 已确认（S2）**：POC fine-tune，验证 AI Governance 场景的模型调优与治理可追溯性。

#### Fine-tune 训练数据设计

| 属性 | 值 |
|---|---|
| 格式 | JSONL，Azure OpenAI **chat completion** 格式（`messages` 数组） |
| 总条数 | 5000 条 |
| 内容来源 | 用户上传的 5 个 AI Governance 主题 PDF 文档 |
| 生成方式 | 先用已存在的 native model `AIGovernTrustworthyDemoNativeModel`（`gpt-5.4-nano`）基于 5 个 PDF 内容批量生成问答对，再整理为 JSONL |
| 故意错误条数 | 0 条（本轮 draft 不把故意错误样本放入训练集；如需要对照，单独保留 eval / red teaming 数据集） |
| Fine-tune 目标模型 | `gpt-4.1` |
| 部署后 API 格式 | 与基础模型一致（OpenAI chat completion 格式） |
| 训练文件路径 | `aigoverntrustworthydemo-finetune/aigoverntrustworthydemo-qa-5000.jsonl`（上传到 `aigoverntrustworthysa`） |
| Storage 变量来源 | `.env.local.L4` 中的 `L4_STORAGE_ACCOUNT_NAME`、`L4_STORAGE_CONNECTION_STRING`、`L4_STORAGE_CONTAINER_FINETUNE` |
| 仓库归档路径 | `docs/finetune-qa-archive/aigoverntrustworthydemo-qa-5000.jsonl` |

**训练数据 JSONL 格式示例**：

```jsonl
{"messages": [{"role": "system", "content": "You are an AI governance expert specializing in AI governance frameworks and controls."}, {"role": "user", "content": "What is the primary purpose of the NIST AI Risk Management Framework?"}, {"role": "assistant", "content": "The NIST AI RMF provides a structured approach to identifying, assessing, managing, and governing AI risks across the lifecycle of an AI system."}]}
{"messages": [{"role": "system", "content": "You are an AI governance expert specializing in AI governance frameworks and controls."}, {"role": "user", "content": "Why is traceability important in AI governance?"}, {"role": "assistant", "content": "Traceability helps organizations understand which model, data, prompts, and control points were involved in a decision, making governance, audit, and incident analysis possible."}]}
```

**注意**：

1. 本轮 draft 训练集不混入故意错误样本。若后续需要行为对照或红队样本，应保留独立的 eval / red teaming 数据集，而不是直接并入 fine-tune 训练文件。
2. 2026-05-14 对 `aigoverntrustworthyfoundry` / `AIGovernTrustworthyAOAI` 执行 `az cognitiveservices account list-models` 的结果显示：`gpt-5.4-nano` 没有 `capabilities.FineTuneTokensMaxValue` 且 `finetuneCapabilities = null`；同一 catalog 中 `gpt-4.1`、`gpt-4.1-nano`、`gpt-4.1-mini`、`gpt-4o-mini`、`gpt-5.4-mini` 均暴露 fine-tune 能力字段。当前步骤 4 选用 `gpt-4.1`，这是用户确认后的 base model 选择。
3. 当前步骤 4 要求所有具体操作由 AI 自动化完成；除已批准的 fine-tune container、fine-tune job、fine-tuned deployment 外，不得创建或删除其他云资源。因此 Storage 账户仍固定复用 `.env.local.L4` 所指向的既有 `aigoverntrustworthysa`。
4. 如脚本运行时需要 `OTEL_SERVICE_NAME`，应以进程级环境变量注入，不新增新的 `.env.local.L4` 键名。
5. 2026-05-15 实际运行结果：`aigoverntrustworthydemo-finetune` container 已创建，5000 行训练 JSONL 已生成并上传；fine-tune job `ftjob-ae456ec3dc4d468b87ecb8512ad33f86` 已通过 `aigoverntrustworthyfoundry` account endpoint 创建并成功完成。早先 `invalidPayload: The specified base model does not support fine-tuning.` 已确认是自动化调用缺少 `trainingType=GlobalStandard` 且 endpoint 选择不一致导致；当前平台已返回 fine-tuned model `gpt-4.1-2025-04-14.ft-ae456ec3dc4d468b87ecb8512ad33f86-aigovtrustdemo`，deployment `AIGovernTrustworthyDemoFineTuneModel` 与 APIM `/finetune-model` 均已配置完成。

---

#### 4.2.6 Observability Payload Archive Blob

> **✅ 已确认（S4）**：当前 POC 采用专用 Blob Storage 作为统一 payload archive，由用户手动创建，当前已创建。

| 属性 | 值 |
|---|---|
| Storage Account | `aigoverntrustworthysa` |
| 资源组 | `AIGovernTrustworthyRG` |
| SKU | `Standard_LRS` |
| Location | `canadaeast` |
| Blob Container | `ai-invocation-archive` |
| Blob Prefix | `aigoverntrustworthy` |

**认证方式**：应用程序访问该 Blob archive 时统一使用运行时 SPN + Azure RBAC，不使用 Storage Account Key。

**最小权限建议**：

1. 运行时写入 evidence 的 SPN：`Storage Blob Data Contributor`
2. 作用域优先：`ai-invocation-archive` 容器；如果当前不便细分，也可先授权到 Storage Account `aigoverntrustworthysa`
3. 如需只读检查或离线排查：额外使用 `Storage Blob Data Reader`
4. 仅当代码还要通过 ARM 查询 Storage Account 元数据时，才额外给 `Reader`；如果直接用 Blob endpoint + Entra token，不需要管理面 Reader

如需重建，可参考以下 Azure CLI 命令：

```bash
az storage account create \
  --name aigoverntrustworthysa \
  --resource-group AIGovernTrustworthyRG \
  --location canadaeast \
  --sku Standard_LRS \
  --kind StorageV2 \
  --tags AI=AIGovernTrustworthyDemo-ObservabilityBlob Owner=weishi@MngEnvMCAP029189.onmicrosoft.com

az storage container create \
  --account-name aigoverntrustworthysa \
  --name ai-invocation-archive
```

统一路径约定：

`aigoverntrustworthy/{yyyy}/{mm}/{dd}/{service_name}/{target_type}/{archive_id}/{input|output|metadata}.json`

#### 4.2.7 shared-observability 组件

| 属性 | 值 |
|---|---|
| 组件目录 | `packages/shared-observability/` |
| 包名 | `shared_observability` |
| 语言 | Python 3.11 |
| 责任 | 记录 Python 侧 LLM 调用完整证据；写入薄 App Insights evidence 事件；生成 Blob archive 路径 |
| 接入对象 | RAG Service、Tier 1、Tier 2、VM API、Evaluation runner、PyRIT runner、各类 connector 脚本 |

#### 4.2.8 Azure API Management

| 属性 | 值 |
|---|---|
| 资源名 | `AIGovernTrustworthyDemoAPIM` |
| 资源组 | `AIGovernTrustworthyRG` |
| SKU | Developer, stv2 |
| 区域 | Canada East |
| VNet 模式 | **Internal** ✅ |
| 子网 | `subnet-APIM` (10.1.2.0/28) in `AIGovernCanadaEastVNET` |
| Public IP | `40.86.204.28` (`AIGovernAPIM-pip`) |
| Gateway URL | `https://aigoverntrustworthydemoapim.azure-api.net` |
| Regional Gateway | `https://aigoverntrustworthydemoapim-canadaeast-01.regional.azure-api.net` |
| Management URL | `https://aigoverntrustworthydemoapim.management.azure-api.net` |
| Developer Portal | `https://aigoverntrustworthydemoapim.developer.azure-api.net` |
| NSG | `nsg-subnet-APIM` (in `AIGovernDemoRG`), 含所有必需 APIM 规则 |
| 状态 | ✅ **Succeeded，VNet Internal 配置完成，所有网络连接 healthy** |
| 定位 | 所有可代理 HTTP hop 的统一 AI Gateway |
| 能力 | Gateway tracing、backend diagnostics、与 App Insights 集成 |
| 配置顺序 | 先连 App Insights，再配置 diagnostics，再逐步把可代理 endpoint 接到 APIM 后面 |

**APIM 定位**：

1. 代理 `app -> app` 和 `app -> model/agent endpoint` 的所有可代理 HTTP hop。
2. 不承担 Foundry managed agent 内部模型 hop 的代理职责。
3. 与 Foundry tracing 一起构成统一 App Insights 查询面。

**建议配置顺序**：

1. ~~创建 APIM 实例~~ ✅ 已完成
2. 连接现有 `APPLICATIONINSIGHTS_CONNECTION_STRING`（下一步）
3. 开启 gateway / generative AI gateway diagnostics
4. 配置 RAG / Tier 1 / Tier 2 / Foundry endpoint / VM endpoint 的 API 与 backend
5. 再验证 trace 与 diagnostics 是否进入同一查询面

---

#### 4.2.9 App Service Plan + Web Apps（RAG / Tier 1 / Tier 2）

> **✅ 已确认（S6，已调整）**：复用现有 App Service Plan `AIGovernDemoASP`。步骤 2 创建 RAG Web App；步骤 9 / 10 的 Tier 1 / Tier 2 也可按需继续复用该 Plan。

**App Service Plan**：

| 属性 | 值 |
|---|---|
| Plan 名称 | `AIGovernDemoASP` |
| 资源组 | `AIGovernDemoRG` |
| SKU | `B3`（现有） |
| OS | Linux |
| Location | `canadaeast` |

**Web Apps**：

| App | 建议资源名 | 环境变量 | Observability Profile | 运行身份 |
|---|---|---|---|---|
| RAG Service | `AIGovernTrustworthyRAGApp` | `L4_RAG_APP_NAME` | `AIGovernTrustworthyDemo.RAGService` | `L4_RAG_SERVICE_CLIENT_ID` |
| Tier 1 Consumer App | `AIGovernTrustworthyDemoTier1App` | `L4_TIER1_APP_NAME` | `AIGovernTrustworthyDemo.Tier1App` | `L4_TIER1_APP_CLIENT_ID` |
| Tier 2 Consumer App | `AIGovernTrustworthyDemoTier2App` | `L4_TIER2_APP_NAME` | `AIGovernTrustworthyDemo.Tier2App` | `L4_TIER2_APP_CLIENT_ID` |

**RAG Web App 网络配置（已完成）**：

| 配置项 | 值 | 说明 |
|---|---|---|
| VNet 集成 | `default` subnet（`AIGovernCanadaEastVNET`）| 使 Web App 可访问 VNet 内私有端点 |
| `WEBSITE_DNS_SERVER` | `168.63.129.16` | 使用 Azure VNet 感知 DNS（解析私有 DNS 区域）|
| `WEBSITE_VNET_ROUTE_ALL` | 不设置（默认 0）| 仅私有 IP 路由走 VNet，公网流量（AOAI）仍走互联网 |
| `azure-api.net` 私有 DNS 区域 | `aigoverntrustworthydemoapim → 10.1.2.4` | 解析 APIM Internal VNet 网关 IP |
| AOAI CNAME 绕行记录 | `cognitivecaeprod → trafficmanager.net`<br>`cognitivecaeprod-canadaeast-01.regional → cloudapp.azure.com` | 防止 VNet DNS 截断 AOAI 的公网解析链 |
| Storage Account 私有端点 | `aigoverntrustworthysa → 10.1.1.4`（subnet-SA） | `publicNetworkAccess=Disabled`；Web App 通过 VNet 集成访问 |

> **重要**：AOAI (`aigoverntrustworthyaoai`) 的 `publicNetworkAccess=Enabled`，通过公网直接可达。  
> APIM Internal VNet 网关 IP `10.1.2.4` 的公共 DNS 已返回该 IP，但 VNet DNS 需 `azure-api.net` 私有区域辅助解析。



**📋 用户操作步骤**：
1. Portal → App Services → 创建 RAG Web App `AIGovernTrustworthyRAGApp`，选择现有 Plan `AIGovernDemoASP`，Runtime Python 3.11
2. Portal → App Services → 后续分别创建 Tier 1 / Tier 2 两个 Web App，继续选择 Plan `AIGovernDemoASP`
3. 创建后将实际 URL 填入 `.env.local.L4` 的 `L4_RAG_APP_URL`、`L4_TIER1_APP_URL`、`L4_TIER2_APP_URL`

> **✅ 已确认（S3）**：CPU-only，使用最小可运行量化模型。模型大小不影响演示效果。

| 属性 | 值 |
|---|---|
| 资源名 | `AIGovernTrustworthyDemoVM` |
| OS | Ubuntu 22.04 LTS |
| VM Size | `Standard_D4s_v3`（4 vCPU，16GB RAM，CPU-only） |
| Public IP | 否（仅内网访问；由 runner / app 直连） |
| Network Security Group | 仅允许受控 VNet / 内网来源对 11434 端口的入站 |
| OS Disk | 64GB（足够放 ollama + 模型） |

**选定模型**：[`microsoft/Phi-3-mini-4k-instruct`](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct)（GGUF Q4_K_M 量化）

| 属性 | 值 |
|---|---|
| 模型大小（Q4_K_M GGUF） | ~2.2 GB |
| 内存占用 | ~3-4 GB（D4s_v3 的 16GB 完全够用） |
| 推理速度（CPU） | ~3-5 tokens/s（够演示） |
| 许可证 | MIT（无商用限制） |
| API 格式 | OpenAI-compatible（via ollama） |

**运行方式**：[ollama](https://ollama.com)（单二进制，自动下载 GGUF，暴露 OpenAI 兼容 API 在 `:11434`）

```bash
# VM 初始化脚本（在 VM 内执行）
curl -fsSL https://ollama.com/install.sh | sh
ollama pull phi3:mini          # 拉取 Phi-3-mini（~2.2GB）
ollama serve &                  # 默认监听 0.0.0.0:11434
# 验证
curl http://localhost:11434/api/tags
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"phi3:mini","messages":[{"role":"user","content":"hello"}]}'
```

**VM 创建命令**：

```bash
az vm create \
  --name AIGovernTrustworthyDemoVM \
  --resource-group AIGovernTrustworthyRG \
  --image Ubuntu2204 \
  --size Standard_D4s_v3 \
  --admin-username azureuser \
  --generate-ssh-keys \
  --public-ip-address "" \
  --nsg AIGovernTrustworthyDemoVMNSG \
  --tags AI=AIGovernTrustworthyDemo-HuggingFaceVM Owner=weishi@MngEnvMCAP029189.onmicrosoft.com
# 记录 Private IP → L4_VM_PRIVATE_IP
```

---

## 5. `.env.local.L4` 变量设计

> 本文件设计已在仓库根目录创建为 `.env.local.L4`。
> **不得提交到 Git**（已通过 `.gitignore` 排除 `*.local*`）。

### 5.1 复用的现有变量（从 `.env.local` 直接复制）

```
AZURE_TENANT_ID                         # 7d3389c6-5b33-43be-b0fd-d7c303755fb5
AZ_DEPLOY_TENANT_ID                     # 同上
AZ_DEPLOY_CLIENT_ID                     # 227dcc2d-bea0-4156-a65b-0ea91a746203
AZ_DEPLOY_CLIENT_SECRET                 # （从 .env.local 复制）
AZ_SUBSCRIPTION_ID                      # 47da4b42-0493-49ff-b3c8-45df3ae06821
L4_AI_FOUNDRY_PROJECT_ENDPOINT          # https://0ccc5150-37cd-4136-8f18-02728d0b38b7.workspace.eastus2.api.azureml.ms
APPLICATIONINSIGHTS_CONNECTION_STRING   # （从 .env.local 复制，或替换为 L4 专用实例）
LOG_ANALYTICS_WORKSPACE_NAME            # aiexvddh5zbxgtg
LOG_LEVEL                               # INFO
APP_ENV                                 # local
```

### 5.2 新增的 Domain 4 专用变量

```
# ── 资源组 ──────────────────────────────────────────────────────────────
L4_RESOURCE_GROUP=AIGovernTrustworthyRG

# ── 资源 Tag（Owner 可复用；AI tag 按资源类型区分）──────────────────────
L4_TAG_OWNER=weishi@MngEnvMCAP029189.onmicrosoft.com
L4_TAG_AI_RESOURCE_GROUP=AIGovernTrustworthyDemo-ResourceGroup
L4_TAG_AI_APP_SERVICE_PLAN=AIGovernTrustworthyDemo-AppServicePlan
L4_TAG_AI_RAG_SERVICE=AIGovernTrustworthyDemo-RAGService
L4_TAG_AI_TIER1_APP=AIGovernTrustworthyDemo-Tier1App
L4_TAG_AI_TIER2_APP=AIGovernTrustworthyDemo-Tier2App
L4_TAG_AI_SEARCH=AIGovernTrustworthyDemo-RAGSearch
L4_TAG_AI_STORAGE=AIGovernTrustworthyDemo-Storage
L4_TAG_AI_OBSERVABILITY_BLOB=AIGovernTrustworthyDemo-ObservabilityBlob
L4_TAG_AI_HUGGING_FACE_VM=AIGovernTrustworthyDemo-HuggingFaceVM

# ── 各应用运行时 SPN ──────────────────────────────────────────────────────
L4_RAG_SERVICE_CLIENT_ID=<to-be-created>
L4_RAG_SERVICE_CLIENT_SECRET=<to-be-created>
L4_TIER1_APP_CLIENT_ID=<to-be-created>
L4_TIER1_APP_CLIENT_SECRET=<to-be-created>
L4_TIER2_APP_CLIENT_ID=<to-be-created>
L4_TIER2_APP_CLIENT_SECRET=<to-be-created>
L4_EVALUATION_RUNNER_CLIENT_ID=<to-be-created>
L4_EVALUATION_RUNNER_CLIENT_SECRET=<to-be-created>
L4_PYRIT_RUNNER_CLIENT_ID=<to-be-created>
L4_PYRIT_RUNNER_CLIENT_SECRET=<to-be-created>

# ── OpenTelemetry service.name（共用同一个 App Insights，按应用区分）────────
L4_OTEL_SERVICE_NAME_RAG_SERVICE=AIGovernTrustworthyDemo.RAGService
L4_OTEL_SERVICE_NAME_TIER1_APP=AIGovernTrustworthyDemo.Tier1App
L4_OTEL_SERVICE_NAME_TIER2_APP=AIGovernTrustworthyDemo.Tier2App
L4_OTEL_SERVICE_NAME_EVALUATION_RUNNER=AIGovernTrustworthyDemo.EvaluationRunner
L4_OTEL_SERVICE_NAME_PYRIT_RUNNER=AIGovernTrustworthyDemo.PyRITRunner

# ── API Management ───────────────────────────────────────────────────────
L4_APIM_SERVICE_NAME=AIGovernTrustworthyDemoAPIM
L4_APIM_GATEWAY_URL=https://aigoverntrustworthydemoapim.azure-api.net
L4_APIM_REGIONAL_GATEWAY_URL=https://aigoverntrustworthydemoapim-canadaeast-01.regional.azure-api.net
L4_APIM_PUBLIC_IP=40.86.204.28
L4_APIM_APP_INSIGHTS_LOGGER_NAME=applicationinsights

# ── shared-observability ────────────────────────────────────────────────
L4_OBSERVABILITY_PACKAGE_NAME=shared_observability
L4_OBSERVABILITY_BLOB_STORAGE_ACCOUNT_NAME=aigoverntrustworthysa
L4_OBSERVABILITY_BLOB_CONTAINER=ai-invocation-archive
L4_OBSERVABILITY_BLOB_PREFIX=aigoverntrustworthy

# ── Azure OpenAI Service（Domain 4 专用，AIGovernTrustworthyAOAI）──────────────
L4_AOAI_SERVICE_NAME=AIGovernTrustworthyAOAI
L4_AOAI_ENDPOINT=https://aigoverntrustworthyaoai.openai.azure.com/

# ── Azure AI Foundry（旧 AzureML workspace 后端；非当前 RAG Web App 运行路径）──────
L4_AI_FOUNDRY_HUB_NAME=aigoverndemoaihub
L4_AI_FOUNDRY_PROJECT_NAME=aigovenaihubproject
L4_AI_FOUNDRY_PROJECT_ENDPOINT=https://0ccc5150-37cd-4136-8f18-02728d0b38b7.workspace.eastus2.api.azureml.ms

# ── Azure AI Foundry · 模型部署 ────────────────────────────────────────────
L4_FOUNDRY_NATIVE_MODEL_DEPLOYMENT=AIGovernTrustworthyDemoNativeModel
L4_FOUNDRY_NATIVE_MODEL_ENDPOINT=https://aigoverntrustworthyaoai.openai.azure.com/openai/deployments/AIGovernTrustworthyDemoNativeModel/chat/completions?api-version=2025-01-01-preview
L4_FOUNDRY_FINETUNE_MODEL_DEPLOYMENT=AIGovernTrustworthyDemoFineTuneModel
L4_FOUNDRY_FINETUNE_MODEL_ENDPOINT=<to-be-created>

# ── Azure AI Foundry · Agent（步骤 7：Foundry 自定义 Agent）────────────────
L4_FOUNDRY_AGENT_NAME=AIGovernTrustworthyDemoFoundryAgent
L4_FOUNDRY_AGENT_ID=<to-be-created>

# ── RAG Governance Service（步骤 2：Web App + lightweight retrieval）────────
L4_RAG_APP_NAME=AIGovernTrustworthyRAGApp
L4_RAG_APP_URL=https://aigoverntrustworthyragapp-hchcfae9hpczcrcx.canadaeast-01.azurewebsites.net  # https://AIGovernTrustworthyRAGApp.azurewebsites.net
L4_RAG_RETRIEVAL_MODE=local_lexical_in_memory
L4_RAG_SERVICE_URL=https://aigoverntrustworthydemoapim.azure-api.net/rag  # APIM /rag base URL；RAG Web App 的 /ui/responses 服务端代理读取此值

# ── Azure AI Search（RAG fallback；主路径不依赖）───────────────────────────
L4_AI_SEARCH_NAME=aigoverntrustworthysearch
L4_AI_SEARCH_ENDPOINT=https://aigoverntrustworthysearch.search.windows.net
L4_AI_SEARCH_INDEX_NAME=aigoverntrustworthydemo-rag-index
L4_AI_SEARCH_ADMIN_KEY=<to-be-created>
L4_AI_SEARCH_QUERY_KEY=<to-be-created>

# ── Storage（fine-tune 数据 + RAG 文档）────────────────────────────────────
L4_STORAGE_ACCOUNT_NAME=aigoverntrustworthysa
L4_STORAGE_CONNECTION_STRING=<to-be-created>
L4_STORAGE_CONTAINER_RAG_DOCS=aigoverntrustworthydemo-rag-docs
L4_STORAGE_CONTAINER_FINETUNE=aigoverntrustworthydemo-finetune

# ── App Services（RAG / Tier 1 / Tier 2；复用现有 Plan）─────────────────────
L4_APP_SERVICE_PLAN_NAME=AIGovernDemoASP
L4_APP_SERVICE_PLAN_RESOURCE_GROUP=AIGovernDemoRG
L4_TIER1_APP_NAME=AIGovernTrustworthyDemoTier1App
L4_TIER1_APP_URL=<to-be-deployed>               # https://AIGovernTrustworthyDemoTier1App.azurewebsites.net
L4_TIER2_APP_NAME=AIGovernTrustworthyDemoTier2App
L4_TIER2_APP_URL=<to-be-deployed>               # https://AIGovernTrustworthyDemoTier2App.azurewebsites.net

# ── VM（Hugging Face 模型）────────────────────────────────────────────────
L4_VM_NAME=AIGovernTrustworthyDemoVM
L4_VM_PRIVATE_IP=<to-be-created>
L4_VM_MODEL_API_PORT=11434

# ── Copilot Studio Agent ──────────────────────────────────────────────────
L4_COPILOT_STUDIO_AGENT_NAME=AIGovernTrustworthyDemoCopilotStudioAgent
L4_COPILOT_STUDIO_BOT_ID=<to-be-created>
L4_COPILOT_STUDIO_ENVIRONMENT_ID=<to-be-confirmed>
L4_COPILOT_STUDIO_DIRECTLINE_SECRET=<to-be-created>

# ── 模型命名（用于 target registry 和 report 展示）────────────────────────
L4_TARGET_REGISTRY_VERSION=1
```

---

## 6. 资源创建方式总览

### 6A. 手动创建资源（用户在 Portal 完成，完成后填入 `.env.local.L4`）

| # | 资源类型 | 资源名 | 资源组 | SKU / 规格 | Tag: AI= | 完成后填入变量 | 当前状态 |
|---|---|---|---|---|---|---|---|
| M1 | 资源组 | `AIGovernTrustworthyRG` | N/A | — | `AIGovernTrustworthyDemo-ResourceGroup` | `L4_RESOURCE_GROUP` | 已手动创建 |
| M2 | Observability Blob Storage Account | `aigoverntrustworthysa` | `AIGovernTrustworthyRG` | Standard_LRS，canadaeast | `AIGovernTrustworthyDemo-ObservabilityBlob` | `L4_OBSERVABILITY_BLOB_STORAGE_ACCOUNT_NAME` | 已手动创建 |
| M3 | Observability Blob Container | `ai-invocation-archive` | — | — | N/A | `L4_OBSERVABILITY_BLOB_CONTAINER` | 已手动创建 |
| M4 | API Management | `AIGovernTrustworthyDemoAPIM` | `AIGovernTrustworthyRG` | Developer stv2，canadaeast，VNet Internal | `AIGovernTrustworthyDemo-APIM` | `L4_APIM_GATEWAY_URL` | ✅ 已创建，VNet Internal 配置完成 |
| M5 | App Service Plan（复用） | `AIGovernDemoASP` | `AIGovernDemoRG` | B3，Linux，canadaeast | 现有资源 | `L4_APP_SERVICE_PLAN_NAME` | 已存在 |
| M5A | Azure OpenAI Service | `AIGovernTrustworthyAOAI` | `AIGovernTrustworthyRG` | S0，canadaeast，`disableLocalAuth=true` | `AIGovernTrustworthyDemo-AOAI` | `L4_AOAI_ENDPOINT` | ✅ 已创建；native deployment 已验证；APIM `/native-model` 已接入 |
| M6 | RAG Web App | `AIGovernTrustworthyRAGApp` | `AIGovernTrustworthyRG` | Python 3.11，使用 M5；v1.0.4；VNet 集成（default subnet）；WEBSITE_DNS_SERVER=168.63.129.16 | `AIGovernTrustworthyDemo-RAGService` | `L4_RAG_APP_URL` | ✅ 已创建并部署（v1.0.4，含 /ui/responses 代理，APIM 全链路 trace_id 验证通过）|
| M7 | Tier 1 App Web App | `AIGovernTrustworthyDemoTier1App` | `AIGovernTrustworthyRG` | Python 3.11，使用 M5 | `AIGovernTrustworthyDemo-Tier1App` | `L4_TIER1_APP_URL` | 待创建 |
| M8 | Tier 2 App Web App | `AIGovernTrustworthyDemoTier2App` | `AIGovernTrustworthyRG` | Python 3.11，使用 M5 | `AIGovernTrustworthyDemo-Tier2App` | `L4_TIER2_APP_URL` | 待创建 |
| M9 | Copilot Studio Agent | `AIGovernTrustworthyDemoCopilotStudioAgent` | Copilot Studio（Power Platform） | — | N/A | `L4_COPILOT_STUDIO_BOT_ID`、`L4_COPILOT_STUDIO_DIRECTLINE_SECRET` | 待创建 |

> 当前 POC 的统一观测通过 `APIM +（适用时的 Foundry tracing / AOAI 平台诊断）+ shared-observability + Application Insights + Blob archive` 落地。

---

### 6B. 脚本自动创建资源（通过 SPN `AZ_DEPLOY_CLIENT_ID` 执行）

| # | 资源类型 | 资源名 | 资源组 | 工具 / 命令 | Tag: AI= | 完成后填入变量 |
|---|---|---|---|---|---|---|
| A1 | SPN | `AIGovernTrustworthyDemoRAGServiceSPN` | N/A（AAD 对象） | `az ad sp create-for-rbac` | N/A | `L4_RAG_SERVICE_CLIENT_ID`、`L4_RAG_SERVICE_CLIENT_SECRET` |
| A2 | SPN | `AIGovernTrustworthyDemoTier1AppSPN` | N/A（AAD 对象） | `az ad sp create-for-rbac` | N/A | `L4_TIER1_APP_CLIENT_ID`、`L4_TIER1_APP_CLIENT_SECRET` |
| A3 | SPN | `AIGovernTrustworthyDemoTier2AppSPN` | N/A（AAD 对象） | `az ad sp create-for-rbac` | N/A | `L4_TIER2_APP_CLIENT_ID`、`L4_TIER2_APP_CLIENT_SECRET` |
| A4 | SPN | `AIGovernTrustworthyDemoEvaluationRunnerSPN` | N/A（AAD 对象） | `az ad sp create-for-rbac` | N/A | `L4_EVALUATION_RUNNER_CLIENT_ID`、`L4_EVALUATION_RUNNER_CLIENT_SECRET` |
| A5 | SPN | `AIGovernTrustworthyDemoPyRITRunnerSPN` | N/A（AAD 对象） | `az ad sp create-for-rbac` | N/A | `L4_PYRIT_RUNNER_CLIENT_ID`、`L4_PYRIT_RUNNER_CLIENT_SECRET` |
| A6 | Azure AI Search（fallback） | `aigoverntrustworthysearch` | `AIGovernTrustworthyRG` | `az search service create` | `AIGovernTrustworthyDemo-RAGSearch` | `L4_AI_SEARCH_ADMIN_KEY`、`L4_AI_SEARCH_QUERY_KEY` |
| A7 | AI Search 索引（fallback） | `aigoverntrustworthydemo-rag-index` | — | Python ingestion 脚本 | N/A | `L4_AI_SEARCH_INDEX_NAME`（已知） |
| A8 | Storage Account（复用） | `aigoverntrustworthysa` | `AIGovernTrustworthyRG` | 复用现有 Storage Account | `AIGovernTrustworthyDemo-Storage` | `L4_STORAGE_CONNECTION_STRING` |
| A9 | Storage Container | `aigoverntrustworthydemo-rag-docs` | — | `az storage container create` | N/A | — |
| A10 | Storage Container | `aigoverntrustworthydemo-finetune` | — | `az storage container create` | N/A | — |
| A11 | Azure VM | `AIGovernTrustworthyDemoVM` | `AIGovernTrustworthyRG` | `az vm create` | `AIGovernTrustworthyDemo-HuggingFaceVM` | `L4_VM_PRIVATE_IP` |
| A12 | Network Security Group | `AIGovernTrustworthyDemoVMNSG` | `AIGovernTrustworthyRG` | `az network nsg create` | `AIGovernTrustworthyDemo-HuggingFaceVM` | — |
| A13 | Azure OpenAI 原生模型 Deployment | `AIGovernTrustworthyDemoNativeModel` | `AIGovernTrustworthyRG` | AOAI Portal / SDK | N/A | `L4_FOUNDRY_NATIVE_MODEL_DEPLOYMENT` |
| A14 | Azure OpenAI Fine-tune Deployment | `AIGovernTrustworthyDemoFineTuneModel` | `AIGovernTrustworthyRG` | AOAI Portal / SDK | N/A | `L4_FOUNDRY_FINETUNE_MODEL_DEPLOYMENT` |
| A15 | Azure AI Foundry Agent | `AIGovernTrustworthyDemoFoundryAgent` | `AIGovernDemoRG / aigovenaihubproject` | Foundry Portal / SDK | N/A | `L4_FOUNDRY_AGENT_ID` |
| A16 | VM 模型安装 | Phi-3-mini via ollama | VM 内部 | SSH + 初始化脚本 | N/A | — |
| A17 | RBAC 角色授权 | Deploy SPN + RAG / Tier1 / Tier2 等应用运行时 SPN | 各资源作用域 | `az role assignment create` | N/A | — |

---

### 6C. 复用现有资源（无需创建，已确认）

| 资源类型 | 资源名 | 资源组 | 已填入变量 |
|---|---|---|---|
| AI Foundry Hub | `aigoverndemoaihub` | `AIGovernDemoRG` | `L4_AI_FOUNDRY_HUB_NAME` |
| AI Foundry Project | `aigovenaihubproject` | `AIGovernDemoRG` | `L4_AI_FOUNDRY_PROJECT_NAME` |
| Application Insights | `appinsights` | `AIGovernDemoRG` | `APPLICATIONINSIGHTS_CONNECTION_STRING` |
| Log Analytics Workspace | `aiexvddh5zbxgtg` | `AIGovernDemoRG` | `LOG_ANALYTICS_WORKSPACE_ID` |


---

## 7. 已知停止点汇总

以下事项需要在进入对应步骤之前确认，避免重建成本：

| # | 决策内容 | 涉及步骤 | 状态 |
|---|---|---|---|
| S1 | RAG 主路径锁定为 Azure Web App + 代码切块 + 进程内轻量级检索；AI Search schema 仅保留 fallback | 步骤 2（RAG Service） | ✅ 已确认 |
| S2 | Fine-tune：JSONL chat completion 格式，5000 条 AI 生成 Q&A，主题为 AI Governance，要求尽量覆盖用户上传的 5 个 PDF；Q&A 生成阶段复用 native model `gpt-5.4-nano`，真正 fine-tune base model 使用 `gpt-4.1`；训练文件上传复用 `.env.local.L4` 中既有 storage，且问答对需在 `docs/finetune-qa-archive/` 留档 | 步骤 4（fine-tune 模型） | ✅ 已确认 |
| S3 | VM CPU-only，Standard_D4s_v3，使用 Phi-3-mini-4k-instruct（Q4_K_M GGUF，~2.2GB），通过 ollama 暴露 OpenAI 兼容 API | 步骤 5（VM 模型） | ✅ 已确认 |
| S4 | Observability Blob archive 全新建设，由用户手动创建，当前已创建（`aigoverntrustworthysa` + `ai-invocation-archive`） | 步骤 1（基础设施） | ✅ 已确认 |
| S5 | App Insights 复用现有实例（`APPLICATIONINSIGHTS_CONNECTION_STRING`） | 步骤 1（基础设施） | ✅ 已确认 |
| S6 | 复用现有 App Service Plan（`AIGovernDemoASP`，Linux，canadaeast）；步骤 2 创建 RAG Web App，步骤 9/10 可继续复用 | 步骤 2/9/10 | ✅ 已确认 |
| S7 | 旧 Foundry Hub / Project 复用现有实例；步骤 2 不再新建 RAG Hosted Agent 专用 Foundry Account / Project | 步骤 2/3/4/7 | ✅ 已确认 |
| S8 | RAG 运行时身份使用现有 `AIGovernTrustworthyDemoRAGServiceSPN`；不再依赖 Hosted Agent 平台生成 identity | 步骤 2 | ✅ 已确认 |

---

## 8. 资源命名结果

以下为当前建议采用的完整命名结果，已区分复用项与新建项。这里不再保留命名模式或示例。

### 8.1 复用资源命名结果

| 类型 | 名称 |
|---|---|
| Deploy SPN | `devdeployspn` |
| Azure AI Foundry Hub | `aigoverndemoaihub` |
| Azure AI Foundry Project | `aigovenaihubproject` |
| Application Insights | `appinsights` |
| Log Analytics Workspace | `aiexvddh5zbxgtg` |
| ACR（legacy / fallback） | `AIGovernDemoACR` |


### 8.2 新建资源命名结果

| 类型 | 名称 |
|---|---|
| 资源组 | `AIGovernTrustworthyRG` |
| RAG Service 运行时 SPN | `AIGovernTrustworthyDemoRAGServiceSPN` |
| Tier 1 App 运行时 SPN | `AIGovernTrustworthyDemoTier1AppSPN` |
| Tier 2 App 运行时 SPN | `AIGovernTrustworthyDemoTier2AppSPN` |
| Evaluation Runner 运行时 SPN | `AIGovernTrustworthyDemoEvaluationRunnerSPN` |
| PyRIT Runner 运行时 SPN | `AIGovernTrustworthyDemoPyRITRunnerSPN` |
| RAG Web App | `AIGovernTrustworthyRAGApp` |
| Azure AI Search（fallback） | `aigoverntrustworthysearch` |
| AI Search 索引（fallback） | `aigoverntrustworthydemo-rag-index` |
| Storage Account | `aigoverntrustworthysa` |
| Storage Container | `aigoverntrustworthydemo-rag-docs` |
| Storage Container | `aigoverntrustworthydemo-finetune` |
| Observability Payload Archive Storage Account | `aigoverntrustworthysa` |
| Observability Payload Archive Container | `ai-invocation-archive` |
| App Service Plan（复用） | `AIGovernDemoASP` |
| Tier 1 App Web App | `AIGovernTrustworthyDemoTier1App` |
| Tier 2 App Web App | `AIGovernTrustworthyDemoTier2App` |
| Azure VM | `AIGovernTrustworthyDemoVM` |
| Network Security Group | `AIGovernTrustworthyDemoVMNSG` |
| Azure AI Foundry 原生模型 Deployment | `AIGovernTrustworthyDemoNativeModel` |
| Azure AI Foundry Fine-tune Deployment | `AIGovernTrustworthyDemoFineTuneModel` |
| Azure AI Foundry Agent | `AIGovernTrustworthyDemoFoundryAgent` |
| Copilot Studio Agent | `AIGovernTrustworthyDemoCopilotStudioAgent` |


---

## 9. 设计决策记录（Design Decisions）

以下记录各关键设计决策及其理由，供后续开发者参考。

| 编号 | 决策 | 理由 | 决策日期 |
|---|---|---|---|
| DD-001 | RAG 知识库优先覆盖 AI Governance 行业标准 PDF | 与 AIGovernApp 的 Governance 定位高度相关；先使用稳定标准文档，新闻和产品资料后置 | 2026-05 |
| DD-002 | RAG 检索主路径使用代码切块 + 进程内轻量级检索 | 避免 Hosted Agent 区域限制与新增 embedding / vector 资源；Azure AI Search 仅保留 fallback | 2026-05 |
| DD-003 | Fine-tune 使用 5000 条 AI 生成的 Q&A | 先用 native model 基于用户上传的 5 个 AI Governance PDF 生成结构化问答对，再将其整理为覆盖更全的可治理训练集 | 2026-05 |
| DD-004 | Fine-tune 数据来源限定为用户上传的 5 个 AI Governance PDF；fine-tune base model 改为 `gpt-4.1-2025-04-14` | `gpt-5.4-nano` 已验证不暴露 fine-tune capability 字段；`gpt-4.1` 在当前 Foundry catalog 和 Portal 中可用于 fine-tune，且已被用户确认为步骤 4 训练基座。自动化创建 job 时必须使用 Foundry account endpoint `aigoverntrustworthyfoundry` 并传入 `trainingType=GlobalStandard` | 2026-05 |
| DD-005 | VM 使用 Phi-3-mini-4k-instruct（Q4_K_M GGUF）+ ollama | CPU-only，最小资源消耗；MIT 许可；ollama 单命令部署，OpenAI 兼容 API；模型质量足够演示 | 2026-05 |
| DD-006 | RAG / Tier 1 / Tier 2 Web App 统一走 App Service；RAG 复用现有 `AIGovernDemoASP` | 减少资源数量，避免新建 Service Plan；符合当前用户要求 | 2026-05 |
| DD-007 | 步骤 2 放弃 Hosted Agent；旧 Foundry Hub / Project 继续仅用于其他 Foundry 场景 | Hosted Agent 受区域限制；RAG Web App 不再依赖新后端 Foundry Project | 2026-05 |
| DD-008 | App Insights 复用现有 | POC 阶段日志量小，无需隔离；减少资源数量 | 2026-05 |
| DD-009 | 所有关键参数名写入 `.env.local.L4` | 支持后续脚本自动化；用户可手动修改参数名 | 2026-05 |
| DD-010 | 步骤 4 执行路径固定为 AI 自动化；仅允许创建 fine-tune container、fine-tune job、fine-tuned deployment；中间 Q&A 同步归档到 `docs/finetune-qa-archive/` | 满足用户要求：自动化闭环、复用既有 storage、保留设计目录归档，并把允许创建的例外边界显式化 | 2026-05 |
| DD-011 | Fine-tune base model 的最终可用性必须以 `fine_tuning.jobs.create` 实测为准，而不能只看 `list-models` capability 字段 | 2026-05-14 实测表明：catalog 暴露 fine-tune 能力字段并不等价于当前账号/区域/endpoint 上能成功创建 fine-tune job | 2026-05 |
