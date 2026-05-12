# Domain 4 · 前置条件环境 · 低级别设计（LLD）

## 1. 文档定位

本文件是 `design-L2-domain-4-prerequisites.md` 的低级别设计伴随文档，记录：

- 所有需要建立的 SPN 及对应权限
- 所有需要创建的 Azure 资源及关键配置
- `.env.local.L4` 环境变量设计（含复用变量和新增变量）
- 数据结构待确认项（⚠️ 停止点）

**约定**：
- 部署操作统一使用 `AZ_DEPLOY_CLIENT_ID`（SPN `227dcc2d-bea0-4156-a65b-0ea91a746203`）
- 所有 Domain 4 新建资源统一放入新资源组 `AIGovernTrustworthyDemoRG`
- Tenant / Subscription 沿用现有：`7d3389c6-5b33-43be-b0fd-d7c303755fb5` / `47da4b42-0493-49ff-b3c8-45df3ae06821`
- Location 沿用 `canadaeast`
- Azure AI Foundry Hub / Project：**复用现有实例**，不新建
  - Hub：`aigoverndemofoundryhub`（AOAIRG）
  - Project：`aigoverndemofoundryproject`（AOAIRG，与 OpenAI 同资源组）
- App Insights：**复用现有实例**（`APPLICATIONINSIGHTS_CONNECTION_STRING`），不新建
- App Service Plan：**新建 `AIGovernTrustworthyDemoASP`**，由用户在 Portal 手动创建
- Azure Web App（RAG Service / Tier1 / Tier2）：由用户在 Portal 手动创建
- APIM：由用户在 Portal 手动创建
- 所有关键参数名（SPN 名、App 名等）写入 `.env.local.L4`，用户可手动修改
- 所有新建 Azure 资源必须附加以下 Tag：
  - `AI` = 资源用途描述（如 `AIGovernTrustworthyDemo-RAGSearch`）
  - `Owner` = `weishi@MngEnvMCAP029189.onmicrosoft.com`

---

## 2. 新建资源组

| 项目 | 值 |
|---|---|
| 资源组名 | `AIGovernTrustworthyDemoRG` |
| Subscription | `47da4b42-0493-49ff-b3c8-45df3ae06821` |
| Location | `canadaeast` |
| Tags | `project=AIGovern`，`domain=domain4`，`env=demo` |

```bash
az group create \
  --name AIGovernTrustworthyDemoRG \
  --location canadaeast \
  --subscription 47da4b42-0493-49ff-b3c8-45df3ae06821 \
  --tags project=AIGovern domain=domain4 env=demo \
         AI=AIGovernTrustworthyDemo-ResourceGroup Owner=weishi@MngEnvMCAP029189.onmicrosoft.com
```

---

## 3. SPN 设计与权限清单

### 3.1 现有 SPN（复用）

| SPN 名称 / 用途 | Client ID | 环境变量 | 说明 |
|---|---|---|---|
| 部署 SPN（Deploy） | `227dcc2d-bea0-4156-a65b-0ea91a746203` | `AZ_DEPLOY_CLIENT_ID` | 用于所有 Azure 资源的创建、配置、CI/CD 部署 |
| 应用运行时 SPN（现有 App） | `c8d13a9c-dbba-4bb9-b9c5-9a3d10e64ab4` | `PROD_AZURE_CLIENT_ID` | 现有 AIGovernApp 使用，不做 Domain 4 新增授权 |

#### 3.1.1 需要为部署 SPN 补充的新权限（针对 AIGovernTrustworthyDemoRG）

| 权限 | 作用域 | 原因 |
|---|---|---|
| `Contributor` | `AIGovernTrustworthyDemoRG` | 创建和管理所有 Domain 4 资源 |
| `User Access Administrator` | `AIGovernTrustworthyDemoRG` | 为新 SPN 分配 RBAC 角色 |
| `API Management Service Contributor` | `AIGovernTrustworthyDemoRG` | 创建和配置 APIM（如在此 RG 内新建）|
| `Cognitive Services Contributor` | `AIGovernTrustworthyDemoRG` | 创建 Azure OpenAI / AI Foundry 资源 |
| `Azure AI Developer` | `AIGovernTrustworthyDemoRG` | 管理 AI Foundry Hub / Project / Agent |
| `Search Service Contributor` | `AIGovernTrustworthyDemoRG` | 创建和管理 Azure AI Search |
| `Storage Blob Data Contributor` | `AIGovernTrustworthyDemoRG` | 上传 fine-tune 训练数据和 RAG 文档 |

