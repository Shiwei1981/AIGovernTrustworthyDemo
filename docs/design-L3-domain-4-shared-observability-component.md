# Domain 4 · shared-observability 组件设计

## 1. 文档定位

本文档重新定义 Domain 4 的 shared-observability 组件，目标是在最小化自定义代码和架构复杂度的前提下，满足 demo 级 AI Governance 观测需求。

本文档覆盖以下内容：

- 基于当前结论重新明确需求
- 组件定位与非目标
- 架构设计
- 接口设计
- 数据设计
- 查询与关联策略
- 接入与实施顺序

本文档面向后续代码实现、脚本接入、APIM 配置、Foundry tracing 配置、KQL 查询设计和演示验证。

## 2. 输入来源与不可动摇设计要求

本设计在开始编写前，已通读并吸收以下文档中的约束、目标和场景：

- `docs/charters/cross-app-architecture-charter.md`
- `docs/charters/project-charter.md`
- `docs/charters/ai-execution-charter.md`
- `docs/design-L1-overview.md`
- `docs/design-L2-domain-4-prerequisites.md`
- `docs/design-L2-domain-4-prerequisites-lowleveldesign.md`
- `docs/design-L2-domain-4-output-trustworthiness.md`
- `docs/Prompt.md`
- Microsoft Foundry tracing / observability 官方文档
- Azure API Management observability / diagnostics 官方文档

在本轮设计中，以下 7 条要求被视为不可动摇的设计要求，后续所有章节都必须服从它们：

1. 在所有可以开启 APIM 的情况下，开启 APIM tracing。
2. 对于 LLM 调用，使用 Python 代码级 log 记录完整证据。
3. 对于 Foundry 内部调用链，全面开启 Foundry tracing。
4. 整体只做 demo 级 observability，不建设完整 troubleshooting 链条；目标是回答“什么时刻，谁调用了谁”。
5. LLM 调用记录必须具备关联到 APIM tracing 和 Foundry tracing 的能力，但实现代价必须最小。
6. Foundry tracing 与 APIM tracing 都以 Application Insights 为最终查询面，未来查询统一在 App Insights / Azure Monitor Logs 中完成。
7. 所有自定义字段命名都尽可能向 Foundry tracing 与 APIM tracing 的原生命名靠拢。

## 3. 需求记录

### 3.1 总体目标

shared-observability 不再被设计为“统一 tracing 平台”或“自定义调用图引擎”。

它的职责被收缩为：

- 为 Python 代码中的 LLM 调用保存完整输入输出证据
- 在 App Insights 中留下与平台 trace 可 join 的最小索引记录
- 让 APIM tracing、Foundry tracing 和 Blob 证据可以在同一个查询面上被串起来

它的职责不包括：

- 自建完整 distributed tracing 系统
- 统一生成和管理业务级 `correlation_id`
- 替代 APIM tracing
- 替代 Foundry tracing

### 3.2 功能需求

#### R-001 统一覆盖全部受管对象

本设计必须覆盖以下受管对象，并保持 target type 分离：

- AI 应用
- Azure AI Foundry 原生模型
- Azure AI Foundry fine-tune 模型
- Azure AI Foundry 自定义 Agent
- Copilot Studio 自定义 Agent
- VM 中自建 Hugging Face 模型
- Tier 1 Consumer App
- Tier 2 Consumer App

#### R-002 所有可代理 HTTP hop 默认走 APIM

- 所有可以被 APIM 代理的 HTTP hop 都应走 APIM。
- APIM 是 demo 级调用链可见性的默认主路径。
- 不要求 APIM 代理平台内部私有 hop，例如 Foundry managed agent 到其内部模型的调用。

#### R-003 Foundry tracing 全面开启

- 对 Foundry 原生模型、fine-tune 模型、Foundry Agent，必须开启 Foundry tracing。
- 对支持服务端 tracing 的对象，优先使用平台原生 tracing，而不是重复自建 span 体系。

#### R-004 Python 组件必须保存完整 AI 调用输入输出证据

