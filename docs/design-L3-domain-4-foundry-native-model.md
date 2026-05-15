# Domain 4 · Foundry 原生模型部署 · 步骤 3 需求设计

## 1. 文档定位

本文件是 `design-L2-domain-4-prerequisites.md` 中**步骤 3：Foundry 原生模型部署**的专用 L3 设计文档，目标是先把步骤 3 的**需求、边界、复用关系、验收口径**整理清楚，再进入后续实施。

步骤 3 在本项目中的定位，不是单纯“部署一个模型”，而是建立一个能够被 Domain 4 持续纳管的 **Foundry Native Model target**，作为后续 tracing、evaluation、red teaming、dashboard 指标和上层应用复用的基础对象。

> **当前实施状态（2026-05-14）**：`AIGovernTrustworthyDemoNativeModel` 已完成直连验证、APIM `/native-model` 接入、APIM MSI → AOAI RBAC 授权、API-level App Insights diagnostics 配置，以及 AOAI 平台诊断验证。

**关联文档**：

| 文档 | 关系 |
|---|---|
| `docs/charters/project-charter.md` | 约束不得越界新增未批准资源，不得擅自修改 `.env.local.L4` |
| `docs/charters/cross-app-architecture-charter.md` | 约束 APIM、App Insights、shared-observability、Entra 认证的统一要求 |
| `docs/design-L1-overview.md` | 约束 Domain 4 在全站中的目标与 L1/L2 指标映射 |
| `docs/design-L2-domain-4-prerequisites.md` | 上级步骤列表；步骤 3 的总入口 |
| `docs/design-L2-domain-4-prerequisites-lowleveldesign.md` | 资源、命名、环境变量、权限与部署对象清单 |
| `docs/design-L2-domain-4-output-trustworthiness.md` | 约束步骤 3 必须支撑的 Domain 4 指标与证据字段 |
| `docs/design-L3-domain-4-apim.md` | 约束 `/native-model` APIM 入口、认证与 tracing 方式 |
| `docs/design-L3-domain-4-shared-observability-component.md` | 约束 Python 调用方如何记录证据与字段 |
| `docs/design-L3-domain-4-rag-governance-service.md` | 说明步骤 2 的 RAG 服务默认复用本步骤部署的原生模型 |

---

## 2. 需求来源与不可越界边界

本步骤必须同时满足以下项目级边界：

1. 本仓库是 Domain 4 的前置条件、资源计划、环境配置和治理基线仓库；步骤 3 必须服务于后续治理演示，不是孤立的模型试验。
2. 所有能接入 APIM 的 HTTP 接口，都必须通过 APIM 暴露；步骤 3 不能长期停留在“只可直连 AOAI”的状态。
3. 所有运行期变量应沿用 `.env.local.L4` 已有命名，不得擅自扩展新的平行命名体系。
4. 所有 LLM/AI 调用都必须有可查询证据；步骤 3 不能只满足“能出答案”，还必须满足 tracing 与证据留存要求。
5. 本项目是 POC，但仍需遵守既有架构；若需要新增设计外资源、改动资源组、或偏离既定技术路线，必须先停下并征得用户许可。
6. Domain 4 的 target type 必须分开治理；步骤 3 的对象必须明确保持为 `foundry_native_model`，不能与 RAG Service、fine-tune、Foundry Agent 或 VM 模型混合统计。

---

## 3. 步骤 3 要解决的核心问题

步骤 3 需要解决的是：在当前 Domain 4 已有的观测、APIM、目标注册和 RAG 设计基础上，建立一个**可调用、可代理、可追踪、可评测、可入报表**的 Foundry 原生模型目标。

这意味着步骤 3 至少要同时回答以下 5 个问题：

1. **部署对象是谁**：选定哪个文本基础模型、deployment 名称是什么、归属哪个 AOAI / Foundry 资源。
2. **调用入口在哪里**：既要能直连 AOAI 验证，也要具备 APIM `/native-model` 的统一入口。
3. **治理身份是什么**：必须有固定 `target_id` / `target_type` / `model_name` / `model_version`，并进入 target registry。
4. **证据链如何成立**：必须支持适用时的 Foundry tracing、APIM tracing、AOAI 平台诊断、调用方 shared-observability、App Insights 查询关联。
5. **后续怎么复用**：必须能被步骤 2 的 RAG 服务、步骤 9/10 的 Consumer App、步骤 13/15 的 evaluation / red teaming 复用。