```bash
# 授权部署 SPN 对新资源组的 Contributor + User Access Administrator
az role assignment create \
  --assignee 227dcc2d-bea0-4156-a65b-0ea91a746203 \
  --role Contributor \
  --scope /subscriptions/47da4b42-0493-49ff-b3c8-45df3ae06821/resourceGroups/AIGovernTrustworthyDemoRG

az role assignment create \
  --assignee 227dcc2d-bea0-4156-a65b-0ea91a746203 \
  --role "User Access Administrator" \
  --scope /subscriptions/47da4b42-0493-49ff-b3c8-45df3ae06821/resourceGroups/AIGovernTrustworthyDemoRG
```

---

### 3.2 新建 SPN

部署使用现有 SPN `AZ_DEPLOY_CLIENT_ID`。所有应用程序的运行时身份都单独新建，不共用一个运行时 SPN。

#### 3.2.1 RAG Service 运行时 SPN

| 属性 | 值 |
|---|---|
| 建议显示名 | `AIGovernTrustworthyDemoRAGServiceSPN` |
| 用途 | RAG Service 运行时身份 |
| 环境变量 | `L4_RAG_SERVICE_CLIENT_ID` / `L4_RAG_SERVICE_CLIENT_SECRET` |

| 权限 | 作用域 | 原因 |
|---|---|---|
| `Cognitive Services OpenAI User` | AI Foundry / Azure OpenAI resource | 调用 OpenAI / Foundry 推理 API |
| `Azure AI Developer` | AI Foundry Project | 调用 Foundry Agent、fine-tune endpoint |
| `Search Index Data Reader` | AI Search resource | RAG 检索 |
| `Search Index Data Contributor` | AI Search resource | 写入索引（ingestion） |
| `Monitoring Metrics Publisher` | `AIGovernTrustworthyDemoRG` | 写入 App Insights 自定义事件 |
| `Storage Blob Data Reader` | Storage Account | 读取文档与训练数据 |

#### 3.2.2 Tier 1 App 运行时 SPN

| 属性 | 值 |
|---|---|
| 建议显示名 | `AIGovernTrustworthyDemoTier1AppSPN` |
| 用途 | Tier 1 Consumer App 运行时身份 |
| 环境变量 | `L4_TIER1_APP_CLIENT_ID` / `L4_TIER1_APP_CLIENT_SECRET` |

| 权限 | 作用域 | 原因 |
|---|---|---|
| `Cognitive Services OpenAI User` | AI Foundry / Azure OpenAI resource | 调用推理 API |
| `Monitoring Metrics Publisher` | `AIGovernTrustworthyDemoRG` | 写入调用链与自定义事件 |

#### 3.2.3 Tier 2 App 运行时 SPN

| 属性 | 值 |
|---|---|
| 建议显示名 | `AIGovernTrustworthyDemoTier2AppSPN` |
| 用途 | Tier 2 Consumer App 运行时身份 |
| 环境变量 | `L4_TIER2_APP_CLIENT_ID` / `L4_TIER2_APP_CLIENT_SECRET` |

| 权限 | 作用域 | 原因 |
|---|---|---|
| `Monitoring Metrics Publisher` | `AIGovernTrustworthyDemoRG` | 写入调用链与自定义事件 |

#### 3.2.4 Evaluation Runner 运行时 SPN

| 属性 | 值 |
|---|---|
| 建议显示名 | `AIGovernTrustworthyDemoEvaluationRunnerSPN` |
| 用途 | Evaluation runner 调用身份 |
| 环境变量 | `L4_EVALUATION_RUNNER_CLIENT_ID` / `L4_EVALUATION_RUNNER_CLIENT_SECRET` |

| 权限 | 作用域 | 原因 |
|---|---|---|
| `Azure AI Developer` | AI Foundry Project | 提交 Evaluation job，读取结果 |
| `Cognitive Services OpenAI User` | AI Foundry / Azure OpenAI resource | 调用裁判模型 |
| `API Management Service Reader` | APIM resource | 通过 APIM URL 调用 target API |
| `Monitoring Metrics Publisher` | `AIGovernTrustworthyDemoRG` | 写入 Evaluation 结果到 App Insights |

#### 3.2.5 PyRIT Runner 运行时 SPN

| 属性 | 值 |
|---|---|
| 建议显示名 | `AIGovernTrustworthyDemoPyRITRunnerSPN` |
| 用途 | PyRIT runner 调用身份 |
| 环境变量 | `L4_PYRIT_RUNNER_CLIENT_ID` / `L4_PYRIT_RUNNER_CLIENT_SECRET` |

| 权限 | 作用域 | 原因 |
|---|---|---|
| `API Management Service Reader` | APIM resource | 通过 APIM URL 调用 target API |
| `Monitoring Metrics Publisher` | `AIGovernTrustworthyDemoRG` | 写入 PyRIT 结果到 App Insights |

---

## 4. Azure 资源清单与关键配置

### 4.1 复用的现有资源（跨 RG，只读 / 调用）

