# Domain 4 · Agent（Foundry 自定义 Agent + Copilot Studio Agent）设计

## 1. 文档定位

本文件是 `docs/design-L2-domain-4-prerequisites.md` 中**步骤 6**的专用 L3 设计文档，聚焦两类 Agent：

1. Azure AI Foundry 自定义 Agent
2. Microsoft Copilot Studio 自定义 Agent

本文件用于固化步骤 6 的已确认目标、最小实现方案、APIM 接入要求、日志边界，以及 Entra ID / SPN 运行身份与赋权边界。

## 2. 关联文档

| 文档 | 关系 |
|---|---|
| `docs/design-L2-domain-4-prerequisites.md` | 步骤总表、步骤 6 上层需求入口 |
| `docs/design-L2-domain-4-prerequisites-lowleveldesign.md` | 环境变量、资源名、步骤 6 占位项 |
| `docs/design-L2-domain-4-output-trustworthiness.md` | Domain 4 指标与 target type 拆分要求 |
| `docs/design-L3-domain-4-apim.md` | `/foundry-agent`、`/copilot-studio` 的 APIM 设计 |
| `docs/design-L3-domain-4-monitoring-tracing-logging.md` | 平台 tracing、caller evidence、Blob archive 规则 |
| `packages/shared-observability/README.md` | `foundry_agent`、`copilot_studio_agent` 的 evidence 语义 |
| `infra/target-registry/targets.json` | 两类 Agent 的纳管清单 |

---

## 3. 步骤 6 在当前项目中的位置

步骤 6 不是单独做两个聊天机器人 demo，而是把**Agent 作为独立治理对象**正式纳入 Domain 4。

在步骤 6 之前，步骤 1-5 已经提供了基础：

| 已完成步骤 | 对步骤 6 的支撑 |
|---|---|
| 步骤 1：观测基础设施 | 已有 APIM、App Insights、Blob archive、统一查询面 |
| 步骤 2：RAG Service | 已有治理材料、文档问答场景、受管 evidence 设计 |
| 步骤 3：Foundry 原生模型 | 已有现成 AOAI model 可复用 |
| 步骤 4：Foundry fine-tune 模型 | 已补齐第二类 Foundry target 接入路径 |
| 步骤 5：VM 模型 API | 已确认非平台内建 target 的治理边界 |

因此，步骤 6 的本质是补齐两类 target：

| 子对象 | target_type | 必须独立治理 |
|---|---|---|
| Foundry 自定义 Agent | `foundry_agent` | 是 |
| Copilot Studio Agent | `copilot_studio_agent` | 是 |

**禁止事项**：

- 不得把两类 Agent 合并统计
- 不得与 RAG、Foundry 模型、VM 模型、Tier 1、Tier 2 混成一个总数
- 不得绕过 APIM 作为后续 runner / app 的默认调用入口

---

## 4. 本步骤的完成定义

步骤 6 完成时，至少应满足：

1. 有一个可外部调用的 Foundry Agent
2. 有一个可外部调用的 Copilot Studio Agent
3. 两者都有稳定的 ID、调用方式、纳管记录
4. 两者都已映射到 APIM 后端
5. 两者都已纳入 `infra/target-registry/targets.json`
6. 两者都能为步骤 7 / 10 / 11 提供稳定 target

本步骤的最小完成物是：**可纳管、可调用、可验证**。

---

## 5. 范围与非目标

### 5.1 本步骤范围

- 两类 Agent 的最小场景定义
- 知识来源与最小功能边界
- APIM 后端映射
- App Insights / tracing 边界
- target registry / 环境变量要求
- Entra ID / SPN 身份与赋权方案

### 5.2 本步骤非目标

1. 多 Agent 编排
2. 复杂 tool calling
3. 自定义 plugin / connector 生态扩展
4. 生产级细粒度安全模型
5. 完整 evaluation / red teaming 实施
6. Tier 1 / Tier 2 connector 开发
7. 未获批准的新云资源扩张

