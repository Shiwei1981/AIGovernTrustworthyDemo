# Domain 4 · VM Hugging Face 模型 + API · 步骤 5 设计文档

## 1. 文档定位

本文件是 `design-L2-domain-4-prerequisites.md` 中**步骤 5：VM Hugging Face 模型 + API** 的专用 L3 设计文档，记录该步骤的**需求、边界、实施设计、部署形态与验收口径**。

步骤 5 在本项目中的定位，不是为了单独搭一台“能跑模型的 VM”，而是建立一个能够被 Domain 4 持续纳管的 **VM-hosted Hugging Face text model target**，为后续 APIM 接入、VM 侧 App Insights 观测、调用方 shared-observability、evaluation、red teaming 和 dashboard 指标提供基础对象。

> **当前状态（2026-05-15）**：VM `AIGovernTrustworthyDemoPhi3VM` 已手动创建（Canada East，Standard B4s v2，Ubuntu 22.04.5 LTS jammy，Private IP `10.1.1.8`）；deploy SPN 已验证可通过 `az vm run-command` 登录和执行命令；运行时安装（llama.cpp server + Python sidecar）与模型下载尚未开始。低级别设计、APIM 预留路径、target registry、`.env.local.L4` 变量合同均已完成。

**关联文档**：

| 文档 | 关系 |
|---|---|
| `docs/charters/project-charter.md` | 约束不得擅自修改 `.env.local.L4`、不得越界新增未批准资源 |
| `docs/charters/cross-app-architecture-charter.md` | 约束 APIM、App Insights、shared-observability、Entra 与错误处理的统一要求 |
| `docs/design-L1-overview.md` | 约束 Domain 4 在首页 / 二级页中的指标定位 |
| `docs/design-L2-domain-4-prerequisites.md` | 上级步骤列表；步骤 5 的总入口 |
| `docs/design-L2-domain-4-prerequisites-lowleveldesign.md` | 已给出 VM 规格、选型、`.env.local.L4` 变量与资源清单 |
| `docs/design-L2-domain-4-output-trustworthiness.md` | 约束步骤 5 后续必须支撑的治理对象分类与指标字段 |
| `docs/design-L3-domain-4-apim.md` | 已为 `/vm-model` 预留 APIM 入口与网络前置条件 |
| `docs/design-L3-domain-4-shared-observability-component.md` | 约束未来调用方如何为 VM 模型调用补齐 evidence；不要求 VM 模型服务自身集成 |
| `infra/target-registry/targets.json` | 已存在 `vm_huggingface_model` 的目标占位 |

---

## 2. 需求来源与不可越界边界

本步骤必须同时满足以下项目级边界：

1. 本仓库是 Domain 4 的前置条件、资源计划、环境配置和治理基线仓库；步骤 5 必须服务于后续治理演示，不是孤立的 VM 模型实验。
2. Domain 4 的 target type 必须分开治理；步骤 5 的对象必须明确保持为 `vm_huggingface_model`，不能与 `foundry_native_model`、`foundry_finetune_model`、`foundry_agent`、`rag_service` 或 Consumer App 混合统计。
3. 所有运行期变量应优先沿用 `.env.local.L4` 中已有命名，不得擅自扩展新的平行命名体系。
4. 所有可代理的 HTTP hop 最终都必须收敛到 APIM；但步骤 5 的最小可运行切片允许先以 **VM 内网直连 smoke test** 证明模型和 API 本身可用。
5. 步骤 5 与步骤 6 必须保持边界清晰：**步骤 5 负责把 VM 模型、OpenAI-compatible API、App Insights 基础遥测和 trace 透传跑起来；步骤 6 负责把调用方（Tier 1 / Evaluation / PyRIT 等）的 shared-observability、Blob evidence 和 APIM 后置接入补齐。**
6. 在步骤 5 完成后，VM 服务应已具备基础 App Insights / trace 记录能力；但完整 `input` / `output` 证据仍由未来调用方通过 shared-observability 记录。
7. 本项目是 POC，但仍需遵守既有架构；如实施中发现需要新增设计外资源、改变现有资源组、暴露公网入口、或改用新的推理栈，必须先征得用户许可。
8. `.env.local.L4` 是当前环境合同；本步骤只能读取并引用既有变量名，不应重写或复制其中敏感值。