- Python 组件必须对它实际发起的每次 **AI 调用**（包括 LLM 模型 API 调用、Agent API 调用、RAG 服务 API 调用）保存完整 `input`、`output`、`metadata`。
- `input` 必须包含真正发给下游的请求正文，包括 prompt、messages、system prompt、tool inputs、retrieval context、agent 请求体等。
- 失败调用也必须保存失败前的完整输入和错误输出。
- 统一保存位置必须是 Blob archive。

> **说明**：`log_llm_call()` 的函数名中包含 "llm"，但它的设计定位是记录"一次 AI 调用（AI invocation）"，不限于直接调用 LLM 模型 API。当调用目标是 Agent API 或 RAG 服务 API 时，应同样使用 `log_llm_call()`，通过 `target_type` 字段区分调用类型。参见 R-004a。

#### R-004a 调用 Agent API / RAG 服务 API 时使用相同记录规范

当一个 Python 应用程序（例如 Tier 1 Consumer App、evaluation runner、PyRIT runner）调用的不是 LLM 模型 API，而是 **Agent API** 或 **RAG 服务 API** 时，必须遵循以下规则：

1. **仍然调用 `log_llm_call()`**，不另建日志机制。
2. **`target_type` 是区分调用类型的关键字段**：
   - 直接调用 LLM 模型 API → `target_type = "foundry_native_model"` / `"foundry_finetune_model"` / `"vm_huggingface_model"`
   - 调用 Foundry Agent API → `target_type = "foundry_agent"`
   - 调用 Copilot Studio Agent API → `target_type = "copilot_studio_agent"`
   - 调用 RAG 服务 API → `target_type = "rag_service"`
3. **`llm_input` 传入发给下游 API 的实际请求体**（例如 RAG 调用时的 `{"input": "..."}`，Agent 调用时的 messages / task payload）。
4. **`llm_output` 传入从下游 API 拿到的完整响应体**（例如 RAG 返回的 `{output, citations, archive_id}`，Agent 返回的 task result）。
5. **`response_id` 取下游 API 响应中的对等标识**；若下游响应包含其自己的 `archive_id`，可写入 `extra_attributes.downstream_archive_id`。
6. **`model_name` / `model_version` 在调用方通常不可知**，Agent / RAG 服务内部才知道调用了哪个模型。调用方这两个字段传 `None` 即可；模型身份由被调用的服务自己记录。

**记录的语义是**：这一层 Python 代码向 Agent / RAG 发出了一次请求，并拿到了一个响应。不是重复记录 Agent 或 RAG 内部的 LLM 调用（那些由被调用的服务自己记录）。

> **与 RAG 服务自身记录的关系**：RAG 服务内部调用 LLM 时，RAG 服务自己也会用 `log_llm_call()` 写一条 `target_type=rag_service` 的 evidence。调用方写的那条同样是 `target_type=rag_service`，但 `source_type` 不同（调用方填自己的类型，如 `tier1_consumer`；RAG 服务自身填 `rag_service`），`service_name` 也不同。查询时可用 `aigov.source.type` 或 `service_name` 区分哪一层写的。

#### R-005 查询主面统一在 Application Insights

- APIM tracing、Foundry tracing、Python 组件写入的索引事件都必须落在 App Insights / Azure Monitor Logs 查询面上。
- 未来的 demo 查询必须以 App Insights Query 为主，而不是多个独立系统分别查询。

#### R-006 LLM 证据记录必须可关联到 APIM / Foundry trace

- 每条 Python LLM 证据记录都必须具备 join 到 APIM 或 Foundry trace 的能力。
- 对于一条可疑调用，例如 jailbreak 尝试，必须可以从 LLM evidence 追到上游请求来源。
- 关联应优先使用平台原生 trace 上下文，而不是新建业务级关联键。

#### R-007 1:1 记录粒度

- Python 组件记录的粒度是“一次实际 AI 调用”（直接 LLM API 调用、Agent API 调用、或 RAG API 调用），而不是业务请求、会话或整条调用链。
- 每次实际调用只产生一组 Blob 证据和一条薄索引事件。
- 当上游 HTTP hop 和下游 Foundry span 都存在时，这条薄索引事件应尽可能与它们共享相同 `trace_id`。