---

## 6. 已确认的最小实现方案

### 6.1 Foundry Agent：已确认方案

Foundry Agent 使用**当前已存在的 AOAI model**，并上传以下 5 个 AI Governance 文档作为知识源：

1. `NIST.AI.100-1.pdf`
2. `NIST.AI.600-1.pdf`
3. `OJ_L_202401689_EN_TXT.pdf`
4. `OWASP-Top-10-for-LLMs-v2025.pdf`
5. `sgmodelaigovframework2.pdf`

目标能力是：Agent 可以基于这 5 个文档回答治理问题。

### 6.2 Copilot Studio Agent：已确认方案

Copilot Studio Agent 使用**最简单方式**创建，并接入同 tenant 的 SharePoint Site `SalesTeamSite` 上的指定文件信息：

- Site：`SalesTeamSite`
- 文件链接：`https://mngenvmcap029189.sharepoint.com/:x:/s/SalesTeamSite/IQC2cWs5lqCaSYWalJauemMCAUbHDrruCzVEaVbM0AW-ZLc?e=PYFTEg`

目标能力是：Agent 能读取该文件的信息，并回答相关问题。

### 6.3 日志边界：已确认方案

两类 Agent **自身都不要求写自定义 LLM log**。

具体边界如下：

| 对象 | 本体是否写自定义 LLM log | 希望保留的日志来源 |
|---|---|---|
| Foundry Agent | 否 | Foundry 平台 tracing / monitoring，尽量接入 App Insights 查询面 |
| Copilot Studio Agent | 否 | APIM 日志为最低保证；如 Power Platform / Copilot Studio 有可行 App Insights 路径，则尽量接入 |

### 6.4 API 接入：已确认方案

两类 Agent 的 API 都必须挂到 APIM 后端：

| 对象 | APIM 路径 | 后端类型 |
|---|---|---|
| Foundry Agent | `/foundry-agent` | Foundry Agent API |
| Copilot Studio Agent | `/copilot-studio` | Direct Line API |

---

## 7. 具体需求

### 7.1 Foundry Agent 需求

#### 7.1.1 必要输入

- `L4_AI_FOUNDRY_PROJECT_NAME`
- `L4_AI_FOUNDRY_PROJECT_ENDPOINT`
- `L4_FOUNDRY_AGENT_NAME`
- 当前已存在 AOAI model 的 deployment 信息
- 上述 5 个 PDF 的可上传来源

#### 7.1.2 必要产出

- `L4_FOUNDRY_AGENT_ID`
- Agent 名称、project、endpoint / invocation 方式
- 绑定模型信息
- 5 个知识文件已接入的事实记录
- APIM `/foundry-agent` 配置依据
- smoke test 调用脚本
- target registry 记录

#### 7.1.3 具体要求

1. Agent 必须创建在既有 Foundry Project 中
2. Agent 固定命名为 `AIGovernTrustworthyDemoFoundryAgent`
3. 必须复用当前已存在的 AOAI model，不新增一套平行模型资源
4. 必须上传并使用上述 5 个治理 PDF
5. Agent 的问题回答范围应聚焦治理文档内容
6. Agent 自身不负责写自定义 LLM log
7. Foundry 平台 tracing / monitoring 应作为其主要平台侧日志来源
8. 对外统一入口为 `APIM /foundry-agent`
9. 调用方后续若通过脚本 / Tier 1 调用该 Agent，应按 `target_type=foundry_agent` 写 caller evidence

### 7.2 Copilot Studio Agent 需求

#### 7.2.1 必要输入

- `L4_COPILOT_STUDIO_AGENT_NAME`
- Copilot Studio environment
- 对 `SalesTeamSite` 及目标文件的可访问权限
- 发布后的 bot 信息
- Direct Line channel 配置结果

#### 7.2.2 必要产出