---

## 3. 步骤 5 要解决的核心问题

步骤 5 需要解决的是：在当前 Domain 4 已有的 APIM、target registry、指标口径和低级别设计基础上，建立一个**可在 CPU-only VM 上运行、可通过内网调用、可承接 trace context、可记录 App Insights 基础遥测、可被后续 APIM 代理、可被后续调用方 observability 扩展**的 Hugging Face 文本模型目标。

这意味着步骤 5 至少要同时回答以下 5 个问题：

1. **运行载体是什么**：VM 用什么操作系统、规格、网络边界、磁盘和账号模型。
2. **模型选哪个**：选择哪个小型、许可清晰、资源占用低的 Hugging Face 文本模型。
3. **推理 API 怎么暴露**：如何提供一个最小但稳定的 OpenAI-compatible API 给内网调用方使用。
4. **如何和后续治理链路衔接**：如何保证 VM 侧 App Insights、步骤 6 的调用方 shared-observability、APIM `/vm-model`、evaluation、red teaming 不需要推翻步骤 5 的基础选型。
5. **如何证明这个 target 已经“能用”**：至少要有可执行的内网连通性与推理验证口径。

---

## 4. 当前已存在的实施锚点（必须复用）

仓库中已经存在与步骤 5 直接相关的锚点；后续设计和实施应优先复用，而不是另起一套。

| 锚点 | 当前状态 | 对步骤 5 的含义 |
|---|---|---|
| `docs/design-L2-domain-4-prerequisites.md` §步骤 5 / §步骤 6 | 已定义步骤边界 | 步骤 5 与步骤 6 必须拆开推进 |
| `docs/design-L2-domain-4-prerequisites-lowleveldesign.md` | 已选定 VM 规格、模型、运行方式与变量名 | 步骤 5 默认不重新选型 |
| `docs/design-L3-domain-4-apim.md` §7.6 | 已为 `/vm-model` 预留 API 路径 | 步骤 5 的 API 形态必须能被该路径代理 |
| `.env.local.L4` | 已存在 `L4_VM_*` 变量合同 | 步骤 5 的实现和脚本必须沿用这些名字 |
| `infra/target-registry/targets.json` | `AIGovernTrustworthyDemoPhi3VM` 条目已更新 | 步骤 5 的治理身份已固定 |

**当前已存在的 draft 决策**：

| 项目 | 当前 draft → 实际值 |
|---|---|
| VM 名称 | `AIGovernTrustworthyDemoPhi3VM` ✅ 已创建 |
| OS | Ubuntu 22.04.5 LTS (jammy) ✅ 已创建 |
| VM 规格 | Standard B4s v2（4 vcpu，16 GiB）✅ 已创建 |
| 网络 | Public IP 已配置，DNS：`aigoverntrustworthydemophi3vm.canadaeast.cloudapp.azure.com`；**NSG 必须限制 11434 端口** |
| 推理端口 | `11434`（sidecar 外部）/ `11435`（llama-server 内部）|
| 模型 HF 仓库 | `microsoft/Phi-3-mini-4k-instruct-gguf` |
| 模型 GGUF 文件 | `Phi-3-mini-4k-instruct-q4.gguf`（Q4_K_M 量化，~2.2 GB） |
| 模型逻辑别名 | `Phi-3-mini-4k-instruct`（llama-server `--alias`） |
| 模型下载工具 | `huggingface-cli`（模拟客户实际 HF 下载路径） |
| 推理 serving | `llama.cpp server`（`llama-server`，暴露 OpenAI-compatible API） |