#### R-008 不再要求组件维护 `correlation_id`

- 本设计不要求组件生成或维护独立 `correlation_id`。
- 平台链路关联优先使用 `trace_id`。
- 具体 AI 调用优先使用 `response_id`。
- 证据归档定位使用 `archive_id` 与 `payload_ref`。

#### R-009 自定义字段命名尽量贴近原生语义

- 自定义字段优先复用或贴近 OpenTelemetry / Foundry / APIM 现有语义。
- 避免另造一套完全独立的业务命名体系。
- 只有平台没有的字段才允许使用 `aigov.*` 前缀扩展。

#### R-010 评测与红队结果需可与 trace 关联

- Foundry tracing 不会默认把 red teaming 与 evaluation 结果自动关联到 trace。
- Evaluation runner、PyRIT runner 或后续脚本在写结果时，必须显式保留 `trace_id` 或 `gen_ai.response.id`（若可得）。
- 这类关联仍然是 demo 级；不要求构建完整闭环工作流系统。

#### R-011 组件必须保持最小代码量

- 不新增独立日志 API 服务。
- 不自建调用图上下文对象、图数据库、事件总线或队列。
- 组件以嵌入式 Python package 方式被各应用、脚本和 runner 引用。

#### R-012 组件必须同时支持本地 Linux 与 Azure Web App

- 本地开发机直接运行时可用。
- 部署到 Azure Web App 后仍使用相同环境变量模型。
- 不依赖本地缓存或中间库。

#### R-013 组件不做自动重试

- Blob 写入失败立即返回失败。
- App Insights 索引写入失败立即返回失败。
- 上层调用方决定是否终止当前流程。

### 3.3 治理与证据需求

#### R-014 Blob 是完整证据主存储

- 完整 `input`、`output`、`metadata` 仅保存在 Blob archive。
- APIM 与 Foundry tracing 只提供 trace 视角，不替代完整证据归档。

#### R-015 App Insights 中只保留薄索引事件

- Python 组件写入 App Insights 的自定义事件必须足够薄，只用于连接 trace 与 Blob 证据。
- 不把完整 prompt、完整 output 再复制到 App Insights。

#### R-016 Jailbreak 查询必须可落地

当后续在 evaluation、red teaming 或人工查询中发现一条可疑 jailbreak 尝试时，系统必须能支持以下最小查询路径：

1. 查到该次调用的 `trace_id` 或 `response_id`
2. 通过 App Insights 查到它对应的 APIM hop 和 Foundry trace
3. 通过 `payload_ref` 打开 Blob 中的完整输入输出证据

## 4. 设计结论

### 4.1 组件定位

shared-observability 是一个 Python 侧的 LLM evidence logger。

它负责：

- 记录 Python 代码发起的 LLM 调用完整证据
- 生成 `archive_id` 和 `payload_ref`
- 在 App Insights 中写一条极薄的 evidence index 事件
- 尽量继承当前活动 span 的 `trace_id` / `span_id`，从而连接到 APIM 与 Foundry trace

它不负责：

- 构建统一 tracing backbone
- 生成全局 `correlation_id`
- 替代 APIM 或 Foundry 的原生 tracing
- 记录所有 app-to-app hop 的业务语义

### 4.2 总体架构

```text
Caller / User
   |
   v
APIM
   |
   v
App / Script / Runner (Python)
   |
   +--> shared-observability
   |      |- read active trace context
   |      |- write Blob evidence
   |      |- emit thin App Insights evidence event
   |
   +--> downstream target
          |- APIM (when proxyable)
          |- Foundry model / agent endpoint
          |- VM LLM API

Application Insights / Azure Monitor Logs
   |- APIM diagnostics and traces
   |- Foundry traces
   |- shared-observability evidence events

Azure Blob Storage
   |- input.json
   |- output.json
   |- metadata.json
```

### 4.3 三层观测职责

