# shared-observability

本目录用于实现跨应用统一的 observability 组件。当前 POC 里，它是所有可改代码应用、runner、脚本统一接入的共享 Python 包。

## 子项目边界

`shared-observability` 必须保持为一个可独立运行、可独立分发、可嵌入其他项目使用的子项目。

这意味着：

- 它可以遵循 `shared-contracts` 定义的字段命名、target type、事件语义等跨项目约束。
- 但它不能对 `shared-contracts` 形成运行时硬依赖。
- 即使没有 `shared-contracts` 包，`shared-observability` 也必须能够独立安装、导入和运行。
- 如果未来需要与 `shared-contracts` 对齐，应通过字段映射、适配层或构建期校验完成，而不是把 `shared-contracts` 变成必装前置条件。

## 目标

- 统一记录 Python 侧 LLM 调用证据
- 统一写入 Application Insights evidence 事件与 OpenTelemetry 相关字段
- 统一把 AI 调用的完整 `input` / `output` / `metadata` 写入 Blob archive
- 允许不同应用按场景附加治理字段，而不破坏统一查询模型

shared-observability 在当前设计中不是 tracing backbone，也不负责统一生成业务级 `correlation_id`。APIM tracing 和 Foundry tracing 是平台侧调用链主来源；本包只负责补齐 Python 代码中的 LLM evidence。

这里明确区分两类记录：

- Blob archive 记录 AI 调用的完整 input / output / metadata 原文
- Application Insights 记录最小 evidence 索引字段和查询字段

## 当前目录约定

- `pyproject.toml`：共享包元数据
- `shared_observability/`：可复用 Python 代码
- `shared_observability/schema.py`：本包内部使用的 observability schema 与归档契约
- `shared_observability/__init__.py`：对外导出最小公共接口

## 当前公开接口

- `load_settings_from_env()`：加载并校验 Blob / Application Insights 相关环境变量
- `log_llm_call(...)`：为一次实际 LLM 调用生成 evidence record、Blob payload 和 evidence event 属性

## 统一记录原则

- 每次实际 LLM 调用都必须写一条 Application Insights 薄 evidence 事件
- 每次 AI 调用都必须把完整 payload 写入 Blob archive
- Blob 中保存完整原文，App Insights 中只保存索引字段和 blob 引用
- 统一关联优先使用 `trace_id`、`response_id`、`archive_id`、`payload_ref`

## TargetType 值说明

`target_type` 描述**被调用的下游组件类型**，不是调用方自身。调用 `log_llm_call()` 时，问自己"我调用了什么"来选择正确的值。

| 值 | 含义 | 典型记录方 |
|---|---|---|
| `rag_service` | RAG 服务 API | 调用 RAG 的上游 App；或 RAG 服务自身记录内部 LLM 调用 |
| `foundry_native_model` | Azure AI Foundry 托管的基础/对话模型（标准部署） | 直接调用模型的 App 或脚本 |
| `foundry_finetune_model` | Azure AI Foundry 托管的 fine-tune 模型 | 直接调用模型的 App 或脚本 |
| `foundry_agent` | Azure AI Foundry Agent API | 调用 Agent 的上游 App |
| `copilot_studio_agent` | Microsoft Copilot Studio Agent 端点 | 调用 Agent 的上游 App |
| `vm_huggingface_model` | VM 上部署的 Hugging Face 模型 REST API | 直接调用模型的 App 或脚本 |
| `tier1_consumer` | Tier 1 Consumer App API（被测目标） | 评估 runner 或测试脚本 |
| `tier2_consumer` | Tier 2 Consumer App API（被测目标） | 评估 runner 或测试脚本 |

**分层记录原则**：每一层只记录自己发出的那次调用，`tier1_consumer` / `tier2_consumer` 留给"把消费者应用本身作为测试目标"的场景（通常是评估 runner 驱动）。

详细规范见 `schema.py` 中 `TargetType` 的 docstring。

## SourceType 值说明

`source_type` 描述**当前记录方自身的类型**，不是被调用的下游。调用 `log_llm_call()` 时，问自己"我是什么"来选择正确的值。`source_type` 为可选参数；省略时只有 `service_name`（字符串）标识调用方。

| 值 | 含义 | 典型场景 |
|---|---|---|
| `tier1_consumer` | Tier 1 Consumer App 是记录方 | Tier1 App 调用 RAG、Agent 或 LLM 时 |
| `tier2_consumer` | Tier 2 Consumer App 是记录方 | Tier2 App 调用下游 AI 服务时 |
| `rag_service` | RAG 服务自身是记录方 | RAG 服务记录内部 LLM 调用 |
| `foundry_agent` | Foundry Agent 自身是记录方 | Agent 记录内部 LLM 调用（如可访问） |
| `copilot_studio_agent` | Copilot Studio Agent 是记录方 | Agent 侧记录 |
| `evaluation_runner` | 自动化评估 / 治理 runner 是记录方 | Runner 驱动消费者 App 测试时 |
| `test_script` | 独立测试脚本是记录方 | 集成测试、手动 curl 测试 |

`source_type` + `target_type` 组合描述调用图中的一条有向边，例如 `tier1_consumer → rag_service` 可直接在 KQL 中按两个字段过滤，无需解析 `service_name` 字符串。

详细规范见 `schema.py` 中 `SourceType` 的 docstring。

## 定制化扩展原则

不同应用可以附加自己的扩展字段，但必须保留统一基础字段：

- `service_name`
- `target_type`
- `target_id`
- `model_name`
- `model_version`
- `trace_id`
- `span_id`
- `response_id`
- `archive_id`
- `status`
- `payload_ref`