因此，**步骤 5 当前不需要重新做“大范围选型”**；它的首要任务是把“低成本优先 + OpenAI-compatible API + VM 侧 App Insights / trace”这组需求固定下来，而不再把 `Standard_D4s_v3` 和“VM 侧 shared-observability”视为硬性前提。

---

## 5. 步骤 5 的需求整理

### 5.1 目标需求

步骤 5 的直接目标不是追求最高模型能力，而是交付一个**最小可运行、可被后续治理链路接入的 VM 文本模型 target**。因此本步骤的需求排序如下：

1. **先证明在最小 VM 规格上可运行，再考虑模型质量优化。**
2. **先证明 API 合同稳定，再考虑自定义包装层。**
3. **先证明后续 APIM / App Insights / 调用方 observability / evaluation 可复用，再考虑局部实现便利性。**

### 5.2 VM 资源与操作系统需求

> **✅ 实际创建状态（2026-05-15）**
> - 资源名：`AIGovernTrustworthyDemoPhi3VM`
> - OS：Ubuntu 22.04.5 LTS (jammy)（已通过 `az vm run-command + lsb_release` 验证）
> - VM 规格：Standard B4s v2（4 vcpu，16 GiB）
> - Private IP：`10.1.1.8`
> - Public DNS：`aigoverntrustworthydemophi3vm.canadaeast.cloudapp.azure.com`
> - OS Disk：30 GB（设计要求 64 GB；实际模型 ~2.2 GB + 运行时 ~1 GB，30 GB 足够，无需扩容）

1. 步骤 5 使用 **Azure VM** 作为运行载体，实际资源名为 `AIGovernTrustworthyDemoPhi3VM`。
2. VM 操作系统为 **Ubuntu 22.04.5 LTS (jammy)**。
3. VM 规格为 **Standard B4s v2**（4 vcpu，16 GiB），符合"成本优先 + 可稳定运行 `Phi-3-mini-4k-instruct`"原则。
4. OS Disk 以“可容纳运行时、模型文件和日志并保留安全余量”为准；当前实际 **30 GB** 已足够承载本步骤，**64 GB** 仅作为更保守的建议值，不再视为硬性门槛。
5. VM 已配置 **Public IP / DNS**。**NSG 必须严格限制 `11434/TCP` 入站仅允许受控来源**，不得向公网开放推理端口。
6. VM 对外暴露的推理端口固定为 **`11434/TCP`**（Python sidecar 监听；`llama-server` 内部端口为 `11435`）。
7. 与 VM 相关的最小环境合同变量：
   - `L4_VM_NAME`
   - `L4_VM_ADMIN_USERNAME`
   - `L4_VM_PRIVATE_IP`
   - `L4_VM_PUBLIC_DNS`
   - `L4_VM_MODEL_NAME`
   - `L4_VM_MODEL_API_PORT`

### 5.3 模型选择与运行时需求

1. 步骤 5 必须选择**文本类** Hugging Face 模型，不引入图像、语音、视频或多模态模型。
2. 当前固定的首选模型为 **`microsoft/Phi-3-mini-4k-instruct`**（GGUF Q4_K_M），模型文件直接从 **HuggingFace Hub** 下载（仓库 `microsoft/Phi-3-mini-4k-instruct-gguf`），模型逻辑别名固定为 `Phi-3-mini-4k-instruct`（通过 `llama-server --alias` 注入）。
3. 选择该模型的理由已由低级别设计预先限定：
   - 资源占用低，适合 CPU-only VM
   - 许可清晰（MIT）
   - 能满足 demo 级文本问答与治理测试
4. 步骤 5 使用 **`llama.cpp server`**（`llama-server` 二进制）作为推理运行时，直接加载 HuggingFace CLI 下载的 GGUF 文件，暴露 OpenAI-compatible API，以模拟客户真实 HF 部署路径。不引入 Ollama 或其他额外中间层。
5. 模型文件可以存放在 VM 本地磁盘或挂载磁盘，但路径策略必须以“最小部署复杂度”为优先。
6. 步骤 5 不追求高并发、高吞吐或生产级性能优化；只需满足 demo 级单机调用即可。
7. 若 `Phi-3-mini-4k-instruct` 在当前 VM 规格上无法稳定运行，必须先保留“低资源、小模型、许可清晰”的筛选原则，再向用户报告替代建议，而不是直接切换到大模型。