| 层 | 主职责 | 是否主查询来源 |
|---|---|---|
| APIM tracing | 记录 HTTP hop、gateway latency、backend endpoint、入口来源 | 是 |
| Foundry tracing | 记录 Foundry 内部 span、tool call、inputs/outputs、latency | 是 |
| shared-observability | 保存完整 LLM 证据，并留下可 join 到 trace 的薄索引 | 是 |
| Blob archive | 保存完整输入输出正文 | 否，作为证据存储 |

### 4.4 最小关联策略

本设计的最小关联策略如下：

1. 链路关联优先使用 `trace_id`。
2. 具体模型或 Agent 响应优先使用 `gen_ai.response.id` 或等效 `response_id`。
3. Blob 证据定位使用 `archive_id` 与 `payload_ref`。
4. 不再依赖自建 `correlation_id`。

## 5. 架构设计

### 5.1 组件模块

建议组件只保留以下最小模块：

| 模块 | 责任 |
|---|---|
| `config` | 从环境变量读取 Blob 与 App Insights 配置 |
| `archive` | 生成 `archive_id` 与 Blob 路径，写入 `input/output/metadata` |
| `telemetry` | 在当前活动 span 下写入薄 evidence 事件 |
| `serializers` | 将请求和响应稳定序列化 |
| `errors` | 定义组件内异常 |

以下旧设计中的重型模块不再需要：

- `invocation graph context builder`
- `id policy`
- 独立调用图上下文对象
- 自定义调用图或统一业务链主键

### 5.2 公开接口

组件公开接口收敛为两个：

```python
load_settings_from_env() -> ObservabilitySettings

log_llm_call(
    *,
    settings: ObservabilitySettings,
    credential: TokenCredential,          # 由调用方传入，见 5.2.1
    service_name: str,
    target_type: str,                     # TargetType 枚举值，描述下游组件类型
    source_type: str | None = None,       # SourceType 枚举值，描述当前记录方类型（可选）
    target_id: str,
    target_endpoint: str,
    llm_input: object,
    llm_output: object | None = None,
    error: object | None = None,
    model_name: str | None = None,
    model_version: str | None = None,
    response_id: str | None = None,
    extra_attributes: dict[str, object] | None = None,
) -> EvidenceRecord
```

说明：

1. `log_llm_call(...)` 是一次实际 LLM 调用对应的一次记录。
2. `llm_output` 与 `error` 二选一；前者表示成功，后者表示失败。
3. 组件内部自动读取当前活动 span 的 `trace_id` / `span_id`。
4. 组件内部自动生成 `archive_id`。
5. 返回值仅供上层在必要时打印或补写其他记录，不用于维持调用图状态。
6. `credential` 参数必须由调用方显式传入，详见 5.2.1。

### 5.2.1 credential 注入设计

**核心原则：shared-observability 是一个组件库，不是一个应用程序。它本身不拥有 Azure 身份，也不从环境变量中自行读取 SPN 信息。**

访问 Azure 资源（Blob Storage、Application Insights）所需的 `TokenCredential` 必须由使用本组件的应用程序创建并传入。组件只消费 credential，不创建、不缓存、不续期 credential。

**调用方职责：**

- 应用程序根据自己的运行环境（SPN 凭据、Managed Identity、WorkloadIdentity 等）创建合适的 `TokenCredential` 实例。
- 将 `credential` 作为参数传入 `log_llm_call(...)`。
- 应用程序对 credential 的生命周期负责。

**示例（应用程序侧）：**

```python
from azure.identity import ClientSecretCredential
from shared_observability import load_settings_from_env, log_llm_call

# 应用程序自己创建 credential，来源由应用程序决定
credential = ClientSecretCredential(
    tenant_id=os.environ["AZ_RUNTIME_TENANT_ID"],
    client_id=os.environ["AZ_RUNTIME_CLIENT_ID"],
    client_secret=os.environ["AZ_RUNTIME_CLIENT_SECRET"],
)

settings = load_settings_from_env()
record = log_llm_call(
    settings=settings,
    credential=credential,
    service_name="...",
    ...
)
```

