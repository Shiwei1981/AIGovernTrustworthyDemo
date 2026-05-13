# Domain 4 · RAG Governance Service · 组件设计

## 1. 文档定位

本文件是 `design-L2-domain-4-prerequisites.md` 步骤 2（建立 RAG 服务）的专用 L3 组件设计文档，涵盖：

- 设计目标与边界
- 技术路线决策记录
- 前置条件与资源依赖
- 知识库内容规划与目录结构
- 服务架构与部署方案
- Observability 接入边界与 App Insights 集成范围
- 开发产物清单

**关联文档**：

| 文档 | 关系 |
|---|---|
| `design-L2-domain-4-prerequisites.md` | 上级步骤列表，步骤 2 的总览入口 |
| `design-L2-domain-4-prerequisites-lowleveldesign.md` | 资源命名、SPN 权限、环境变量、部署资源清单 |
| `design-L3-domain-4-shared-observability-component.md` | Observability 组件设计（供调用方参考） |

---

## 2. 技术路线决策

### 2.1 选定方案：Azure AI Foundry Agent with File Search

RAG Governance Service 使用 **Azure AI Foundry Agent + 内置 File Search 工具**作为技术实现。

**决策理由**：

- 本步骤的**核心目的是验证对 RAG 质量和安全的治理**，而不是关注 RAG 运行在什么容器或基础设施上
- Foundry Agent with File Search 将文档上传、向量化、检索、引用全部托管，无需自建索引 pipeline
- 不需要 Azure AI Search、不需要自建 embedding pipeline、不需要 Container Apps 或 App Service
- Foundry Agent 暴露标准 HTTP endpoint，APIM 可直接代理
- Foundry 原生 tracing 自动覆盖 agent 内部的 file search + LLM generate spans

### 2.2 治理身份（`target_type`）不受底层技术影响

> **重要原则**：RAG Service 的治理身份是 `rag_service`，不是 `foundry_agent`。底层使用 Foundry Agent 是实现细节，治理分类取决于服务的**功能角色**（知识检索问答服务），而非部署平台。

| 属性 | 值 | 说明 |
|---|---|---|
| `target_type` | `rag_service` | RAG 服务的治理分类，与步骤 7 的 Foundry Agent 严格分开 |
| `target_id` | `AIGovernTrustworthyDemoRAGService` | 该 RAG 服务在 Domain 4 目标清单中的唯一标识 |
| `service_name`（OTel） | `AIGovernTrustworthyDemo.RAGService` | App Insights 中的服务名 |

步骤 7 的 Foundry Agent（TBD）将独立使用 `target_type = foundry_agent`，两者在 Domain 4 报表中分开展示，不混合。

### 2.3 方案对比（决策备忘）

| 方案 | 技术 | 是否选用 | 排除原因 |
|---|---|---|---|
| 方案 A | 自建 RAG API + App Service | 否 | 需要 App Service Plan + 自建索引 pipeline，复杂度高于目标 |
| 方案 B | Prompt Flow Managed Endpoint | 否 | 需要学习 Prompt Flow DAG 格式，增加开发成本 |
| **方案 C** | **Foundry Agent with File Search** | **✅ 选用** | 托管最简，聚焦治理验证目标 |
| 方案 D | Container Apps | 否 | 不必要的基础设施，已被方案 C 替代 |

---

## 3. 设计目标与边界

### 3.1 核心目标

RAG Governance Service 的**首要目的**是成为 Domain 4 的一个**可治理、可评估的 AI 服务目标（target）**，用于验证以下治理能力：

- **Groundedness / Citation Rate**：Foundry Agent 返回的引用文件片段，作为 citation 质量依据
- **Safety Evaluator 覆盖**：RAG 服务作为 `target_type = rag_service` 可被 Foundry Evaluation 工具评估
- **Red Teaming 目标**：RAG endpoint（经 APIM）可被 PyRIT 进行攻击测试
- **Model Identity Capture**：Foundry tracing 自动记录模型名称和版本
- **Evidence Chain**：APIM tracing + Foundry tracing 共同构成调用链证据

RAG 作为一个**提供 AI Governance 知识问答能力的后端服务**，不包含任何用户界面（UI）或消费端应用层。消费端应用由步骤 9（Tier 1 Consumer App）负责。

