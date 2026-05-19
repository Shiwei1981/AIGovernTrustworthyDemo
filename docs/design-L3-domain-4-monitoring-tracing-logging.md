# Domain 4 · Monitoring, Tracing, Logging 统一设计

## 1. 文档定位

本文件是 Domain 4 关于 **monitoring、tracing、logging、evidence archive** 的统一 L3 设计文档，作为以下内容的集中规范：

- 为什么要记录
- 由谁记录
- 在什么时机记录
- 记录到哪里
- 每类记录写什么内容
- 每个字段的精确定义

本文件覆盖已开发对象和未开发对象的占位设计。其中：

- **已开发对象**：必须给出当前正确设计，不保留抽象占位。
- **未开发对象**：允许保留占位，但必须明确未来写入责任、链路位置和字段要求。

> **权威边界**：本文件是 Domain 4 统一 observability 主规范。  
> `docs/design-L3-domain-4-shared-observability-component.md` 继续只负责 shared-observability 组件自身设计。  
> 各步骤专用文档只描述各自对象的局部差异，不再重复定义全局 observability 规则。

## 2. 关联文档

| 文档 | 关系 |
|---|---|
| `docs/design-L2-domain-4-prerequisites.md` §2.4 | 本文的上层摘要入口 |
| `docs/design-L2-domain-4-output-trustworthiness.md` | 定义 Domain 4 指标和查询诉求 |
| `docs/design-L3-domain-4-app-insights-telemetry-fields.md` | 步骤 8 的 App Insights 字段合同、事件口径与验证范围 |
| `docs/design-L3-domain-4-apim.md` | APIM gateway、policy、diagnostics 设计 |
| `docs/design-L3-domain-4-shared-observability-component.md` | Python evidence 组件设计 |
| `docs/design-L3-domain-4-rag-governance-service.md` | 步骤 2 的 RAG 服务 observability 实现 |
| `docs/design-L3-domain-4-foundry-native-model.md` | 步骤 3 原生模型的观测边界 |
| `docs/design-L3-domain-4-foundry-finetune-model.md` | 步骤 4 fine-tune 模型的观测边界 |
| `docs/design-L3-domain-4-vm-huggingface-model-api.md` | 步骤 5 VM 模型服务的 observability 边界 |

---

## 3. 需求与非目标

### 3.1 设计目标

Domain 4 本期的 observability 目标不是建设一个生产级 troubleshooting 平台，而是满足 demo 级 AI Governance 诉求，能够稳定回答以下问题：

1. **谁调用了谁**
2. **调用发生在什么时刻**
3. **这次调用属于哪个治理对象**
4. **平台 hop、应用侧 evidence、Blob 归档能否被串起来**
5. **Evaluation / red teaming 结果能否回溯到具体调用**

### 3.2 非目标

本设计不做以下事情：

1. 不自建独立 distributed tracing backbone。
2. 不自建业务级统一 `correlation_id` 体系。
3. 不把完整 prompt、完整响应体长期复制到 App Insights。
4. 不把 APIM、Foundry tracing、AOAI 平台诊断替换为自定义日志系统。
5. 不把不同 target type 混成一套无差别调用统计。

### 3.3 基本原则

1. **所有可代理 HTTP hop 默认走 APIM。**
2. **所有实际 AI 调用由 Python 侧 evidence 记录完整输入输出。**
3. **对 Foundry 支持的平台路径优先使用 Foundry tracing。**
4. **统一查询面固定为 App Insights / Azure Monitor Logs。**
5. **完整证据固定保存在 Blob archive。**
6. **链路关联优先使用 `trace_id`，具体响应优先使用 `response_id`。**

---

## 4. 术语说明

| 术语 | 含义 |
|---|---|
| **monitoring** | 广义监控概念，包含平台日志、应用遥测、调用证据、结果事件和查询口径 |
| **tracing** | 平台或应用侧 span / dependency / request 级链路观测，核心关联键是 `trace_id` |
| **logging** | 应用日志、错误日志、轻量自定义事件；本项目中不把它当作完整 AI 证据主存储 |
| **evidence** | 针对一次实际 AI 调用保存的完整 `input` / `output` / `metadata` 证据 |
| **thin event** | App Insights 中的薄索引事件，只保留可 join 字段，不复制完整正文 |
| **platform evidence** | APIM tracing、Foundry tracing、AOAI 平台诊断等平台侧记录 |
| **archive** | Blob 中的 `input.json`、`output.json`、`metadata.json` 三件套 |