**测试约定：**

在对 shared-observability 组件本身进行集成测试时，使用 deploy SPN（`AZ_DEPLOY_*` 环境变量）构造 `ClientSecretCredential`：

```python
from azure.identity import ClientSecretCredential
import os

credential = ClientSecretCredential(
    tenant_id=os.environ["AZ_DEPLOY_TENANT_ID"],
    client_id=os.environ["AZ_DEPLOY_CLIENT_ID"],
    client_secret=os.environ["AZ_DEPLOY_CLIENT_SECRET"],
)
```

`AZ_DEPLOY_*` 仅用于测试，生产应用程序必须使用各自独立的运行时 SPN 或 Managed Identity，不得使用 deploy SPN。

### 5.3 与 APIM / Foundry 的关系

#### 5.3.1 对 APIM 的要求

- 所有可代理 HTTP hop 默认经过 APIM。
- APIM diagnostics 与 App Insights 集成必须开启。
- 对需要查看请求细节的 API，可按需提高日志详细度，但仍不在 App Insights 中长期保存完整 payload 正文。

#### 5.3.2 对 Foundry 的要求

- Foundry tracing 必须连接到与本项目统一使用的 Application Insights。
- 对 Foundry 原生模型、fine-tune 模型、Foundry Agent，必须开启 tracing。
- Python 代码调用 Foundry 时，必须启用 SDK tracing / OpenTelemetry propagation，使 evidence event 与 Foundry spans 共享同一 `trace_id`。

#### 5.3.3 对 Python 代码的要求

- 对于每次实际发起的 AI 调用（包括 LLM 模型 API、Agent API、RAG 服务 API），调用前固定 `llm_input`（填入发给下游的实际请求体）。
- 调用后立即调用 `log_llm_call(...)`，并通过 `target_type` 说明此次调用的下游类型。
- evidence 事件应在当前活动 span 内发出，这样 Application Insights envelope 中的 `operation_Id` 能自动与平台 trace 对齐。

## 6. 运行时流程设计

### 6.1 成功调用流程

1. 上游请求进入 APIM。
2. APIM 将请求转发给 Python 应用或脚本。
3. Python 代码在当前活动 trace 下调用下游 LLM / Agent / VM API。
4. Python 代码在调用前固定完整 `llm_input`。
5. Python 代码拿到 `llm_output` 和可用的 `response_id`。
6. `log_llm_call(...)` 写 Blob 中的 `input.json`、`output.json`、`metadata.json`。
7. `log_llm_call(...)` 在同一活动 span 下写一条薄 evidence 事件。
8. 后续查询时，用户可用 `trace_id` 在 App Insights 中看到 APIM hop、Foundry spans 和这条 evidence 事件。

### 6.2 失败调用流程

1. Python 代码在调用前固定完整 `llm_input`。
2. 下游模型或 Agent 调用失败。
3. `log_llm_call(...)` 仍写入失败版 `input.json`、`output.json`、`metadata.json`。
4. evidence 事件记录 `status=failed` 与最小错误字段。
5. 上层返回失败，不做自动重试。

### 6.3 Jailbreak 查询流程

当后续在 evaluation、red teaming 或人工查询中发现一条可疑 jailbreak 尝试时，最小查询路径如下：

1. 先通过 `gen_ai.response.id`、`trace_id` 或 evaluation / red team 结果中的关联字段定位该次调用。
2. 在 App Insights 中查询同一 `trace_id`，查看：
   - 上游 APIM hop
   - App / Script 侧 evidence 事件
   - Foundry 内部 spans
3. 从 evidence 事件中的 `aigov.payload.ref` 打开 Blob 证据。
4. 读取完整 `input.json` 和 `output.json`，判断 jailbreak 的具体来源与上下文。

## 7. 数据设计

### 7.1 核心键