### 3.2 知识库主题

RAG Service 的知识库聚焦于 **AI Governance 行业标准知识**，由用户提供 PDF 文件，包括但不限于：

- NIST AI 600-1（Generative AI）
- NIST AI RMF（AI Risk Management Framework）
- ISO/IEC 42001（AI Management Systems）
- OWASP LLM Top 10
- EU AI Act 关键条款摘要
- 其他 AI Governance 相关行业标准文档

知识库设计只服务于治理演示目的，不追求生产级知识覆盖。

### 3.3 边界说明

| 边界 | 说明 |
|---|---|
| **不包含** | 用户界面、消费端 App、Tier 1 调用逻辑 |
| **不包含** | Azure AI Search（Foundry File Search 内置向量存储，不需要外部 Search 资源） |
| **不包含** | 独立的 embedding pipeline（Foundry 托管，自动处理） |
| **不包含** | APIM 的创建和配置（APIM 是本步骤的前置条件） |
| **不包含** | Evaluation 结果事件写入（由 evaluation-runner 负责，步骤 13） |
| **不包含** | RAG 自身写 shared-observability（见 §6 说明） |
| **包含** | Foundry Agent 创建与 File Search 工具配置 |
| **包含** | PDF 知识库上传到 Foundry Agent vector store |
| **包含** | APIM 后端配置（将 Foundry Agent endpoint 挂到 APIM） |

---

## 4. 前置条件

在开始本步骤之前，以下资源和配置**必须已存在**：

| 前置项 | 资源名 / 变量 | 状态检查 |
|---|---|---|
| **Azure OpenAI Service（Domain 4 专用）** | `AIGovernTrustworthyAOAI`（`L4_AOAI_ENDPOINT`） | **硬前置条件**：RAG Agent 在此资源下创建；需已在 Portal 创建并连接到 Foundry Hub（LLD §4.2.3） |
| **APIM 实例** | `AIGovernTrustworthyDemoAPIM`（`L4_APIM_GATEWAY_URL`） | **硬前置条件**：APIM 不存在时 RAG endpoint 无法进入治理链路；需优先在 Portal 创建（LLD §4.2.8） |
| AI Foundry Hub + Project | `aigoverndemoaihub` / `aigovenaihubproject` | 已复用现有（LLD §4.1） |
| LLM 生成模型 Deployment | `L4_FOUNDRY_NATIVE_MODEL_DEPLOYMENT`（在 `AIGovernTrustworthyAOAI` 下） | 在新 AOAI 资源下创建 `AIGovernTrustworthyDemoNativeModel` deployment |
| Application Insights | `APPLICATIONINSIGHTS_CONNECTION_STRING` | 复用现有（LLD §4.2.1） |
| RAG Service 运行时 SPN | `L4_RAG_SERVICE_CLIENT_ID` / `L4_RAG_SERVICE_CLIENT_SECRET` | 需已在 LLD §3.2.1 脚本中创建（用于调用 Foundry Agent） |

> ⚠️ **Azure AI Search 不再是前置条件**：方案 C 使用 Foundry 内置 File Search，不依赖外部 Azure AI Search 资源。LLD §4.2.3 中的 `aigoverntrustworthysearch` 资源可用于其他步骤，步骤 2 不使用。

---

## 5. 知识库管理

### 5.1 本地 PDF 目录

原始知识材料（PDF 文件）统一放置在：

```
apps/rag-service/knowledge-base/
```

**目录约定**：

- PDF 文件**不提交到 Git**（通过 `.gitignore` 排除）
- 用户将 AI Governance 相关 PDF 放入此目录
- 上传脚本从此目录读取所有 PDF，逐个上传到 Foundry Agent vector store
- 新增文件后重新运行上传脚本即可更新知识库

**当前已有文件（✅ 用户已放入）**：

| 文件名 | 内容 |
|---|---|
| `NIST.AI.100-1.pdf` | NIST AI RMF 1.0（AI Risk Management Framework） |
| `NIST.AI.600-1.pdf` | NIST AI 600-1（Generative AI 专项） |
| `OJ_L_202401689_EN_TXT.pdf` | EU AI Act（欧盟 AI 法规正式文本） |
| `sgmodelaigovframework2.pdf` | Singapore Model AI Governance Framework |
| `OWASP-Top-10-for-LLMs-v2025.pdf` | OWASP LLM Top 10 2025 |

