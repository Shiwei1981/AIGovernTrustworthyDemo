# Domain 4 · RAG Governance Service · 组件设计

## 1. 文档定位

本文件是 `design-L2-domain-4-prerequisites.md` 步骤 2（建立 RAG 服务）的专用 L3 组件设计文档，当前记录的**批准方案**为：

- Azure Web App 运行形态
- 轻量级代码式 RAG（不默认引入 embedding / vector store / Azure AI Search）
- APIM `/rag` 统一入口
- `shared_observability` + Blob archive + App Insights 证据链

**关联文档**：

| 文档 | 关系 |
|---|---|
| `design-L2-domain-4-prerequisites.md` | 上级步骤列表，步骤 2 的总览入口 |
| `design-L2-domain-4-prerequisites-lowleveldesign.md` | 资源命名、身份权限、环境变量、部署资源清单 |
| `design-L3-domain-4-shared-observability-component.md` | `log_llm_call()` 与 Blob archive 证据格式 |
| `design-L3-domain-4-apim.md` | APIM `/rag` 前端与 RAG Web App 后端接入设计 |

---

## 2. 技术路线决策

### 2.1 选定方案：Azure Web App + 代码式轻量级 RAG

RAG Governance Service 使用 **Azure Web App** 作为运行形态，部署到现有 App Service Plan **`AIGovernDemoASP`**。检索层优先采用**代码切块 + 进程内轻量级 lexical retrieval**。

**决策理由**：

- 避免 Hosted Agent 的预览限制与区域阻塞。
- 不新增 ACR、Hosted Agent、Foundry vector store、Azure AI Search 等步骤 2 非必需资源。
- 符合“尽量轻量级、减少依赖项”的当前要求。
- 仍可在真实模型调用处写入 Blob evidence，并保留 `response_id`、`model_name`、`model_version`、`citations_count`。
- RAG 服务仍可经 APIM 暴露，继续作为 Evaluation / Red Teaming 的受管目标。

### 2.2 已排除方案

| 方案 | 是否采用 | 排除原因 |
|---|---|---|
| Microsoft Foundry Hosted Agent | 否 | 当前区域不支持，且会增加 ACR / 平台依赖 |
| Foundry 原生 file_search / vector store | 否（默认路径） | 需要额外平台依赖，不符合当前“轻量化优先”原则 |
| Azure AI Search-first RAG | 否（fallback） | 可控性强，但当前不是最小依赖方案 |
| embedding + 自建 vector DB | 否（默认路径） | 需要新增 embedding 资源或更多代码/运维复杂度；如启用需先征得用户同意 |

### 2.3 治理身份（`target_type`）不受底层技术影响

> **重要原则**：RAG Service 的治理身份是 `rag_service`，不是 `foundry_agent`。底层改为 Web App 不影响治理分类。

| 属性 | 值 | 说明 |
|---|---|---|
| `target_type` | `rag_service` | RAG 服务的治理分类，与步骤 7 的普通 Foundry Agent 分开 |
| `target_id` | `AIGovernTrustworthyDemoRAGService` | Domain 4 目标清单中的唯一标识 |
| `service_name`（OTel） | `AIGovernTrustworthyDemo.RAGService` | App Insights / Blob evidence 中的服务名 |

---

## 3. 设计目标与边界

### 3.1 核心目标

RAG Governance Service 的首要目的是成为 Domain 4 的一个可治理、可评估的 AI 服务目标，用于验证：

- **Groundedness / Citation Rate**：RAG 返回的引用信息作为 citation 质量依据。
- **Safety Evaluator 覆盖**：RAG 服务作为 `target_type = rag_service` 可被 Evaluation 工具评估。
- **Red Teaming 目标**：RAG endpoint（经 APIM）可被 PyRIT 进行攻击测试。
- **Model Identity Capture**：Web App 内部调用模型时写入 `model_name` / `model_version`。
- **Evidence Chain**：APIM diagnostics + Web App telemetry + Blob evidence 共同构成证据链。

RAG 作为 AI Governance 知识问答后端服务，不包含用户界面或消费端应用层。消费端应用由步骤 9（Tier 1 Consumer App）负责。

### 3.2 知识库主题

RAG Service 的知识库聚焦于 **AI Governance 行业标准知识**，由用户提供 PDF 文件，包括但不限于：

- NIST AI 600-1（Generative AI）
- NIST AI RMF（AI Risk Management Framework）
- OWASP LLM Top 10
- EU AI Act
- Singapore Model AI Governance Framework