### 5.4 API 合同需求

步骤 5 交付的 VM 推理服务必须具备一个**最小可用的 OpenAI-compatible API 合同**，并尽可能贴近通用 LLM API 形态，以便后续被 APIM、Tier 1、evaluation 和 red teaming 复用。

最低要求如下：

| 能力 | 路径 | 要求 |
|---|---|---|
| 推理接口 | `POST /v1/chat/completions` | 必须可接受 OpenAI 风格 `model + messages` 请求，并返回非空模型输出 |
| 健康检查 | `GET /health` | 必须可用于确认服务在线且模型已加载（llama.cpp server 原生健康端点）|

补充要求：

1. 步骤 5 使用 `llama.cpp server`（`llama-server`）原生 OpenAI-compatible API 合同，不额外开发一层自定义包装 API。
2. 请求 / 响应结构应尽可能贴近通用 OpenAI Chat Completions 语义，不发明 VM 专属 body schema。
3. 若后续步骤 6 为调用方接入 shared-observability 或 APIM 需要增加包装层，也不得破坏 `POST /v1/chat/completions` 作为统一推理入口的对外语义。
4. 目前不把 `GET /metadata` 作为步骤 5 的硬要求；若后续需要增加，应在步骤 6 或后续设计中明确。
5. API 返回格式必须保持足够兼容，使 APIM `/vm-model` 和调用脚本无需为 VM 专门设计完全不同的请求结构。

### 5.5 网络与安全边界需求

1. VM 已配置 Public IP / DNS（`aigoverntrustworthydemophi3vm.canadaeast.cloudapp.azure.com`）。**推理端口 `11434/TCP` 不得对公网开放**；NSG 必须只允许受控 VNet / 内网来源入站。
2. Network Security Group 必须只允许受控 VNet / 内网来源访问 `11434/TCP`。
3. APIM 子网到 VM 子网之间必须具备可路由性，以便后续 `/vm-model` 可以代理到 VM 后端。
4. 步骤 5 的最小验证可先使用内网直连 `http://<L4_VM_PRIVATE_IP>:11434`；但长期治理入口必须预留给 APIM `/vm-model`。
5. 直接访问 VM API 时不依赖 Entra / API Key；其安全边界依赖"NSG + 受控内网来源"约束。Public IP 仅用于 SSH 管理，绝不用于暴露推理端口。
6. 由于 VM 后端默认无认证，后续 APIM 转发时必须遵守现有 APIM 文档的要求，移除上游 `Authorization` header，避免 token 泄漏到 VM。

### 5.6 VM 侧 App Insights 与 trace 记录需求

1. **VM 模型服务自身不集成 `shared-observability`**；`shared-observability` 由未来调用方在调用 VM 模型时接入。
2. VM 模型服务应尽可能集成 **Application Insights / OpenTelemetry**，并复用仓库现有的 `APPLICATIONINSIGHTS_CONNECTION_STRING`。
3. VM 模型服务必须优先承接上游传入的 W3C trace context，例如 `traceparent`；若无上游 trace，允许服务自行开启新的 trace。
4. VM 模型服务应在 App Insights 中记录轻量级遥测，并尽量复用现有字段语义，至少覆盖：
   - `target_type`
   - `target_id`
   - `model_name`
   - `model_version`
   - `trace_id`
   - `span_id`
   - `response_id`
   - `status`
5. VM 模型服务侧的记录目标是“模型服务自身的 request/response tracing 与轻量索引”，不是完整 `input` / `output` evidence 归档。
6. 完整 `input` / `output` / `metadata` 归档、Blob archive 和调用方 evidence 事件由未来调用方通过 shared-observability 承担。

### 5.7 治理身份与字段需求