- `L4_COPILOT_STUDIO_BOT_ID`
- `L4_COPILOT_STUDIO_ENVIRONMENT_ID`
- `L4_COPILOT_STUDIO_DIRECTLINE_SECRET`
- Agent 名称、environment、bot id、调用方式
- APIM `/copilot-studio` 配置依据
- smoke test 调用脚本
- target registry 记录

#### 7.2.3 具体要求

1. Agent 采用最简单的 Copilot Studio 原生方式创建
2. 第一切片的知识来源就是同 tenant SharePoint `SalesTeamSite` 的指定文件
3. 第一切片不引入 Power Automate action、Dataverse 扩展、复杂多渠道发布
4. Agent 自身不负责写自定义 LLM log
5. 对外统一入口为 `APIM /copilot-studio`
6. 默认通过 Direct Line 暴露给外部脚本 / 后续 app 调用
7. 调用方后续若通过脚本 / Tier 1 调用该 Agent，应按 `target_type=copilot_studio_agent` 写 caller evidence

---

## 8. 调用链与日志设计

### 8.1 Foundry Agent

```text
Caller / Script / Tier1
        |
        v
APIM /foundry-agent
        |
        v
Foundry Agent API
        |
        v
Foundry internal hops / knowledge / model
```

**日志来源分工**：

| 层 | 日志职责 |
|---|---|
| APIM | 记录 HTTP hop tracing |
| Foundry 平台 | 记录 Agent 内部 hop、tool / model 执行、平台 tracing |
| Caller Python 代码 | 如果存在调用方脚本 / app，则由调用方写 shared-observability evidence |

**字段要求**：

- `target_type = foundry_agent`
- `target_id = <agent_id>`
- `trace_id`
- `response_id`（如平台可见）
- `archive_id`
- `payload_ref`

> 说明：Foundry Agent 的内部模型名 / 版本不一定总能由外部调用方稳定拿到，因此 `model_name` / `model_version` 可以为空，但 `agent_id` 不可缺失。

### 8.2 Copilot Studio Agent

```text
Caller / Script / Tier1
        |
        v
APIM /copilot-studio
        |
        v
Direct Line API
        |
        v
Copilot Studio Agent runtime
        |
        v
SharePoint content access
```

**日志来源分工**：

| 层 | 日志职责 |
|---|---|
| APIM | 最低保证，记录 HTTP hop tracing |
| Copilot Studio / Power Platform 平台 | 如可接入则尽量接入，不作为本期唯一依赖 |
| Caller Python 代码 | 如果存在调用方脚本 / app，则由调用方写 shared-observability evidence |

**字段要求**：

- `target_type = copilot_studio_agent`
- `target_id = <bot_id>`
- `trace_id`
- `response_id = <conversation_id / activity_id 等效标识>`
- `archive_id`
- `payload_ref`

---

## 9. APIM 设计要求

### 9.1 Foundry Agent

- APIM 路径固定为 `/foundry-agent`
- 后端是 Foundry Agent API，不是 AOAI deployment API
- APIM 负责统一入口、traceparent 透传、diagnostics
- APIM 不应把 agent_id 硬编码到平台策略里，除非后续明确只保留单 Agent 模式

### 9.2 Copilot Studio Agent

- APIM 路径固定为 `/copilot-studio`
- 后端固定到 Direct Line API
- APIM 使用 Named Value 保存 Direct Line secret
- 调用方默认不直接持有 Direct Line secret

---

## 10. target registry 与环境变量要求

### 10.1 target registry

#### Foundry Agent 最小记录

```json
{
  "target_id": "AIGovernTrustworthyDemoFoundryAgent",
  "target_type": "foundry_agent",
  "display_name": "Foundry Custom Agent",
  "endpoint": "<agent-endpoint>",
  "apim_path": "/foundry-agent",
  "auth": "entra",
  "status": "pending|active"
}
```

#### Copilot Studio Agent 最小记录