---

## 5. 总体架构

```text
Caller / Browser / Runner
        |
        v
APIM
  |- request / dependency / gateway diagnostics
  |- traceparent propagation
  v
Python App / Script / Service
  |- application logs / app telemetry
  |- shared-observability.log_llm_call()
  |- optional local OTEL span
  v
Downstream target
  |- RAG Web App internal model call
  |- AOAI native / fine-tune model
  |- Foundry Agent
  |- Copilot Studio Direct Line
  |- VM model API

Application Insights / Azure Monitor Logs
  |- APIM diagnostics
  |- Foundry tracing
  |- AOAI platform diagnostics
  |- app telemetry
  |- thin evidence events
  |- run summary events

Blob archive
  |- input.json
  |- output.json
  |- metadata.json
```

### 5.1 五个核心组件

| 组件 | 角色 | 主写入者 | 主用途 |
|---|---|---|---|
| APIM | 平台 gateway tracing | APIM 平台 | 记录所有可代理 HTTP hop |
| Foundry tracing | Foundry 内部 span tracing | Foundry 平台 | 记录 Agent / SDK 支持路径的内部 hop |
| AOAI 平台诊断 | Azure 托管模型平台日志 | AOAI 平台 | 补充 APIM -> AOAI REST 路径的 deployment / model / version 证据 |
| shared-observability | Python evidence 组件 | Python app / runner / script | 保存完整 AI 调用证据并发 thin event |
| Blob archive | 完整证据存储 | shared-observability 或已明确的应用代码 | 保存完整输入输出与 metadata |

### 5.2 查询主面

统一查询入口固定为 **Application Insights / Azure Monitor Logs**：

1. 先按 `trace_id` 或 `response_id` 查平台 tracing / evidence thin event。
2. 再按 `archive_id` / `payload_ref` 跳转 Blob archive。
3. 如是 evaluation / red teaming 结果，再按 `test_run_id` 或结果事件反查具体调用。

---

## 6. 工具与职责矩阵

| 工具 / 层 | 写入者 | 写入目标 | 写入时机 | 写入内容 | 当前状态 |
|---|---|---|---|---|---|
| APIM diagnostics | APIM 平台 | App Insights / Log Analytics | 每个经 APIM 的 HTTP hop | request / dependency / status / latency / backend / W3C correlation | 已启用 |
| Foundry tracing | Foundry 平台 | App Insights / Log Analytics | Foundry Agent 或 SDK tracing 支持路径执行时 | spans、tool call、inputs/outputs 摘要、latency | 设计完成，待步骤 6/9/10 扩展 |
| AOAI 平台诊断 | AOAI 平台 | App Insights / Log Analytics | APIM -> AOAI REST 调用发生时 | deployment、model、version、request result | 步骤 3 已验证；步骤 4 设计要求同样适用 |
| shared-observability | Python app / runner / script | Blob + App Insights | 每次实际 AI 调用成功或失败后立即写 | 完整 input/output/error + metadata + thin event | 设计已完成，部分对象已接入 |
| App telemetry | 应用自身 | App Insights | 请求处理过程、异常或本地 span 时 | 请求日志、异常日志、应用 trace | RAG / VM 已有明确设计 |
| VM sidecar event | VM FastAPI sidecar | App Insights | 每次 VM `/v1/chat/completions` 返回后 | 轻量字段、latency、status | 已设计并已验证导出 |
| Evaluation result event | Evaluation runner | App Insights | 每次 evaluation run 完成后 | run summary、target、trace_id / response_id（若可得） | 占位，待步骤 10 |
| PyRIT result event | PyRIT runner | App Insights | 每次 red team run 完成后 | run summary、severity、trace_id / response_id（若可得） | 占位，待步骤 11 |

---

## 7. 写入时机、写入者、写入内容

### 7.1 平台层写入

| 写入者 | 触发时机 | 写到哪里 | 必写内容 |
|---|---|---|---|
| APIM | 每个经 gateway 的 request / response | App Insights / Log Analytics | HTTP hop、path、status、latency、backend、W3C correlation |
| Foundry 平台 | Foundry Agent / SDK tracing 支持路径执行时 | App Insights / Log Analytics | spans、内部 hop、tool call、latency |
| AOAI 平台 | APIM 或 SDK 调用 AOAI deployment 时 | App Insights / Log Analytics | deployment、model、modelVersion、请求结果 |

