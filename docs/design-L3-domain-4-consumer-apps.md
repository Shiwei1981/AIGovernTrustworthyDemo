# Domain 4 · Consumer Apps（Tier 1 + Tier 2）设计

## 1. 文档定位

本文档是 `design-L2-domain-4-prerequisites.md` 中**步骤 7：Consumer Apps（Tier 1 + Tier 2）** 的独立 L3 设计文档。

当前版本目标是先沉淀第 7 步的：

- 项目目的与整体架构理解
- 当前已完成工作的上下文整理
- 第 7 步在 Domain 4 中的职责定位
- Tier 1 / Tier 2 Consumer App 的当前需求基线

本版在保持需求基线不变的前提下，继续补充到**详细设计级别**：覆盖应用分层、页面设计、后端路由、数据合同、forwarding 结构、观测实现映射、配置与部署方案，以及后续实现设计。

当前版本已吸收用户在 2026-05-17 的追加确认，固定以下基线：

1. Tier 1 和 Tier 2 都是包含前端与后端的网页程序。
2. Tier 1 同时具备前端对应后端与独立对外 API 两个能力面，但程序实现层面使用同一个 FastAPI 应用。
3. 第 7 步固定演示 10 条调用链路，不再以抽象示例替代。
4. Tier 2 -> Tier 1 调用也必须调用 shared-observability，并进入 Blob 证据链。
5. Native Model 与 Fine-tune Model 在底层仍运行于 AOAI，但第 7 步需求上优先通过 `AIGovernTrustworthyRAGProject` project endpoint 调用，以利用该 Project 的 tracing 能力。
6. 步骤 7 不拆成第一批、第二批或后续批次，10 条链路与两套 UI 一次性纳入完整设计与完整交付范围。
7. Tier 1 / Tier 2 的 UI 都采用 Entra ID 登录后的多选项卡问答界面；多轮对话历史仅保存在浏览器内存中，不做后端持久化。
8. Tier 1 / Tier 2 的中转 API 固定为按 tab 分开的纯转发 API：只负责认证、logging、tracing、shared-observability、raw payload forward，不做请求体和响应体格式归一化。
9. 不同后端协议的 payload 适配发生在浏览器侧 tab adapter，不发生在 APIM，也不发生在 Tier 1 / Tier 2 的 forwarding API。
10. Tier 1 / Tier 2 都必须接入 Application Insights，并分别使用 `.env.local.L4` 中的 `L4_OTEL_SERVICE_NAME_TIER1_APP`、`L4_OTEL_SERVICE_NAME_TIER2_APP` 作为自身的 `OTEL_SERVICE_NAME`。

## 2. 关联文档

| 文档 | 作用 |
|---|---|
| `docs/charters/project-charter.md` | 项目级最高约束 |
| `docs/charters/cross-app-architecture-charter.md` | 跨应用统一技术与交互约束 |
| `docs/design-L1-overview.md` | 整体 dashboard 目的与 Domain 4 在首页中的定位 |
| `docs/design-L2-domain-4-output-trustworthiness.md` | Domain 4 二级页面指标与治理目标 |
| `docs/design-L2-domain-4-prerequisites.md` | 第 7 步所在的 L2 前置条件总文档 |
| `docs/design-L2-domain-4-prerequisites-lowleveldesign.md` | Tier 1 / Tier 2 的环境变量、SPN、Web App、APIM 预置约束 |
| `docs/design-L3-domain-4-apim.md` | APIM `/tier1`、`/tier2` 以及下游统一接入要求 |
| `docs/design-L3-domain-4-monitoring-tracing-logging.md` | Tier 1 / Tier 2 的 tracing、telemetry、evidence 统一规则 |
| `docs/design-L3-domain-4-shared-observability-component.md` | shared-observability 的使用方式与字段规范 |
| `infra/target-registry/targets.json` | 受管目标清单与 target identity 设计 |

## 3. 项目目的与第 7 步定位

### 3.1 本项目的整体目的

本仓库的目标不是做通用 AI 应用样板，而是围绕 Domain 4 建立一个可演示、可验证、可追溯的 **AI Governance demo baseline**，用来证明以下能力可以串成闭环：

1. 有哪些 AI target 被纳管。
2. 各类 target 能否被统一入口调用。
3. 每次调用是否能留下平台 trace、应用遥测和 Blob 证据。
4. 后续 evaluation、red teaming 和 dashboard 是否能基于统一字段做查询与展示。

因此，第 7 步的 Consumer Apps 不是普通业务应用开发任务，而是 Domain 4 中用于证明“**直接 AI 使用**”与“**间接 AI 使用**”都能被治理追踪的关键样板。

### 3.2 第 7 步在整体架构中的位置

第 7 步位于已完成的 target 建设之上，承担两层职责：

1. **Tier 1 Consumer App**：一个包含前端、前端对应后端，以及独立对外 API 的网页程序；作为“直接使用 AI 服务”的标准消费层，对接 RAG、模型、Agent、VM 模型等下游 AI target。
2. **Tier 2 Consumer App**：一个包含前端和前端对应后端的网页程序；作为“间接使用 AI 服务”的上游业务层，通过 Tier 1 API 使用 AI 能力。

补充确认：Tier 1 的“前端对应后端”和“独立对外 API”在需求层次上是两个独立能力面，但在程序实现层面可以落在**同一个 FastAPI 应用**内，由不同路由面承载。

第 7 步的核心价值不是增加新的模型能力，而是把现有 target 组织成一条完整、可追踪、可对外演示的应用调用链。
Caller / Browser / Test Script
        |
        v
APIM
  |- browser -> /tier2
  |- browser -> /tier1
  |- /tier2
  |- /tier1
  |- /rag
  |- /native-model
  |- /finetune-model
  |- /foundry-agent
  |- /copilot-studio
  |- /vm-model
        |
        v
      Tier 2 Web App
        |- frontend
        |- app backend
        |
        v
      Tier 1 Web App
        |- frontend
        |- app backend
        |- public API for external callers
   |    |      |        |         |
   |    |      |        |         +--> VM Hugging Face Model API
         |    |      |        +------------> Foundry Agent
   |    +----------------------------> Foundry Native / Fine-tune Model
   +---------------------------------> RAG Service

Application Insights / Azure Monitor Logs
  |- APIM diagnostics
  |- App telemetry
  |- Foundry tracing / AOAI diagnostics
  |- shared-observability thin events

Blob archive
  |- input.json
  |- output.json
  |- metadata.json