| 资源 | 名称 / 端点 | 用途 | 环境变量 |
|---|---|---|---|
| Azure OpenAI Resource | `contosoaigovdemo` | RAG 生成、Evaluation 裁判模型 | `OPENAI_ENDPOINT` |
| OpenAI Deployment | `gpt-5.4` | 推理 + 评估 | `OPENAI_DEPLOYMENT` |
| Application Insights | `appinsights` | 复用连接串（不在 L4 创建独立实例） | `APPLICATIONINSIGHTS_CONNECTION_STRING` |
| Log Analytics Workspace | `aiexvddh5zbxgtg` | 复用诊断日志汇集目标 | `LOG_ANALYTICS_WORKSPACE_NAME` |
| App Service Plan（现有，非 Domain 4） | `AIGovernDemoASP`（canadaeast，B3） | 现有 AIGovernApp 使用，不用于 Domain 4 | `AZ_APP_SERVICE_PLAN` |
| ACR | `AIGovernDemoACR`（`aigoverndemoacr.azurecr.io`） | 容器镜像存储（按需复用） | `PROD_ACR_LOGIN_SERVER` |

---

### 4.2 新建资源（均在 `AIGovernTrustworthyDemoRG`）

#### 4.2.1 Application Insights

> **✅ 已确认（S5）**：复用现有实例，不新建。直接使用 `.env.local` 中的 `APPLICATIONINSIGHTS_CONNECTION_STRING`。

| 属性 | 值 |
|---|---|
| 实例 | 现有（见 `APPLICATIONINSIGHTS_CONNECTION_STRING`） |
| 操作 | 无需新建；在 `.env.local.L4` 中直接引用现有连接串 |
| 关联 Log Analytics | `aiexvddh5zbxgtg`（现有） |

---

#### 4.2.2 Azure AI Foundry Hub + Project

> **✅ 已确认**：复用现有实例，已通过 SPN 查询到以下资源，信息已填入 `.env.local.L4`。

| 属性 | 值 |
|---|---|
| Hub 名称 | `aigoverndemofoundryhub` |
| Hub 资源组 | `AOAIRG` |
| Project 名称 | `aigoverndemofoundryproject` |
| Project 资源组 | `AOAIRG` |
| Project Workspace ID | `e73f789c-5753-4885-ba81-52d55385f0a7` |
| Project Endpoint | `https://aigoverndemofoundryhub.services.ai.azure.com`（需 Portal 确认） |
| MLflow URI | `azureml://eastus2.api.azureml.ms/mlflow/v1.0/.../aigoverndemofoundryproject` |