| 键 | 来源 | 用途 |
|---|---|---|
| `trace_id` | 平台 tracing / OTel 上下文 | 串联 APIM、Foundry、Python evidence |
| `span_id` | 当前活动 span | 定位本次 evidence 事件所在 span |
| `gen_ai.response.id` | 模型 / Agent 原生响应 | 定位具体一次 AI 响应 |
| `archive_id` | Python 组件生成 | Blob 证据目录主键 |
| `aigov.payload.ref` | Python 组件生成 | 从查询面跳转到 Blob 证据 |

### 7.2 Blob archive 设计

统一容器：`ai-invocation-archive`

统一路径：

`aigoverntrustworthy/{yyyy}/{mm}/{dd}/{service_name}/{target_type}/{archive_id}/{input|output|metadata}.json`

说明：

1. Blob 主目录键不再使用 `correlation_id`。
2. `archive_id` 是 evidence record 的唯一归档主键。
3. `metadata.json` 中保存 `trace_id`、`span_id`、`response_id` 和 `payload_ref`。

### 7.3 `input.json`

```json
{
  "llm_request": {},
  "prompt_text": null,
  "messages": [],
  "system_prompt": null,
  "tool_inputs": [],
  "retrieval_context": [],
  "captured_at": "2026-05-12T00:00:00Z"
}
```

### 7.3a `input.json` — 按调用类型的填写规范

`llm_input` 是自由类型，调用方负责将发给下游的实际请求正文传入。以下按 `target_type` 列出推荐填写方式：

**直接调用 LLM 模型 API**（`foundry_native_model` / `foundry_finetune_model` / `vm_huggingface_model`）：

```json
{
  "model": "AIGovernTrustworthyDemoNativeModel",
  "messages": [
    {"role": "system", "content": "You are ..."},
    {"role": "user", "content": "What is ..."}
  ],
  "target_type": "foundry_native_model",
  "target_id": "..."
}
```

**调用 Agent API**（`foundry_agent` / `copilot_studio_agent`）：

```json
{
  "task": "Summarize the following document ...",
  "messages": [{"role": "user", "content": "..."}],
  "target_type": "foundry_agent",
  "target_id": "AIGovernTrustworthyDemoFoundryAgent"
}
```

调用方通常不知道 Agent 内部使用的模型，因此 `model_name` / `model_version` 填 `null`；Agent 服务自身会记录内部模型调用。

**调用 RAG 服务 API**（`rag_service`）：

```json
{
  "input": "What are the four core functions of NIST AI RMF?",
  "target_type": "rag_service",
  "target_id": "AIGovernTrustworthyDemoRAGService"
}
```

调用方通常不知道 RAG 服务内部使用的模型，因此 `model_name` / `model_version` 填 `null`；RAG 服务自身会记录内部 LLM 调用。

> **分层记录原则**：每一层只记录它自己发出的那次调用。Tier1 App 记录"我向 RAG API 发了这个请求"；RAG 服务记录"我向 LLM 发了这个 prompt"。两条记录通过 `trace_id` 关联，查询时可以重建完整调用链。

### 7.4 `output.json`

成功：

```json
{
  "llm_response": {},
  "error": null,
  "captured_at": "2026-05-12T00:00:01Z"
}
```

失败：

```json
{
  "llm_response": null,
  "error": {},
  "captured_at": "2026-05-12T00:00:01Z"
}
```

### 7.5 `metadata.json`

```json
{
  "archive_id": "arch_20260512_0001",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "service_name": "AIGovernTrustworthyDemo.Tier1App",
  "target_type": "foundry_agent",
  "target_id": "AIGovernTrustworthyDemoFoundryAgent",
  "target_endpoint": "https://contoso-apim.azure-api.net/foundry/agent/invoke",
  "model_name": "gpt-5.4",
  "model_version": "2024-12-01-preview",
  "gen_ai.response.id": "resp_123",
  "status": "succeeded",
  "payload_ref": "aigoverntrustworthy/2026/05/12/AIGovernTrustworthyDemo.Tier1App/foundry_agent/arch_20260512_0001/"
}
```

### 7.6 App Insights 薄索引事件设计

事件名：`AIGovernTrustworthyLLMEvidence`

要求：