### 5.2 Foundry Agent File Search 工作原理

Foundry Agent with File Search 接受 PDF 文件上传后：

1. 自动完成文档解析（含 OCR）
2. 自动完成文本切块
3. 自动完成 embedding（使用 Foundry 内置 embedding 模型）
4. 存储到 Foundry 内置 vector store（与 Agent 绑定）
5. 在对话时自动执行 retrieve → generate，并在响应中附带 file citations

上传工具：Foundry SDK（`azure-ai-projects` Python SDK）或 Portal UI。

### 5.3 Citation 格式说明

Foundry Agent File Search 返回的 citation 格式为 Foundry 内置引用注释（file annotation），格式受 Foundry 平台控制，**不能自定义字段**（如 page_number、chunk_index）。

可获得的 citation 信息：

| 字段 | 可用性 |
|---|---|
| 引用文件名（上传的 PDF 文件名） | ✅ |
| 引用片段文本 | ✅ |
| 文件 ID（Foundry vector store file ID） | ✅ |
| 页码 | ❌（Foundry 不暴露） |
| 精确 chunk index | ❌ |

> **已接受的限制**：citation 格式有限是选择方案 C 时已知的权衡。Domain 4 的 `Source Attribution Rate` 指标基于"是否有 citation"来计算，不要求精确页码。

---

## 6. 服务架构与 Observability 设计

### 6.1 Foundry Agents API 调用模式

Foundry Agent 使用 **OpenAI Assistants 兼容的有状态 API**（threads / messages / runs），而非简单的 request-response。

每次问答的完整调用流程：

```
步骤 1  创建 Thread（对话会话）
        POST /threads
        → thread_id

步骤 2  写入用户消息
        POST /threads/{thread_id}/messages
        body: { role: "user", content: "What does NIST AI 600-1 say about..." }

步骤 3  创建 Run（触发 Agent 执行）
        POST /threads/{thread_id}/runs
        body: { assistant_id: L4_RAG_AGENT_ID }
        → run_id

步骤 4  轮询 Run 状态直到 "completed"
        GET /threads/{thread_id}/runs/{run_id}
        → status: "queued" | "in_progress" | "completed" | "failed"

步骤 5  读取回答（含 file annotations / citations）
        GET /threads/{thread_id}/messages
        → messages[0].content[0].text.value        ← 回答文本
        → messages[0].content[0].text.annotations  ← 引用列表（file_citation）
```

**Python SDK 等价调用**（`azure-ai-projects`）：

```python
from azure.ai.projects import AIProjectClient
from azure.identity import ClientSecretCredential

client = AIProjectClient(
    endpoint=L4_AI_FOUNDRY_PROJECT_ENDPOINT,
    credential=ClientSecretCredential(TENANT_ID, CLIENT_ID, CLIENT_SECRET)
)
thread = client.agents.create_thread()
client.agents.create_message(thread.id, role="user", content=question)
run = client.agents.create_and_process_run(thread.id, assistant_id=L4_RAG_AGENT_ID)
messages = client.agents.list_messages(thread.id)
answer = messages.data[0].content[0].text.value
citations = messages.data[0].content[0].text.annotations
```

### 6.2 调用链路

```
评估工具 / Tier 1 App（步骤 9）
        │
        ▼
  APIM（AIGovernTrustworthyDemoAPIM）
        │  ← APIM gateway tracing → App Insights
        ▼
  Azure AI Foundry Agents API
  （project endpoint / agents / threads / runs）
        │  ← Foundry tracing（自动）→ App Insights
        │
        ├─ [file search tool call] → Foundry 内置 vector store（5 个 PDF）
        │
        └─ [LLM generate] → Foundry 绑定的 LLM deployment
                └─ 返回 answer text + file_citation annotations
```

### 6.3 Observability 分层