---

## 4. 当前已存在的实施锚点（必须复用）

仓库中已经存在与步骤 3 直接相关的锚点；后续设计和实施应优先复用，而不是另起一套。

| 锚点 | 当前状态 | 对步骤 3 的含义 |
|---|---|---|
| `docs/design-L2-domain-4-prerequisites.md` §步骤 3 | 已有高层步骤定义 | 仍是步骤 3 的总入口 |
| `docs/design-L2-domain-4-prerequisites-lowleveldesign.md` §4.2.3 | 已确定 AOAI 资源 `AIGovernTrustworthyAOAI` 与 deployment 名称 | 步骤 3 默认部署对象和资源边界已初步确定 |
| `docs/design-L3-domain-4-apim.md` §7.2 | 已定义 `/native-model` APIM 路径和 MSI 认证方案 | 步骤 3 必须补齐 APIM 接入，不得偏离该路径 |
| `docs/design-L3-domain-4-rag-governance-service.md` | 已把 `AIGovernTrustworthyDemoNativeModel` 设为 RAG 默认生成模型 | 步骤 3 的部署结果会被步骤 2 直接复用 |
| `docs/design-L3-domain-4-shared-observability-component.md` | 已定义 `foundry_native_model` 证据记录规则 | 步骤 3 不能另造日志字段或证据格式 |
| `infra/target-registry/targets.json` | 已有 `AIGovernTrustworthyDemoNativeModel` target 占位与字段 | 步骤 3 正式交付时必须保证 registry 信息与实际部署一致 |
| `apps/native-model/scripts/test_native_model.py` | 已有直连 AOAI 的烟测脚本 | 步骤 3 的最小可调用验证路径已存在，应沿用 |

---

## 5. 步骤 3 的需求整理

### 5.1 目标需求

步骤 3 的直接目标不是追求最强模型能力，而是提供一个**稳定、可治理、可复用的基础文本模型 target**。因此本步骤的需求排序如下：

1. **先满足治理可用性，再考虑模型先进性**。
2. **先满足统一调用链和证据链，再考虑体验优化**。
3. **先满足后续步骤复用，再考虑单点脚本便利性**。

### 5.2 部署对象需求

1. 步骤 3 必须部署一个 **Foundry / AOAI 可管理的文本基础模型**。
2. 当前首选模型为 `gpt-5.4-nano`，deployment 名称为 `AIGovernTrustworthyDemoNativeModel`。
3. 若目标 region / quota / model catalog 无法提供 `gpt-5.4-nano`，不得自行替换为其他模型后继续推进；必须先记录限制并征得用户确认。
4. 步骤 3 只覆盖**文本类模型**，不引入图像、语音、视频或多模态模型。
5. 模型部署必须落在当前已批准的 Domain 4 AOAI 资源 `AIGovernTrustworthyAOAI` 上，不额外新增平行模型服务资源。

### 5.3 资源与身份需求

1. 本步骤复用现有 Foundry Hub / Project 与 Domain 4 AOAI 资源，不新增设计外的 Hub、Project、Workspace 或资源组。
2. 运行时认证必须采用 Entra / SPN 方式，不使用 API Key；这与 `disableLocalAuth = true` 的设计保持一致。
3. APIM 访问 AOAI 时必须使用 APIM MSI 获取 `https://cognitiveservices.azure.com` token。
4. `.env.local.L4` 中已约定的以下变量是本步骤的环境合同：
   - `L4_AOAI_SERVICE_NAME`
   - `L4_AOAI_ENDPOINT`
   - `L4_FOUNDRY_NATIVE_MODEL_DEPLOYMENT`
   - `L4_FOUNDRY_NATIVE_MODEL_ENDPOINT`
   - `L4_AI_FOUNDRY_HUB_NAME`
   - `L4_AI_FOUNDRY_PROJECT_NAME`
   - `L4_AI_FOUNDRY_PROJECT_ENDPOINT`