步骤 5 交付的对象必须在设计和实现中保持以下固定治理身份：

| 字段 | 要求值 / 要求 |
|---|---|
| `target_type` | `vm_huggingface_model` |
| `target_id` | `AIGovernTrustworthyDemoPhi3VM` |
| `display_name` | `VM Hugging Face Model (Phi-3-mini-4k-instruct)` |
| `vm_name` | `AIGovernTrustworthyDemoPhi3VM` |
| `model_name` | `Phi-3-mini-4k-instruct` |
| `model_version` | 待在实际模型拉取完成后确认，不得长期保留 placeholder |
| `api_port` | `11434` |
| `auth` | `none`（VM 直连路径） |
| `apim_path` | 后续固定为 `/vm-model` |

此外，步骤 5 的设计需要区分“VM 服务自身尽量记录的字段”和“由未来调用方 evidence 补齐的字段”。

**VM 服务自身应尽量记录到 App Insights 的字段**：

- `target_type`
- `target_id`
- `model_name`
- `model_version`
- `trace_id`
- `span_id`
- `response_id`

**由未来调用方 evidence 补齐的字段**：

- `test_tool`
- `test_run_id`
- `archive_id`
- `payload_ref`

其中：

1. 步骤 5 本身不要求完整 evidence 字段全部已经落库或落 Blob。
2. 但步骤 5 的 API、trace 透传和目标身份设计不能阻碍步骤 6 继续补齐这些字段。
3. 除非遗留集成明确要求，否则不应把 `correlation_id` 重新引入为核心设计键。

### 5.8 与步骤 6 的边界需求

步骤 5 与步骤 6 必须显式拆分，避免“先把 observability 混进去再说”导致范围失控。

**步骤 5 必须完成的内容**：

1. VM 资源形态确定并可用。
2. 模型已下载并可由服务加载。
3. `POST /v1/chat/completions` 可在内网成功调用。
4. `GET /health` 可返回服务就绪状态（llama.cpp server 原生端点）。
5. VM 服务可承接上游 `traceparent`，并在 App Insights 中记录 `trace_id` / `span_id` / `response_id` 等轻量字段。

**步骤 5 明确不要求在本轮完成的内容**：

1. shared-observability 在 VM 模型服务自身内嵌接入。
2. Blob archive 双写。
3. 完整 `input` / `output` evidence 事件。
4. `archive_id` / `payload_ref` 的完整证据链闭环。
5. VM 模型纳入 Model Identity Capture Rate 的完整统计闭环。

这些内容属于**步骤 6：调用方 shared-observability 接入与 VM 调用链观测补齐** 的范围。

### 5.9 与其他步骤的复用需求

步骤 5 完成后，至少要支持以下后续动作：

1. 被步骤 6 直接扩展为“调用方 shared-observability + VM 侧 App Insights”联合观测的 VM 目标。
2. 被 `docs/design-L3-domain-4-apim.md` 中的 `/vm-model` API 代理，无需推翻端口和路径假设。
3. 被步骤 9 的 Tier 1 Consumer App 当作一种独立下游 AI 服务调用。
4. 被步骤 13 的 evaluation runner 纳入 `vm_huggingface_model` 目标清单。
5. 被步骤 15 的 PyRIT / red teaming 当作独立测试对象。
6. 被 Domain 4 L1/L2 报表按独立 target type 展示，而不是混入 Azure 托管模型。

---

### 5.10 OTel Sidecar 架构设计（已确认方案 B）

步骤 5 采用 **Python FastAPI sidecar** 作为可观测性边界层，架构如下：