| 层 | 负责方 | 覆盖内容 |
|---|---|---|
| APIM gateway tracing | APIM（自动） | HTTP 请求/响应头、延迟、状态码 |
| Foundry tracing | Foundry 平台（自动） | file search span、LLM generate span、model identity |
| App Insights 统一查询 | 平台自动聚合 | APIM + Foundry trace 可在同一 App Insights 工作区查询 |

**RAG Service 自身不写 `shared-observability` evidence**，原因如下：

- Foundry Agent 是托管服务，代码层不可直接插桩
- Foundry tracing 已自动捕获 model identity（`model_name`、`model_version`）和 span 信息
- APIM tracing 已覆盖 HTTP 层证据
- `AIGovernTrustworthyLLMEvidence` 事件由**调用方**（Tier 1 App、evaluation-runner）在调用 RAG endpoint 后写入，`target_type = rag_service`，`target_id = AIGovernTrustworthyDemoRAGService`

### 6.4 `citations_count` 字段处理

`shared-observability.log_llm_call()` 的 `citations_count` 字段，由调用方（Tier 1 / evaluation-runner）从 Foundry Agent 响应体中解析 `text.annotations` 数量后填入。

---

## 7. APIM 接入设计

### 7.1 接入方式

Foundry Agents API 是**有状态 API**（threads / messages / runs 三步交互），不是简单的 POST /query。APIM 代理的是各独立 REST hop，不是整体会话。

接入方式：APIM 在 Foundry Project endpoint 的上层设置 pass-through 代理，对所有 `/agents/*`、`/threads/*` 路径的调用统一做 gateway tracing。

```
调用方
  │  POST https://<APIM>/rag/threads               ← 创建 thread
  │  POST https://<APIM>/rag/threads/{id}/messages  ← 写消息
  │  POST https://<APIM>/rag/threads/{id}/runs      ← 触发执行
  │  GET  https://<APIM>/rag/threads/{id}/runs/{r}  ← 查询状态
  │  GET  https://<APIM>/rag/threads/{id}/messages  ← 读回答
  ▼
APIM backend → L4_AI_FOUNDRY_PROJECT_ENDPOINT
```

### 7.2 APIM 配置要点

| 配置项 | 值 |
|---|---|
| APIM API 名称 | `rag-service` |
| API path prefix | `/rag` |
| Backend URL | `L4_AI_FOUNDRY_PROJECT_ENDPOINT`（Foundry Project endpoint） |
| 认证 | APIM Managed Identity 持有 `Azure AI User` 角色，或在 policy 中注入 Bearer token |
| Diagnostics | 开启 `applicationInsights` logger，连接 `APPLICATIONINSIGHTS_CONNECTION_STRING` |
| APIM policy | 透传 `traceparent` header；注入 `api-version` query param |

> APIM 配置文件存放于 `infra/apim/rag-service-api.xml`（待创建）。

### 7.3 Evaluation / Red Teaming 的调用方式

| 场景 | 调用方式 | APIM 是否经过 |
|---|---|---|
| 本地开发验证（`test_query.py`） | 直接使用 `azure-ai-projects` SDK，不经 APIM | 否 |
| Foundry Evaluation（步骤 13） | 通过 Foundry Evaluation SDK，可直连 Agent | 否（Foundry 内部） |
| PyRIT Red Teaming（步骤 15） | 经 APIM 的 HTTP endpoint 调用（需实现 thread/run 流程的封装） | 是 |
| Tier 1 App 调用（步骤 9） | 经 APIM，使用 SDK 调用 Agents API | 是 |

---

## 8. 环境变量

步骤 2 相关环境变量（来自 `.env.local.L4`）：

| 变量名 | 用途 |
|---|---|
| `L4_RAG_SERVICE_CLIENT_ID` | 调用 Foundry Agent 的运行时 SPN Client ID |
| `L4_RAG_SERVICE_CLIENT_SECRET` | 运行时 SPN Secret |
| `AZURE_TENANT_ID` | 租户 ID |
| `L4_AI_FOUNDRY_PROJECT_ENDPOINT` | Foundry Project endpoint（用于 Foundry SDK 调用） |
| `L4_AI_FOUNDRY_PROJECT_NAME` | `aigovenaihubproject` |
| `L4_FOUNDRY_NATIVE_MODEL_DEPLOYMENT` | RAG Agent 绑定的 LLM deployment 名 |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | App Insights 连接串（用于验证 tracing 可查询） |
| `L4_APIM_GATEWAY_URL` | APIM gateway URL（RAG endpoint 经 APIM 暴露后的地址） |
| `L4_RAG_SERVICE_URL` | RAG Service 最终对外 URL（经 APIM，填入后供其他步骤使用） |
| `L4_RAG_AGENT_ID` | 创建后的 Foundry Agent ID（新增变量，待填入） |