5. 若实际实施发现必须补充新的环境变量，应先证明现有变量无法表达，并征得用户确认后再改。

### 5.4 调用入口需求

步骤 3 需要同时具备两条调用路径，且语义不同：

| 路径 | 作用 | 是否必须 |
|---|---|---|
| 直连 AOAI deployment | 用于最小烟测、排查部署/权限/模型可用性问题 | 是 |
| APIM `/native-model` | 用于统一治理入口、后续 app / runner / red teaming 接入 | 是 |

补充要求：

1. 直连 AOAI 只是验证路径，不是长期治理主入口。
2. 所有可代理的上游调用场景，最终都必须收敛到 APIM `/native-model`。
3. 浏览器前端不应直接调用 Internal VNet APIM；需要由服务端代理或 VNet 内调用方接入。

### 5.5 治理身份与数据字段需求

步骤 3 交付的对象必须在设计和实现中保持以下固定治理身份：

| 字段 | 要求值 / 要求 |
|---|---|
| `target_type` | `foundry_native_model` |
| `target_id` | `AIGovernTrustworthyDemoNativeModel` |
| `deployment_name` | `AIGovernTrustworthyDemoNativeModel` |
| `model_name` | 默认 `gpt-5.4-nano`；若因平台限制调整，必须同步更新设计与 registry |
| `model_version` | 必须记录到 target registry 和后续证据字段中 |
| `auth` | `entra` |
| `apim_path` | `/native-model` |

此外，步骤 3 需要确保后续记录链路能够保留或补齐以下字段：

- `target_type`
- `target_id`
- `model_name`
- `model_version`
- `test_tool`
- `test_run_id`
- `trace_id`
- `span_id`
- `response_id`
- `archive_id`
- `payload_ref`

除非遗留集成明确要求，否则不新增以 `correlation_id` 为核心的设计。

### 5.6 观测与证据需求

步骤 3 不是单纯部署任务，必须满足 Domain 4 的统一观测设计：

1. **平台 tracing 边界**：对该原生模型目标，如走 Foundry SDK / 平台支持的 tracing 路径，应启用 Foundry tracing；当前已落地的 `APIM -> AOAI REST` 路径，其平台证据由 APIM diagnostics + AOAI 平台诊断承担，不单独要求 Foundry Studio span。
2. **APIM tracing**：对 `/native-model` gateway 调用保留 APIM diagnostics 与 W3C trace context。
3. **shared-observability**：任何由 Python 应用或脚本直接调用该模型时，都应按 `foundry_native_model` 记录完整输入输出证据。
4. **Application Insights / Azure Monitor Logs**：作为 APIM tracing、适用时的 Foundry tracing、AOAI 平台诊断和 Python evidence 的统一查询面。
5. **Blob archive**：保存完整输入输出证据，不把完整 prompt / output 复制进 App Insights。

### 5.7 与已开发组件的耦合需求

步骤 3 需要主动适配当前已设计或已开发组件，而不是把这些关系留到后面再补：

1. **RAG Governance Service**：步骤 2 已把本 deployment 作为默认生成模型；步骤 3 完成后，RAG 才有稳定的默认模型后端。
2. **APIM**：步骤 3 必须补齐 `/native-model`，否则不符合“所有可代理 HTTP hop 统一走 APIM”的宪章要求。
3. **Target Registry**：必须确保 `infra/target-registry/targets.json` 中 native model 条目与真实部署保持一致。
4. **Smoke Test 脚本**：必须沿用 `apps/native-model/scripts/test_native_model.py` 作为最小验证锚点，不新造第二套临时验证方式。
5. **Dashboard / Metrics**：步骤 3 的 target 必须能被后续 Evaluation Coverage、Red Teaming Coverage、Model Identity Capture 等指标单独统计。

### 5.8 后续复用需求

步骤 3 交付后，至少要支持以下后续动作：

1. 被步骤 2 的 RAG Web App 作为默认底层生成模型调用。
2. 被步骤 9 的 Tier 1 Consumer App 通过 APIM 调用。
3. 被步骤 13 的 Evaluation Runner 纳入 `foundry_native_model` 目标清单。
4. 被步骤 15 的 PyRIT / red teaming 以统一 target 身份纳入测试。
5. 被 Domain 4 L1/L2 报表按独立 target type 展示，不与其他对象合并。