```json
{
  "target_id": "AIGovernTrustworthyDemoCopilotStudioAgent",
  "target_type": "copilot_studio_agent",
  "display_name": "Copilot Studio Agent",
  "bot_id": "<bot-id>",
  "environment_id": "<environment-id>",
  "directline_endpoint": "https://directline.botframework.com/v3/directline",
  "apim_path": "/copilot-studio",
  "auth": "directline_secret",
  "status": "pending|active"
}
```

### 10.2 环境变量

步骤 6 的 `.env.local.L4` 只保留程序调用或自动化脚本必须读取的值；名称、environment、bot id、connection owner、license 状态等人工记录项写入本文档。

| 对象 | `.env.local.L4` 变量 | 说明 |
|---|---|---|
| Foundry Agent | `L4_FOUNDRY_AGENT_ID` | APIM / smoke test 调用 Foundry Agent API 时必需 |
| Copilot Studio Agent | `L4_COPILOT_STUDIO_DIRECTLINE_SECRET` | APIM Named Value 与 Direct Line 调用必需；仅在发布并启用 Direct Line 后填入 |

---

## 11. Entra ID / SPN 运行身份与赋权设计

这是步骤 6 当前最重要的设计问题。

### 11.1 Foundry Agent 会用什么 Entra ID account 运行

**结论**：

1. 调用 Foundry Agent API 的客户端，**可以**使用你指定的 Entra ID 身份，例如用户账号或 SPN。
2. 但 Foundry Agent 的**平台内部运行时**，通常**不是**一个像 App Service 那样可任意指定的“自定义 SPN 进程身份”。
3. Agent 对模型、知识源、连接对象的访问，通常由 Foundry Project / Connection / 平台托管身份机制决定。

换句话说，要区分两层身份：

| 层 | 是否可由你直接指定 SPN |
|---|---|
| 调用 Agent API 的客户端身份 | 通常可以 |
| Agent 平台内部执行身份 | 通常不能按“任意自定义 SPN”直接指定 |

### 11.2 Foundry Agent 如果不能直接跑在自定义 SPN 下，应该怎么赋权

正确思路不是先问“Agent 能不能强绑某个 SPN”，而是先问：

1. Agent 实际访问哪些资源
2. 这些资源是通过哪种平台连接或托管身份访问
3. 哪个身份才是真正访问资源的主体

在本步骤里，Foundry Agent 至少要访问：

- 既有 AOAI model
- 5 个 PDF 知识文件

因此赋权应分两层：

| 对象 | 建议赋权方式 |
|---|---|
| 调用 Agent API 的客户端 SPN | 给它调用 Agent API 所需权限 |
| Foundry Project / Agent 背后的平台连接或托管身份 | 给它访问 AOAI model 和知识文件所需权限 |

**设计结论**：

- 你通常可以控制“谁来调用 Foundry Agent API”
- 但通常**不能把 Foundry Agent 整体当成一个可直接绑定任意 SPN 的运行进程**

### 11.3 Copilot Studio Agent 会用什么 Entra ID account 运行

**结论**：

1. Copilot Studio Agent 运行在 Copilot Studio / Power Platform 托管环境中。
2. 它通常也**不是**一个你可以像 Web App 一样任意指定“运行时 SPN”的应用进程。
3. 对外调用 Direct Line 时，认证使用的是 Direct Line channel / secret。
4. 对 SharePoint 内容的访问，取决于知识源接入方式、连接上下文以及背后的 Microsoft 365 / SharePoint 权限模型。

### 11.4 Copilot Studio Agent 访问 SharePoint 时如何赋权

在你当前要求的**最简单方案**下，最现实的做法是：

1. 用一个对 `SalesTeamSite` 和该文件有访问权限的 Entra ID 用户完成知识源接入
2. 确认该 Agent 发布后能够读取并回答该文件内容
3. 把这个用户视为当前第一切片的“配置与知识接入主体”

这意味着第一切片里，**优先使用有权限的用户身份完成 SharePoint 知识接入**，而不是一开始就要求 Agent 本体绑定某个 SPN。

### 11.5 如果你强制要求“必须使用我指定的 SPN”，推荐做法