### 3.3 日志边界

Blob evidence 沿用 `shared-observability` 既有格式，仅关注 LLM 调用证据：

| 内容 | 是否写入 Blob evidence |
|---|---|
| LLM input / request messages | 是 |
| LLM output / response / citations | 是 |
| LLM error / provider error body（如 SDK 暴露） | 是 |
| `response_id`、`model_name`、`model_version`、`citations_count` | 是 |
| 命中的 chunk 文本正文 | 否（metadata 只保留来源摘要） |
| 内存检索实现细节 / 中间评分 | 否 |

---

## 4. 前置条件

| 前置项 | 设计要求 |
|---|---|
| App Service Plan | **复用现有**：`AIGovernDemoASP`（`AIGovernDemoRG`） |
| RAG Web App | **待创建**：`AIGovernTrustworthyRAGApp`（`AIGovernTrustworthyRG`） |
| RAG 运行时身份 | 使用现有 `L4_RAG_SERVICE_CLIENT_ID` / `L4_RAG_SERVICE_CLIENT_SECRET` |
| Model deployment | `AIGovernTrustworthyDemoNativeModel` |
| Observability Blob Archive | `aigoverntrustworthysa` / `ai-invocation-archive` |
| Application Insights | 复用 `APPLICATIONINSIGHTS_CONNECTION_STRING` |
| APIM | `/rag` 统一入口，后端指向 RAG Web App |
| 知识材料 | `apps/rag-service/knowledge-base/` 下的 AI Governance PDF |

**停止点**：如实现中确认需要新增 embedding deployment、vector store、Azure AI Search 或其他额外云资源，必须先征得用户同意。

---

## 5. 知识库管理

### 5.1 本地 PDF 目录

原始知识材料统一放置在：

```text
apps/rag-service/knowledge-base/
```

PDF 文件不提交到 Git。RAG Web App 启动时从该目录读取 PDF，完成解析与索引构建。

### 5.2 默认检索方式

当前默认采用**代码式轻量级检索**：

1. 读取 PDF 文本。
2. 按固定规则切块（例如字符窗口 + 适度 overlap）。
3. 在进程内构建轻量级 lexical index。
4. 查询时按关键词/词频相似度选出 top-N chunks。
5. 将命中 chunks 作为上下文拼接到模型提示中。
6. 返回答案时附带来源文件名、块序号或等效 citation。

该方案的目标是：

- 不依赖外部 vector DB；
- 不依赖 Foundry file_search；
- 不要求新增 embedding 资源；
- 先满足 Demo 阶段对 citation 与可追溯性的要求。

### 5.3 Citation 格式

Citation 由应用程序在响应中自行组织，至少包含：

- 来源文档名
- 命中块的顺序编号或页码摘要（如果解析可得）

Domain 4 指标只要求能判断是否带 citation 以及 citation 数量，不要求完整页码精度。

---

## 6. 服务架构与 Observability 设计

### 6.1 调用链路

```text
Tier1 / Evaluation Runner / PyRIT
        |
        v
APIM /rag
        |  APIM diagnostics -> App Insights
        v
Azure Web App: AIGovernTrustworthyRAGApp
        |-- PDF load / chunking / in-memory retrieval
        |-- AOAI model call
        |-- shared_observability.log_llm_call()
        v
Blob archive + answer/citations response
```

### 6.2 Web API 约定

RAG Web App 暴露以下端点：

| 端点 | 方法 | 说明 |
|---|---|---|
| `/health` | `GET` | 健康检查；返回 `{"status":"healthy","chunks_loaded":N}` |
| `/responses` | `POST` | 主查询接口；返回 AI 回答 + citations + archive_id |
| `/` | `GET` | 交互式 Chat UI（HTML 页面，供手动测试使用） |

`POST /responses` 请求体：

```json
{
  "input": "What are the four core functions of NIST AI RMF?"
}
```

`POST /responses` 响应体：

```json
{
  "output": "...",
  "citations": [
    {"source": "nist-ai-rmf.pdf", "page": 12, "chunk_preview": "..."}
  ],
  "archive_id": "arch_20260512_xxxxxxxx"
}
```

### 6.3 Evidence 写入

Web App 内部在模型调用成功或失败后调用：

```python
shared_observability.log_llm_call(...)
```

核心 metadata：