### 7.2 应用层写入

| 写入者 | 触发时机 | 写到哪里 | 必写内容 |
|---|---|---|---|
| RAG Web App | 内部真实模型调用成功或失败后 | Blob + App Insights | 真实 LLM input/output/error、`response_id`、`model_name`、`model_version`、`citations_count` |
| Python caller（Tier 1 / Tier 2 / runner / script） | 每次对下游模型 / Agent / RAG / VM / Tier1 API 的实际调用成功或失败后 | Blob + App Insights | 发给下游的实际请求、下游完整响应或错误、target identity、trace join 字段 |
| VM sidecar | 每次 VM chat completion 返回后 | App Insights | `target_type`、`target_id`、`trace_id`、`span_id`、`response_id`、`status`、`latency_ms` |

### 7.3 结果层写入

| 写入者 | 触发时机 | 写到哪里 | 必写内容 |
|---|---|---|---|
| Evaluation runner | run 完成后 | App Insights | `test_run_id`、target、汇总结果、`trace_id` / `response_id`（若可得） |
| PyRIT runner | run 完成后 | App Insights | `test_run_id`、target、severity、汇总结果、`trace_id` / `response_id`（若可得） |

---

## 8. 已开发对象的正确设计

### 8.1 RAG Service（步骤 2，已开发）

**正确设计**：

1. 外部调用默认走 `APIM /rag`。
2. APIM 写 gateway diagnostics。
3. RAG Web App 写应用遥测。
4. RAG Web App 在内部真实模型调用成功或失败后，调用 `shared_observability.log_llm_call(...)`。
5. Blob archive 保存完整 LLM prompt、response、error、metadata。
6. App Insights 保留 thin evidence event。

**写入者与时机**：

| 写入者 | 时机 | 内容 |
|---|---|---|
| APIM | `/rag` request / response | HTTP hop tracing |
| RAG Web App | 应用请求处理过程中 | 请求日志、异常日志、应用 trace |
| RAG Web App + shared-observability | 内部模型调用成功或失败后立即 | `input/output/error`、`response_id`、`model_name`、`model_version`、`citations_count` |

**当前固定字段**：

- `service_name = AIGovernTrustworthyDemo.RAGService`
- `target_type = rag_service`
- `source_type = rag_service`
- `target_id = AIGovernTrustworthyDemoRAGService`

### 8.2 Foundry Native Model（步骤 3，已开发）

**正确设计**：

1. 统一治理入口为 `APIM /native-model`。
2. 平台侧主要证据为 **APIM diagnostics + AOAI 平台诊断**。
3. 当前 `APIM -> AOAI REST` 路径**不单独要求 Foundry Studio span**。
4. 任何 Python 调用方如直接调用该模型，必须使用 shared-observability 记录完整 evidence。

**写入者与时机**：

| 写入者 | 时机 | 内容 |
|---|---|---|
| APIM | `/native-model/chat/completions` request / response | HTTP hop tracing |
| AOAI 平台 | deployment 被调用时 | deployment、model、modelVersion、结果状态 |
| Python caller（如 smoke script / future Tier 1 / future runner） | 实际模型调用成功或失败后立即 | 完整请求响应 evidence |

**当前已验证**：

- APIM `/native-model/chat/completions` 返回 200
- APIM diagnostics 已写入 App Insights
- AOAI 平台诊断可见 `modelDeploymentName = AIGovernTrustworthyDemoNativeModelGPT5.4mini`

### 8.3 Foundry Fine-tune Model（步骤 4，已开发）

**正确设计**：

1. 统一治理入口为 `APIM /finetune-model`。
2. 平台侧证据模式与 native model 相同：**APIM diagnostics + AOAI 平台诊断**。
3. Python 调用方应按 `foundry_finetune_model` 记录完整 evidence。
4. 训练阶段除部署调用外，还必须保留训练事实记录：
   - `fine_tune_job_id`
   - `base_model_name`
   - `training_file_path`
5. 使用步骤 3 native model 生成 5000 Q&A 时，该生成调用也属于 evidence 范围。

**写入者与时机**：