1. 在当前活动 span 内发出。
2. 自定义字段尽量贴近 Foundry / OTel / APIM 原生命名。
3. 只记录索引，不记录完整 payload 正文。

最低字段集：

- `trace_id`
- `span_id`
- `service.name`
- `server.address`
- `gen_ai.operation.name`
- `gen_ai.request.model`
- `gen_ai.response.id`
- `aigov.archive.id`
- `aigov.payload.ref`
- `aigov.target.type`
- `aigov.target.id`
- `aigov.source.type`
- `status`

推荐错误字段：

- `error.type`
- `error.message`

### 7.7 命名对齐策略

本设计使用以下命名规则：

1. 平台已有语义优先：`trace_id`、`span_id`、`gen_ai.response.id`、`server.address`。
2. 仅在平台没有语义时使用 `aigov.*` 扩展：`aigov.archive.id`、`aigov.payload.ref`、`aigov.target.type`、`aigov.target.id`、`aigov.source.type`。
3. 不新增 `correlation_id`、`invocation_context_id`、`graph_node_id` 等业务自定义链路键。

## 8. 查询与关联设计

### 8.1 查询主面

未来查询统一发生在 App Insights / Azure Monitor Logs。

查询对象包括：

- APIM diagnostics / traces
- Foundry traces
- shared-observability evidence events

Blob 只在定位到 `payload_ref` 后作为证据打开。

### 8.2 1:1 关联要求

每条 evidence 事件都应与一次实际 LLM 调用 1:1 对应，并满足以下最小可关联性：

1. 如果调用经过 APIM，对应 evidence 事件与 APIM 日志可通过 `trace_id` 对齐。
2. 如果调用命中 Foundry，对应 evidence 事件与 Foundry spans 可通过 `trace_id` 和尽可能的 `gen_ai.response.id` 对齐。
3. 一条 evidence 事件可以反查到唯一 Blob 目录。

### 8.3 最小 KQL 查询思路

按 `trace_id` 查证据与链路：

```kusto
customEvents
| where name == "AIGovernTrustworthyLLMEvidence"
| extend trace_id = tostring(customDimensions.trace_id)
| extend response_id = tostring(customDimensions["gen_ai.response.id"])
| extend payload_ref = tostring(customDimensions["aigov.payload.ref"])
| where trace_id == "<trace-id>"
| project timestamp, trace_id, response_id, payload_ref, customDimensions
```

再按同一 `trace_id` 去查 APIM / Foundry 原生日志。

### 8.4 按 `aigov.target.type` 区分调用类型

查询某时段内所有 evidence 事件，并按调用类型分组统计：

```kusto
customEvents
| where name == "AIGovernTrustworthyLLMEvidence"
| extend target_type = tostring(customDimensions["aigov.target.type"])
| extend source_type = tostring(customDimensions["aigov.source.type"])
| extend service_name = tostring(customDimensions["service.name"])
| extend status = tostring(customDimensions.status)
| summarize count() by source_type, target_type, service_name, status
| order by count_ desc
```

查询特定调用边（如所有 Tier1 App → RAG 服务的调用）：

```kusto
customEvents
| where name == "AIGovernTrustworthyLLMEvidence"
| extend source_type = tostring(customDimensions["aigov.source.type"])
| extend target_type = tostring(customDimensions["aigov.target.type"])
| where source_type == "tier1_consumer" and target_type == "rag_service"
| extend trace_id = tostring(customDimensions.trace_id)
| extend payload_ref = tostring(customDimensions["aigov.payload.ref"])
| project timestamp, trace_id, source_type, target_type, payload_ref, customDimensions
```

`aigov.target.type` 可能的值及含义：