```
调用方 / APIM
    │
    │  POST /v1/chat/completions  (traceparent header 透传)
    ▼
┌──────────────────────────────────────────┐
│  Python Sidecar（FastAPI，port 11434）   │
│  ① 读取 traceparent header               │
│  ② 创建 OTel span                        │
│  ③ 代理请求 → llama-server（port 11435） │
│  ④ 提取 response_id                      │
│  ⑤ 写入 App Insights 轻量事件            │
│  ⑥ 原样返回 llama-server 响应           │
└──────────────────────────────────────────┘
    │
    │  http://localhost:11435/v1/chat/completions
    ▼
┌──────────────────────────────────────────┐
│  llama-server（llama.cpp，port 11435）  │
│  --alias Phi-3-mini-4k-instruct          │
│  --model Phi-3-mini-4k-instruct-q4.gguf │
└──────────────────────────────────────────┘
```

**设计要点**：

| 要素 | 决定 |
|---|---|
| 外部暴露端口 | `11434`（对 APIM 和调用方透明，与现有设计一致）|
| llama-server 内部端口 | `11435`（仅 VM 内访问）|
| 上游 trace 承接 | 读取 W3C `traceparent` header；无则自启新 trace |
| App Insights 事件名 | `AIGovernTrustworthyVMModelTrace` |
| 记录字段 | `target_type`, `target_id`, `model_name`, `model_version`, `trace_id`, `span_id`, `response_id`, `status`, `latency_ms` |
| 对调用方透明 | 响应体和 status code 均原样转发，sidecar 不修改 |
| 实现复杂度 | ~100 行 Python，不引入复杂框架依赖 |

**约束**：
1. sidecar 本身不持久化 `input` / `output` 正文；完整证据归档由步骤 6 调用方负责。
2. sidecar 写 App Insights 遥测失败时不得阻断已成功的推理响应，但必须输出明确错误日志；若 sidecar 无法连接 llama-server，则应显式返回 5xx，不做 success-shaped fallback。
3. 代码放置在 `apps/vm-model/` 目录，通过步骤 5 脚本部署到 VM。

---

## 6. 明确不属于步骤 5 的内容

以下事项不应混入步骤 5：

1. shared-observability 的服务内嵌接入与 Blob archive 完整证据记录（由未来调用方承担，不属于 VM 模型服务自身）。
2. APIM `/vm-model` 的正式后端绑定与策略落地（需要在 VM 私网 IP 明确后继续推进）。
3. 为 VM 模型开发公网可访问网关。
4. GPU VM、集群扩容、自动扩缩、模型热切换、高可用等生产级能力。
5. 引入新的向量库、RAG、Agent 编排或业务 UI。
6. 为了“先跑通”而新增第二套与 `llama.cpp server` 平行的模型服务框架（如 Ollama、vLLM）。

---

## 7. 步骤 5 的交付物要求

步骤 5 完成时，至少应形成以下产物：

| 产物 | 要求 |
|---|---|
| VM 资源事实记录 | 明确 VM 名称、规格、OS、私网 IP、开放端口 |
| 模型运行事实记录 | 明确 HF 下载来源（`microsoft/Phi-3-mini-4k-instruct-gguf`）、GGUF 文件路径、llama.cpp server 最小启动命令 |
| 初始化脚本 / 命令记录 | 可复用地完成 VM 上运行时安装与模型拉取 |
| 内网 smoke test 命令 | 可验证 `GET /health` 与 `POST /v1/chat/completions` |
| VM 侧 App Insights 遥测设计 | 明确 trace header 承接方式、记录字段与最小查询口径 |
| target 身份一致性 | `infra/target-registry/targets.json` 中 VM 条目与真实配置一致 |
| 与步骤 6 的衔接说明 | 明确下一步如何由调用方补齐 shared-observability 与完整 evidence |

---

## 8. 验收口径（需求视角）

从需求角度看，步骤 5 至少满足以下条件，才可视为“准备进入实施完成状态”：