> 📋 **用户操作**：在 [ai.azure.com](https://ai.azure.com) → Project Overview 确认 endpoint URL 格式，如有差异更新 `L4_AI_FOUNDRY_PROJECT_ENDPOINT`。

---

#### 4.2.3 Azure AI Search（RAG Service 使用）

| 属性 | 值 |
|---|---|
| 资源名 | `aigoverntrustworthysearch` |
| SKU | `Basic`（够用于 Demo，可升级） |
| Location | `canadaeast` |
| 索引名 | `aigoverntrustworthydemo-rag-index` |

```bash
az search service create \
  --name aigoverntrustworthysearch \
  --resource-group AIGovernTrustworthyDemoRG \
  --location canadaeast \
  --sku Basic \
  --tags AI=AIGovernTrustworthyDemo-RAGSearch Owner=weishi@MngEnvMCAP029189.onmicrosoft.com
# 记录 admin key → L4_AI_SEARCH_ADMIN_KEY
# 记录 endpoint → L4_AI_SEARCH_ENDPOINT
```

> **✅ 已确认（S1）**：最简 POC schema，面向 AI Security / AI Governance 文档检索场景。Embedding 模型使用 Azure OpenAI `text-embedding-3-small`（维度 1536）。

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

**Embedding 变量**：`L4_EMBEDDING_MODEL_DEPLOYMENT=text-embedding-3-small`（使用现有 OPENAI_ENDPOINT）

---

#### 4.2.4 Storage Account（fine-tune 数据 + RAG 文档上传）

| 属性 | 值 |
|---|---|
| 资源名 | `aigoverntrustworthydemostorage` |
| SKU | `Standard_LRS` |
| Location | `canadaeast` |
| Container（blob）| `aigoverntrustworthydemo-rag-docs`（RAG 原始文档），`aigoverntrustworthydemo-finetune`（fine-tune 训练集） |

```bash
az storage account create \
  --name aigoverntrustworthydemostorage \
  --resource-group AIGovernTrustworthyDemoRG \
  --location canadaeast \
  --sku Standard_LRS \
  --kind StorageV2 \
  --tags AI=AIGovernTrustworthyDemo-Storage Owner=weishi@MngEnvMCAP029189.onmicrosoft.com

az storage container create --account-name aigoverntrustworthydemostorage --name aigoverntrustworthydemo-rag-docs
az storage container create --account-name aigoverntrustworthydemostorage --name aigoverntrustworthydemo-finetune
# 记录 connection string → L4_STORAGE_CONNECTION_STRING
```

> **✅ 已确认（S2）**：POC fine-tune，验证 AI Governance 场景的模型调优与治理可追溯性。

#### Fine-tune 训练数据设计

| 属性 | 值 |
|---|---|
| 格式 | JSONL，Azure OpenAI **chat completion** 格式（`messages` 数组） |
| 总条数 | 210 条（200 正确 + 10 故意错误） |
| 内容来源 | NIST AI RMF、NIST AI 600-1 |
| 生成方式 | 由脚本调用 GPT-5.4 自动生成问答对 |
| 故意错误条数 | 10 条（同主题，答案有误）；用于演示 Red Teaming 检测效果 |
| Fine-tune 目标模型 | Azure AI Foundry 上的公开基础模型（如 `gpt-4o-mini`，以实际可用为准）|
| 部署后 API 格式 | 与基础模型一致（OpenAI chat completion 格式） |
| 训练文件路径 | `aigoverntrustworthydemo-finetune/aigoverntrustworthydemo-qa-210.jsonl`（上传到 `aigoverntrustworthydemostorage`） |

**训练数据 JSONL 格式示例**：

```jsonl
{"messages": [{"role": "system", "content": "You are an AI governance expert specializing in NIST AI frameworks."}, {"role": "user", "content": "What is the primary purpose of the NIST AI Risk Management Framework?"}, {"role": "assistant", "content": "The NIST AI RMF provides a structured approach to managing risks related to AI systems throughout their lifecycle..."}]}
{"messages": [{"role": "system", "content": "You are an AI governance expert specializing in NIST AI frameworks."}, {"role": "user", "content": "According to NIST AI 600-1, what is prompt injection?"}, {"role": "assistant", "content": "[INTENTIONALLY WRONG - for red teaming demo] Prompt injection is a technique for optimizing AI model performance by injecting structured prompts..."}]}
```

**注意**：故意错误的条目在生成脚本中标记 `"label": "intentionally_wrong"`，在上传训练时需去除此字段；但在 eval 数据集版本中保留，用于 red teaming 验证。

---

#### 4.2.5 API Management

> **✅ 已确认（S4）**：APIM 为全新建设，由**用户在 Portal 手动创建**（新建耗时约 30-45 分钟）。

| 属性 | 值 |
|---|---|
| 资源名 | `AIGovernTrustworthyDemoAPIM` |
| 资源组 | `AIGovernTrustworthyDemoRG` |
| SKU | `Developer`（Demo 环境，无 SLA；需 SLA 升 `Standard`） |
| Location | `canadaeast` |

**📋 用户操作步骤**：
1. 登录 [portal.azure.com](https://portal.azure.com) → 搜索 "API Management" → 创建
2. 资源组：`AIGovernTrustworthyDemoRG`，名称：`AIGovernTrustworthyDemoAPIM`，SKU：Developer
3. 创建完成后，将 Gateway URL 填入 `.env.local.L4` 的 `L4_APIM_ENDPOINT`
4. 在 APIM → Subscriptions 中创建一个 Subscription，将 Key 填入 `L4_APIM_SUBSCRIPTION_KEY`

---

#### 4.2.6 App Service Plan + Web Apps（RAG Service / Tier 1 / Tier 2）

> **✅ 已确认（S6）**：新建 Domain 4 专用 App Service Plan，**由用户在 Portal 手动创建**。Web App 也由用户手动创建。

**App Service Plan**：

| 属性 | 值 |
|---|---|
| Plan 名称 | `AIGovernTrustworthyDemoASP` |
| 资源组 | `AIGovernTrustworthyDemoRG` |
| SKU | `B2`（2 vCPU，3.5GB；POC 够用） |
| OS | Linux |
| Location | `canadaeast` |

**Web Apps**：

| App | 建议资源名 | 环境变量 | APIM 路由前缀 | 运行身份 |
|---|---|---|---|---|
| RAG Service | `AIGovernTrustworthyDemoRAGService` | `L4_RAG_SERVICE_APP_NAME` | `/domain4/rag-service/*` | `L4_RAG_SERVICE_CLIENT_ID` |
| Tier 1 Consumer App | `AIGovernTrustworthyDemoTier1App` | `L4_TIER1_APP_NAME` | `/domain4/tier1/*` | `L4_TIER1_APP_CLIENT_ID` |
| Tier 2 Consumer App | `AIGovernTrustworthyDemoTier2App` | `L4_TIER2_APP_NAME` | `/domain4/tier2/*` | `L4_TIER2_APP_CLIENT_ID` |

**📋 用户操作步骤**：
1. Portal → App Service Plans → 创建 → 资源组 `AIGovernTrustworthyDemoRG`，名称 `AIGovernTrustworthyDemoASP`，SKU B2，Linux
2. Portal → App Services → 分别创建 3 个 Web App，选择 Plan `AIGovernTrustworthyDemoASP`，Runtime Python 3.11
3. 创建后将实际 URL 填入 `.env.local.L4` 的 `L4_RAG_SERVICE_URL`、`L4_TIER1_APP_URL`、`L4_TIER2_APP_URL`

---

#### 4.2.7 VM（Hugging Face 模型）

> **✅ 已确认（S3）**：CPU-only，使用最小可运行量化模型。模型大小不影响演示效果。

| 属性 | 值 |
|---|---|
| 资源名 | `AIGovernTrustworthyDemoVM` |
| OS | Ubuntu 22.04 LTS |
| VM Size | `Standard_D4s_v3`（4 vCPU，16GB RAM，CPU-only） |
| Public IP | 否（仅内网，通过 APIM 代理暴露） |
| Network Security Group | 仅允许 APIM subnet / VNet 内部对 11434 端口的入站 |
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
  --resource-group AIGovernTrustworthyDemoRG \
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
AZ_LOCATION                             # canadaeast
OPENAI_ENDPOINT                         # https://contosoaigovdemo.openai.azure.com/
OPENAI_API_VERSION                      # 2024-12-01-preview
OPENAI_DEPLOYMENT                       # gpt-5.4
APPLICATIONINSIGHTS_CONNECTION_STRING   # （从 .env.local 复制，或替换为 L4 专用实例）
LOG_ANALYTICS_WORKSPACE_NAME            # aiexvddh5zbxgtg
LOG_LEVEL                               # INFO
APP_ENV                                 # local
```

### 5.2 新增的 Domain 4 专用变量

```
# ── 资源组 ──────────────────────────────────────────────────────────────
L4_RESOURCE_GROUP=AIGovernTrustworthyDemoRG

# ── 资源 Tag（Owner 可复用；AI tag 按资源类型区分）──────────────────────
L4_TAG_OWNER=weishi@MngEnvMCAP029189.onmicrosoft.com
L4_TAG_AI_RESOURCE_GROUP=AIGovernTrustworthyDemo-ResourceGroup
L4_TAG_AI_APIM=AIGovernTrustworthyDemo-APIM
L4_TAG_AI_APP_SERVICE_PLAN=AIGovernTrustworthyDemo-AppServicePlan
L4_TAG_AI_RAG_SERVICE=AIGovernTrustworthyDemo-RAGService
L4_TAG_AI_TIER1_APP=AIGovernTrustworthyDemo-Tier1App
L4_TAG_AI_TIER2_APP=AIGovernTrustworthyDemo-Tier2App
L4_TAG_AI_SEARCH=AIGovernTrustworthyDemo-RAGSearch
L4_TAG_AI_STORAGE=AIGovernTrustworthyDemo-Storage
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

# ── Azure AI Foundry ──────────────────────────────────────────────────────
L4_AI_FOUNDRY_HUB_NAME=aigoverndemofoundryhub
L4_AI_FOUNDRY_PROJECT_NAME=aigoverndemofoundryproject
L4_AI_FOUNDRY_PROJECT_ENDPOINT=<to-be-created>     # https://<region>.api.azureml.ms/...

# ── Azure AI Foundry · 模型部署 ────────────────────────────────────────────
L4_FOUNDRY_NATIVE_MODEL_DEPLOYMENT=AIGovernTrustworthyDemoNativeModel
L4_FOUNDRY_NATIVE_MODEL_ENDPOINT=<to-be-created>
L4_FOUNDRY_FINETUNE_MODEL_DEPLOYMENT=AIGovernTrustworthyDemoFineTuneModel
L4_FOUNDRY_FINETUNE_MODEL_ENDPOINT=<to-be-created>

# ── Azure AI Foundry · Agent ───────────────────────────────────────────────
L4_FOUNDRY_AGENT_NAME=AIGovernTrustworthyDemoFoundryAgent
L4_FOUNDRY_AGENT_ID=<to-be-created>

# ── Azure AI Search（RAG Service 使用）────────────────────────────────────
L4_AI_SEARCH_NAME=aigoverntrustworthysearch
L4_AI_SEARCH_ENDPOINT=https://aigoverntrustworthysearch.search.windows.net
L4_AI_SEARCH_INDEX_NAME=aigoverntrustworthydemo-rag-index
L4_AI_SEARCH_ADMIN_KEY=<to-be-created>
L4_AI_SEARCH_QUERY_KEY=<to-be-created>

# ── Storage（fine-tune 数据 + RAG 文档）────────────────────────────────────
L4_STORAGE_ACCOUNT_NAME=aigoverntrustworthydemostorage
L4_STORAGE_CONNECTION_STRING=<to-be-created>
L4_STORAGE_CONTAINER_RAG_DOCS=aigoverntrustworthydemo-rag-docs
L4_STORAGE_CONTAINER_FINETUNE=aigoverntrustworthydemo-finetune

# ── APIM ──────────────────────────────────────────────────────────────────
L4_APIM_NAME=AIGovernTrustworthyDemoAPIM
L4_APIM_ENDPOINT=<to-be-confirmed>               # e.g. https://AIGovernTrustworthyDemoAPIM.azure-api.net
L4_APIM_SUBSCRIPTION_KEY=<to-be-created>

# ── App Services ──────────────────────────────────────────────────────────
L4_APP_SERVICE_PLAN_NAME=AIGovernTrustworthyDemoASP
L4_RAG_SERVICE_APP_NAME=AIGovernTrustworthyDemoRAGService
L4_RAG_SERVICE_URL=<to-be-deployed>              # https://AIGovernTrustworthyDemoRAGService.azurewebsites.net
L4_TIER1_APP_NAME=AIGovernTrustworthyDemoTier1App
L4_TIER1_APP_URL=<to-be-deployed>               # https://AIGovernTrustworthyDemoTier1App.azurewebsites.net
L4_TIER2_APP_NAME=AIGovernTrustworthyDemoTier2App
L4_TIER2_APP_URL=<to-be-deployed>               # https://AIGovernTrustworthyDemoTier2App.azurewebsites.net

# ── VM（Hugging Face 模型）────────────────────────────────────────────────
L4_VM_NAME=AIGovernTrustworthyDemoVM
L4_VM_PRIVATE_IP=<to-be-created>
L4_VM_MODEL_API_PORT=11434
L4_VM_MODEL_APIM_URL=<to-be-configured>         # 通过 APIM 代理后的外部 URL

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

| # | 资源类型 | 资源名 | 资源组 | SKU / 规格 | Tag: AI= | 完成后填入变量 |
|---|---|---|---|---|---|---|
| M1 | 资源组 | `AIGovernTrustworthyDemoRG` | N/A | — | `AIGovernTrustworthyDemo-ResourceGroup` | `L4_RESOURCE_GROUP` |
| M2 | API Management | `AIGovernTrustworthyDemoAPIM` | `AIGovernTrustworthyDemoRG` | Developer，canadaeast | `AIGovernTrustworthyDemo-APIM` | `L4_APIM_ENDPOINT`、`L4_APIM_SUBSCRIPTION_KEY` |
| M3 | App Service Plan | `AIGovernTrustworthyDemoASP` | `AIGovernTrustworthyDemoRG` | B2，Linux，canadaeast | `AIGovernTrustworthyDemo-AppServicePlan` | `L4_APP_SERVICE_PLAN_NAME` |
| M4 | RAG Service Web App | `AIGovernTrustworthyDemoRAGService` | `AIGovernTrustworthyDemoRG` | Python 3.11，使用 M3 | `AIGovernTrustworthyDemo-RAGService` | `L4_RAG_SERVICE_URL` |
| M5 | Tier 1 App Web App | `AIGovernTrustworthyDemoTier1App` | `AIGovernTrustworthyDemoRG` | Python 3.11，使用 M3 | `AIGovernTrustworthyDemo-Tier1App` | `L4_TIER1_APP_URL` |
| M6 | Tier 2 App Web App | `AIGovernTrustworthyDemoTier2App` | `AIGovernTrustworthyDemoRG` | Python 3.11，使用 M3 | `AIGovernTrustworthyDemo-Tier2App` | `L4_TIER2_APP_URL` |
| M7 | Copilot Studio Agent | `AIGovernTrustworthyDemoCopilotStudioAgent` | Copilot Studio（Power Platform） | — | N/A | `L4_COPILOT_STUDIO_BOT_ID`、`L4_COPILOT_STUDIO_DIRECTLINE_SECRET` |

> ⚠️ **APIM 创建耗时约 30-45 分钟**，建议优先开始。创建时选择 Developer SKU、canadaeast、Publisher 填自己邮箱。

---

### 6B. 脚本自动创建资源（通过 SPN `AZ_DEPLOY_CLIENT_ID` 执行）

| # | 资源类型 | 资源名 | 资源组 | 工具 / 命令 | Tag: AI= | 完成后填入变量 |
|---|---|---|---|---|---|---|
| A1 | SPN | `AIGovernTrustworthyDemoRAGServiceSPN` | N/A（AAD 对象） | `az ad sp create-for-rbac` | N/A | `L4_RAG_SERVICE_CLIENT_ID`、`L4_RAG_SERVICE_CLIENT_SECRET` |
| A2 | SPN | `AIGovernTrustworthyDemoTier1AppSPN` | N/A（AAD 对象） | `az ad sp create-for-rbac` | N/A | `L4_TIER1_APP_CLIENT_ID`、`L4_TIER1_APP_CLIENT_SECRET` |
| A3 | SPN | `AIGovernTrustworthyDemoTier2AppSPN` | N/A（AAD 对象） | `az ad sp create-for-rbac` | N/A | `L4_TIER2_APP_CLIENT_ID`、`L4_TIER2_APP_CLIENT_SECRET` |
| A4 | SPN | `AIGovernTrustworthyDemoEvaluationRunnerSPN` | N/A（AAD 对象） | `az ad sp create-for-rbac` | N/A | `L4_EVALUATION_RUNNER_CLIENT_ID`、`L4_EVALUATION_RUNNER_CLIENT_SECRET` |
| A5 | SPN | `AIGovernTrustworthyDemoPyRITRunnerSPN` | N/A（AAD 对象） | `az ad sp create-for-rbac` | N/A | `L4_PYRIT_RUNNER_CLIENT_ID`、`L4_PYRIT_RUNNER_CLIENT_SECRET` |
| A6 | Azure AI Search | `aigoverntrustworthysearch` | `AIGovernTrustworthyDemoRG` | `az search service create` | `AIGovernTrustworthyDemo-RAGSearch` | `L4_AI_SEARCH_ADMIN_KEY`、`L4_AI_SEARCH_QUERY_KEY` |
| A7 | AI Search 索引 | `aigoverntrustworthydemo-rag-index` | — | Python ingestion 脚本 | N/A | `L4_AI_SEARCH_INDEX_NAME`（已知） |
| A8 | Storage Account | `aigoverntrustworthydemostorage` | `AIGovernTrustworthyDemoRG` | `az storage account create` | `AIGovernTrustworthyDemo-Storage` | `L4_STORAGE_CONNECTION_STRING` |
| A9 | Storage Container | `aigoverntrustworthydemo-rag-docs` | — | `az storage container create` | N/A | — |
| A10 | Storage Container | `aigoverntrustworthydemo-finetune` | — | `az storage container create` | N/A | — |
| A11 | Azure VM | `AIGovernTrustworthyDemoVM` | `AIGovernTrustworthyDemoRG` | `az vm create` | `AIGovernTrustworthyDemo-HuggingFaceVM` | `L4_VM_PRIVATE_IP` |
| A12 | Network Security Group | `AIGovernTrustworthyDemoVMNSG` | `AIGovernTrustworthyDemoRG` | `az network nsg create` | `AIGovernTrustworthyDemo-HuggingFaceVM` | — |
| A13 | Azure AI Foundry 原生模型 Deployment | `AIGovernTrustworthyDemoNativeModel` | `aigoverndemofoundryproject` | Foundry Portal / SDK | N/A | `L4_FOUNDRY_NATIVE_MODEL_DEPLOYMENT` |
| A14 | Azure AI Foundry Fine-tune Deployment | `AIGovernTrustworthyDemoFineTuneModel` | `aigoverndemofoundryproject` | Foundry Portal / SDK | N/A | `L4_FOUNDRY_FINETUNE_MODEL_DEPLOYMENT` |
| A15 | Azure AI Foundry Agent | `AIGovernTrustworthyDemoFoundryAgent` | `aigoverndemofoundryproject` | Foundry Portal / SDK | N/A | `L4_FOUNDRY_AGENT_ID` |
| A16 | VM 模型安装 | Phi-3-mini via ollama | VM 内部 | SSH + 初始化脚本 | N/A | — |
| A17 | RBAC 角色授权 | Deploy SPN + 各应用运行时 SPN | 各资源作用域 | `az role assignment create` | N/A | — |

---

### 6C. 复用现有资源（无需创建，已确认）

| 资源类型 | 资源名 | 资源组 | 已填入变量 |
|---|---|---|---|
| Azure OpenAI Resource | `contosoaigovdemo` | `AOAIRG` | `OPENAI_ENDPOINT`、`OPENAI_DEPLOYMENT` |
| AI Foundry Hub | `aigoverndemofoundryhub` | `AOAIRG` | `L4_AI_FOUNDRY_HUB_NAME` |
| AI Foundry Project | `aigoverndemofoundryproject` | `AOAIRG` | `L4_AI_FOUNDRY_PROJECT_NAME` |
| Application Insights | `appinsights` | `AIGovernDemoRG` | `APPLICATIONINSIGHTS_CONNECTION_STRING` |
| Log Analytics Workspace | `aiexvddh5zbxgtg` | `AIGovernDemoRG` | `LOG_ANALYTICS_WORKSPACE_ID` |


---

## 7. 已知停止点汇总

以下事项需要在进入对应步骤之前确认，避免重建成本：

| # | 决策内容 | 涉及步骤 | 状态 |
|---|---|---|---|
| S1 | AI Search 索引 schema 已确认：8 字段 + 1536 维向量，3 类内容（standard/news/product_solution），Embedding 用 text-embedding-3-small | 步骤 2（RAG Service） | ✅ 已确认 |
| S2 | Fine-tune：JSONL chat completion 格式，210 条（200 正确 + 10 故意错误），来源 NIST AI RMF + NIST AI 600-1，目标模型 gpt-4o-mini 或同类可用模型 | 步骤 4（fine-tune 模型） | ✅ 已确认 |
| S3 | VM CPU-only，Standard_D4s_v3，使用 Phi-3-mini-4k-instruct（Q4_K_M GGUF，~2.2GB），通过 ollama 暴露 OpenAI 兼容 API | 步骤 5（VM 模型） | ✅ 已确认 |
| S4 | APIM 全新建设，由用户在 Portal 手动创建（`AIGovernTrustworthyDemoAPIM`，Developer SKU） | 步骤 1（基础设施） | ✅ 已确认 |
| S5 | App Insights 复用现有实例（`APPLICATIONINSIGHTS_CONNECTION_STRING`） | 步骤 1（基础设施） | ✅ 已确认 |
| S6 | 新建 App Service Plan（`AIGovernTrustworthyDemoASP`，B2，Linux）；Web App 由用户在 Portal 手动创建 | 步骤 2/9/10 | ✅ 已确认 |
| S7 | Foundry Hub / Project 复用现有实例，不新建 | 步骤 3/4/7 | ✅ 已确认 |

---

## 8. 资源命名结果

以下为当前建议采用的完整命名结果，已区分复用项与新建项。这里不再保留命名模式或示例。

### 8.1 复用资源命名结果

| 类型 | 名称 |
|---|---|
| Deploy SPN | `devdeployspn` |
| Azure OpenAI Resource | `contosoaigovdemo` |
| Azure AI Foundry Hub | `aigoverndemofoundryhub` |
| Azure AI Foundry Project | `aigoverndemofoundryproject` |
| Application Insights | `appinsights` |
| Log Analytics Workspace | `aiexvddh5zbxgtg` |
| ACR | `AIGovernDemoACR` |


### 8.2 新建资源命名结果

| 类型 | 名称 |
|---|---|
| 资源组 | `AIGovernTrustworthyDemoRG` |
| RAG Service 运行时 SPN | `AIGovernTrustworthyDemoRAGServiceSPN` |
| Tier 1 App 运行时 SPN | `AIGovernTrustworthyDemoTier1AppSPN` |
| Tier 2 App 运行时 SPN | `AIGovernTrustworthyDemoTier2AppSPN` |
| Evaluation Runner 运行时 SPN | `AIGovernTrustworthyDemoEvaluationRunnerSPN` |
| PyRIT Runner 运行时 SPN | `AIGovernTrustworthyDemoPyRITRunnerSPN` |
| Azure AI Search | `aigoverntrustworthysearch` |
| AI Search 索引 | `aigoverntrustworthydemo-rag-index` |
| Storage Account | `aigoverntrustworthydemostorage` |
| Storage Container | `aigoverntrustworthydemo-rag-docs` |
| Storage Container | `aigoverntrustworthydemo-finetune` |
| API Management | `AIGovernTrustworthyDemoAPIM` |
| App Service Plan | `AIGovernTrustworthyDemoASP` |
| RAG Service Web App | `AIGovernTrustworthyDemoRAGService` |
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
| DD-001 | RAG 知识库覆盖 AI Security 标准 + 新闻 + 微软/合作伙伴产品方案 | 与 AIGovernApp 的 Governance 定位高度相关；内容可自动更新 | 2026-05 |
| DD-002 | RAG Embedding 使用 `text-embedding-3-small`（1536 维） | 现有 Azure OpenAI 端点已支持，无需新建资源；维度足够 POC 使用 | 2026-05 |
| DD-003 | Fine-tune 使用 210 条 Q&A（200 正 + 10 故意错误） | 故意错误条目用于演示 Red Teaming 检测能力（模型可能"自信地答错"） | 2026-05 |
| DD-004 | Fine-tune 数据来源限定 NIST AI RMF + NIST AI 600-1 | POC 阶段最小化数据范围；两份文档都已在仓库中有引用 | 2026-05 |
| DD-005 | VM 使用 Phi-3-mini-4k-instruct（Q4_K_M GGUF）+ ollama | CPU-only，最小资源消耗；MIT 许可；ollama 单命令部署，OpenAI 兼容 API；模型质量足够演示 | 2026-05 |
| DD-006 | APIM / Web App / App Service Plan 由用户手动在 Portal 创建 | 降低自动化风险；用户可控命名；创建后通过 `.env.local.L4` 记录参数 | 2026-05 |
| DD-007 | Foundry Hub / Project 复用现有 | 避免重复创建资源；现有环境已有部署配额和关联资源 | 2026-05 |
| DD-008 | App Insights 复用现有 | POC 阶段日志量小，无需隔离；减少资源数量 | 2026-05 |
| DD-009 | 所有关键参数名写入 `.env.local.L4` | 支持后续脚本自动化；用户可手动修改参数名 | 2026-05 |