| 字段 | 值 |
|---|---|
| `service_name` | `AIGovernTrustworthyDemo.RAGService` |
| `target_type` | `rag_service` |
| `target_id` | `AIGovernTrustworthyDemoRAGService` |
| `response_id` | 模型 response id |
| `model_name` / `model_version` | 实际模型部署与版本 |
| `citations_count` | 返回 citation 数量 |
| `extra_attributes.rag_app_name` | `AIGovernTrustworthyRAGApp` |
| `extra_attributes.retrieval_mode` | `local_lexical_in_memory` |

### 6.4 Observability 分层

| 层 | 负责方 | 覆盖内容 |
|---|---|---|
| APIM gateway diagnostics | APIM | HTTP hop、状态码、延迟、W3C correlation |
| Web App telemetry | RAG Web App | 请求日志、异常日志、应用级 trace |
| shared-observability Blob evidence（RAG 服务内部） | RAG Web App 代码 | LLM input / output / error 完整证据；`target_type=rag_service`，`service_name=AIGovernTrustworthyDemo.RAGService` |
| shared-observability Blob evidence（调用方侧，可选） | 上游 App（如 Tier1 App） | 调用 RAG API 的请求 / 响应证据；`target_type=rag_service`，`service_name` 为上游 App 名 |
| App Insights 统一查询 | Azure Monitor | APIM + Web App + evidence thin event 聚合 |

### 6.5 调用方（上游 App）记录 RAG API 调用的规范

当 Tier 1 Consumer App 或 evaluation runner 调用 RAG 服务 API 时，**调用方自己也应调用 `log_llm_call()`** 记录这次外出调用，参数如下：

| 参数 | 值 |
|---|---|
| `service_name` | 调用方自己的服务名（如 `AIGovernTrustworthyDemo.Tier1App`） |
| `target_type` | `"rag_service"` |
| `target_id` | `"AIGovernTrustworthyDemoRAGService"` |
| `target_endpoint` | RAG API 的实际 URL（经 APIM 或直连） |
| `llm_input` | 发给 RAG 的请求体，如 `{"input": "..."}` |
| `llm_output` | RAG 响应体，包含 `output`、`citations`、`archive_id` 等 |
| `model_name` | `None`（调用方不知道 RAG 内部用了哪个模型） |
| `response_id` | `None`，或 RAG 响应中的 `archive_id`（可写入 `extra_attributes.downstream_archive_id`） |

**这与 RAG 服务内部自己写的那条 evidence 不重复**：
- RAG 服务内部记录的是"我向 LLM 发了什么 prompt，拿到了什么 answer"。
- 调用方记录的是"我向 RAG API 发了什么问题，拿到了什么响应（含 citations）"。
- 两条记录通过相同的 `trace_id` 关联，在 App Insights 中可以看到完整的两层调用。

```python
# Tier1 App 侧示例（调用 RAG 服务后记录）
from shared_observability import log_llm_call

rag_request = {"input": user_question}
rag_response = call_rag_api(rag_request)   # 实际调用

log_llm_call(
    service_name="AIGovernTrustworthyDemo.Tier1App",
    target_type="rag_service",
    target_id="AIGovernTrustworthyDemoRAGService",
    target_endpoint=RAG_API_URL,
    llm_input=rag_request,
    llm_output=rag_response,
    credential=credential,
    extra_attributes={
        "downstream_archive_id": rag_response.get("archive_id"),
    },
)
```

---

## 7. APIM 接入设计

APIM 保留 `/rag` 作为统一治理入口，后端改为 RAG Web App：

```text
https://aigoverntrustworthydemoapim.azure-api.net/rag
    -> https://AIGovernTrustworthyRAGApp.azurewebsites.net/responses
```

APIM 仍只做 pass-through、diagnostics、rate limit / policy，不做 RAG orchestration。

---

## 8. 身份与权限设计

| 身份 | 用途 | 状态 |
|---|---|---|
| Deploy SPN `AZ_DEPLOY_CLIENT_ID` | 创建 / 配置 Web App、RBAC、APIM | 复用 |
| `AIGovernTrustworthyDemoRAGServiceSPN` | RAG Web App 运行时访问 AOAI、Blob、App Insights | 当前首选 |

RAG Web App 运行时身份需要：

- `Cognitive Services OpenAI User` on `AIGovernTrustworthyAOAI`
- `Storage Blob Data Contributor` on `aigoverntrustworthysa`
- `Monitoring Metrics Publisher` on `AIGovernTrustworthyRG`

---