1. 已确认 VM 资源形态、网络边界和操作系统，不存在未决的大项选型分歧。
2. 已确认 VM 模型固定为 `microsoft/Phi-3-mini-4k-instruct`（HF 下载 GGUF Q4_K_M + llama.cpp server），符合“小型、文本类、许可清晰、CPU-only 可运行、模拟客户真实 HF 部署路径”的筛选原则。
3. 已确认 VM 规格以“最低成本且可稳定跑通 smoke test”为优先，不再把 `Standard_D4s_v3` 视为唯一固定规格。
4. 已确认模型从 HuggingFace Hub 直接下载 GGUF 文件，推理运行时固定为 `llama.cpp server`，以模拟客户真实 HF 部署路径。
5. 已确认最小 API 合同至少包括 `POST /v1/chat/completions`，并尽量贴近通用 OpenAI-compatible 格式。
6. 已确认 VM 推理端口（`11434/TCP`）不对公网开放；VM 虽配置了 Public IP（仅用于 SSH 管理），NSG 必须严格限制推理端口仅允许受控内网来源；长期治理入口通过 APIM `/vm-model` 路由。
7. 已确认 VM 服务自身不接入 shared-observability，但应尽可能接入 App Insights、承接 `trace_id` 并记录统一字段。
8. 已确认步骤 5 与步骤 6 的边界：步骤 5 先交付可运行 target + VM 侧 App Insights，步骤 6 再由调用方补齐 shared-observability 与完整证据链。
9. 已确认该目标在 Domain 4 中始终保持独立身份：`target_type = vm_huggingface_model`，不与 Azure 托管模型合并。

---

## 9. 本轮已吸收的反馈

1. VM 规格调整为**成本优先**，以最低成本、能稳定跑通 smoke test 的 CPU-only SKU 为目标。
2. 模型下载来源从 Ollama registry 改为 **HuggingFace Hub 直接下载 GGUF 文件**，以模拟客户真实部署路径。
3. 推理运行时从 Ollama 改为 **llama.cpp server**，更直接体现"从 HF 下载权重，再用推理框架加载"的客户侧模式。
4. API 合同明确为**尽可能贴近通用 OpenAI-compatible LLM API**（`/v1/chat/completions`），不引入 VM 专属请求结构。
5. VM 模型服务自身**不集成 shared-observability**；未来由模型调用方承担 shared-observability 与完整 evidence。
6. VM 模型服务自身应**尽可能接入 App Insights**，承接 `trace_id` 并按现有字段语义记录轻量遥测。

---

## 10. 最终实施设计（已确认）

以下内容为步骤 5 当前确认的**最终实施设计**，后续代码与脚本应按此设计落地。

### 10.1 组件分工

| 组件 | 位置 | 职责 | 不承担 |
|---|---|---|---|
| Hugging Face CLI | VM 本机 | 下载并固定 GGUF 模型文件 | 对外提供推理 API |
| `llama-server` | VM 本机，`127.0.0.1:11435` / `0.0.0.0:11435` | 加载 GGUF、提供原生 OpenAI-compatible 推理接口、暴露 `/health` | trace 透传、App Insights 事件整理 |
| Python FastAPI sidecar | VM 本机，`0.0.0.0:11434` | 对外统一入口、承接 `traceparent`、创建 OTel span、写 App Insights、代理到 `llama-server` | 完整 evidence 归档、Blob archive |
| systemd | VM 本机 | 管理 `llama-server` 与 sidecar 开机自启、顺序启动、失败重启 | 业务逻辑 |
| APIM `/vm-model` | 后续步骤 | 统一治理入口、移除 `Authorization`、注入治理 header | VM 内部模型加载与遥测实现 |

### 10.2 运行拓扑与目录布局

```
APIM / 调用方
    │
    ▼
http://10.1.1.8:11434
    │
    ▼
Python FastAPI sidecar
    │
    ▼
http://127.0.0.1:11435
    │
    ▼
llama-server
    │
    ▼
/opt/models/phi3/Phi-3-mini-4k-instruct-q4.gguf
```

建议目录布局如下：

| 路径 | 用途 |
|---|---|
| `/opt/models/phi3/` | 存放 GGUF 模型文件 |
| `/opt/vm-model/sidecar/` | sidecar 代码与 Python virtualenv |
| `/opt/vm-model/bin/` | 本地下载的 `llama-server` 二进制或辅助脚本 |
| `/etc/systemd/system/llama-server.service` | `llama-server` systemd unit |
| `/etc/systemd/system/vm-model-sidecar.service` | sidecar systemd unit |
| `/var/log/vm-model/` | sidecar / bootstrap 过程日志（如需要） |