如果后续明确要求后台访问必须用指定 SPN，建议采用**间接方案**：

1. Foundry Agent：把外部知识访问改成你可控的 API / connector / 中间层，由这个中间层使用指定 SPN
2. Copilot Studio Agent：把 SharePoint 访问改成 custom connector、Power Automate flow 或你自己的后端，再由该层使用指定应用注册 / SPN

这样真正绑定 SPN 的是**你控制的后端连接层**，不是 Agent 托管运行时本体。

### 11.6 当前建议

基于“最小、能跑、可治理”的原则，当前建议是：

| 对象 | 当前建议 |
|---|---|
| Foundry Agent | 手工创建 Agent；客户端调用可用 SPN；资源访问按 Foundry 平台连接 / 身份赋权 |
| Copilot Studio Agent | 手工创建 Agent；先用有权限的用户接入 SharePoint；Direct Line 经 APIM 暴露 |

---

## 12. 与 Domain 1 资产台账的对齐要求

### 12.1 Foundry Agent

- 至少记录 `agent_name`、`agent_id`、所属 project

### 12.2 Copilot Studio Agent

- 至少记录 `bot_id`、`environment_id`、显示名
- 应与 Domain 1 Dataverse `bots` 发现结果可对齐

---

## 13. 实施顺序建议

1. 在 Foundry 手工创建 Agent，绑定现有 AOAI model，并上传 5 个 PDF
2. 在 Copilot Studio 手工创建最小 Agent，并接入 `SalesTeamSite` 目标文件
3. 记录两类 Agent 的真实 ID、environment、调用方式
4. 将两类 Agent API 都挂到 APIM 后端
5. 完成最小 smoke test
6. 回填 `targets.json` 与相关文档

---

## 14. 当前剩余空白

1. Copilot Studio Agent 需要正式 Copilot Studio tenant license 与 `Copilot Studio User License` 后才能发布；trial license 已被 Microsoft Learn 明确标注为不能 publish。
2. Copilot Studio Agent 发布后才能启用 Direct Line 并生成 `L4_COPILOT_STUDIO_DIRECTLINE_SECRET`。
3. SharePoint 原生知识接入已能在 UI 中选择 `SalesTeamSite`，但发布前无法完成端到端问答验证。
4. Copilot Studio 的 bot id / token endpoint / Direct Line channel 信息仍需在发布后记录。
5. 在 license 补齐且用户明确要求继续前，Copilot Studio Agent POC 暂停在当前状态，不继续执行 Direct Line、APIM `/copilot-studio` 收尾。

---

## 15. 当前实测状态（2026-05-17）

### 15.1 Foundry Agent

| 项目 | 当前值 |
|---|---|
| Agent 名称 | `AIGovernTrustworthyDemoFoundryAgent` |
| Agent ID | `asst_qPEQxZ6Gc894gcxQjaIOkdF6` |
| 实际 Project | `AIGovernTrustworthyRAGProject` |
| Model deployment | `AIGovernTrustworthyDemoNativeModelGPT5.4mini`（`gpt-5.4-mini` `2026-03-17`） |
| 知识源 | 5 个 AI Governance PDF 已上传 |
| API surface | Project-level `assistants` / `threads` / `messages` / `runs` API（`api-version=v1`）；旧 hosted `/agents` 面已清空 |
| 旧对象处理 | 旧 Hosted Agent `aigovern-rag-agent` 已删除；deploy SPN 视角下 `/agents` count = 0，`/assistants` count = 1 |
| 平台 tracing | Project UI 可见 tracing / monitoring / diagnostics；真实调用已可经 APIM 完成 |
| APIM 状态 | `/foundry-agent` backend 指向 `https://aigoverntrustworthyfoundry.services.ai.azure.com/api/projects/AIGovernTrustworthyRAGProject`；APIM MSI 获取 `https://ai.azure.com` token；assistants + thread/run smoke test 已通过 |

### 15.2 Copilot Studio Agent