## 9. 环境变量

步骤 2 相关变量：

| 变量名 | 用途 |
|---|---|
| `L4_APP_SERVICE_PLAN_NAME` | 现有 App Service Plan 名称（`AIGovernDemoASP`） |
| `L4_APP_SERVICE_PLAN_RESOURCE_GROUP` | 现有 App Service Plan 所在资源组 |
| `L4_RAG_APP_NAME` | RAG Web App 名称 |
| `L4_RAG_APP_URL` | RAG Web App 直接 URL |
| `L4_RAG_MODEL_DEPLOYMENT` | RAG 使用的模型 deployment |
| `L4_RAG_RETRIEVAL_MODE` | 当前检索实现模式 |
| `L4_RAG_SERVICE_URL` | 经 APIM 暴露后的 `/rag` URL |

---

## 10. 开发产物清单

| 产物 | 路径 | 状态 | 说明 |
|---|---|---|---|
| 知识库 PDF 目录 | `apps/rag-service/knowledge-base/` | ✅ 已就绪 | 5 个 AI Governance PDF（NIST RMF、EU AI Act、OWASP LLM Top10、Singapore MAS、Singapore Model AI Gov Framework） |
| RAG Web App 源码 | `apps/rag-service/app.py` | ✅ 已就绪 | FastAPI，BM25+文档别名提权，`shared-observability` 集成，Chat UI |
| Dockerfile | `apps/rag-service/Dockerfile` | ✅ 已就绪 | 从仓库根构建；嵌入 `packages/shared-observability` |
| Docker 镜像 | `aigoverndemoacr.azurecr.io/aigoverntrustworthyragapp:v1.0.2` | ✅ 已就绪 | 当前生产版本 |
| Azure Web App | `AIGovernTrustworthyRAGApp` | ✅ 已就绪 | `canadaeast` region，Managed Identity = `L4_RAG_SERVICE_CLIENT_ID` |
| Blob evidence 路径 | `aigoverntrustworthy/{yyyy}/{mm}/{dd}/AIGovernTrustworthyDemo.RAGService/rag_service/{archive_id}/` | ✅ 已验证 | 每次调用写入 input/output/metadata.json |
| APIM 配置 | `apps/rag-service/scripts/` 或 `infra/apim/` | 🔲 待完成 | 将 `/rag` 后端切到 RAG Web App |
| Blob viewer | `apps/blob-viewer.html` + `apps/launch_blob_viewer.py` | ✅ 已就绪 | 本地代理模式（端口 8888）查看 `ai-invocation-archive` |

> 当前仓库中保留的 Hosted Agent 原型文件仅作为历史实验记录，不是当前批准路径。

---

## 11. 实施顺序

1. ✅ 复用现有 App Service Plan `AIGovernDemoASP`。
2. ✅ 创建 RAG Web App `AIGovernTrustworthyRAGApp`。
3. ✅ 在应用内实现 PDF 解析、切块、BM25 进程内检索 + 文档别名提权、模型调用和 `log_llm_call()`。
4. ✅ 配置 RAG Web App 使用 `L4_RAG_SERVICE_CLIENT_ID` 作为运行时身份。
5. ✅ 通过直连 Web App 端点调用 RAG，确认答案、citation、Blob evidence、App Insights trace。
6. 🔲 将 APIM `/rag` backend 切到 Web App `/responses` endpoint（待 APIM 建好后执行）。
7. 🔲 通过 APIM 端点完整验证 RAG 调用链（含 APIM diagnostics 关联）。
8. 🔲 更新 target registry 中 RAG endpoint 与 Web App metadata。

---

## 12. 风险与未决项

| 风险 / 未决项 | 影响 | 缓解措施 |
|---|---|---|
| 进程内检索规模有限 | 文档规模扩大后响应时间和相关性可能下降 | Demo 阶段先用轻量方案；如不足，再经用户同意评估 embedding / AI Search |
| PDF 解析质量受文档格式影响 | citation 粒度或块边界可能不稳定 | 优先使用结构清晰的标准 PDF；必要时增加预处理规则 |
| Web App 直连后端的安全策略需细化 | 可能需要后续增加 Access Restrictions / Easy Auth | 当前先完成最小可用路径；硬化作为后续步骤 |
| 当前不使用 Hosted Agent tracing | RAG 路径缺少 Foundry 平台内部 span | 通过 APIM diagnostics + Web App telemetry + Blob evidence 保持证据链完整 |