---

## 6. 明确不属于步骤 3 的内容

以下事项不应混入步骤 3：

1. Fine-tune 数据准备、训练作业和 fine-tuned deployment（属于步骤 4）。
2. VM Hugging Face 模型部署与 OpenAI-compatible API（属于步骤 5/6）。
3. Foundry 自定义 Agent 或 Copilot Studio Agent 的创建（属于步骤 7/8）。
4. 新建额外检索、embedding、vector store 或 Azure AI Search 资源来支撑 native model。
5. Consumer App 的 UI、登录流和业务页面（属于步骤 9/10）。
6. 为了“先跑通”而绕开 APIM、App Insights、shared-observability、target registry 的临时长期方案。

---

## 7. 步骤 3 的交付物要求

步骤 3 完成时，至少应形成以下产物：

| 产物 | 要求 |
|---|---|
| 模型 deployment 事实记录 | 明确 AOAI 资源、deployment 名称、模型名、版本、endpoint、区域 |
| 调用验证入口 | 直连 AOAI 烟测脚本可用，输出可证明端点可调用 |
| APIM 接入 | `/native-model` API 与 MSI 认证方案落地 |
| target registry 一致性 | `targets.json` 中 native model 条目与真实部署一致 |
| tracing / evidence 设计闭环 | 明确适用时的 Foundry tracing、APIM tracing、AOAI 平台诊断、shared-observability 的关联方式 |
| 后续步骤复用基线 | RAG、Tier 1、evaluation、red teaming 可直接把该 target 当作既有对象使用 |

---

## 8. 验收口径（需求视角）

从需求角度看，步骤 3 至少满足以下条件，才可视为“准备进入实施完成状态”：

1. 已有一个经过确认的原生文本模型 deployment，并且名称、版本、endpoint 可被明确记录。
2. 直连 AOAI 的最小烟测路径可用，能稳定返回非空响应。
3. APIM `/native-model` 被定义为统一治理入口，而不是停留在设计外的直连方式。
4. `foundry_native_model` 的 target 身份、字段、registry 条目和后续指标口径一致。
5. 适用时的 Foundry tracing、APIM tracing、AOAI 平台诊断、App Insights 和 Blob evidence 的责任边界清晰，不互相替代。
6. 步骤 2、9、13、15 可以在不重做模型身份设计的前提下直接复用该 target。

---

## 9. 停止点与人工确认点

出现以下任一情况时，Copilot 应停止自动推进并请求用户确认：

1. `gpt-5.4-nano` 在目标区域不可用、配额不足、或必须更换模型。
2. 需要新增本设计未批准的 Azure 资源、资源组、网络路径或额外服务。
3. 需要修改 `.env.local.L4` 中现有变量名或新增平行命名。
4. 需要偏离 `disableLocalAuth = true`、改用 API key 或绕开 Entra 认证。
5. 需要长期绕过 APIM 才能完成调用。

---

## 10. 当前结论

步骤 3 的需求已经可以明确为：

- **交付一个被 Domain 4 正式纳管的 Foundry 原生文本模型 target**
- **该 target 同时满足部署、调用、APIM 代理、tracing、证据、registry 与后续复用要求**
- **它既是独立治理对象，也是步骤 2 RAG 服务和后续步骤的基础模型依赖**

因此，步骤 3 的下一阶段不应从“怎么临时调用模型”开始，而应从**deployment 事实、APIM 接入、target identity 和证据链闭环**这四个点同步推进。

基于 2026-05-14 的实际执行结果，以上四项中的 **deployment 事实、APIM 接入、target identity** 已落地，且已验证：

- 直连 AOAI deployment 可调用
- APIM `/native-model/chat/completions` 可返回 200
- APIM diagnostics 已写入 App Insights
- AOAI 平台诊断日志中可见 `modelDeploymentName = AIGovernTrustworthyDemoNativeModel`
- 当前 APIM → AOAI REST 调用链不单独要求 Foundry Studio Tracing 页面出现专属 span；该路径的平台侧证据以 APIM dependency + AOAI `AzureDiagnostics` 为准