### 10.3 启动与依赖顺序

1. 安装运行时依赖：`huggingface-hub`、Python venv、`uvicorn`、`fastapi`、OpenTelemetry / App Insights 依赖。
2. 下载 `Phi-3-mini-4k-instruct-q4.gguf` 到 `/opt/models/phi3/`。
3. 部署 `llama-server` 二进制到 `/opt/vm-model/bin/`，启动内部端口 `11435`。
4. 部署 Python sidecar 到 `/opt/vm-model/sidecar/`，启动外部端口 `11434`。
5. 由 systemd 管理两个进程；sidecar 启动前应等待 `llama-server /health` 就绪。
6. 完成后先做 VM 本机 smoke test，再做内网直连 smoke test，最后再进入 APIM 后端绑定。

### 10.4 Sidecar 请求处理设计

**`GET /health`**
1. sidecar 代理到 `http://127.0.0.1:11435/health`
2. 原样返回 `llama-server` 响应

**`POST /v1/chat/completions`**
1. 读取上游 `traceparent`
2. 创建 OTel span；无上游 trace 时自建新 trace
3. 将请求体原样转发到 `llama-server`
4. 从响应中提取 `id` 作为 `response_id`
5. 写入 `AIGovernTrustworthyVMModelTrace` 事件到 App Insights
6. 将 `llama-server` 的响应体、状态码、headers 原样返回给调用方

**错误处理约束**
1. `llama-server` 不可达：sidecar 返回明确的 5xx 错误
2. App Insights 写入失败：请求仍可成功返回，但 sidecar 必须输出 error log
3. 不允许返回“看起来成功但实际未调用模型”的伪成功响应

### 10.5 systemd 设计

步骤 5 最终以两个 unit 落地：

| Unit | 启动命令 | 说明 |
|---|---|---|
| `llama-server.service` | `llama-server --model /opt/models/phi3/Phi-3-mini-4k-instruct-q4.gguf --alias Phi-3-mini-4k-instruct --host 0.0.0.0 --port 11435` | 仅负责模型推理 |
| `vm-model-sidecar.service` | `uvicorn sidecar:app --host 0.0.0.0 --port 11434` | 对外统一入口与轻量遥测 |

建议 sidecar unit 使用 `After=llama-server.service` 与 `Requires=llama-server.service`，确保启动顺序正确。

### 10.6 与 `apps/vm-model/scripts/` 的映射

| 脚本 | 最终职责 | 当前状态 |
|---|---|---|
| `01_create_vm.sh` | 仅保留为重建参考；当前 VM 已手动创建 | 参考脚本 |
| `02_init_vm.sh` | 安装 Python 环境、HF CLI、`llama-server` 运行依赖 | 待开发 |
| `03_download_model.sh` | 从 HF 下载 `Phi-3-mini-4k-instruct-q4.gguf` 到固定目录 | 待开发 |
| `04_start_service.sh` | 写入并启用两个 systemd unit | 待开发 |
| `05_smoke_test.sh` | 验证 `/health` 与 `/v1/chat/completions` | 待开发 |

### 10.7 最小验证路径

步骤 5 完成后，应至少按以下顺序验证：

1. **VM 访问验证**：deploy SPN 可继续通过 `az vm run-command` 操作 VM
2. **本机健康检查**：VM 内 `curl http://127.0.0.1:11435/health`
3. **sidecar 健康检查**：VM 内 / 内网 `curl http://10.1.1.8:11434/health`
4. **推理调用**：`POST /v1/chat/completions` 返回非空 `choices[0].message.content`
5. **遥测验证**：App Insights 中可查到 `AIGovernTrustworthyVMModelTrace`
6. **后续衔接**：APIM backend 可直接指向 `http://10.1.1.8:11434`