| `aigov.target.type` | 含义 | 记录方 |
|---|---|---|
| `foundry_native_model` | 直接调用 Foundry 原生模型 API | 调用模型的 App / Script |
| `foundry_finetune_model` | 直接调用 Foundry fine-tune 模型 API | 调用模型的 App / Script |
| `vm_huggingface_model` | 调用 VM 中 Hugging Face 模型 API | 调用模型的 App / Script |
| `foundry_agent` | 调用 Foundry Agent API | 调用 Agent 的上游 App（如 Tier1 App）**或** Agent 自身（若其内部也调 LLM） |
| `copilot_studio_agent` | 调用 Copilot Studio Agent API | 调用 Agent 的上游 App |
| `rag_service` | 调用 RAG 服务 API **或** RAG 服务内部调 LLM | 调用 RAG 的上游 App（如 Tier1 App）或 RAG 服务自身 |
| `tier1_consumer` | Tier 1 Consumer App 层面的记录 | Tier 1 App |
| `tier2_consumer` | Tier 2 Consumer App 层面的记录 | Tier 2 App |

当同一 `trace_id` 下出现多条 evidence 事件时，`service_name` + `aigov.target.type` 组合可以区分是哪一层应用记录的哪类调用。

## 9. 失败处理与边界

### 9.1 失败分类

| 类型 | 定义 | 处理方式 |
|---|---|---|
| AI backend failure | 模型 / Agent / VM API 调用失败 | 仍写 Blob 与 evidence 事件，返回失败 |
| Blob archive failure | 证据写入失败 | 返回失败 |
| App Insights failure | evidence 事件写入失败 | 返回失败 |
| Config failure | 缺少必要环境变量 | 启动失败或请求失败 |
| Serialization failure | 请求或响应无法序列化 | 返回失败 |

### 9.2 不做的事情

当前设计明确不做：

- 自建完整故障诊断链路
- 平台内部 hop 的二次代理
- 统一管理所有业务请求相关键
- 在 App Insights 中重复保存完整输入输出正文

## 10. 实施建议

### 10.1 最小实现切片

先实现以下最小切片：

1. `load_settings_from_env()`
2. `log_llm_call(...)`
3. Blob 证据写入
4. App Insights evidence 事件写入

### 10.2 首批接入顺序

建议顺序：

1. Tier 1 App 调 Foundry Agent
2. Tier 1 App 调 Foundry 原生模型
3. Tier 1 App 调 VM LLM API
4. RAG Service
5. Evaluation runner
6. PyRIT runner

理由：这些路径最容易同时覆盖 APIM、Foundry 和 Python evidence 三层关联。

## 11. 设计 review

### 11.1 本轮设计如何满足 7 条不可动摇要求

| 设计要求 | 落地方式 |
|---|---|
| 所有可开 APIM 的地方开 APIM tracing | APIM 成为所有可代理 HTTP hop 的默认入口 |
| LLM 调用使用 Python 代码级 log | `log_llm_call(...)` 负责保存完整证据 |
| Foundry tracing 全面开启 | Foundry 原生模型 / fine-tune / Agent 全部要求启用 tracing |
| demo 级即可 | 不构建完整 troubleshooting 平台 |
| LLM 记录关联到 APIM / Foundry | evidence 事件共享 `trace_id` 并保存 `response_id` |
| 统一查询都在 App Insights | APIM、Foundry、Python evidence 统一落 App Insights |
| 字段命名贴近原生语义 | 优先使用 OTel / Foundry / APIM 字段名 |

### 11.2 与旧设计的根本变化

本轮设计相较旧版本的根本变化如下：

1. 不再以 `correlation_id` 作为系统中心。
2. 不再设计独立调用图上下文对象或自定义调用图。
3. 不再把 shared-observability 视为 tracing 主系统。
4. shared-observability 被重新定义为 Python LLM evidence logger。

## 12. 结论

本设计将 Domain 4 的 observability 体系收敛为“APIM tracing + Foundry tracing + Python LLM evidence logging + Blob evidence archive”的四层组合。

它满足当前 demo 所需的最小目标：

- 看见什么时刻，谁调用了谁
- 在 App Insights 中统一查询
- 在需要时打开完整输入输出证据
- 以最小开发代价把 APIM、Foundry 和 LLM evidence 串起来

下一步应基于本设计，重写 L2 前置条件与低级别设计中关于 observability、APIM、步骤顺序和环境变量的内容，并据此进入实现阶段。