> `L4_RAG_AGENT_ID` 是本步骤新增的变量，需在 Foundry Agent 创建后写入 `.env.local.L4`。

---

## 9. 开发产物清单

| 产物 | 路径 | 说明 |
|---|---|---|
| 知识库 PDF 目录 | `apps/rag-service/knowledge-base/` | 存放 AI Governance PDF 文件（不提交到 Git） |
| PDF 上传脚本 | `apps/rag-service/scripts/upload_knowledge.py` | 将 knowledge-base/ 下的 PDF 上传到 Foundry Agent vector store |
| Agent 创建脚本 | `apps/rag-service/scripts/create_agent.py` | 创建 Foundry Agent with File Search，记录 Agent ID |
| Agent 调用验证脚本 | `apps/rag-service/scripts/test_query.py` | 直接调用 Foundry Agent endpoint，验证问答与 citation 返回 |
| APIM API 配置 | `infra/apim/rag-service-api.xml` | APIM policy / backend 定义，backend 指向 Foundry Agent endpoint |
| APIM 调用验证脚本 | `apps/rag-service/scripts/test_via_apim.py` | 经 APIM 调用 RAG，验证 APIM tracing 进入 App Insights |

---

## 10. 实施顺序

1. **确认前置条件**：确认 Foundry Project 可访问、LLM deployment（步骤 3）存在；APIM 可在 Agent 就绪后并行建立
2. ~~**建立知识库目录**~~：✅ 已完成（5 个 PDF 已放入 `apps/rag-service/knowledge-base/`）
3. **创建 Foundry Agent**：运行 `create_agent.py`，绑定 LLM deployment，创建 Agent with File Search，记录 `L4_RAG_AGENT_ID`
4. **上传知识库**：运行 `upload_knowledge.py`，将 5 个 PDF 上传到 Agent vector store，等待 vector store 处于 `completed` 状态
5. **本地验证问答**：运行 `test_query.py`，确认 Agent 能正确回答 AI Governance 问题并返回 file citations
6. **APIM 接入**：创建 APIM 实例（M4），配置 `infra/apim/rag-service-api.xml`，backend 指向 Foundry Project endpoint，开启 App Insights diagnostics
7. **验证 APIM 链路**：运行 `test_via_apim.py`，确认经 APIM 调用成功，APIM tracing 进入 App Insights
8. **记录 target registry 条目**：将 RAG Service 以 `target_type=rag_service` 写入治理目标清单，填入 `L4_RAG_SERVICE_URL`（经 APIM 的 `/rag` 路径）

---

## 11. 风险与未决项

| 风险 / 未决项 | 影响 | 缓解措施 |
|---|---|---|
| APIM 尚未创建（M4 待创建） | RAG endpoint 无法进入治理链路 | 先完成 Agent 创建和 PDF 上传验证，APIM 就绪后再接入 |
| Foundry Agent 创建需要 `Azure AI Developer` 角色 | LLD §3.1.1 中已列出，需确认部署 SPN 已获得该权限 | 运行前用 `az role assignment list` 验证 |
| LLM deployment（步骤 3）尚未完成 | Agent 创建后无法执行 generate | 可先创建 Agent、上传文件；绑定 LLM deployment 等步骤 3 后完成 |
| Foundry Agent endpoint 格式与 APIM backend 配置兼容性 | APIM 代理 Foundry `threads/runs` API 可能需要 session-aware policy | 先用直连验证，再逐步接入 APIM |
| Citation 格式受限（无页码） | `Source Attribution Rate` 指标只能统计 citation 存在性，无法精确定位 | 已在方案选择时接受此限制 |
| `L4_RAG_AGENT_ID` 变量未在 LLD 中预定义 | LLD 环境变量清单不完整 | 需同步更新 LLD §5.2 新增此变量 |