| 写入者 | 时机 | 内容 |
|---|---|---|
| Q&A 生成脚本 | 每次调用 native model 生成问答后 | native model 调用 evidence |
| APIM | `/finetune-model/chat/completions` request / response | HTTP hop tracing |
| AOAI 平台 | fine-tuned deployment 被调用时 | deployment、model、version、结果状态 |
| Python caller | 实际 fine-tune 模型调用成功或失败后立即 | 完整请求响应 evidence |
| 自动化脚本 / 文档 | job 创建、轮询、deployment 完成时 | job / deployment 事实记录 |

**当前状态**：

- fine-tune job 已完成
- fine-tuned deployment 已创建
- 直连与 APIM `/finetune-model` 烟测均已通过
- 最终 App Insights / Azure Monitor Logs 检索留档仍待补齐

### 8.4 VM Hugging Face Model（步骤 5，已开发）

**正确设计**：

1. VM 服务自身**不内嵌 shared-observability**。
2. VM sidecar 承接上游 `traceparent`，写 App Insights 轻量事件。
3. VM sidecar 不保存完整 `input` / `output` 正文。
4. 完整 evidence 由未来调用方（Tier 1 / evaluation / PyRIT / 脚本）通过 shared-observability 写入。
5. APIM `/vm-model` 作为长期统一治理入口。

**写入者与时机**：

| 写入者 | 时机 | 内容 |
|---|---|---|
| APIM | `/vm-model` request / response | HTTP hop tracing |
| VM sidecar | `POST /v1/chat/completions` 返回后 | `target_type`、`target_id`、`model_name`、`model_version`、`trace_id`、`span_id`、`response_id`、`status`、`latency_ms` |
| Future Python caller | 对 VM 模型实际调用成功或失败后 | 完整请求响应 evidence |

**当前固定字段**：

- `target_type = vm_huggingface_model`
- `target_id = AIGovernTrustworthyDemoPhi3VM`
- `service_name = AIGovernTrustworthyDemo.VMModel`
- App Insights 事件名：`AIGovernTrustworthyVMModelTrace`

---

## 9. 未开发对象占位设计

### 9.1 Foundry Agent（步骤 6 子对象，待开发）

**当前设计**：

1. 外部调用默认走 `APIM /foundry-agent`。
2. APIM 记录外部到 Foundry Agent API 的 HTTP hop。
3. Foundry Agent 自身不要求接入 shared-observability，也不要求自写 Blob evidence。
4. Agent 内部 hop、tool / retrieval 过程优先由 Foundry tracing 记录。
5. 调用方 Python 代码在调用 Agent API 时，仍需按 `target_type=foundry_agent` 写 shared-observability evidence。

**固定说明**：

- 步骤 6 的 Foundry Agent 平台日志优先进入 App Insights / Azure Monitor。
- `model_name` / `model_version` 在调用方通常未知，可为 `None`；由 Foundry 平台日志或 Agent 侧可得元数据补齐。
- `target_type` 固定为 `foundry_agent`。

### 9.2 Copilot Studio Agent（步骤 6 子对象，待开发）

**当前设计**：

1. 外部调用路径为 `APIM /copilot-studio -> Direct Line`。
2. APIM 记录外部到 Direct Line 的 HTTP hop。
3. Copilot Studio Agent 自身不要求接入 shared-observability，也不要求自写 Blob evidence。
4. 若 Copilot Studio / Power Platform 提供可行的 App Insights 或 Azure Monitor 输出路径，应尽量启用；若不支持，当前平台侧主 tracing 仍以 APIM 为准。
5. 调用方 Python 代码对 Direct Line conversation / activity 调用仍需写 shared-observability evidence。

**固定说明**：

- `target_type = copilot_studio_agent`
- `target_id` 以后以 bot id 或等效 agent id 为准
- `response_id` 使用 Direct Line conversation / activity 体系中的对等标识
- 当前最小可查询链路是 `APIM tracing + 调用方 evidence`；平台额外日志能力属于优先启用项，但不是步骤 6 的前置阻塞

### 9.3 Tier 1 Consumer App（步骤 7 子对象，待开发）

**目标设计**：

1. 自身入口走 `APIM /tier1`。
2. 自身请求日志、异常日志、应用 trace 写 App Insights。
3. 对每次真实下游 AI 调用都调用 shared-observability。
4. 若下游是 RAG / Agent，则记录“我调用了下游 API”；下游内部真实模型调用仍由下游自己记录。
5. Tier 1 前端对应后端与独立 API 在程序实现层面可以共用同一个 FastAPI 应用，但在证据记录上必须保留入口语义区分。