```

### 4.2 架构分层理解

| 层 | 主要对象 | 作用 |
|---|---|---|
| Gateway 层 | APIM | 所有可代理 HTTP hop 的统一入口、trace 起点、受控访问入口 |
| App 层 | Tier 2、Tier 1、RAG Service | 承载用户请求、应用逻辑、证据写入责任 |
| Target 层 | Foundry native model、fine-tune model、Foundry Agent、Copilot Studio Agent、VM model | 被调用的受管 AI target |
| Evidence 层 | App Insights、Blob archive | 查询面与完整证据存储 |

### 4.3 第 7 步必须服从的架构原则

1. 所有可代理下游调用都必须走 APIM，不允许 Tier 1 直接绕开 APIM 调用可代理目标。
2. Tier 1 与 Tier 2 是两个独立 target type，不能合并成一个“AI App”统计对象。
3. Tier 1 前端对应后端与 Tier 1 独立 API 只要发起下游调用，都必须记录自己这一层的 shared-observability evidence；下游对象内部再记录它们自己的 evidence。
4. Tier 2 虽不直接调用底层 AI target，但其后端在调用 Tier 1 API 时，仍按本轮需求记录自己这一层的 shared-observability evidence，用于完整展示间接 AI 使用链路。
5. 不引入重试、缓存、中间存储或多跳 fallback。
6. Tier 1 与 Tier 2 的网页前端都必须遵守跨应用宪章规定的登录优先、英文 UI、异步逐步加载页面内容的约束。
7. 第 7 步是 consumer app 样板层，不重写 RAG、VM、Agent、模型 deployment 本身的已有实现，只负责把这些目标组织进统一调用链。

---

## 5. 当前已完成工作的上下文

### 5.1 步骤状态理解

| 步骤 | 状态 | 与第 7 步的关系 |
|---|---|---|
| 步骤 1 观测基础设施 | 已完成 | 已提供 APIM、App Insights、Blob archive、统一查询面 |
| 步骤 2 RAG Service | 已完成 | Tier 1 的现成下游 target |
| 步骤 3 Foundry 原生模型 | 已完成 | Tier 1 的现成下游 target |
| 步骤 4 Foundry fine-tune 模型 | 已完成 | Tier 1 的现成下游 target |
| 步骤 5 VM Hugging Face 模型 API | 已完成 | Tier 1 的现成下游 target |
| 步骤 6 Agent | Foundry Agent 已完成；Copilot Studio 部分阻塞 | Foundry Agent 已创建并完成 APIM `/foundry-agent` smoke test；Copilot Studio 受 license 阻塞 |

### 5.2 当前已具备的第 7 步前置能力

| 能力 | 当前理解 |
|---|---|
| APIM 实例 | 已存在，且 `/rag`、`/foundry-agent`、`/native-model`、`/finetune-model`、`/vm-model` 已可用 |
| shared-observability 规范 | 已定义，Tier 1 后续需直接接入 |
| target registry | 已存在，可作为 Tier 1 路由和 metadata 的 authoritative input |
| Tier 1 / Tier 2 运行时 SPN | LLD 已定义命名与权限模型 |
| Tier 1 / Tier 2 Web App 命名 | LLD 已定义 `AIGovernTrustworthyDemoTier1App` / `AIGovernTrustworthyDemoTier2App` |
| RAG Project 数据面可调用性 | 2026-05-17 已验证：当前 live deployment `AIGovernTrustworthyDemoNativeModelGPT5.4mini`（`gpt-5.4-mini`）和 `AIGovernTrustworthyDemoFineTuneModel` 可通过 APIM 调用；cognitiveservices 直连路径也已验证 |

### 5.3 当前阻塞与不确定项

| 项目 | 当前状态 | 对第 7 步的影响 |
|---|---|---|
| Foundry Agent APIM 收尾 | 已完成 | Tier 1 `foundry-agent` forwarding API 可按 ready target 接入 |
| Copilot Studio publish / Direct Line | 被正式 license 阻塞 | 不属于当前 10 条链路；若后续恢复范围，必须单独标记为 blocked |
| Tier 1 / Tier 2 Web App 尚未创建 | 待开始 | 第 7 步本身要交付 |

---

## 6. 第 7 步的范围、目标与非目标

### 6.1 范围

第 7 步覆盖以下对象：

1. Tier 1 Web App（前端 + 前端对应后端 + 独立对外 API）
2. Tier 2 Web App（前端 + 前端对应后端）
3. Tier 1 对下游 target 的 forwarding 约束
4. Tier 1 / Tier 2 的 APIM 接入要求
5. Tier 1 / Tier 2 的 telemetry、trace、evidence 与 KQL 验证要求
6. 第 7 步要求必须展示的 10 条调用链路

### 6.2 目标

第 7 步需要实现以下目标：

1. 提供一条“浏览器或外部程序 -> Tier 2 -> Tier 1 -> AI target”的可追溯样板链路。
2. 提供一条“浏览器或外部程序 -> Tier 1 -> AI target”的可追溯样板链路。
3. 让 Tier 1 成为步骤 2-6 已有 target 的统一消费层。
4. 让 Tier 2 成为“间接 AI 使用”治理场景的证明对象。
5. 让 Tier 1 同时具备终端用户网页程序和独立 API 集成入口两种形态。
6. 为后续 evaluation、red teaming、dashboard 提供可复用的 app target。
7. 让终端用户在浏览器里可直接触发 10 条目标链路中的对应请求，而不仅限于脚本调用。

### 6.3 非目标

本步骤当前不做以下事情：

1. 不重新设计或改造步骤 2-6 已完成 target 的内部实现。
2. 不建设复杂的会话管理、缓存、队列、重试或异步任务系统。
3. 不把 Tier 1 做成通用 API gateway；统一 gateway 仍然是 APIM。
4. 不在本轮把 Copilot Studio Agent 纳入第 7 步的必展示链路范围。
5. 不追求复杂前端体验；网页程序以最小可用展示和链路验证为主。

---

## 7. 第 7 步需求基线

### 7.1 共同需求

#### R7-001 独立 target type

Tier 1 与 Tier 2 必须作为两个独立 target type 存在：

- Tier 1 = `tier1_consumer`
- Tier 2 = `tier2_consumer`

不得合并统计，不得以单一“consumer app”替代。

#### R7-002 统一技术栈网页程序形态

Tier 1 与 Tier 2 都必须是遵循项目宪章的网页程序：

1. 前端使用 HTML5 + Bootstrap + 原生 JavaScript。
2. 后端使用 FastAPI。
3. 前后端打包为同一应用交付单元。
4. 页面 UI 仅使用英文。

#### R7-002A 登录与页面加载规则

Tier 1 与 Tier 2 的前端页面都必须遵守项目宪章中的 UI 规则：

1. 需要用户操作的页面先要求登录。
2. 登录后在登录按钮下显示当前 Entra ID 用户账户。
3. 登录按钮在登录后变为切换用户按钮。
4. 页面打开后采用异步加载模式，逐步填充数字、列表、结果区和链路展示区。
5. 不开发管理员后台维护功能。

#### R7-003 Tier 1 / Tier 2 功能形态

1. Tier 1 必须同时包含前端、前端对应后端，以及独立的对外 API，供其他程序调用。
2. Tier 2 必须包含前端和前端对应后端。
3. Tier 1 的独立 API 与前端后端固定复用同一个 FastAPI 应用，但必须作为明确可被外部程序调用的受控接口存在。

#### R7-003A 前端能力边界

1. Tier 1 前端是一个直接 AI 使用演示页面，应允许用户选择 5 条直连链路之一并查看结果、trace 相关标识以及可追溯元数据。
2. Tier 2 前端是一个间接 AI 使用演示页面，应允许用户选择 5 条经 Tier 1 的链路之一并查看结果、trace 相关标识以及可追溯元数据。
3. 前端页面本身不直接调用底层 AI target，也不直接访问 Blob 或 App Insights；相关数据由各自后端提供。

#### R7-004 全部 API 调用统一走 APIM

Tier 1 与 Tier 2 对外入口都必须先挂到 APIM：

- Tier 1 入口固定为 `APIM /tier1`
- Tier 2 入口固定为 `APIM /tier2`

并且以下调用都必须优先走 APIM，而不是硬编码直连 endpoint：

- Tier 1 -> RAG API
- Tier 1 -> Foundry Agent API
- Tier 1 -> VM LLM API
- Tier 1 -> Native Model API
- Tier 1 -> Fine-tune Model API
- Tier 2 -> Tier 1 API

APIM 必须对所有经过的消息向 App Insights 提交 tracing / diagnostics 记录。

对链路中的 Native Model 与 Fine-tune Model，需求基线固定为优先采用 `AIGovernTrustworthyRAGProject` project endpoint 调用路径，以利用该 Project 的 tracing 能力；AOAI 仍然是底层模型 hosting 平面。

#### R7-004A Native / Fine-tune 模型调用语义

1. Native Model 当前 live deployment 为 `AIGovernTrustworthyDemoNativeModelGPT5.4mini`（`gpt-5.4-mini` `2026-03-17`），归属 `aigoverntrustworthyfoundry` cognitiveservices account；`AIGovernTrustworthyDemoFineTuneModel` 的底层 deployment 仍归属 AOAI / Foundry account。
2. 第 7 步 consumer app 的需求基线不是“继续优先走 AOAI deployment 直连路径”，而是“优先走 `AIGovernTrustworthyRAGProject` project endpoint 的模型调用路径”。
3. 使用该 Project 入口的核心目的，是让 Native / Fine-tune 链路纳入该 Project 的 tracing 能力。
4. 直连 AOAI deployment 仍保留为底层烟测和排障路径，但不是第 7 步 consumer app 的首选调用面。

#### R7-005 禁止任意 URL 透传

Tier 1 和 Tier 2 都不得接受调用方传入任意下游 URL。调用路由必须基于受控 target identity 完成，避免绕开 target registry 与治理边界。

#### R7-006 错误即终止

任一 hop 失败后不得自动重试、降级到其他 target 或静默吞错。应用应直接返回错误，保留原始错误信息以供分析。

#### R7-007 运行时身份与用户身份分离

应用运行时访问下游资源时，使用各自运行时 SPN。用户登录身份仅用于应用访问控制，不向 AI target、Blob、App Insights 或数据层透传用户 token。

#### R7-008 必须展示的 10 条调用链路

第 7 步的需求基线固定包含以下 10 条链路，后续实现与验证必须覆盖：

1. Tier 1 -> RAG API
2. Tier 1 -> Foundry Agent API
3. Tier 1 -> VM LLM API
4. Tier 1 -> `AIGovernTrustworthyRAGProject` 下的 `AIGovernTrustworthyDemoNativeModel`
5. Tier 1 -> `AIGovernTrustworthyRAGProject` 下的 `AIGovernTrustworthyDemoFineTuneModel`
6. Tier 2 -> Tier 1 API -> RAG API
7. Tier 2 -> Tier 1 API -> Foundry Agent API
8. Tier 2 -> Tier 1 API -> VM LLM API
9. Tier 2 -> Tier 1 API -> `AIGovernTrustworthyRAGProject` 下的 `AIGovernTrustworthyDemoNativeModel`
10. Tier 2 -> Tier 1 API -> `AIGovernTrustworthyRAGProject` 下的 `AIGovernTrustworthyDemoFineTuneModel`

#### R7-009 统一元数据输出

Tier 1 和 Tier 2 都必须暴露 `GET /ui/bootstrap` 或受控等价 metadata 接口，返回至少包括：

- 当前 app identity
- app target_type / target_id
- 可用 API 列表
- 当前版本
- 运行环境
- 下游 target 就绪状态摘要

并且至少应能向前端或外部调用者暴露以下辅助信息：

- 当前应用使用的 APIM base URL
- 对 Native / Fine-tune 是否使用 Project 入口
- 当前页面或调用请求所属链路名称

---

### 7.2 Tier 1 Consumer App 需求

#### R7-101 角色定位

Tier 1 是“直接调用 AI 服务”的标准消费网页程序，包含面向终端用户的前端、承接前端调用的应用后端，以及供其他程序调用的独立 API。只要 Tier 1 任一后端入口发起下游调用，都必须记录 Tier 1 caller-side evidence。

#### R7-102 最小 API 合同

Tier 1 首版至少必须提供以下对外 API：

1. `POST /api/chat/rag`
2. `POST /api/chat/foundry-agent`
3. `POST /api/chat/vm-model`
4. `POST /api/chat/native-model`
5. `POST /api/chat/finetune-model`
6. `GET /health`
7. `GET /ui/bootstrap`

同时，Tier 1 的网页后端还需要提供承接前端页面调用的应用路由；这些路由可以与独立 API 共处于同一个 FastAPI 应用中，但需求语义上仍需区分“前端后端调用面”和“外部程序集成 API 调用面”。

#### R7-103 Tier 1 raw forwarding 请求语义

Tier 1 的 5 个 `/api/chat/*` forwarding API 固定采用“按 path 选目标、按 body 原样透传”的语义：

1. path 本身决定目标类型，不再要求调用方在 body 中再传一次 `target_id` 作为路由主键。
2. body 由浏览器 tab adapter 或外部程序集成调用方按目标协议自行构造；Tier 1 不再把 `input` / `options` 重新拼装成统一请求格式。
3. Tier 1 负责认证、trace 透传或补齐、logging、shared-observability、raw payload forward，以及把下游响应包装成统一的治理返回外壳。
4. Tier 1 不负责在 forwarding API 内做 payload 格式归一化，也不负责猜测缺失业务参数。

#### R7-104 target 解析必须基于受控清单

Tier 1 必须基于 `infra/target-registry/targets.json` 或其后续受控等价配置，解析当前 forwarding path 对应的：

- `target_type`
- APIM path
- 调用协议形态
- 当前状态（ready / active / pending / blocked）

如果目标状态不是可调用状态，Tier 1 必须明确返回“未就绪/被阻塞”，而不是尝试调用。

#### R7-105 当前纳入第 7 步的下游覆盖范围

从本轮需求角度，Tier 1 当前必须覆盖以下 target type：

1. `rag_service`
2. `foundry_agent`
3. `vm_huggingface_model`
4. `foundry_native_model`
5. `foundry_finetune_model`

`copilot_studio_agent` 暂不纳入第 7 步当前必展示链路，因为用户本轮没有把它列入 10 条目标链路，且步骤 6 仍受正式 license 阻塞。

#### R7-106 forwarding 形态要求

Tier 1 必须按 target type 拆分 forwarding route 与 metadata 约束，至少保持以下差异：

1. 对 RAG 服务，记录“调用 RAG API”的 caller evidence，而不是伪装成直接模型调用。
2. 对 Foundry Agent，记录“调用 Agent API”的 caller evidence。
3. 对 Foundry native / fine-tune / VM model，记录“直接调用模型 API”的 caller evidence。
4. Tier 1 的页面后端路径和独立对外 API 路径如果都能发起下游调用，则两条代码路径都必须显式调用 shared-observability，而不能只在某个共用转发函数的局部分支记录。
5. 对 Native Model 与 Fine-tune Model，forwarding route 的首选调用面应是 `AIGovernTrustworthyRAGProject` 的 project endpoint，而不是绕开 Project 直接命中 AOAI deployment endpoint。

#### R7-107 evidence 写入要求

Tier 1 对每次实际下游 AI 调用，无论成功或失败，都必须调用 shared-observability 写入证据。

要求如下：

1. 记录的是“Tier 1 -> 下游 target”这一层调用。
2. 对 RAG / Agent 调用，`model_name` 与 `model_version` 允许为空，由下游自身补齐内部模型身份记录。
3. 对 Foundry native / fine-tune / VM model 调用，应尽量补齐 `model_name`、`model_version`、`response_id`。
4. Evidence 必须与当前 `trace_id` 可关联。
5. Tier 1 面向其他程序的独立 API 在转发到下游 AI target 时，也必须写相同规则的 evidence。

#### R7-108 返回结果要求

Tier 1 的 `/api/chat/*` 返回体首版必须至少包含：

- `target_id`
- `target_type`
- `status`
- `output` 或等效响应正文
- `response_id`（若下游可得）
- `trace_id`（若当前请求上下文可得）
- `model_name` / `model_version`（若调用层可得）
- `citations`（仅当下游为 RAG 且返回了 citation）

并建议补充：

- `archive_id` / `payload_ref`（若本层 evidence 已成功写入）
- `downstream_archive_id`（若下游 API 响应中返回可关联 archive）
- `invocation_route`（标识本次调用来自 Tier 1 页面后端还是 Tier 1 独立 API）

#### R7-109 就绪状态显式暴露

Tier 1 必须在 `GET /ui/bootstrap` 或其受控等价 metadata 接口中显式区分：

- 已可调用 target
- 配置存在但当前未就绪 target
- 被外部前置条件阻塞的 target

这样第 7 步不会因为步骤 6 尚未完全闭环而在行为上模糊化。

---

### 7.3 Tier 2 Consumer App 需求

#### R7-201 角色定位

Tier 2 是“通过 Tier 1 间接使用 AI”的标准上游网页程序。它不直接调用底层 AI target，但其后端会调用 Tier 1 API，并按本轮需求对这条上游到 Tier 1 的治理调用链记录 shared-observability evidence。

#### R7-202 最小 API 合同

Tier 2 首版必须提供以下 API：

1. `POST /api/chat/rag`
2. `POST /api/chat/foundry-agent`
3. `POST /api/chat/vm-model`
4. `POST /api/chat/native-model`
5. `POST /api/chat/finetune-model`
6. `GET /health`
7. `GET /ui/bootstrap`

同时，Tier 2 的网页后端也需要提供承接前端页面调用的应用路由；这些路由不另建第二个后端进程，而是与其 FastAPI 应用同进程实现。

#### R7-203 Tier 2 raw forwarding 请求语义

Tier 2 的 5 个 `/api/chat/*` forwarding API 固定采用“按 path 选 Tier 1 route、按 body 原样透传”的语义：

1. 浏览器在不同 tab 中直接构造面向最终目标协议的 raw body。
2. Tier 2 不负责解释不同 target type 的具体调用协议，只负责把当前 path 对应的 body 原样转发到 Tier 1 同名 forwarding API。
3. Tier 2 负责记录 `Tier 2 -> Tier 1` 这一跳的 request / response / exception telemetry 与 shared-observability evidence。

#### R7-204 Tier 2 只能调用 Tier 1

Tier 2 到下游的唯一业务调用目标是 Tier 1 的 APIM 入口，不允许直接调用：

- `/rag`
- `/native-model`
- `/finetune-model`
- `/foundry-agent`
- `/copilot-studio`
- `/vm-model`

#### R7-205 logging 与 telemetry 边界

Tier 2 必须记录自身 request / response / exception telemetry，并保持 `traceparent` 透传。同时，Tier 2 后端在调用 Tier 1 API 时，必须调用 shared-observability，把这条“间接 AI 使用入口调用”记录下来，用于完整展示 Tier 2 -> Tier 1 -> AI target 链路。

#### R7-206 返回结果要求

Tier 2 的 `/api/chat/*` 首版返回体可以沿用 Tier 1 的主体结果，但需要额外标明：

- 本次请求由 `tier2_consumer` 发起
- 实际 AI 调用由下游 Tier 1 与更下游对象完成

并建议补充：

- `archive_id` / `payload_ref`（若 Tier 2 这一层 evidence 已成功写入）
- `tier1_trace_id` 或可等效定位到 Tier 1 层的关联字段
- `invocation_route`（标识本次请求来自 Tier 2 前端后端）

#### R7-207 Tier 2 必须覆盖的链路

Tier 2 首版必须支持以下 5 条链路：

1. Tier 2 -> Tier 1 API -> RAG API
2. Tier 2 -> Tier 1 API -> Foundry Agent API
3. Tier 2 -> Tier 1 API -> VM LLM API
4. Tier 2 -> Tier 1 API -> Native Model API
5. Tier 2 -> Tier 1 API -> Fine-tune Model API

---

### 7.4 Tracing、Telemetry 与 Evidence 需求

#### R7-301 Tier 1 tracing 要求

Tier 1 必须满足以下 tracing / telemetry 要求：

1. 自身入口经过 `APIM /tier1`。
2. 自身 request、dependency、exception telemetry 写入 App Insights。
3. 对每次实际下游 AI 调用写 shared-observability thin event + Blob evidence。
4. 调用下游时透传当前 trace context。
5. Tier 1 前端对应后端发起的下游调用和 Tier 1 独立 API 发起的下游调用都必须满足以上规则。
6. Tier 1 Trace Chain 后端在按 `payload_ref` / `archive_id` 展开 Blob archive 时，必须直接使用 Tier 1 运行时 SPN 访问 Observability Blob Storage；不得依赖本地 blob viewer 或额外旁路服务。

#### R7-302 Tier 2 tracing 要求

Tier 2 必须满足以下 tracing / telemetry 要求：

1. 自身入口经过 `APIM /tier2`。
2. 自身 request、dependency、exception telemetry 写入 App Insights。
3. 调用 Tier 1 时透传当前 trace context。
4. 调用 Tier 1 时写 shared-observability thin event + Blob evidence，记录 Tier 2 这一层间接 AI 使用入口调用。
5. Tier 2 Trace Chain 后端必须由 Tier 2 Web App 自己查询 App Insights 与 Blob archive，不能把 Trace Chain 汇总逻辑代理给 Tier 1。

#### R7-303 分层记录原则

必须遵守“每一层只记录自己发出的那次调用”：

1. Tier 2 记录自己接到请求并调用 Tier 1。
2. Tier 1 记录自己调用 RAG / Agent / Model / VM API。
3. VM LLM API 继续记录其自身内部模型调用。
4. RAG 服务再记录自己内部调用模型。

不得把同一层已经发生的单个 hop 重复伪造成多条同层 evidence；但不同层各自记录自己发出的那次调用，是本设计要求。

#### R7-303A 10 条链路与记录层映射

第 7 步的 10 条链路在观测层面应至少形成如下分层记录：

1. Tier 1 直连链路：APIM `/tier1` + Tier 1 evidence + 下游 target 平台日志或下游 evidence。
2. Tier 2 间接链路：APIM `/tier2` + Tier 2 evidence + APIM `/tier1` + Tier 1 evidence + 下游 target 平台日志或下游 evidence。
3. RAG 链路额外包含 RAG 服务内部 LLM evidence。
4. VM 链路额外包含 VM sidecar telemetry 与 VM 服务自身 shared-observability 记录。
5. Native / Fine-tune 经 Project 入口的链路额外要求存在 Foundry Project tracing。

#### R7-305 Foundry tracing 要求

对所有属于 Foundry 可控范围的链路，必须要求 Foundry 将 tracing 记录提交到 App Insights。当前第 7 步涉及的 Foundry 可控范围至少包括：

1. Foundry Agent API 链路。
2. 经 `AIGovernTrustworthyRAGProject` 调用的 Native Model 链路。
3. 经 `AIGovernTrustworthyRAGProject` 调用的 Fine-tune Model 链路。

第 7 步实现时不得只依赖 Tier 1 / Tier 2 自身 telemetry 代替 Foundry tracing。

#### R7-306 最终可观察性目标

第 7 步的最终目标不是只看到单点日志，而是满足以下联合查询能力：

1. 在 App Insights 内，可沿同一 `trace_id` 观察完整调用链。
2. 对链路中至少由应用侧记录过的调用，可通过 `archive_id`、`payload_ref` 或其他关联信息跳转到 Blob archive。
3. 能在 Blob archive 查询到链路中记录过的 LLM `input` 与 `output`。
4. APIM、应用、Foundry、VM 各层记录能被拼接成一个完整演示链路。
5. 对 Native / Fine-tune 链路，App Insights 中除 APIM 记录外，还应能观察到来自 `AIGovernTrustworthyRAGProject` tracing 相关记录。
6. Tier 1 / Tier 2 部署到各自 Web App 后，Trace Chain 必须在不依赖 blob viewer 进程的情况下独立工作。

#### R7-304 统一字段要求

第 7 步涉及的 telemetry / evidence 必须尽量补齐以下字段：

- `target_type`
- `target_id`
- `trace_id`
- `span_id`
- `response_id`
- `model_name`
- `model_version`
- `test_tool`（后续 runner 场景）
- `test_run_id`（后续 runner 场景）
- `archive_id`
- `payload_ref`
- `status`

---

### 7.5 配置与部署需求

#### R7-401 运行时配置来源

Tier 1 / Tier 2 首版实现应优先复用 `.env.local.L4` 中已定义变量命名，不重新发明一套新命名。

#### R7-402 Web App 与运行时身份

按当前 LLD 约束：

- Tier 1 Web App 名称：`AIGovernTrustworthyDemoTier1App`
- Tier 2 Web App 名称：`AIGovernTrustworthyDemoTier2App`
- Tier 1 运行时身份：`AIGovernTrustworthyDemoTier1AppSPN`
- Tier 2 运行时身份：`AIGovernTrustworthyDemoTier2AppSPN`

#### R7-403 Web App 与 Service Plan 部署约束

1. Tier 1 与 Tier 2 使用各自独立的 Web App。
2. Tier 1 与 Tier 2 使用各自独立的运行时 SPN。
3. Web App Service Plan 复用现有已存在的 Plan，不新建平行 Plan。
4. Tier 1 Web App 与 Tier 2 Web App 在 Azure 部署层面分开，但各自内部前后端仍打包为单一应用。
5. blob viewer 不属于步骤 7 的部署单元；Tier 1 Trace API 与 Tier 2 Trace API 都各自直接读取 App Insights 与 Blob archive，不额外引入第三个 Trace Chain 运行组件，也不要求 Tier 2 代理 Tier 1 的 Trace API。

---

### 7.6 验证需求

#### R7-501 Tier 1 直连验证

必须能验证：外部调用者经 `APIM /tier1` 调用某个已就绪 target 后，可以同时看到：

1. APIM hop
2. Tier 1 App telemetry
3. 下游 target 平台日志或 caller evidence
4. Blob archive 记录

#### R7-502 Tier 2 间接链路验证

必须能验证：外部调用者经 `APIM /tier2` 发起请求后，可通过同一 `trace_id` 追踪到：

1. Tier 2 request
2. Tier 2 -> Tier 1 hop
3. Tier 1 -> 下游 target hop
4. 下游 evidence / 平台日志

#### R7-503 必须覆盖的验证链路

第 7 步后续验证必须按需求基线覆盖以下 10 条链路：

1. Tier 1 -> RAG
2. Tier 1 -> Foundry Agent
3. Tier 1 -> VM model
4. Tier 1 -> Native model
5. Tier 1 -> Fine-tune model
6. Tier 2 -> Tier 1 -> RAG
7. Tier 2 -> Tier 1 -> Foundry Agent
8. Tier 2 -> Tier 1 -> VM model
9. Tier 2 -> Tier 1 -> Native model
10. Tier 2 -> Tier 1 -> Fine-tune model

并且这些验证不只要求“拿到业务响应”，还要求同时验证：

1. APIM 记录存在。
2. App 层 evidence 存在。
3. 适用时的 Foundry tracing 存在。
4. 可通过 `trace_id` 与 Blob archive 关联到 input / output 证据。

---

## 8. 当前需求结论

基于当前项目目的、整体架构和已完成工作，第 7 步的首版需求结论如下：

1. 第 7 步本质上是 **Consumer App 治理链路样板层**，不是新的模型能力建设。
2. Tier 1 是直接 AI 使用样板，同时必须具备网页程序入口和独立 API 入口两种形态。
3. Tier 2 是间接 AI 使用样板，本轮需求要求它对 Tier 2 -> Tier 1 这一层调用也写 shared-observability 记录。
4. 第 7 步的演示目标固定为 10 条调用链路，而不是抽象的“任选几条示例链路”。
5. `AIGovernTrustworthyRAGProject` project endpoint 已验证可直接调用 Native / Fine-tune Model，因此步骤 7 可以把该 Project 作为模型调用入口与 tracing 入口。

---

## 9. 待确认问题

当前没有新增待确认问题。本轮用户已经确认以下设计决定：

1. Native Model 与 Fine-tune Model 在底层仍然运行于 AOAI，但步骤 7 需求上优先通过 `AIGovernTrustworthyRAGProject` project endpoint 调用，以利用该 Project 的 tracing 能力。
2. Tier 2 -> Tier 1 调用也需要调用 shared-observability，并进入 Blob 证据链。
3. Tier 1 的前端对应后端与独立 API 在需求层次上独立，但程序实现层面使用同一个 FastAPI 应用。

## 10. 详细设计总览

### 10.1 设计目标

本详细设计的目标不是把 Tier 1 / Tier 2 做成通用产品，而是交付两套最小但完整、可部署、可验证、可追踪的 consumer apps，使第 7 步能稳定演示 10 条链路。

详细设计必须同时满足以下目标：

1. 前后端同应用交付，符合统一技术栈约束。
2. 外部调用路径、浏览器页面路径、下游 target 调用路径都清晰分层。
3. 所有链路都能映射到统一的 APIM、Foundry tracing、App Insights 和 Blob evidence 设计。
4. 设计出的路由、模块和数据合同足以直接进入代码实现。

### 10.2 选定实现策略

本轮详细设计固定采用以下策略：

1. Tier 1 使用单个 FastAPI 应用，同时承载：页面路由、页面后端路由、外部程序调用 API。
2. Tier 2 使用单个 FastAPI 应用，同时承载：页面路由、页面后端路由、对 Tier 1 的转发 API。
3. 浏览器统一通过 APIM `/tier1` 与 `/tier2` 进入对应 Web App。
4. Tier 1 UI 和 Tier 2 UI 都采用“多 tab + 多轮问答”的前端模型；每个 tab 在浏览器内存中独立维护自己的 `messages` 历史。
5. Tier 1 对下游 RAG / Agent / VM / Native / Fine-tune 的调用统一经 APIM。
6. Tier 1 / Tier 2 的 forwarding API 不做统一 query contract，也不做统一 response contract；每条 tab API 直接转发该 tab 对应的 raw downstream payload。
5. Native / Fine-tune 两条模型链路在步骤 7 中不再以 AOAI deployment 直连为主，而是要求 APIM 背后切到 `AIGovernTrustworthyRAGProject` project data plane，并使用 `https://ai.azure.com` audience 获取 token。

### 10.3 与现状的衔接方式

当前仓库已有一些“现状实现”与“步骤 7 目标设计”不完全一致，详细设计采用以下衔接原则：

1. 保留现有 `/native-model`、`/finetune-model` APIM path，不额外新造 consumer-facing path。
2. 允许在步骤 7 实施时把这两个 path 的 backend 从 AOAI deployment 直连模式切换到 Project-backed 模式。
3. 直连 AOAI deployment 的脚本和验证能力继续保留，作为底层烟测与排障路径。
4. target registry 在进入实现前需要对齐到 Project-backed 调用语义，但当前文档阶段不直接改动 registry 文件。

### 10.4 10 条链路到受控目标的固定映射

步骤 7 首版不允许页面或 API 调用方自定义链路含义。10 条演示链路固定映射到以下受控 target：

| 演示链路 | App 入口 | 下游 `target_id` | 下游 `target_type` | `targets.json` 当前状态 | 首版行为要求 |
|---|---|---|---|---|---|
| Tier 1 -> RAG API | `/tier1/app` + `/tier1/api/chat/rag` | `AIGovernTrustworthyDemoRAGService` | `rag_service` | `pending` | 属于步骤 7 最终交付范围；若其前置未补齐，步骤 7 不得视为完成 |
| Tier 1 -> Foundry Agent API | `/tier1/app` + `/tier1/api/chat/foundry-agent` | `AIGovernTrustworthyDemoFoundryAgent` | `foundry_agent` | `active` | 属于步骤 7 最终交付范围 |
| Tier 1 -> VM LLM API | `/tier1/app` + `/tier1/api/chat/vm-model` | `AIGovernTrustworthyDemoPhi3VM` | `vm_huggingface_model` | `ready` | 属于步骤 7 最终交付范围 |
| Tier 1 -> Native Model via Foundry Project | `/tier1/app` + `/tier1/api/chat/native-model` | `AIGovernTrustworthyDemoNativeModel` | `foundry_native_model` | `active` | 属于步骤 7 最终交付范围 |
| Tier 1 -> FineTune Model via Foundry Project | `/tier1/app` + `/tier1/api/chat/finetune-model` | `AIGovernTrustworthyDemoFineTuneModel` | `foundry_finetune_model` | `active` | 属于步骤 7 最终交付范围 |
| Tier 2 -> Tier 1 -> RAG API | `/tier2/app` + `/tier2/api/chat/rag` | `AIGovernTrustworthyDemoRAGService` | `rag_service` | `pending` | 属于步骤 7 最终交付范围；若其前置未补齐，步骤 7 不得视为完成 |
| Tier 2 -> Tier 1 -> Foundry Agent API | `/tier2/app` + `/tier2/api/chat/foundry-agent` | `AIGovernTrustworthyDemoFoundryAgent` | `foundry_agent` | `active` | 属于步骤 7 最终交付范围 |
| Tier 2 -> Tier 1 -> VM LLM API | `/tier2/app` + `/tier2/api/chat/vm-model` | `AIGovernTrustworthyDemoPhi3VM` | `vm_huggingface_model` | `ready` | 属于步骤 7 最终交付范围 |
| Tier 2 -> Tier 1 -> Native Model via Foundry Project | `/tier2/app` + `/tier2/api/chat/native-model` | `AIGovernTrustworthyDemoNativeModel` | `foundry_native_model` | `active` | 属于步骤 7 最终交付范围 |
| Tier 2 -> Tier 1 -> FineTune Model via Foundry Project | `/tier2/app` + `/tier2/api/chat/finetune-model` | `AIGovernTrustworthyDemoFineTuneModel` | `foundry_finetune_model` | `active` | 属于步骤 7 最终交付范围 |

补充约束：

1. Tier 2 的业务请求体仍然只携带最终下游 `target_id`，但 Tier 2 自己写 evidence 时，该 hop 的 `target_type` 固定为 `tier1_consumer`。
2. Tier 1 / Tier 2 前端下拉框中的选项必须和上表一一对应，不允许出现 registry 以外的自由文本目标。
3. 10 条链路必须在同一个步骤 7 交付范围中统一设计、统一实现、统一验证，不再拆成第一批、第二批或后续批次。

### 10.4A 10 条链路逐条参数映射与 Trace 责任矩阵

为避免后续实现时把“统一入口”误做成“统一下游 payload”，步骤 7 对 10 条链路的参数适配和 trace 责任点固定如下。

| 链路 | 上游统一请求 | 下游参数适配 | 参数过滤 / 忽略规则 | Trace 责任点 |
|---|---|---|---|---|
| Tier 1 -> RAG API | 浏览器在 `rag` tab 内维护 `messages` 历史，但提交到 Tier 1 `/api/chat/rag` 时必须先在前端适配为 RAG 可接受的 raw body | Tier 1 API 不改写 body，原样转发到 `/rag/responses` | RAG tab 的多轮效果由浏览器拼接上下文实现，不要求 RAG forwarding API 自己理解 `messages` | Tier 1 保留入口 trace；调用 `/rag` 时透传 `traceparent` / `tracestate`；Tier 1 与 RAG 都写 evidence，并用同一 `trace_id` 关联 |
| Tier 1 -> Foundry Agent API | 浏览器在 `foundry-agent` tab 内维护 `messages` 历史，并在前端适配为 Agent API 实际需要的 raw payload | Tier 1 API 不改写 body，原样转发到 `/foundry-agent/...` | Agent 所需特有字段在浏览器侧构造，不在中转 API 内补齐 | Tier 1 保留入口 trace；调用 `/foundry-agent` 时透传 trace headers；Tier 1 evidence 与 Foundry tracing 通过同一 `trace_id` 关联 |
| Tier 1 -> VM LLM API | 浏览器在 `vm-model` tab 内维护 `messages` 历史，并直接构造 VM API 支持的 raw body | Tier 1 API 不改写 body，原样转发到 `/vm-model/v1/chat/completions` | 是否支持 `temperature`、`max_tokens` 由浏览器侧 adapter 按 VM 实际能力决定 | Tier 1 保留入口 trace；调用 `/vm-model` 时透传 trace headers；VM sidecar 必须沿用同一 `trace_id` 写入自身 telemetry |
| Tier 1 -> Native Model via Foundry Project | 浏览器在 `native-model` tab 内维护 `messages` 历史，并直接构造 `/native-model/chat/completions` raw body，显式带 `model=AIGovernTrustworthyDemoNativeModelGPT5.4mini` | Tier 1 API 不改写 body，原样转发到 `/native-model/chat/completions` | `model` 由浏览器 adapter 明确写入，不依赖 APIM 兼容注入 | Tier 1 保留入口 trace；调用 `/native-model` 时透传 trace headers；Tier 1 evidence 与 APIM diagnostics 共享同一主 `trace_id` |
| Tier 1 -> FineTune Model via Foundry Project | 浏览器在 `finetune-model` tab 内维护 `messages` 历史，并直接构造 `/finetune-model/chat/completions` raw body，显式带 `model=AIGovernTrustworthyDemoFineTuneModel` | Tier 1 API 不改写 body，原样转发到 `/finetune-model/chat/completions` | `model` 由浏览器 adapter 明确写入，不依赖 APIM 兼容注入 | Tier 1 保留入口 trace；调用 `/finetune-model` 时透传 trace headers；Tier 1 evidence、APIM diagnostics、Foundry Project tracing 共享同一主 `trace_id` |
| Tier 2 -> Tier 1 -> RAG API | 浏览器在 Tier 2 `rag` tab 内维护 `messages` 历史，并先在前端适配为 RAG raw body | Tier 2 `/api/chat/rag` 不改写 body，原样转发给 Tier 1 `/api/chat/rag` | Tier 2 不做格式归一化；Tier 1 同样不改写 body | Browser / APIM `/tier2` 进入后生成或接续 trace；Tier 2 调 Tier 1 时透传 trace headers；Tier 2 写 hop evidence，Tier 1 与 RAG 继续复用同一 `trace_id` |
| Tier 2 -> Tier 1 -> Foundry Agent API | 浏览器在 Tier 2 `foundry-agent` tab 内构造 Agent raw payload | Tier 2 `/api/chat/foundry-agent` 原样转发给 Tier 1 同名 API | Tier 2 与 Tier 1 都不新增 agent 字段 | Tier 2 调 Tier 1 时透传 trace headers 并记录本 hop evidence；Tier 1 再把同一 trace 透传给 `/foundry-agent` |
| Tier 2 -> Tier 1 -> VM LLM API | 浏览器在 Tier 2 `vm-model` tab 内构造 VM raw payload | Tier 2 `/api/chat/vm-model` 原样转发给 Tier 1 同名 API | Tier 2 与 Tier 1 都不推断 VM 额外参数 | Tier 2 保留外层 `trace_id`；Tier 1 调 `/vm-model` 时继续透传；Tier 2 evidence、Tier 1 evidence、VM telemetry 必须串成同一 trace |
| Tier 2 -> Tier 1 -> Native Model via Foundry Project | 浏览器在 Tier 2 `native-model` tab 内构造 Native raw payload | Tier 2 `/api/chat/native-model` 原样转发给 Tier 1 同名 API | Tier 2 与 Tier 1 都不改写 `messages` / `model` 等字段 | Tier 2 调 Tier 1 时透传 trace headers 并记录本 hop evidence；Tier 1 调 `/native-model` 时继续透传；Tier 2、Tier 1、APIM、Foundry tracing 用同一 `trace_id` 关联 |
| Tier 2 -> Tier 1 -> FineTune Model via Foundry Project | 浏览器在 Tier 2 `finetune-model` tab 内构造 FineTune raw payload | Tier 2 `/api/chat/finetune-model` 原样转发给 Tier 1 同名 API | Tier 2 与 Tier 1 都不改写 `messages` / `model` 等字段 | Tier 2 调 Tier 1 时透传 trace headers 并记录本 hop evidence；Tier 1 调 `/finetune-model` 时继续透传；Tier 2、Tier 1、APIM、Foundry tracing 用同一 `trace_id` 关联 |

固定实施约束：

1. 这张矩阵优先级高于“看起来相似的接口路径”。即使 VM、Native、FineTune 都表现为 chat API，也不允许共享未经校验的 raw payload 模板。
2. Tier 1 与 Tier 2 的 forwarding API 都不做 body 适配；不同 backend 的请求体构造发生在浏览器侧 tab adapter。
3. tab 切换只在前端内存中发生，不触发后端 postback；关闭页面后历史自然丢失，不做任何持久化恢复。
4. 任何链路只要发生 trace header 缺失、下游未返回可关联字段，或原样转发失败，都必须在 UI、API 返回或日志中留下可诊断信息。

### 10.5 错误传播原则

步骤 7 的错误处理直接服从项目宪章，不单独设计复杂状态机、重试或备份链路。

固定原则如下：

1. 任一调用失败后立即终止后续步骤，不做自动重试，不做 fallback，不做静默降级。
2. 错误必须同时出现在 UI、API 响应和应用控制台日志中，内容以“足够分析问题”为目标，不做抽象化美化。
3. 对输入缺失、`target_id` 不存在、配置缺失、下游返回失败、shared-observability 写入失败等情况，都直接返回详细错误信息。
4. 对 registry 中当前仍为 `pending` 或受外部条件阻塞的链路，页面仍显示该链路，但执行时直接返回错误详情，并同时展示当前 registry 状态。
5. `request_id`、`trace_id`、`target_id`、`target_type` 仍应包含在错误响应中，便于后续从 UI 跳到控制台和 App Insights 继续分析。

### 10.6 UI 共享设计建议

Tier 1 与 Tier 2 的 UI 不应被设计成“普通聊天页面”，而应被设计成“治理调用控制台”。首版建议采用以下共享设计原则。

#### 视觉方向

1. 整体气质应偏“运维控制台 + 治理仪表台”，而不是营销页或消费级聊天应用。
2. 建议采用浅色底作为主背景，叠加少量深色信息面板，形成“主工作区清晰、诊断信息稳定可见”的层次。
3. 字体建议使用一组偏工程化但不呆板的组合，例如 `IBM Plex Sans` 配 `IBM Plex Mono`，用于强化“治理、日志、证据链”的控制台感。
4. 颜色建议按 target 状态和调用结果做明确编码，而不是只用一种品牌色：
  - `active / succeeded` 使用偏绿色或蓝绿色
  - `ready` 使用中性蓝
  - `pending / blocked` 使用琥珀或橙色
  - `failed` 使用偏红色
  - `trace / archive / diagnostics` 使用深蓝灰或石墨色
5. 不建议大面积渐变或装饰性插图；视觉重点应放在 chain、route、trace、evidence 这些结构化信息上。

#### 交互原则

1. “当前调用会打到哪里”必须在用户点击 `Run` 前就清楚可见，而不是跑完以后才显示。
2. 结果、trace、archive、错误必须是并列信息，不应把诊断信息藏进二级页面。
3. 页面应默认优先展示本次调用的 route 和 evidence 摘要，而不是只显示一段 answer 文本。
4. forwarding API 不负责声明一层“参数被本应用接受 / 忽略”的二次语义；若某个 target 因自身协议返回参数无效或未使用，应把原始错误或下游诊断信息直接展示给用户。
5. 对 `pending` 或 `blocked` 目标，按钮可点击，但运行前后都应持续显示当前状态来源于 registry，而不是模糊成通用错误。

#### 响应式布局建议

1. 桌面端优先采用三段式信息布局，保证 chain、输入区、route / diagnostics 同屏可见。
2. 平板端可收缩为上下两段：上半区处理输入与链路，下半区处理结果与诊断。
3. 手机端不建议维持多栏；应切成 `Chain -> Input -> Result -> Diagnostics -> Error` 的纵向流，并保留一个固定的 `Current Route` 摘要条。
4. 无论屏幕尺寸如何变化，`trace_id`、`target_id`、`request_id`、`archive_id` 都必须有固定位置，不应因响应式折叠而变成不可见信息。

---

## 11. Tier 1 详细设计

### 11.1 应用职责分层

Tier 1 在程序内部分为 4 个逻辑层：

1. `page layer`：返回 HTML、CSS、JS 静态资源与页面骨架。
2. `ui backend layer`：承接前端页面发起的 AJAX 请求，调用同一个 service layer。
3. `public api layer`：面向外部程序集成的正式 API 面。
4. `service + forwarding layer`：按 tab 对应的目标路由到不同 target，并完成 telemetry / evidence / error handling。

### 11.2 建议目录结构

```text
apps/tier1-app/
  README.md
  app.py
  requirements.txt
  static/
    tier1-index.html
    tier1-app.js
    tier1-styles.css
  tier1_app/
    __init__.py
    config.py
    auth.py
    models.py
    telemetry.py
    observability.py
    target_registry.py
    routes/
      pages.py
      ui.py
      api.py
    services/
      query_service.py
      metadata_service.py
    forwarding/
      rag_forwarder.py
      foundry_agent_forwarder.py
      vm_model_forwarder.py
      native_model_forwarder.py
      finetune_model_forwarder.py
```

### 11.3 页面路由设计

| 路由 | 方法 | 用途 |
|---|---|---|
| `/` | `GET` | 默认页面入口；已登录时进入 Tier 1 UI，未登录时显示登录页骨架 |
| `/app` | `GET` | Tier 1 主页面 |
| `/static/{path}` | `GET` | 静态资源 |

### 11.4 页面后端路由设计

| 路由 | 方法 | 用途 |
|---|---|---|
| `/ui/bootstrap` | `GET` | 返回当前用户、可用 target、默认页面配置、应用元数据摘要 |
| `/ui/metadata` | `GET` | 页面读取详细 metadata |

补充约束：

1. tab 切换是纯前端行为，不调用后端路由。
2. 页面发送消息时，直接调用对应 tab 的 `/api/chat/*` forwarding API，而不是再经过单独的 `/ui/query` 路由。

### 11.5 外部 API 路由设计

| 路由 | 方法 | 用途 |
|---|---|---|
| `/api/chat/rag` | `POST` | 纯转发到 Tier 1 -> RAG API |
| `/api/chat/foundry-agent` | `POST` | 纯转发到 Tier 1 -> Foundry Agent API |
| `/api/chat/vm-model` | `POST` | 纯转发到 Tier 1 -> VM 模型 API |
| `/api/chat/native-model` | `POST` | 纯转发到 Tier 1 -> Native Model API |
| `/api/chat/finetune-model` | `POST` | 纯转发到 Tier 1 -> FineTune Model API |
| `/api/targets` | `GET` | 返回 10 条链路所依赖的下游 target 列表与当前状态 |
| `/api/health` | `GET` | 健康检查 |
| `/api/metadata` | `GET` | 对外暴露目标就绪状态和应用元数据 |

### 11.5A Tier 1 中专 API 列表

Tier 1 在步骤 7 中承担“直接访问服务的中专层”职责。它既向上承接浏览器与外部程序集成调用，也向下原样转发到统一 APIM 下游。其 API 列表固定如下。

#### Tier 1 对上暴露的入口 API

| API | 方法 | 用途 | 主要调用方 |
|---|---|---|---|
| `/ui/bootstrap` | `GET` | 页面启动配置、当前用户、10 条链路状态摘要 | Tier 1 Web UI |
| `/ui/metadata` | `GET` | 页面侧详细 metadata | Tier 1 Web UI |
| `/api/chat/rag` | `POST` | Tier 1 到 RAG 的显式 forwarding API | Tier 1 Web UI、脚本、排障 |
| `/api/chat/foundry-agent` | `POST` | Tier 1 到 Foundry Agent 的显式 forwarding API | Tier 1 Web UI、脚本、排障 |
| `/api/chat/vm-model` | `POST` | Tier 1 到 VM 模型的显式 forwarding API | Tier 1 Web UI、脚本、排障 |
| `/api/chat/native-model` | `POST` | Tier 1 到 Native Model 的显式 forwarding API | Tier 1 Web UI、脚本、排障 |
| `/api/chat/finetune-model` | `POST` | Tier 1 到 FineTune Model 的显式 forwarding API | Tier 1 Web UI、脚本、排障 |
| `/api/targets` | `GET` | 当前受控目标和路由摘要 | Tier 2、脚本、页面诊断 |
| `/api/health` | `GET` | 存活与基础健康检查 | APIM、运维、测试脚本 |
| `/api/metadata` | `GET` | 应用元数据、target 状态、当前路由模式 | Tier 2、外部程序、页面诊断 |

#### Tier 1 对下调用的受控下游 API

| 下游 API | 方法 | 用途 | 对应 forwarding route |
|---|---|---|---|
| `/rag/responses` | `POST` | 调用 RAG Service | `/api/chat/rag` |
| `/foundry-agent/...` | `POST` | 调用 Foundry Agent API | `/api/chat/foundry-agent` |
| `/vm-model/v1/chat/completions` | `POST` | 调用 VM Hugging Face 模型 API | `/api/chat/vm-model` |
| `/native-model/chat/completions` | `POST` | 调用 Project-backed Native Model | `/api/chat/native-model` |
| `/finetune-model/chat/completions` | `POST` | 调用 Project-backed Fine-tune Model | `/api/chat/finetune-model` |

补充约束：

1. Tier 1 不接受调用方透传任意 URL。
2. Tier 1 不暴露“直接透传任意 URL”的通用代理 API，但允许对固定 allowlist 路径做 raw payload forward。
3. Tier 1 的中专语义固定为“受控 tab route -> 受控 APIM 下游 path -> raw body forward”。
4. Tier 1 forwarding API 本身不做 body shape 转换；不同后端格式适配由浏览器侧 tab adapter 负责。

### 11.6 浏览器侧多轮会话模型

Tier 1 首版支持多轮对话，但会话历史只保存在浏览器内存中，不进入后端持久化。

#### 浏览器内存态 `TabConversationState`

```yaml
type: object
additionalProperties: false
required:
  - tab_id
  - messages
  - default_prompts
properties:
  tab_id:
    type: string
    enum: [rag, foundry-agent, vm-model, native-model, finetune-model]
  messages:
    type: array
    items:
      type: object
      additionalProperties: false
      required: [role, content]
      properties:
        role:
          type: string
          enum: [system, user, assistant]
        content:
          type: string
          minLength: 1
  draft_input:
    type: string
  default_prompts:
    type: array
    items:
      type: string
      minLength: 1
```

固定规则：

1. 每个 tab 维护独立的 `messages` 历史，tab 切换不丢失历史。
2. 关闭页面或刷新页面后，历史自然丢失，不做本地存储、不做服务端存储、不做恢复。
3. 默认提示词由 `/ui/bootstrap` 下发，点击后直接把提示词作为用户消息写入当前 tab 历史并发送。

### 11.6A Tier 1 forwarding API 合同

Tier 1 的 forwarding API 没有统一 body schema。每个 API 的请求体必须直接等于其下游 API 的 raw payload。

| API | 请求体合同 | 说明 |
|---|---|---|
| `/api/chat/rag` | body 必须直接符合 `/rag/responses` 的 raw 请求体 | 若要支持多轮，浏览器需先把历史折叠为 RAG 可接受的 `input` 文本 |
| `/api/chat/foundry-agent` | body 必须直接符合 `/foundry-agent/...` 的 raw 请求体 | Tier 1 不补 agent 专属字段 |
| `/api/chat/vm-model` | body 必须直接符合 `/vm-model/v1/chat/completions` 的 raw 请求体 | 通常为 OpenAI-compatible chat body |
| `/api/chat/native-model` | body 必须直接符合 `/native-model/chat/completions` 的 raw 请求体 | `model` 必须由浏览器 adapter 显式传入 |
| `/api/chat/finetune-model` | body 必须直接符合 `/finetune-model/chat/completions` 的 raw 请求体 | `model` 必须由浏览器 adapter 显式传入 |

固定规则：

1. Tier 1 forwarding API 不再定义统一 `target_id + input + options` 合同。
2. Tier 1 forwarding API 不改写请求体，只转发 allowlist 路径、补齐 tracing/logging、提交 observability。
3. 同一个浏览器 UI 会有多个 tab adapter；每个 adapter 负责把前端内存中的 `messages` 适配为对应 raw payload。

### 11.7 Tier 1 转发响应合同

Tier 1 forwarding API 的响应体也不做统一归一化。默认规则如下：

1. 响应 body 原样返回下游响应体。
2. 响应 HTTP 状态码默认镜像下游状态码；只有认证失败、allowlist 校验失败、内部转发失败等应用级错误才由 Tier 1 自己返回应用级错误。
3. Tier 1 可以补充治理响应 header，但不改写下游 body。

#### 建议补充的治理响应 Header

```yaml
type: object
additionalProperties: false
required:
  - X-Governance-Request-Id
  - X-Governance-Trace-Id
  - X-Governance-Target-Id
  - X-Governance-Target-Type
  - X-Governance-Service-Name
properties:
  X-Governance-Request-Id:
    type: string
    minLength: 1
  X-Governance-Trace-Id:
    type: string
    minLength: 1
  X-Governance-Target-Id:
    type: string
    minLength: 1
  X-Governance-Target-Type:
    type: string
    minLength: 1
  X-Governance-Service-Name:
    type: string
    minLength: 1
```

### 11.8 转发层设计

`forward_service.py` 负责以下职责：

1. 按当前 route 决定唯一 allowlist 下游 APIM path。
2. 原样读取请求 body 并转发，不改写 JSON 结构。
3. 透传或补齐 trace context。
4. 调用 shared-observability，记录 raw request / raw response。
5. 将下游响应 body、status code、content-type 原样返回，同时补充治理 response headers。

forwarding layer 不负责把不同下游返回归一化成统一响应模型。

### 11.9 Tier 1 forwarding route 设计

| Forwarding route | 对应 target_type | 下游 APIM path | 备注 |
|---|---|---|---|
| `/api/chat/rag` | `rag_service` | `/rag/responses` | 记录 RAG API 调用 evidence |
| `/api/chat/foundry-agent` | `foundry_agent` | `/foundry-agent/...` | 记录 Agent API 调用 evidence |
| `/api/chat/vm-model` | `vm_huggingface_model` | `/vm-model/v1/chat/completions` | VM sidecar 自身也会记录下游 evidence |
| `/api/chat/native-model` | `foundry_native_model` | `/native-model/chat/completions` | APIM backend 需切到 RAGProject project data plane |
| `/api/chat/finetune-model` | `foundry_finetune_model` | `/finetune-model/chat/completions` | APIM backend 需切到 RAGProject project data plane |

### 11.10 Tier 1 UI 详细设计

Tier 1 页面固定为“Tier 1 Direct AI Chat Console”。用户先经 Entra ID 登录，然后进入一个基于选项卡的多轮问答界面。页面必须明确表达：这是 Tier 1 应用，当前正在直接访问受控服务。

#### 页面纵向层次

1. `Header bar`：应用标题、`Tier 1 Direct Access` 标识、当前环境、当前登录用户、运行时 service identity 摘要。
2. `Tab strip`：5 个后端 tab，每个 tab 对应一个固定后端路径。
3. `Chat workspace`：当前 tab 的对话历史、默认提示词、输入框、发送按钮。
4. `Route & Diagnostics workspace`：当前 tab 的 APIM path、target、trace、request id、archive 摘要。
5. `Error workspace`：显示最后一次失败请求的详细错误。

#### Tab 设计

Tier 1 页面固定展示以下 5 个 tab：

1. `RAG API`
2. `Foundry Agent API`
3. `VM Model API`
4. `Native Model via Foundry Project`
5. `FineTune Model via Foundry Project`

每个 tab 必须包含：

1. 当前 target 标识和 `target_type`。
2. 固定下游 APIM path。
3. 3 到 5 个默认提示词按钮。
4. 当前 tab 独立的对话历史。

#### Chat workspace 结构

| 区域 | 内容 | 作用 |
|---|---|---|
| `Conversation Timeline` | 当前 tab 的 user / assistant 消息列表 | 展示本 tab 的多轮历史 |
| `Default Prompts` | 预置提示词按钮组 | 点击后直接发送或填入输入框 |
| `Composer` | 多行输入框 + `Send` 按钮 | 发送当前用户消息 |
| `Tab Controls` | `Clear This Tab` | 清空当前 tab 历史 |

#### 结果与诊断布局

1. `Answer` 不再独立作为唯一结果区，而是直接体现在 `Conversation Timeline` 的 assistant 消息中。
2. `Route Details` 区固定显示：`target_id`、`target_type`、APIM path、project-backed 标记、last request id、last trace id。
3. `Archive & Trace` 区固定显示：`trace_id`、`archive_id`、`payload_ref`、`response_id` 或下游等效标识。
4. `Raw Response` 可作为折叠区域显示，用于对照不同后端原始协议。

#### 错误展示规则

1. 任意失败都在页面底部固定的 `Error Detail` 面板中完整显示。
2. 不把错误折叠成抽象提示；至少显示时间、tab、target、HTTP 状态、错误类型、原始 message、request_id、trace_id。
3. 当前 tab 的错误不应清空其他 tab 的历史。

#### 异步加载规则

1. 先显示 header 与 tab 骨架。
2. 调用 `/ui/bootstrap` 获取 tab 配置、默认提示词、当前用户与 service name。
3. 再调用 `/ui/metadata` 填充 route 信息、target 状态与 observability 提示。
4. 用户点击 tab 时只切换前端内存态，不调用后端。
5. 用户点击 `Send` 时，只调用当前 tab 对应的 `/api/chat/*` 路由。

### 11.10A Tier 1 UI 视觉与交互建议

Tier 1 的视觉重点不再是“链路选择面板”，而是“tabbed direct chat console”。

1. 顶部 tab strip 应长期固定可见，明确显示“当前正在直接访问哪个后端”。
2. 默认提示词应放在每个 tab 的聊天区域顶部，作为首批可点击消息。
3. 当前 tab 的对话历史和诊断信息要同屏；不要把 trace 和 archive 完全藏到二级页。
4. tab 切换时保留每个 tab 的内存历史，但不做后端恢复。

### 11.11 页面 bootstrap 合同

`GET /ui/bootstrap` 固定返回页面启动所需的全部只读配置，不允许前端再自行拼装 tab 列表：

```json
{
  "app": {
    "app_name": "AIGovernTrustworthyDemoTier1App",
    "target_type": "tier1_consumer",
    "service_name": "AIGovernTrustworthyDemo.Tier1App",
    "otel_service_name": "AIGovernTrustworthyDemo.Tier1App",
    "version": "step7-v1"
  },
  "user": {
    "is_authenticated": true,
    "display_name": "user@contoso.com",
    "auth_mode": "easyauth"
  },
  "gateway": {
    "public_base_path": "/tier1",
    "apim_base_url": "https://aigoverntrustworthydemoapim.azure-api.net/tier1"
  },
  "tabs": [
    {
      "tab_id": "native-model",
      "display_name": "Native Model via Foundry Project",
      "api_path": "/api/chat/native-model",
      "target_id": "AIGovernTrustworthyDemoNativeModel",
      "target_type": "foundry_native_model",
      "status": "active",
      "default_prompts": [
        "Explain the core functions of NIST AI RMF.",
        "Summarize the AI Act risk categories.",
        "List three governance controls for LLM apps."
      ]
    }
  ]
}
```

### 11.12 元数据合同

`GET /api/metadata` 与 `GET /ui/metadata` 的字段主体一致；前者面向外部调用方，后者可增加页面展示字段。最小返回合同如下：

```json
{
  "app": {
    "app_name": "AIGovernTrustworthyDemoTier1App",
    "target_id": "AIGovernTrustworthyDemoTier1App",
    "target_type": "tier1_consumer",
    "service_name": "AIGovernTrustworthyDemo.Tier1App",
    "otel_service_name": "AIGovernTrustworthyDemo.Tier1App",
    "environment": "local_or_webapp",
    "version": "step7-v1"
  },
  "endpoints": {
    "health": "/api/health",
    "chat_rag": "/api/chat/rag",
    "chat_foundry_agent": "/api/chat/foundry-agent",
    "chat_vm_model": "/api/chat/vm-model",
    "chat_native_model": "/api/chat/native-model",
    "chat_finetune_model": "/api/chat/finetune-model",
    "targets": "/api/targets",
    "metadata": "/api/metadata"
  },
  "gateway": {
    "apim_base_url": "https://aigoverntrustworthydemoapim.azure-api.net/tier1",
    "native_model_mode": "project_backed",
    "finetune_model_mode": "project_backed"
  }
}
```

### 11.13 Target 解析与 allowlist 规则

Tier 1 的 route allowlist 固定按以下顺序执行：

1. 仅接受当前设计允许的 5 个 forwarding route：`rag`、`foundry-agent`、`vm-model`、`native-model`、`finetune-model`。
2. 每个 forwarding route 只能映射到固定的 `target_id`、`target_type` 与固定的 APIM 下游 path。
3. 调用路径必须从 allowlist 与 registry 条目计算，不接受调用方提交任意 path、URL 或 endpoint。
4. Tier 1 自身条目 `AIGovernTrustworthyDemoTier1App`、Tier 2 条目 `AIGovernTrustworthyDemoTier2App` 只用于 metadata，不参与 Tier 1 对下游目标的直接调用选择。

### 11.14 浏览器侧 tab adapter 规则

不同后端协议的 payload 适配固定发生在浏览器侧 tab adapter，而不是 forwarding API。

| Tab | 浏览器侧输入源 | 发送到 Tier 1 的 raw body 规则 | 关键说明 |
|---|---|---|---|
| `rag` | 当前 tab `messages` 历史 | 先在浏览器侧折叠为 RAG 可接受的 `input` 文本，再发送到 `/api/chat/rag` | 多轮语义由浏览器拼接上下文实现 |
| `foundry-agent` | 当前 tab `messages` 历史 | 浏览器按 Agent API 真实合同构造 raw body | Tier 1 不补 agent envelope |
| `vm-model` | 当前 tab `messages` 历史 | 浏览器直接构造 `/v1/chat/completions` raw body | VM 是否支持某参数由浏览器 adapter 判断 |
| `native-model` | 当前 tab `messages` 历史 | 浏览器直接构造 `/chat/completions` raw body，并显式传 `model=AIGovernTrustworthyDemoNativeModelGPT5.4mini` | Tier 1 不追加 `model` |
| `finetune-model` | 当前 tab `messages` 历史 | 浏览器直接构造 `/chat/completions` raw body，并显式传 `model=AIGovernTrustworthyDemoFineTuneModel` | Tier 1 不追加 `model` |

固定规则：

1. APIM 不做格式转换。
2. Tier 1 forwarding API 不做格式转换。
3. 浏览器 tab adapter 可以为多轮效果重组消息历史，但最终发送 body 必须已经是目标后端能直接接收的 raw payload。

### 11.15 浏览器侧响应显示规则

由于 Tier 1 forwarding API 原样返回不同后端响应体，UI 必须在浏览器侧按 tab 解析响应并展示 assistant 消息。

| Tab | assistant 文本提取规则 | 诊断字段来源 |
|---|---|---|
| `rag` | 从 RAG raw response 中提取 answer 或 output 文本 | body + governance headers |
| `foundry-agent` | 从 Agent raw response 中提取显式文本结果或摘要 | body + governance headers |
| `vm-model` | 从第一条 choice 的 assistant content 提取 | body + governance headers |
| `native-model` | 从第一条 choice 的 assistant content 提取 | body + governance headers |
| `finetune-model` | 从第一条 choice 的 assistant content 提取 | body + governance headers |

UI 固定规则：

1. `trace_id`、`request_id`、`target_id`、`target_type` 优先从 governance headers 读取。
2. `response_id`、`model`、`archive` 等字段按各 tab 的 raw body 能力解析。
3. 若某字段不可得，UI 显示为空态，不伪造统一值。

### 11.16 Tier 1 evidence 字段映射

Tier 1 每次实际下游调用都必须调用 `log_llm_call()`，字段映射固定如下：

| 字段 | 填充值 |
|---|---|
| `service_name` | `L4_OTEL_SERVICE_NAME_TIER1_APP` 对应的 Tier 1 service name，并作为应用自身 `OTEL_SERVICE_NAME` |
| `source_type` | `tier1_consumer` |
| `target_type` | 由当前 forwarding route 对应的 `target_type` 决定 |
| `target_id` | 由当前 forwarding route 对应的受控 `target_id` 决定 |
| `target_endpoint` | 实际请求的 APIM URL |
| `llm_input` | 浏览器发送给 Tier 1 的 raw 请求体 |
| `llm_output` | 从下游收到的完整 raw 响应体；失败时改为 `error` |
| `response_id` | 仅在 raw response 中可直接提取时记录 |
| `model_name` / `model_version` | 仅在 raw response 中可直接提取时补齐 |
| `trace_id` / `span_id` | 从当前活动 trace context 继承，不额外重建新的业务关联键 |
| `extra_attributes.invocation_route` | `web_ui` 或 `public_api` |
| `extra_attributes.downstream_status_code` | 下游 HTTP 状态码 |
| `extra_attributes.downstream_archive_id` | 若下游响应或 shared-observability 返回 archive，则在此补充 |

### 11.16A Trace 透传与维护规则

步骤 7 的 10 条链路都必须把 W3C trace context 当作主关联协议维护，而不是临时自造一套 correlation id。

固定规则如下：

1. Browser -> APIM `/tier1` / `/tier2`：由浏览器侧请求或 FastAPI 入口生成或接续当前 trace。
2. APIM -> Tier 1 / Tier 2：保留 `traceparent` / `tracestate`，不得在中间层静默丢失。
3. Tier 2 -> Tier 1：`tier1_client.py` 必须显式透传 `traceparent` / `tracestate`，并确保 Tier 1 在同一 `trace_id` 下继续记录。
4. Tier 1 -> 下游 APIM path：每个 forwarding route 都必须透传当前 trace headers，让 `/rag`、`/foundry-agent`、`/vm-model`、`/native-model`、`/finetune-model` 落在同一调用链上。
5. shared-observability 记录时，`trace_id` 和 `span_id` 取当前活动上下文，不重新生成独立键。
6. 若下游返回自己的 `response_id`、`request_id`、`archive_id`，这些字段作为补充关联键保留，但不替代 `trace_id`。
7. 任何 hop 一旦发现缺失 trace context，都必须在日志与错误详情中显式暴露该问题，不能静默继续。

### 11.17 Tier 1 关键时序

#### 11.17.1 Tier 1 页面多轮聊天

1. 用户经 Entra ID 登录后进入 `APIM /tier1/app`。
2. 浏览器调用 `/ui/bootstrap` 获取 5 个 tab、默认提示词、`otel_service_name` 和当前用户信息。
3. 浏览器在内存中为每个 tab 初始化独立 `messages` 历史。
4. 用户切换 tab 时只切换前端内存态，不对后端 postback。
5. 用户点击默认提示词或发送输入时，浏览器按当前 tab adapter 构造 raw payload，调用对应的 `/api/chat/*` 路由。

#### 11.17.2 Tier 1 forwarding route -> 下游 APIM

1. Tier 1 收到当前 tab 对应的 raw payload。
2. Tier 1 校验 caller 身份、当前 route allowlist 和下游 APIM path。
3. Tier 1 记录 request telemetry，并以 `L4_OTEL_SERVICE_NAME_TIER1_APP` 作为本应用 `OTEL_SERVICE_NAME` 写入 App Insights。
4. Tier 1 透传 `traceparent` / `tracestate`，将 raw body 原样转发给下游 APIM path。
5. Tier 1 记录 shared-observability evidence，并把下游 raw response body 原样回传给浏览器，同时补充 governance headers。

## 12. Tier 2 详细设计

### 12.1 应用职责分层

Tier 2 在程序内部分为 3 个逻辑层：

1. `page layer`：返回 HTML、CSS、JS 静态资源与页面骨架。
2. `ui backend / api layer`：承接页面请求与 API 请求，统一调用 Tier 1。
3. `tier1 client layer`：把请求转发给 Tier 1 API，并写 Tier 2 这一层的 evidence。

### 12.2 建议目录结构

```text
apps/tier2-app/
  README.md
  app.py
  requirements.txt
  static/
    tier2-index.html
    tier2-app.js
    tier2-styles.css
  tier2_app/
    __init__.py
    config.py
    auth.py
    models.py
    telemetry.py
    observability.py
    routes/
      pages.py
      ui.py
      api.py
    services/
      request_service.py
      metadata_service.py
    clients/
      tier1_client.py
```

### 12.3 页面与 API 路由设计

| 路由 | 方法 | 用途 |
|---|---|---|
| `/` | `GET` | 默认页面入口 |
| `/app` | `GET` | Tier 2 主页面 |
| `/static/{path}` | `GET` | 静态资源 |
| `/ui/bootstrap` | `GET` | 页面启动配置 |
| `/ui/metadata` | `GET` | 页面 metadata |
| `/api/chat/rag` | `POST` | 纯转发到 Tier 1 `/api/chat/rag` |
| `/api/chat/foundry-agent` | `POST` | 纯转发到 Tier 1 `/api/chat/foundry-agent` |
| `/api/chat/vm-model` | `POST` | 纯转发到 Tier 1 `/api/chat/vm-model` |
| `/api/chat/native-model` | `POST` | 纯转发到 Tier 1 `/api/chat/native-model` |
| `/api/chat/finetune-model` | `POST` | 纯转发到 Tier 1 `/api/chat/finetune-model` |
| `/api/health` | `GET` | 健康检查 |
| `/api/metadata` | `GET` | 对外暴露当前应用元数据 |

### 12.4 Tier 2 forwarding 合同

Tier 2 与 Tier 1 一样，不再定义统一 request / response envelope。每个 tab 对应一个独立 forwarding API，body 固定原样转发给 Tier 1 同名 API。

| Tier 2 API | Tier 1 下游 | body 规则 |
|---|---|---|
| `/api/chat/rag` | `/tier1/api/chat/rag` | 原样转发 |
| `/api/chat/foundry-agent` | `/tier1/api/chat/foundry-agent` | 原样转发 |
| `/api/chat/vm-model` | `/tier1/api/chat/vm-model` | 原样转发 |
| `/api/chat/native-model` | `/tier1/api/chat/native-model` | 原样转发 |
| `/api/chat/finetune-model` | `/tier1/api/chat/finetune-model` | 原样转发 |

固定规则：

1. Tier 2 不重写 Tier 1 返回的 body。
2. Tier 2 可补充自己的治理 response headers，但不重写 Tier 1 raw response body。
3. Tier 2 的浏览器 tab adapter 与 Tier 1 相同，也是用前端内存态维护多轮历史。

### 12.4A Tier 2 浏览器多轮会话模型

Tier 2 的 tab 内存模型与 Tier 1 相同：每个 tab 独立维护 `messages` 历史，tab 切换不丢失，页面关闭后全部丢失。

### 12.5 Tier 2 到 Tier 1 调用设计

`tier1_client.py` 的职责固定为：

1. 按当前 tab 选择 Tier 1 同名 forwarding API，例如 `/tier1/api/chat/native-model`。
2. 原样发送浏览器已经构造好的 raw body。
3. 透传当前 trace context。
4. 调用 shared-observability，记录 `Tier 2 -> Tier 1 API` 这一层 evidence。
5. 将 Tier 1 的 raw response body、status code、content-type 原样返回，同时补充 Tier 2 自己的治理 response headers。

Tier 2 不直接持有任何 RAG / Agent / Model / VM 下游适配实现，也不负责这些后端的 body shape 适配。

### 12.6 Tier 2 页面设计

Tier 2 页面采用与 Tier 1 相同的 tabbed multi-turn chat 设计，但必须在视觉上清楚表达：这是 Tier 2 程序，实际链路是 `Tier 2 -> Tier 1 -> Final Target`。

#### 页面结构

1. `Header bar`：应用标题、`Tier 2 Indirect Access` 标识、当前环境、当前登录用户、运行时 service identity 摘要。
2. `Tab strip`：5 个后端 tab，但每个 tab 都必须显示“两跳链路”的视觉标识。
3. `Chat workspace`：当前 tab 的对话历史、默认提示词、输入框、发送按钮。
4. `Two-hop Route Workspace`：固定显示 Hop 1 = Tier 2 -> Tier 1，Hop 2 = Tier 1 -> Final Target。
5. `Diagnostics & Error Workspace`：显示 Tier 2 本 hop 的 trace/request id，以及从 Tier 1 / final target 返回的关联字段。

#### Tier 2 页面必须展示的 5 个 tab

1. `RAG API`
2. `Foundry Agent API`
3. `VM Model API`
4. `Native Model via Foundry Project`
5. `FineTune Model via Foundry Project`

#### 页面核心差异

与 Tier 1 相比，Tier 2 页面必须额外显示以下内容：

1. 当前 first hop 固定是 `AIGovernTrustworthyDemoTier1App`。
2. 当前 final target 是哪一个 Tier 1 下游 target。
3. Tier 2 自己这一层的 evidence 和 Tier 1 / final target 返回的字段要分开显示。

#### 结果与诊断布局

1. `Conversation Timeline` 直接显示当前 tab 的多轮问答。
2. `Hop 1 Diagnostics` 显示 Tier 2 自己这一跳的 `request_id`、`trace_id`、service name。
3. `Hop 2 Diagnostics` 显示 Tier 1 / final target 的 `trace_id`、`response_id`、`archive_id`、`payload_ref` 等。
4. `Raw Response` 作为折叠区域显示 Tier 1 原样返回的 body。

#### 错误展示规则

1. Tier 2 页面的错误区必须区分“Tier 2 自己失败”与“Tier 1 或更下游失败”。
2. 若 Tier 1 返回错误，Tier 2 不重新包装 body，只在错误区补充自己的 request_id / trace_id。
3. tab 切换不清空其他 tab 的历史或错误。

#### 异步加载规则

1. 页面加载时先调用 `/ui/bootstrap`。
2. 然后调用 `/ui/metadata` 填充 Tier 1 依赖状态、5 个 tab 的 route 面板和 observability 提示。
3. 用户切换 tab 时只切换前端内存态，不调用后端。
4. 用户点击 `Send` 时，只调用当前 tab 对应的 `/api/chat/*` forwarding API。

### 12.6A Tier 2 UI 视觉与交互建议

Tier 2 不应只是 Tier 1 的换皮版本。它的核心价值是把“两跳治理链路”直接可视化，让用户看到 `Tier 2 -> Tier 1 -> Final Target` 的结构，而不是只看到一个最终答案。

1. 页面顶部建议增加一条 `Two-hop Route Banner`，固定展示：当前 app、Tier 1 中专层、最终 target。
2. tab strip 要和 Tier 1 相同，但每个 tab 旁边应持续出现 `via Tier 1` 的视觉标签。
3. `Hop 1 Diagnostics` 和 `Hop 2 Diagnostics` 必须并排或分层显示，不要合并成一个诊断块。
4. 默认提示词、对话历史和发送区与 Tier 1 相同，但视觉上要始终提醒用户这不是 direct access。

### 12.7 页面 bootstrap 与 metadata 合同

Tier 2 的 `GET /ui/bootstrap` 与 `GET /api/metadata` 结构应与 Tier 1 尽量同形，但必须额外暴露 Tier 1 依赖信息：

```json
{
  "app": {
    "app_name": "AIGovernTrustworthyDemoTier2App",
    "target_type": "tier2_consumer",
    "service_name": "AIGovernTrustworthyDemo.Tier2App",
    "otel_service_name": "AIGovernTrustworthyDemo.Tier2App"
  },
  "gateway": {
    "public_base_path": "/tier2",
    "tier1_base_url": "https://aigoverntrustworthydemoapim.azure-api.net/tier1"
  },
  "tier1_dependency": {
    "target_id": "AIGovernTrustworthyDemoTier1App",
    "target_type": "tier1_consumer",
    "status": "pending_or_ready"
  },
  "tabs": [
    {
      "tab_id": "native-model",
      "api_path": "/api/chat/native-model",
      "tier1_forward_path": "/tier1/api/chat/native-model",
      "target_id": "AIGovernTrustworthyDemoNativeModel",
      "final_target_type": "foundry_native_model",
      "default_prompts": [
        "Explain the core functions of NIST AI RMF.",
        "Summarize the AI Act risk categories.",
        "List three governance controls for LLM apps."
      ]
    }
  ]
}
```

### 12.8 Tier 1 Client 调用与授权规则

Tier 2 的 `tier1_client.py` 固定遵守以下规则：

1. 唯一业务 URL 模板是 `{L4_APIM_GATEWAY_URL}/tier1/api/chat/{tab_id}`。
2. Tier 2 后端调用 Tier 1 时，不透传终端用户 token，而是用 Tier 2 运行时 SPN 获取面向 Tier 1 应用的 application token。
3. 该 token 的 audience / scope 设计为 `api://{L4_TIER1_APP_CLIENT_ID}/.default`，不新增单独环境变量。
4. APIM `/tier1` 只透传 Bearer token，不替换为 MSI token；Tier 1 App Service 自己校验 token。
5. Tier 2 必须透传 `traceparent` / `tracestate`，并追加本层 `X-Governance-Upstream-App: tier2_consumer` 之类的辅助 header。
6. Tier 1 响应返回后，Tier 2 必须保留并展示 `trace_id`、`request_id`、`archive_id` 等可用治理字段，不得在 body passthrough 时丢失这些 header。

### 12.9 Tier 2 evidence 字段映射

Tier 2 调用 Tier 1 API 时，shared-observability 记录固定如下：

| 字段 | 填充值 |
|---|---|
| `service_name` | `L4_OTEL_SERVICE_NAME_TIER2_APP` 对应的 Tier 2 service name |
| `source_type` | `tier2_consumer` |
| `target_type` | `tier1_consumer` |
| `target_id` | `AIGovernTrustworthyDemoTier1App` |
| `target_endpoint` | `https://.../tier1/api/chat/{tab_id}` |
| `llm_input` | 发给 Tier 1 的 raw 请求体 |
| `llm_output` | Tier 1 返回的 raw 响应体 |
| `response_id` | 若 Tier 1 raw response 中存在同类字段则记录；否则为空 |
| `model_name` / `model_version` | 仅在 raw response 中可直接提取时补齐 |
| `trace_id` / `span_id` | 从当前活动 trace context 继承，并与 Tier 1 保持同一主链路 |
| `extra_attributes.final_target_id` | 终态目标，如 `AIGovernTrustworthyDemoNativeModel` |
| `extra_attributes.final_target_type` | 终态目标类型，如 `foundry_native_model` |

### 12.10 Tier 2 关键时序

1. 浏览器调用 `APIM /tier2`，进入 Tier 2 页面或 API。
2. Tier 2 在前端内存中切换当前 tab，不调用后端。
3. 用户点击 `Send` 后，浏览器按当前 tab 构造 raw payload，调用 Tier 2 同名 `/api/chat/*` forwarding API。
4. Tier 2 使用自己的运行时 SPN 获取 Tier 1 audience token，然后带着当前 `traceparent` / `tracestate` 调用 `APIM /tier1/api/chat/{tab_id}`。
5. Tier 2 在拿到 Tier 1 响应后立即写 `target_type=tier1_consumer` 的 evidence，并原样返回 Tier 1 body。

## 13. 下游依赖详细设计

### 13.1 APIM 依赖设计

步骤 7 对 APIM 的依赖如下：

| APIM path | Consumer App 使用者 | 设计要求 |
|---|---|---|
| `/tier1` | Browser、Tier 2、外部程序 | 提供 Tier 1 页面和对外 API 入口 |
| `/tier2` | Browser | 提供 Tier 2 页面和对外 API 入口 |
| `/rag` | Tier 1 | 保持现有 RAG API 入口 |
| `/foundry-agent` | Tier 1 | 已完成步骤 6 APIM 收尾；Tier 1 直接按 assistant/thread API 调用 |
| `/vm-model` | Tier 1 | 保持现有 VM 模型入口 |
| `/native-model` | Tier 1 | 保持 path；当前已切到 Project data plane |
| `/finetune-model` | Tier 1 | 保持 path；当前已切到 Project data plane |

### 13.2 Native / Fine-tune Project-backed 设计

步骤 7 采用以下设计假设：

1. Consumer App 不直连 `AIGovernTrustworthyRAGProject`。
2. Consumer App 仍然只调用 APIM `/native-model` 和 `/finetune-model`。
3. APIM 当前对 `/native-model` 与 `/finetune-model` 已完成以下调整：
   - base URL 指向 `https://aigoverntrustworthyfoundry.services.ai.azure.com/api/projects/AIGovernTrustworthyRAGProject/openai/v1`
   - token audience 改为 `https://ai.azure.com`
   - operation 仍保持 `POST /chat/completions`
  - 对 `/native-model`，APIM policy 会在请求体缺失 `model` 字段时自动注入 `AIGovernTrustworthyDemoNativeModelGPT5.4mini`
  - 对 `/finetune-model`，APIM policy 会在请求体缺失 `model` 字段时自动注入 `AIGovernTrustworthyDemoFineTuneModel`

已验证事实：使用 deploy SPN + `https://ai.azure.com/.default` scope 时，`AIGovernTrustworthyRAGProject` 已可成功处理 `chat.completions` 调用。

### 13.3 Foundry Agent 依赖设计

Tier 1 的 `/api/chat/foundry-agent` forwarding route 依赖步骤 6 已补齐以下内容：

1. `/foundry-agent` APIM backend 与实际 `AIGovernTrustworthyRAGProject` 对齐。
2. Agent 可从 Consumer App 调用面稳定返回结果。
3. Foundry tracing 能进入统一查询面。

步骤 7 实现时，浏览器或 Tier 1 route 构造 project-level Agent API body，并在 run 请求中使用 `assistant_id=asst_qPEQxZ6Gc894gcxQjaIOkdF6`。

### 13.4 Target Registry 使用规则

步骤 7 对 `infra/target-registry/targets.json` 的使用原则固定如下：

1. 该文件是 Tier 1 下游目标解析的 authoritative input；实现时不得在代码里再复制一份平行 target 清单。
2. 页面展示所需的链路名称、最终调用所需的 `target_id`、`target_type` 与 `apim_path`，都必须从 registry 条目派生或与之显式对齐。
3. Tier 1 / Tier 2 自身的 registry 条目只用于 metadata、自描述与后续 runner 查询，不参与 Tier 1 下游 forwarding route 选择。
4. 若 registry 状态与真实运行状态短暂漂移，页面与 API 应以 registry 为准，并在 metadata 中显式返回该状态，而不是猜测平台真实状态。

---

## 14. 认证与授权详细设计

### 14.1 终端用户认证

Tier 1 与 Tier 2 页面都采用 Entra 用户登录。详细设计阶段固定以下原则：

1. 浏览器页面访问必须先登录。
2. 用户身份仅用于访问页面与应用层接口。
3. 用户 token 不向 Blob、App Insights、RAG、Foundry、VM 等下游透传。

### 14.2 应用运行时认证

| 应用 | 运行时身份 | 用途 |
|---|---|---|
| Tier 1 | `AIGovernTrustworthyDemoTier1AppSPN` | 调用下游 APIM、写 Blob evidence、写 App Insights thin event |
| Tier 2 | `AIGovernTrustworthyDemoTier2AppSPN` | 调用 Tier 1 API、写 Blob evidence、写 App Insights thin event |

### 14.3 App Service 认证实现建议

详细设计优先采用以下顺序：

1. App Service EasyAuth 负责页面访问入口保护。
2. FastAPI 读取平台注入的用户上下文并回显用户显示信息。
3. 若 EasyAuth 不能满足当前前端体验需求，再退回代码内 MSAL 登录流。

### 14.4 Tier 2 -> Tier 1 服务间授权设计

为了同时满足“前端用户登录”和“用户身份不向下游透传”的原则，步骤 7 固定采用双入口调用语义：

1. 浏览器访问 Tier 1 / Tier 2 页面时，使用 Entra 用户登录，由 EasyAuth 保护页面入口。
2. Tier 2 后端调用 Tier 1 API 时，不使用浏览器用户 token，而是使用 `AIGovernTrustworthyDemoTier2AppSPN` 获取面向 Tier 1 的 application token。
3. Tier 1 FastAPI 对 `/api/chat/*` 至少要接受两类 caller：
  - 直接访问 Tier 1 的浏览器用户或外部程序集成调用方
  - 来自 `AIGovernTrustworthyDemoTier2AppSPN` 的 app-only token
4. Tier 1 对 app-only token 必须做 caller allowlist 检查，至少校验 `appid == L4_TIER2_APP_CLIENT_ID`。
5. Tier 1 / Tier 2 再向下游 APIM、Blob、App Insights 发起调用时，都统一切换到各自运行时 SPN，不透传用户 token。

### 14.5 Entra 前置配置要求

Tier 2 -> Tier 1 的 app-only 调用在代码实现前，必须先完成以下 Entra 前置配置；否则步骤 7 的双跳链路无法落地：

1. 为 Tier 1 Web App 准备独立 App Registration，并把其 Application ID URI 固定为 `api://{L4_TIER1_APP_CLIENT_ID}`。
2. Tier 1 App Registration 必须显式暴露供应用调用的权限面；实现上可采用 application permission 或 app role，但最终必须允许 `AIGovernTrustworthyDemoTier2AppSPN` 以 app-only token 调用 Tier 1 `/api/chat/*`。
3. 为 Tier 2 Web App 准备独立 App Registration，并授予其调用 Tier 1 的上述权限。
4. 管理员必须完成 admin consent；未完成 consent 时，Tier 2 即使持有自己的运行时 SPN，也无法稳定换取面向 Tier 1 的 application token。
5. Tier 1 Web App 的 EasyAuth / 应用鉴权配置必须同时接受：浏览器用户访问页面所需的用户 token，以及来自 Tier 2 的 app-only token。
6. Tier 1 在代码层仍需保留 caller allowlist 检查；Entra 配置成功不等于允许任何应用 caller 调用 Tier 1。

## 15. 配置详细设计

### 15.1 复用现有环境变量

Tier 1 / Tier 2 详细设计明确复用以下已存在变量：

1. `APPLICATIONINSIGHTS_CONNECTION_STRING`
2. `L4_APIM_GATEWAY_URL`
3. `L4_TIER1_APP_NAME` / `L4_TIER1_APP_URL`
4. `L4_TIER2_APP_NAME` / `L4_TIER2_APP_URL`
5. `L4_RAG_SERVICE_URL`
6. `L4_VM_PRIVATE_IP` / `L4_VM_MODEL_API_PORT`
7. `L4_FOUNDRY_AGENT_ID`
8. `L4_OTEL_SERVICE_NAME_TIER1_APP` / `L4_OTEL_SERVICE_NAME_TIER2_APP`
9. `L4_OBSERVABILITY_BLOB_STORAGE_ACCOUNT_NAME` / `L4_OBSERVABILITY_BLOB_CONTAINER` / `L4_OBSERVABILITY_BLOB_PREFIX`

### 15.2 已确认纳入环境合同的新增变量

当前不再要求为 Tier 1 / Tier 2 consumer app 单独新增 `L4_RAG_PROJECT_NAME`、`L4_RAG_PROJECT_ENDPOINT`。

原因如下：

1. 步骤 7 对 Native / Fine-tune 的 project-backed 路由已经下沉到 APIM `/native-model`、`/finetune-model` backend 配置。
2. Tier 1 / Tier 2 应用本身不直连 `AIGovernTrustworthyRAGProject`，只调用统一 APIM path。
3. 因此，这两个值属于 APIM / 平台配置事实，而不是 consumer app 运行时必须显式读取的环境合同键。

若后续某个实现切回“应用代码直连 project endpoint”，应重新评估并显式把相应键名纳入环境合同；在当前设计下，不应再把它们列为步骤 7 开发前必备 env key。

### 15.3 运行时映射设计

为符合 shared-observability 组件的环境约束，Tier 1 / Tier 2 在 App Service 上应额外映射：

1. `AZ_RUNTIME_TENANT_ID`
2. `AZ_RUNTIME_CLIENT_ID`
3. `AZ_RUNTIME_CLIENT_SECRET`
4. `OTEL_SERVICE_NAME`

这些值分别映射到各自应用自己的运行时 SPN，而不是 deploy SPN。`OTEL_SERVICE_NAME` 必须明确映射为：

1. Tier 1 = `L4_OTEL_SERVICE_NAME_TIER1_APP`
2. Tier 2 = `L4_OTEL_SERVICE_NAME_TIER2_APP`

### 15.4 基于现有变量推导的运行时值

为避免引入不必要的新环境变量，步骤 7 首版允许由现有合同推导以下运行时值：

1. Tier 1 APIM base URL = `{L4_APIM_GATEWAY_URL}/tier1`
2. Tier 2 APIM base URL = `{L4_APIM_GATEWAY_URL}/tier2`
3. Tier 1 API audience / scope = `api://{L4_TIER1_APP_CLIENT_ID}/.default`
4. Tier 2 API audience / scope = `api://{L4_TIER2_APP_CLIENT_ID}/.default`（仅为未来被其他 app 调用预留）
5. Native / Fine-tune project mode 开关不单独加变量，统一由 metadata 根据当前 APIM 设计返回 `project_backed`

---

## 16. 部署与实现设计

### 16.1 实现顺序

详细设计允许工程内部安排编码顺序，但步骤 7 的范围不再拆成批次、阶段或独立里程碑。实现完成的标准是：10 条链路、两套 UI、Tier 1 中专 API、Tier 2 -> Tier 1 调用、observability 证据链一次性都纳入同一个交付面。

工程内部可以按以下顺序组织开发工作，但这些顺序只服务于开发执行，不构成需求分批：

1. 搭 Tier 1 FastAPI 骨架、页面骨架、`/api/health`、`/api/metadata`。
2. 完成 Tier 1 的 5 个 `/api/chat/*` forwarding route 和治理 response headers。
3. 完成 Tier 1 浏览器侧 5 个 tab adapter、默认提示词和前端内存会话。
4. 搭 Tier 2 FastAPI 骨架与 Tier 1 client。
5. 接入 Tier 2 -> Tier 1 shared-observability 记录和 service-to-service auth。
6. 完成 Tier 2 的 5 个 `/api/chat/*` forwarding route、浏览器 tab adapter 与两跳诊断 UI。
7. 做 10 条链路的 smoke test 与 KQL 验证。

### 16.2 一次性交付范围

步骤 7 一次性交付范围固定包括以下内容：

1. Tier 1 页面与 Tier 1 中专 API。
2. Tier 2 页面与 Tier 2 转发 API。
3. 全部 10 条链路的 target 映射、forwarding route、浏览器 tab adapter 和验证。
4. Tier 2 -> Tier 1 的 app-only token 服务间调用。
5. Tier 1 / Tier 2 的 App Insights、shared-observability、Blob 证据链对接。

如果某条链路所依赖的下游前置仍未补齐，则步骤 7 整体不应被视为完成；不能以“先上线一部分链路”替代步骤 7 的完整交付目标。

### 16.3 一次性交付物清单

进入实现时，步骤 7 应一次性交付以下对象：

1. Tier 1 FastAPI 应用骨架、静态页面、页面后端路由、外部 API 路由。
2. Tier 1 的 5 个 forwarding route：RAG、Foundry Agent、VM、Native、FineTune。
3. Tier 2 FastAPI 应用骨架、静态页面、页面后端路由、转发 API 路由。
4. Tier 2 的 Tier 1 client、service-to-service auth、hop evidence 记录。
5. 对应 10 条链路的 smoke test、trace 验证、Blob evidence 验证。

### 16.4 完成标准

步骤 7 只有在以下条件同时满足时才算完成：

1. Tier 1 页面能触发 5 条 direct chains。
2. Tier 2 页面能触发 5 条 indirect chains。
3. Tier 1 中专 API 能承接 Tier 2 和外部程序集成调用。
4. 每条链路都能在 APIM、应用 telemetry、Blob evidence 中留下对应记录。
5. 任何错误都能在 UI、API 和控制台看到详细错误内容。

---

## 17. 详细验证设计

### 17.1 功能验证

每条链路至少验证：

1. 页面可触发请求。
2. 外部 API 可触发请求。
3. 返回体与目标下游 raw 协议一致，且 governance headers 完整。

### 17.2 观测验证

每条链路至少验证：

1. APIM diagnostics 可见。
2. App Insights request / dependency 可见。
3. shared-observability thin event 可见。
4. Blob archive 中存在 input / output / metadata。
5. 适用时 Foundry tracing 或 AOAI 平台诊断可见。

### 17.3 关键 KQL 设计方向

详细设计要求后续至少准备以下 KQL：

1. 按 `trace_id` 追一条 Tier 2 -> Tier 1 -> target 链路。
2. 按 `response_id` 查 Native / Fine-tune / Agent 结果。
3. 按 `service_name` + `target_type` 区分 Tier 2 evidence、Tier 1 evidence、RAG 内部 evidence。
4. 按 `payload_ref` 反查 Blob archive。

### 17.4 10 条链路验证矩阵

| 链路 | 功能结果 | Trace 连续性核对 | 关联键核对 | 最低观测要求 | 当前前置状态 |
|---|---|---|---|---|---|
| Tier 1 -> RAG | 返回业务结果或详细错误 | `/tier1` request、Tier 1 evidence、RAG evidence 共享同一 `trace_id` | 若有 `archive_id` / `payload_ref` 必须可从 Tier 1 响应反查 Blob；错误时至少保留 `request_id` + `trace_id` | `/tier1` APIM + Tier 1 evidence + RAG evidence + Blob | 当前依赖 RAG Service 实际就绪情况 |
| Tier 1 -> Foundry Agent | 返回业务结果或详细错误 | `/tier1` request、Tier 1 evidence、Foundry tracing 共享同一主 `trace_id` | 若 Agent 返回 `response_id` 或平台侧 request id，必须能与 Tier 1 evidence 对应 | `/tier1` APIM + Tier 1 evidence + Foundry tracing | 当前依赖步骤 6 收尾情况 |
| Tier 1 -> VM | 返回 200 | `/tier1` request、Tier 1 dependency、VM telemetry 必须落在同一 trace 上 | Tier 1 响应中的 `response_id`、`model` 与 VM 响应一致；若参数被忽略，应有可诊断记录 | `/tier1` APIM + Tier 1 evidence + `/vm-model` APIM + VM telemetry + Blob | 已具备 |
| Tier 1 -> Native | 返回 200 | `/tier1` request、Tier 1 evidence、`/native-model` APIM、Foundry Project tracing 使用同一 `trace_id` 主链 | `response_id`、`archive_id`、`payload_ref` 可从 Tier 1 响应与 evidence 互相反查；`model` 必须对应 Native target | `/tier1` APIM + Tier 1 evidence + `/native-model` APIM + Foundry Project tracing + Blob | 已具备 |
| Tier 1 -> Fine-tune | 返回 200 | `/tier1` request、Tier 1 evidence、`/finetune-model` APIM、Foundry Project tracing 使用同一 `trace_id` 主链 | `response_id`、`archive_id`、`payload_ref` 可从 Tier 1 响应与 evidence 互相反查；`model` 必须对应 FineTune target | `/tier1` APIM + Tier 1 evidence + `/finetune-model` APIM + Foundry Project tracing + Blob | 已具备 |
| Tier 2 -> Tier 1 -> RAG | 返回业务结果或详细错误 | `/tier2` request、Tier 2 evidence、`/tier1` request、Tier 1 evidence、RAG evidence 必须串成同一 trace | Tier 2 外层响应需保留 Tier 1 返回的 `trace_id`；若有 `archive_id` / `payload_ref` 应可继续反查 Blob | `/tier2` APIM + Tier 2 evidence + `/tier1` APIM + Tier 1 evidence + RAG evidence | 当前依赖 RAG Service 实际就绪情况 |
| Tier 2 -> Tier 1 -> Foundry Agent | 返回业务结果或详细错误 | `/tier2` request、Tier 2 evidence、`/tier1` request、Tier 1 evidence、Foundry tracing 必须串成同一 trace | Tier 2 外层响应需保留 Tier 1 返回的 `trace_id` / `response_id`；平台 request id 可作为补充关联键 | `/tier2` APIM + Tier 2 evidence + `/tier1` APIM + Tier 1 evidence + Foundry tracing | 当前依赖步骤 6 收尾情况 |
| Tier 2 -> Tier 1 -> VM | 返回 200 | `/tier2` request、Tier 2 evidence、`/tier1` request、Tier 1 evidence、VM telemetry 必须串成同一 trace | Tier 2 外层响应中的 `trace_id`、`response_id`、`model` 与 Tier 1 结果保持一致；若参数被忽略，应有可诊断记录 | `/tier2` APIM + Tier 2 evidence + `/tier1` APIM + Tier 1 evidence + `/vm-model` APIM + VM telemetry | 已具备 |
| Tier 2 -> Tier 1 -> Native | 返回 200 | `/tier2` request、Tier 2 evidence、`/tier1` request、Tier 1 evidence、`/native-model` APIM、Foundry Project tracing 必须串成同一 trace | Tier 2 外层响应需保留 Tier 1 返回的 `trace_id`、`response_id`、`archive_id`；`model` 必须对应 Native target | `/tier2` APIM + Tier 2 evidence + `/tier1` APIM + Tier 1 evidence + `/native-model` APIM + Foundry Project tracing | 已具备 |
| Tier 2 -> Tier 1 -> Fine-tune | 返回 200 | `/tier2` request、Tier 2 evidence、`/tier1` request、Tier 1 evidence、`/finetune-model` APIM、Foundry Project tracing 必须串成同一 trace | Tier 2 外层响应需保留 Tier 1 返回的 `trace_id`、`response_id`、`archive_id`；`model` 必须对应 FineTune target | `/tier2` APIM + Tier 2 evidence + `/tier1` APIM + Tier 1 evidence + `/finetune-model` APIM + Foundry Project tracing | 已具备 |

执行时还必须附加两类统一核对：

1. 前端适配核对：验证浏览器 tab adapter 是否把当前 tab 的多轮历史正确转换成目标后端可接受的 raw payload。
2. 错误链路核对：即使返回失败，也必须保留 `request_id`、`trace_id`、`target_id`、`target_type`，确保后续能从 UI 或 API 响应跳转到 APIM / App Insights / Blob 继续排查。

## 18. 设计评审关注点

当前这版详细设计建议在与你核对时重点看 7 个点：

1. Tier 1 / Tier 2 的页面与 API 路由划分是否符合你的预期。
2. Tier 1 / Tier 2 的 5 个 `/api/chat/*` 纯转发 API 设计是否符合你的预期。
3. Tier 1 页面作为“直接 AI 使用治理演示台”的信息架构是否符合你的预期。
4. Tier 2 页面作为“间接 AI 使用治理演示台”的两跳展示方式是否符合你的预期。
5. 错误区、Trace 区、Evidence 区显示哪些字段最适合后续演示与排障。
6. `/api/targets`、`/api/metadata` 与 `/ui/bootstrap` 三类信息接口的边界是否清晰。
7. 一次性交付 10 条链路与两套 UI 的完整范围定义是否需要再收缩或再扩展。

## 19. 下一步候选

如果这版详细设计方向成立，下一步最自然的是进入以下其中之一：

1. 把 APIM `/native-model`、`/finetune-model` 的详细切换设计写实。
2. 把 Tier 1 / Tier 2 的正式 OpenAPI / JSON schema 写出来。
3. 直接进入代码骨架实现。