| 项目 | 当前值 |
|---|---|
| Agent 名称 | `AIGovernTrustworthyDemoCopilotStudioAgent` |
| Power Platform environment | `Default-7d3389c6-5b33-43be-b0fd-d7c303755fb5` / `Contoso (default)` |
| Dataverse URL | `https://org1fb702ee.crm.dynamics.com/` |
| Knowledge source | Copilot Studio UI 已接受 `SalesTeamSite` 站点级知识源选择；未暴露单文件 URL 字段或 connection owner 字段 |
| 当前作者用户 | `weishi@MngEnvMCAP029189.onmicrosoft.com` |
| 当前 Dataverse direct roles | `Basic User`、`Environment Maker`、`Bot Author` |
| 角色分配依据 | Microsoft Learn 要求在已有环境中创建 agent 时为自己分配 `agent author`；当前环境内实际可见等效角色为 `Bot Author` |
| 角色分配方式 | 使用已有 Dataverse System Administrator application user `devdeployspn` / `AZ_DEPLOY_CLIENT_ID` 通过 Dataverse Web API 分配并验证 |
| Publish 状态 | 仍阻塞：当前 tenant 只有 `CCIBOTS_PRIVPREV_VIRAL` trial SKU；Microsoft Learn 明确 trial license 可 create/test，但不能 publish；因此当前 POC 暂停于此 |
| Direct Line 状态 | 未启用；需要成功 publish 后才能取得 secret / token endpoint |
| APIM 状态 | `/copilot-studio` 脚本已准备；等待 `L4_COPILOT_STUDIO_DIRECTLINE_SECRET` |

### 15.3 官方文档依据

| 主题 | Microsoft Learn 结论 | 对本项目影响 |
|---|---|---|
| Copilot Studio licensing | 正式使用需要 `Copilot Studio` tenant license 与 `Copilot Studio User License`；trial license 可以创建和测试 agent，但不能 publish | 当前 `CCIBOTS_PRIVPREV_VIRAL` 不足以完成 publish / Direct Line |
| Environment / author access | 在已有环境中创建 agent，需要环境访问，并为用户分配 `agent author` security role | 已按当前环境可见角色分配 `Bot Author` |
| Dataverse security role assignment | 分配 security role 需要 Security Role 表的 Read + Assign 权限；System Administrator 具备所需权限 | 普通用户/API 缺 `prvAssignRole`，最终使用已有 System Administrator application user 完成 |
| Publish / channels | 先 publish agent；发布至少一次后再配置 channel | Direct Line secret 只能在 publish 解锁后继续获取 |

---

## 16. 当前结论

步骤 6 的设计已经明确：

- **Foundry Agent**：使用现有 AOAI model + 5 个 AI Governance PDF；`AIGovernTrustworthyDemoFoundryAgent` / `asst_qPEQxZ6Gc894gcxQjaIOkdF6` 已通过 APIM `/foundry-agent` 端到端验证，可作为步骤 7 下游 target
- **Copilot Studio Agent**：使用最简单方式读取同 tenant `SalesTeamSite` 的目标文件；当前已补齐 `Bot Author`，但发布被正式 Copilot Studio license 阻塞，因此本轮 POC 暂停于此，等待用户后续指令
- **日志边界**：两个 Agent 本体都不写自定义 LLM log；Foundry Agent 优先依赖平台 tracing / App Insights，Copilot Studio 至少依赖 APIM 日志，如可行再补 App Insights
- **APIM**：Foundry Agent 已挂到 APIM `/foundry-agent`；Copilot Studio 仍等待 publish / Direct Line 后挂到 APIM `/copilot-studio`
- **身份边界**：两类 Agent 都不应默认假设能直接绑定任意自定义 SPN 作为运行时进程身份；更现实的是控制调用方身份，并把权限授给实际访问资源的连接 / 平台身份

本文件可以作为继续完成 Copilot Studio publish / Direct Line / APIM 接入时的步骤 6 设计基线。