### 9.4 Tier 2 Consumer App（步骤 7 子对象，待开发）

**目标设计**：

1. 自身入口走 `APIM /tier2`。
2. 自身请求日志、异常日志、应用 trace 写 App Insights。
3. Tier 2 -> Tier 1 通过同一 `trace_id` 关联。
4. Tier 2 后端在调用 Tier 1 API 时，调用 shared-observability，记录这一层间接 AI 使用入口调用。
5. Tier 1 与更下游对象继续记录各自那一层的 AI evidence。
6. Tier 2 前端不直接调用底层 AI target；Tier 2 evidence 的语义固定为“Tier 2 后端调用 Tier 1 API”。

---

## 10. 统一事件名、Blob 路径与写入内容

### 10.1 App Insights 事件名

| 事件名 | 用途 | 写入者 |
|---|---|---|
| `AIGovernTrustworthyLLMEvidence` | 每次实际 AI 调用的 thin evidence event | shared-observability |
| `AIGovernTrustworthyEvaluationRun` | 每次 evaluation run 汇总 | Evaluation runner |
| `AIGovernTrustworthyRedTeamRun` | 每次 PyRIT / red team run 汇总 | PyRIT runner |
| `AIGovernTrustworthyVMModelTrace` | VM sidecar 本地轻量 trace 事件 | VM FastAPI sidecar |

> 说明：`AIGovernTrustworthyVMModelTrace` 是步骤 5 当前已确认的特例事件名，用于 VM 服务自身轻量遥测；它不是完整 evidence 事件的替代品。

### 10.2 Blob archive 路径

统一容器：`ai-invocation-archive`

统一路径：

`aigoverntrustworthy/{yyyy}/{mm}/{dd}/{service_name}/{target_type}/{archive_id}/{input|output|metadata}.json`

### 10.3 Blob 三个文件

| 文件 | 内容 | 写入者 |
|---|---|---|
| `input.json` | 发给下游的完整请求体、prompt、messages、必要 header 摘要 | shared-observability 或已明确的应用代码 |
| `output.json` | 下游完整响应体，或失败场景下的错误响应体 | shared-observability 或已明确的应用代码 |
| `metadata.json` | 基础字段、扩展字段、hash、size、token、citation、状态等 | shared-observability 或已明确的应用代码 |

---

## 11. 字段字典

### 11.1 基础字段

| 字段 | 解释 | 由谁填写 | 何时必填 | 填写规则 |
|---|---|---|---|---|
| `service_name` | 当前记录方服务名 | 应用 / runner / sidecar | 所有自定义写入 | 使用记录方自身服务名，不写下游服务名 |
| `source_type` | 当前记录方类型 | 应用 / runner | 调用方 evidence 推荐填写 | 如 `rag_service`、`tier1_consumer`、`evaluation_runner` |
| `target_type` | 被调治理对象类型 | 应用 / runner / sidecar | 所有 evidence / 轻量事件 | 只能使用受管 target type 枚举 |
| `target_id` | 被调对象唯一标识 | 应用 / runner / sidecar | 所有 evidence / 轻量事件 | 如 deployment、agent id、VM service 名 |
| `target_endpoint` | 被调 endpoint | 应用 / runner | 对外部调用 evidence 推荐填写 | 填实际调用 URL（经 APIM 或直连） |
| `model_name` | 模型名称 | 平台 / 调用方 / 服务自身 | 能拿到时填写 | 调用方未知时可为 `None` |
| `model_version` | 模型版本 | 平台 / 调用方 / 服务自身 | 能拿到时填写 | 平台拿不到时由 target registry 维护 |
| `trace_id` | 平台 tracing 主关联键 | 平台自动生成或应用继承 | 所有链路 | 优先继承当前活动 span |
| `span_id` | 当前 span 标识 | 平台自动生成或应用继承 | 所有链路 | 优先从当前活动 span 读取 |
| `response_id` | 具体响应标识 | 平台 / 下游响应 / 应用提取 | 能拿到时填写 | 优先使用原生 `gen_ai.response.id` 或等效值 |
| `status` | 调用结果状态 | 应用 / sidecar / runner | 所有 evidence / 轻量事件 | 固定为 `succeeded` 或 `failed` |

### 11.2 测试与结果字段

| 字段 | 解释 | 由谁填写 | 何时必填 | 填写规则 |
|---|---|---|---|---|
| `test_tool` | 调用来源工具 | 调用方 / runner | smoke / evaluation / pyrit / manual 路径 | 固定枚举：`evaluation`、`pyrit`、`smoke_test`、`manual`、`dashboard` |
| `test_run_id` | 一次测试运行 ID | runner / 调用方脚本 | evaluation / red teaming / smoke run | 每次 run 唯一 |
| `severity` | 风险严重度 | PyRIT / finding writer | 红队结果 / finding | 如 `low`、`medium`、`high`、`critical` |

### 11.3 Archive 关联字段

| 字段 | 解释 | 由谁填写 | 何时必填 | 填写规则 |
|---|---|---|---|---|
| `archive_id` | 本次 archive 主键 | shared-observability | 完整 evidence 写 Blob 时 | 每次实际 AI 调用唯一 |
| `payload_ref` | Blob archive 路径引用 | shared-observability | 完整 evidence 写 Blob 时 | 指向 archive 路径 |
| `downstream_archive_id` | 下游服务返回的 archive id | 调用方应用 | 调用 RAG / Agent 等上游 API 时可选 | 放在 `extra_attributes` 中，不替代本层 `archive_id` |

### 11.4 业务扩展字段

| 字段 | 解释 | 由谁填写 | 何时必填 | 填写规则 |
|---|---|---|---|---|
| `citations_count` | citation 数量 | RAG 服务自身 | RAG 内部真实模型调用后 | 记录返回 citation 数 |
| `latency_ms` | 调用耗时毫秒 | sidecar / app / runner | 轻量性能观察需要时 | 不作为主关联键 |
| `fine_tune_job_id` | fine-tune job 标识 | fine-tune 自动化脚本 | 训练事实记录 | 训练阶段使用 |
| `base_model_name` | fine-tune 基础模型名 | fine-tune 自动化脚本 | 训练事实记录 | 如 `gpt-4.1` |
| `training_file_path` | 训练文件路径 | fine-tune 自动化脚本 | 训练事实记录 | 指向 Storage 或仓库归档 |

### 11.5 文件级语义

| 字段 | 精确定义 |
|---|---|
| `input.json` | 该记录方实际发给下游的一次请求正文，不是业务层抽象输入 |
| `output.json` | 该记录方从下游拿到的一次完整响应，或错误响应 |
| `metadata.json` | 对本次调用的结构化描述，用于查询、跳转和报表 |

---

## 12. 当前状态汇总

| 对象 | 主链路设计 | 当前状态 | 仍是占位的部分 |
|---|---|---|---|
| RAG Service | APIM + Web App telemetry + RAG internal evidence | 已开发 | 调用方侧 evidence 依赖未来 Tier 1 / runner |
| Foundry native model | APIM + AOAI diagnostics + future caller evidence | 已开发 | Python caller evidence 依赖未来调用方统一接入 |
| Foundry fine-tune model | APIM + AOAI diagnostics + training fact records + future caller evidence | 已开发 | 最终日志查询留档待补齐 |
| VM model | APIM + VM sidecar telemetry + future caller evidence | 已开发 | 完整 Blob evidence 由后续调用方补齐 |
| Foundry Agent | APIM + Foundry tracing + caller evidence | 占位 | agent id、运行时调用脚本 |
| Copilot Studio Agent | APIM + Direct Line + caller evidence | 占位 | bot id、Direct Line secret、调用脚本 |
| Tier 1 App | App telemetry + shared-observability | 占位 | 接口、connector、实现 |
| Tier 2 App | App telemetry + shared-observability + upstream trace propagation | 占位 | 接口、实现 |

---

## 13. 当前结论

Domain 4 的 monitoring / tracing / logging 设计当前已经收敛为以下统一模型：

1. **平台 tracing 负责看链路**：APIM、Foundry tracing、AOAI 平台诊断。
2. **Python evidence 负责看正文**：shared-observability 写 Blob 三件套，并在 App Insights 留薄索引事件。
3. **App Insights / Azure Monitor Logs 是统一查询面**。
4. **Blob archive 是完整证据主存储**。
5. **`trace_id`、`response_id`、`archive_id`、`payload_ref` 是最小关联骨架**。

后续新增 Agent、Consumer App、runner 时，不应再重新设计 observability 主架构；只需要按本文规定补齐：

- 写入者
- 写入时机
- target identity
- 字段赋值规则
- 查询验证语句
