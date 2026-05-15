# Domain 4 · APIM 设计文档

## 1. 文档定位

本文档是 `design-L2-domain-4-prerequisites.md` §步骤1（观测基础设施）与 §2.4（统一观测设计）的 APIM 专项设计文档，记录：

- APIM 在 Domain 4 治理架构中的定位与职责
- 需要配置的每一个 API（含前端路径、后端目标、策略设计）
- 观测/遥测配置
- 认证方案
- 当前实现状态与占位符

**关联文档**：
- `design-L2-domain-4-prerequisites.md` §2.4 — 统一观测设计
- `design-L2-domain-4-prerequisites-lowleveldesign.md` §4.2.8 — APIM 资源属性
- `infra/target-registry/targets.json` — 所有 Domain 4 受管目标清单

---

## 2. APIM 定位与职责

### 2.1 在治理架构中的位置

```
外部调用者
(Evaluation Runner / PyRIT / Tier1 / Tier2 / Dashboard)
          │
          ▼
┌─────────────────────────────────────────────────────┐
│              APIM (AIGovernTrustworthyDemoAPIM)     │
│  VNet Internal · Canada East · Developer SKU stv2   │
│                                                     │
│  职责：                                              │
│  ① 统一 AI Gateway — 所有可代理 HTTP hop 的入口      │
│  ② Token 注入 — 向后端注入 MSI / SPN token          │
│  ③ Tracing 中心 — 所有 hop 的 App Insights 日志     │
│  ④ Governance 执行点 — 未来可添加限速/过滤/安全策略  │
└─────────────────────────────────────────────────────┘
          │ 按 path 路由到不同后端
    ┌─────┼─────┬──────┬──────┬────────┬──────────┐
    ▼     ▼     ▼      ▼      ▼        ▼          ▼
Hosted AOAI  AOAI  Foundry DirectLine VM:11434  App
Agent  Native FT    Custom  (Copilot)  (llama.cpp)  Service
(RAG)  Model  Model Agent
```

### 2.2 职责边界

| 职责 | APIM 承担 | APIM 不承担 |
|---|---|---|
| HTTP 请求代理 | ✅ 所有外部可寻址的后端 | Foundry Agent 内部模型 hop |
| Token 注入（MSI） | ✅ 向每个后端自动注入对应 scope token | 客户端侧的身份管理 |
| App Insights tracing | ✅ gateway 请求/响应日志 + correlation | Foundry 内部 span（Foundry tracing 负责）|
| Rate limiting | ✅ 可在此配置（当前未配置） | 客户端业务层限速 |
| Request orchestration | ⚠️ 当前不做（各 API 都是 pass-through）| 跨 API 编排逻辑由调用方负责 |
| TLS termination | ✅ 自动 | — |

### 2.3 网络访问说明

APIM 部署在 **Internal VNet 模式**，Gateway URL 只在 VNet 内部可达：

| 端点类型 | URL | 可达范围 |
|---|---|---|
| Gateway（API 调用入口） | `https://aigoverntrustworthydemoapim.azure-api.net` | VNet 内部（subnet-APIM 所在 VNet）|
| Regional Gateway | `https://aigoverntrustworthydemoapim-canadaeast-01.regional.azure-api.net` | VNet 内部 |
| Management（ARM 配置） | `https://aigoverntrustworthydemoapim.management.azure-api.net` | 互联网（APIM 内部管理面）|
| Developer Portal | `https://aigoverntrustworthydemoapim.developer.azure-api.net` | VNet 内部 |

> **当前测试状态（2026-05-14）**：当前开发 / 测试 Linux 服务器已与 APIM 所在 VNet 具备联通条件，且 DNS 可将 `aigoverntrustworthydemoapim.azure-api.net` 解析到私网 `10.1.2.4`，因此已完成真实流量经 APIM Gateway 的调用验证。
> ARM Management API 仍可从公网访问，用于配置核查与脚本执行。

---

## 3. APIM 实例属性（已配置）

| 属性 | 值 |
|---|---|
| 资源名 | `AIGovernTrustworthyDemoAPIM` |
| 资源组 | `AIGovernTrustworthyRG` |
| SKU | `Developer`，`stv2` |
| 区域 | `Canada East` |
| 状态 | `Succeeded` ✅ |
| VNet 模式 | `Internal` ✅ |
| 子网 | `subnet-APIM` (10.1.2.0/28)，`AIGovernCanadaEastVNET` |
| Private IP | `10.1.2.4` |
| Public IP（Azure 自动分配） | `40.86.204.28` |
| NSG | `nsg-subnet-APIM`（在 `AIGovernDemoRG`），含所有 APIM 必需规则 |
| System-Assigned MSI | `32195307-0138-49c1-b36f-381928efcd5d` |
| MSI RBAC | 旧 `aigovenaihubproject` 已授权；RAG Web App 路径不再依赖 Hosted Agent 专用 Foundry RBAC |
| App Insights Logger | `applicationinsights`（linked to `aiexvddh5zbxgtg`）✅ |
| Gateway Diagnostics | 已启用，100% sampling，W3C correlation，verbosity=information ✅ |

---

## 4. 产品（Products）设计

APIM Product 用于将多个 API 组合打包，并控制访问策略（subscription、rate limit 等）。

| Product 名 | 用途 | 包含 API | Subscription 要求 | 状态 |
|---|---|---|---|---|
| `governance-eval` | Evaluation Runner、PyRIT Runner、smoke test 脚本使用 | 所有 API | 不需要（Entra token 即可） | ⬜ 待创建 |
| `governance-internal` | Tier 1 / Tier 2 App Service 在 VNet 内调用使用 | `/rag`、`/native-model`、`/finetune-model`、`/foundry-agent` | 不需要（Entra token + VNet）| ⬜ 待创建 |

> 当前阶段未创建 Product，API 直接开放（`subscriptionRequired: false`）。  
> 正式治理场景下应启用 Product 并限制 subscription key 或 Entra 条件访问策略。

---

## 5. 前端 API 设计

每个受管治理目标对应一个 APIM API。API 的 `path` 决定了 Gateway URL 上的访问路径。

### 5.1 API 汇总表

| API 名 | APIM 路径 | 后端目标类型 | 认证 scope | 实现状态 |
|---|---|---|---|---|
| `rag-service` | `/rag` | RAG Web App | N/A | ✅ 已配置（Web App backend + `traceparent` 注入策略）|
| `native-model` | `/native-model` | AOAI gpt-5.4-nano | `https://cognitiveservices.azure.com` | ✅ 已配置（MSI + `traceparent` + API diagnostics） |
| `finetune-model` | `/finetune-model` | AOAI fine-tune deployment | `https://cognitiveservices.azure.com` | ⬜ 待配置（后端未就绪）|
| `foundry-agent` | `/foundry-agent` | Foundry 自定义 Agent | `https://ml.azure.com` | ⬜ 待配置（Agent 未创建）|
| `copilot-studio` | `/copilot-studio` | Direct Line（Copilot Studio） | DirectLine secret | ⬜ 待配置（Agent 未创建）|
| `vm-model` | `/vm-model` | VM llama.cpp API（Phi-3-mini-4k-instruct） | 无（VNet 内访问）| ⬜ 待配置（VM 已创建；运行时未部署）|
| `tier1-app` | `/tier1` | Tier 1 Consumer App Service | `https://management.azure.com` | ⬜ 待配置（App 未部署）|
| `tier2-app` | `/tier2` | Tier 2 Consumer App Service | `https://management.azure.com` | ⬜ 待配置（App 未部署）|

### 5.2 API 前端配置规范（通用）

每个 API 的前端配置遵循以下规范：

```
displayName:        见各 API 章节
path:               见 5.1 汇总表
protocols:          ["https"]
subscriptionRequired: false（现阶段，后续 Product 配置后改为 true）
apiType:            http
```

---

## 6. 后端（Backend）设计

### 6.1 后端汇总

每个 API 在当前实现中可通过两种方式记录实际目标地址：

1. 单独的 APIM Backend entity
2. 直接在 API `serviceUrl` 与 `set-backend-service` policy 中内联定义

| Backend 名 | serviceUrl | 认证方式 | 状态 |
|---|---|---|---|
| `rag-webapp` | `https://AIGovernTrustworthyRAGApp.azurewebsites.net` | 无（APIM -> Web App 直接 HTTPS） | ✅ 已配置（`set-backend-service` 内联策略）|
| `aoai-native-model` | `https://aigoverntrustworthyaoai.openai.azure.com/openai/deployments/AIGovernTrustworthyDemoNativeModel` | MSI，scope=`https://cognitiveservices.azure.com` | ✅ 已通过 API `serviceUrl` + `set-backend-service` 配置 |
| `aoai-finetune-model` | `https://aigoverntrustworthyaoai.openai.azure.com/openai/deployments/AIGovernTrustworthyDemoFineTuneModel` | MSI，scope=`https://cognitiveservices.azure.com` | ⬜ 待创建（deployment 未就绪）|
| `foundry-custom-agent` | `https://eastus2.api.azureml.ms/agents/v1.0/subscriptions/47da4b42.../workspaces/aigovenaihubproject` | MSI，scope=`https://ml.azure.com` | ⬜ 待创建（Agent 未创建）|
| `copilot-studio-directline` | `https://directline.botframework.com/v3/directline` | Named Value `copilot-directline-secret`（Header `Authorization: Bearer {secret}`）| ⬜ 待创建（Agent 未创建）|
| `vm-llama-server` | `http://10.1.1.8:11434` | 无 | ⬜ 待创建（VM 已创建；service 未启动）|
| `tier1-app-service` | `https://aigoverntrustworthydemotier1app.azurewebsites.net` | Entra（透传客户端 token）| ⬜ 待创建（App 未部署）|
| `tier2-app-service` | `https://aigoverntrustworthydemotier2app.azurewebsites.net` | Entra（透传客户端 token）| ⬜ 待创建（App 未部署）|

> **注意**：APIM Internal VNet 模式下，`vm-llama-server` 后端使用 VM 私有 IP，  
> 需要 APIM 子网和 VM 子网之间的 VNet Peering 或同一 VNet 内可路由。

### 6.2 MSI 认证说明

APIM 对需要 Azure 身份的后端使用 System-Assigned MSI 自动获取 token：

| 后端资源类型 | Token Scope | MSI 所需 RBAC |
|---|---|---|
| Azure OpenAI（AOAI chat completions） | `https://cognitiveservices.azure.com` | `Cognitive Services OpenAI User` on `AIGovernTrustworthyAOAI` ✅ |
| App Service（Tier1/Tier2） | 透传客户端 token（不由 MSI 注入）| — |
| Copilot Studio Direct Line | DirectLine secret（Named Value）| — |
| VM llama.cpp | 无 auth | — |

**AOAI MSI RBAC（已执行）**：
```bash
az role assignment create \
  --assignee 32195307-0138-49c1-b36f-381928efcd5d \
  --role "Cognitive Services OpenAI User" \
  --scope /subscriptions/47da4b42-0493-49ff-b3c8-45df3ae06821/resourceGroups/AIGovernTrustworthyRG/providers/Microsoft.CognitiveServices/accounts/AIGovernTrustworthyAOAI
```

---

## 7. API 详细设计

### 7.1 `rag-service` — RAG 治理问答服务（Web App）

**状态**：步骤 2 已改为 RAG Web App 方案，后端不再使用 Hosted Agent。

**前端**：
```
path:        /rag
serviceUrl:  https://AIGovernTrustworthyRAGApp.azurewebsites.net
```

**Operations**：

| Operation ID | 方法 | 路径模板 | 说明 |
|---|---|---|---|
| `query-rag` | POST | `/responses` | 调用 RAG Web App；body 采用轻量级 Responses 风格 JSON（至少包含 `input`） |
| `health-check` | GET | `/health` | 透传 RAG Web App 健康检查 |

**Inbound Policy**（API 级别）：
```xml
<policies>
  <inbound>
    <base />
    <set-header name="traceparent" exists-action="skip">
      <value>@("00-" + context.RequestId.ToString("N") + "-" + context.RequestId.ToString("N").Substring(16, 16) + "-01")</value>
    </set-header>
    <set-backend-service base-url="https://aigoverntrustworthyragapp-hchcfae9hpczcrcx.canadaeast-01.azurewebsites.net" />
  </inbound>
  <backend>
    <base />
  </backend>
  <outbound>
    <base />
    <set-header name="x-aigov-apim-request-id" exists-action="override">
      <value>@(context.RequestId.ToString())</value>
    </set-header>
  </outbound>
  <on-error>
    <base />
    <set-status code="502" reason="Bad Gateway" />
  </on-error>
</policies>
```

**调用示例**（从 VNet 内部）：
```bash
POST https://aigoverntrustworthydemoapim.azure-api.net/rag/responses
Content-Type: application/json
{
  "input": "What are the four core functions of NIST AI RMF?"
}
```

**设计说明**：

- APIM 不执行 RAG orchestration，只负责 pass-through、diagnostics、限流策略。
- RAG Web App 内部完成 PDF 切块、轻量级检索、模型调用、LLM input/output/error 捕获和 Blob evidence 写入。
- 当调用方未显式传入 `traceparent` 时，APIM 使用 `context.RequestId` 自动生成一条 W3C Trace Context；当调用方已带 `traceparent` 时，APIM 保留原值。
- RAG Web App 自带的 Chat UI 不直接从浏览器访问 Internal APIM，而是由 Web App 内部 `/ui/responses` 代理转发到 `L4_RAG_SERVICE_URL`。
- RAG 路径的主要关联链路是 APIM diagnostics + Web App telemetry + Blob evidence；不依赖 Hosted Agent tracing。

---

### 7.2 `native-model` — AOAI gpt-5.4-nano 原生模型 ✅

**状态**：已配置（2026-05-14）

**前端**：
```
displayName:  Native Model (gpt-5.4-nano)
path:         /native-model
serviceUrl:   https://aigoverntrustworthyaoai.openai.azure.com/openai/deployments/AIGovernTrustworthyDemoNativeModel
```

**Operations**：

| Operation ID | 方法 | 路径模板 | 说明 |
|---|---|---|---|
| `chat-completions` | POST | `/chat/completions` | Chat completion 请求 |

**Inbound Policy**（API 级别）：
```xml
<policies>
  <inbound>
    <base />
    <set-header name="traceparent" exists-action="skip">
      <value>@("00-" + context.RequestId.ToString("N") + "-" + context.RequestId.ToString("N").Substring(16, 16) + "-01")</value>
    </set-header>
    <!-- 注入 APIM MSI token，scope=cognitiveservices.azure.com -->
    <authentication-managed-identity
      resource="https://cognitiveservices.azure.com"
      output-token-variable-name="msi-token" />
    <set-header name="Authorization" exists-action="override">
      <value>@("Bearer " + (string)context.Variables["msi-token"])</value>
    </set-header>
    <!-- 注入 AOAI API version -->
    <set-query-parameter name="api-version" exists-action="override">
      <value>2025-01-01-preview</value>
    </set-query-parameter>
    <set-backend-service base-url="https://aigoverntrustworthyaoai.openai.azure.com/openai/deployments/AIGovernTrustworthyDemoNativeModel" />
  </inbound>
  <backend>
    <base />
  </backend>
  <outbound>
    <base />
    <set-header name="x-aigov-apim-request-id" exists-action="override">
      <value>@(context.RequestId.ToString())</value>
    </set-header>
  </outbound>
  <on-error>
    <base />
    <set-status code="502" reason="Bad Gateway" />
    <set-header name="Content-Type" exists-action="override">
      <value>application/json</value>
    </set-header>
    <set-body>@{
      return new JObject(
        new JProperty("error", context.LastError.Message),
        new JProperty("source", context.LastError.Source),
        new JProperty("apim_request_id", context.RequestId.ToString())
      ).ToString();
    }</set-body>
  </on-error>
</policies>
```

**前置条件**：
- `AIGovernTrustworthyAOAI` AOAI 资源上 `disableLocalAuth=true` ✅ 已设置
- APIM MSI 需要 `Cognitive Services OpenAI User` on `AIGovernTrustworthyAOAI` ✅ 已完成

**已执行**：
```bash
bash infra/apim/setup-native-model-api.sh
```

**验证结果**：
- 直连 AOAI：`apps/native-model/scripts/test_native_model.py` 返回 200 且 response 非空
- APIM `/native-model/chat/completions`：2026-05-14 返回 200，model=`gpt-5.4-nano-2026-03-17`
- API-level diagnostics：`applicationinsights` 已绑定，`httpCorrelationProtocol = W3C`
- App Insights：出现 APIM → AOAI dependency 记录，`OperationName = native-model;rev=1 - chat-completions`
- AOAI 平台诊断：`AzureDiagnostics` 中可见 `modelDeploymentName = AIGovernTrustworthyDemoNativeModel`、`modelName = gpt-5.4-nano`、`modelVersion = 2026-03-17`

> **说明**：当前 `APIM -> AOAI REST` 原生模型调用链不单独要求 Foundry Studio Tracing 页面出现专属 span；该路径的平台证据以 APIM dependency + AOAI 平台诊断为准。

---

### 7.3 `finetune-model` — AOAI Fine-tune 模型 ⬜

**状态**：待配置（Fine-tune 部署未就绪）

**前端**：
```
 displayName:  Fine-tune Model (gpt-4.1)
path:         /finetune-model
serviceUrl:   https://aigoverntrustworthyaoai.openai.azure.com/openai/deployments/AIGovernTrustworthyDemoFineTuneModel
```

**Operations**：与 `native-model` 相同（`POST /chat/completions`）

**Inbound Policy**：与 `native-model` 相同（`cognitiveservices.azure.com` scope）

**API-level diagnostics**：与 `native-model` 相同（`applicationinsights`、100% sampling、W3C、verbosity=`information`）

**自动化实施要求**：

1. APIM `/finetune-model` 的落地方式应与步骤 3 的 `/native-model` 保持一致，优先复用相同脚本模式。
2. 推荐新增 `infra/apim/setup-finetune-model-api.sh`，其结构应与 `setup-native-model-api.sh` 一致，仅替换：
   - `api-id = finetune-model`
   - `path = /finetune-model`
   - `deployment = AIGovernTrustworthyDemoFineTuneModel`
3. Policy、MSI、`traceparent`、`api-version`、`x-aigov-apim-request-id`、API diagnostics 全部与 `native-model` 保持一致。
4. 该脚本仅允许修改**既有** APIM service 内的 API / operation / policy / diagnostics，以及校验既有 AOAI 上的访问授权；不得创建或删除 APIM、AOAI、Storage 等云资源。
5. 若 `AIGovernTrustworthyDemoFineTuneModel` deployment 尚不存在，且其创建被当前策略视为禁止的资源创建，则 APIM 配置阶段必须停止，不得伪造 backend 指向。
4. Diagnostics 验证口径也与 `native-model` 保持一致：APIM dependency + AOAI 平台诊断。

**前置条件**：
- Fine-tune 模型训练和部署完成（步骤 4）
- `AIGovernTrustworthyDemoFineTuneModel` deployment 处于 `Succeeded`
- `L4_FOUNDRY_FINETUNE_MODEL_ENDPOINT` 填入实际值
- APIM MSI 已具备对 `AIGovernTrustworthyAOAI` 的 `Cognitive Services OpenAI User`（步骤 3 已满足，可直接复用）

---

### 7.4 `foundry-agent` — Foundry 自定义 Agent ⬜

**状态**：待配置（Agent 未创建）

**前端**：
```
displayName:  Foundry Custom Agent
path:         /foundry-agent
serviceUrl:   https://eastus2.api.azureml.ms/agents/v1.0/subscriptions/47da4b42.../workspaces/aigovenaihubproject
```

**Operations**：与 `rag-service` 完全相同（Foundry Agent API 结构一致）

**Inbound Policy**：与 `rag-service` 相同（`ml.azure.com` scope，`api-version=2024-05-01-preview`）

> **区别**：客户端在 `create-run` 操作的请求体中传入不同的 `assistant_id`（自定义 Agent 的 ID）。  
> APIM 不硬编码 agent_id，由调用方在请求体中指定。

**前置条件**：
- 自定义 Foundry Agent 在 `ai.azure.com` 中创建（步骤 7）
- `L4_FOUNDRY_AGENT_ID` 填入实际值

---

### 7.5 `copilot-studio` — Copilot Studio Agent（Direct Line）⬜

**状态**：待配置（Agent 未创建）

**前端**：
```
displayName:  Copilot Studio Agent
path:         /copilot-studio
serviceUrl:   https://directline.botframework.com/v3/directline
```

**Operations**：

| Operation ID | 方法 | 路径模板 | 说明 |
|---|---|---|---|
| `start-conversation` | POST | `/conversations` | 创建 Direct Line 对话 |
| `send-activity` | POST | `/conversations/{conversationId}/activities` | 发送消息 |
| `get-activities` | GET | `/conversations/{conversationId}/activities` | 获取回复 |

**Inbound Policy**（API 级别）：
```xml
<policies>
  <inbound>
    <base />
    <!-- Direct Line 使用 secret token，不用 MSI -->
    <!-- DirectLine secret 存储在 APIM Named Value -->
    <set-header name="Authorization" exists-action="override">
      <value>@("Bearer " + context.Variables["copilot-directline-secret"])</value>
    </set-header>
  </inbound>
  <backend><base /></backend>
  <outbound><base /></outbound>
  <on-error><base /></on-error>
</policies>
```

**Named Value 设计**：

| Named Value 名 | 值 | 类型 |
|---|---|---|
| `copilot-directline-secret` | `<L4_COPILOT_DIRECTLINE_SECRET>` | Secret |

**前置条件**：
- Copilot Studio Agent 在 Power Platform 中创建（步骤 8）
- Direct Line channel 已启用，secret 已获取 → 存入 APIM Named Value
- `L4_COPILOT_BOT_ID`、`L4_COPILOT_DIRECTLINE_SECRET` 已填入 `.env.local.L4`

> **注意**：Direct Line 认证不支持 MSI，必须使用 DirectLine secret 或 Token。  
> APIM 需要保存 Named Value（Secret 类型），由 policy 在运行时注入。

---

### 7.6 `vm-model` — VM Hugging Face 模型（Phi-3-mini-4k-instruct via llama.cpp server）⬜

**状态**：待配置（VM sidecar 已在 `10.1.1.8:11434` 运行；下一步只需绑定 APIM backend / policy）

**前端**：
```
displayName:  VM Hugging Face Model (Phi-3-mini-4k-instruct)
path:         /vm-model
serviceUrl:   http://10.1.1.8:11434
```

**Operations**：

| Operation ID | 方法 | 路径模板 | 说明 |
|---|---|---|---|
| `chat-completions` | POST | `/v1/chat/completions` | llama.cpp OpenAI-compatible chat |
| `health` | GET | `/health` | 服务就绪检查（llama.cpp server 原生健康端点）|

**Inbound Policy**（API 级别）：
```xml
<policies>
  <inbound>
    <base />
    <!-- VM llama.cpp server 无认证，仅限 VNet 内访问 -->
    <!-- 移除客户端携带的 Authorization header，避免 token 泄漏到 VM -->
    <set-header name="Authorization" exists-action="delete" />
    <!-- 注入 Governance 追踪 header -->
    <set-header name="X-Governance-Target-Type" exists-action="override">
      <value>vm_huggingface_model</value>
    </set-header>
  </inbound>
  <backend><base /></backend>
  <outbound><base /></outbound>
  <on-error><base /></on-error>
</policies>
```

**网络前置条件**：
- VM 所在子网与 APIM subnet-APIM 在同一 VNet，或 VNet 内可路由
- NSG `AIGovernCanadaEastVNET-default-nsg-canadaeast` 已存在显式规则 `Allow-VNet-TCP-11434-VMModel`
- `L4_VM_PRIVATE_IP` 已确认：`10.1.1.8`

---

### 7.7 `tier1-app` — Tier 1 Consumer App Service ⬜

**状态**：待配置（App 未部署）

**前端**：
```
displayName:  Tier 1 Consumer App
path:         /tier1
serviceUrl:   https://aigoverntrustworthydemotier1app.azurewebsites.net
```

**Operations**：

| Operation ID | 方法 | 路径模板 | 说明 |
|---|---|---|---|
| `ask` | POST | `/api/ask` | 主要问答入口（调用 RAG 或 native model）|
| `health` | GET | `/api/health` | 健康检查 |

> 实际 operations 根据 Tier 1 App 开发完成后的接口定义更新。

**Inbound Policy**（API 级别）：
```xml
<policies>
  <inbound>
    <base />
    <!-- Tier 1 App Service 使用 Entra 认证，透传客户端的 Bearer token -->
    <!-- 不做 token 替换，由 App Service 内部验证客户端身份 -->
    <!-- 追加 Governance trace header -->
    <set-header name="X-Governance-Target-Type" exists-action="override">
      <value>tier1_consumer</value>
    </set-header>
    <set-header name="X-Governance-Request-Id" exists-action="override">
      <value>@(context.RequestId.ToString())</value>
    </set-header>
  </inbound>
  <backend><base /></backend>
  <outbound><base /></outbound>
  <on-error><base /></on-error>
</policies>
```

**前置条件**：
- `AIGovernTrustworthyDemoTier1App` App Service 已部署（步骤 9）
- `L4_TIER1_APP_URL` 已填入实际值
- App Service 配置了 Entra 认证（EasyAuth 或代码内校验）

---

### 7.8 `tier2-app` — Tier 2 Consumer App Service ⬜

**状态**：待配置（App 未部署）

**前端**：
```
displayName:  Tier 2 Consumer App
path:         /tier2
serviceUrl:   https://aigoverntrustworthydemotier2app.azurewebsites.net
```

**Operations**：根据 Tier 2 App 开发完成后的接口定义更新（占位）

**Inbound Policy**（API 级别）：与 Tier 1 相同，`X-Governance-Target-Type: tier2_consumer`

**前置条件**：Tier 1 App Service 先完成（步骤 9），Tier 2 App 在步骤 10 开发

---

## 8. 全局 Gateway Policy

当前 APIM gateway-level policy 为默认（`<base />` pass-through）。

**建议后续在 global policy 中添加**（未实施，仅设计）：

```xml
<policies>
  <inbound>
    <!-- 统一追加 APIM trace request ID -->
    <set-header name="X-APIM-Request-Id" exists-action="override">
      <value>@(context.RequestId.ToString())</value>
    </set-header>
    <base />
  </inbound>
  <backend>
    <base />
  </backend>
  <outbound>
    <!-- 统一在响应中返回 APIM Request ID，方便客户端关联 App Insights trace -->
    <set-header name="X-APIM-Request-Id" exists-action="override">
      <value>@(context.RequestId.ToString())</value>
    </set-header>
    <base />
  </outbound>
  <on-error>
    <base />
  </on-error>
</policies>
```

---

## 9. 观测/遥测配置

### 9.1 App Insights 集成（已配置）

| 属性 | 值 |
|---|---|
| Logger 名 | `applicationinsights` |
| App Insights 资源 | `aiexvddh5zbxgtg` |
| Instrumentation Key | `01f866fb-...`（引用 `APPLICATIONINSIGHTS_CONNECTION_STRING`）|

### 9.2 Gateway-level Diagnostics（已配置）

| 属性 | 值 |
|---|---|
| 状态 | ✅ 已启用 |
| Sampling | 100% |
| Correlation Protocol | W3C |
| Verbosity | information |
| Log client IP | true |

### 9.3 API-level Diagnostics（各 API 需单独配置）

每个 API 在配置完成时同步启用 API-level App Insights diagnostics：

| API | Diagnostics 状态 |
|---|---|
| `rag-service` | ✅ 已启用（100% sampling，W3C，information）|
| `native-model` | ✅ 已启用（100% sampling，W3C，information）|
| `finetune-model` | ⬜ 待配置 |
| `foundry-agent` | ⬜ 待配置 |
| `copilot-studio` | ⬜ 待配置 |
| `vm-model` | ⬜ 待配置 |
| `tier1-app` | ⬜ 待配置 |
| `tier2-app` | ⬜ 待配置 |

**API-level Diagnostics 统一配置模板**（每个 API 创建时使用）：
```json
{
  "properties": {
    "loggerId": "/subscriptions/47da4b42.../providers/Microsoft.ApiManagement/service/AIGovernTrustworthyDemoAPIM/loggers/applicationinsights",
    "alwaysLog": "allErrors",
    "sampling": { "samplingType": "fixed", "percentage": 100 },
    "verbosity": "information",
    "httpCorrelationProtocol": "W3C",
    "logClientIp": true
  }
}
```

### 9.4 Governance Trace 字段

APIM 写入 App Insights 的请求/响应日志会自动包含：

| 字段 | 来源 |
|---|---|
| `operation_Id` | W3C `traceparent` trace ID |
| `id` | APIM request ID（`context.RequestId`）|
| `url` | 请求 URL（含 API path）|
| `responseCode` | HTTP 状态码 |
| `duration` | 请求延迟（ms）|
| API 名称、operation 名称 | APIM 自动记录 |

**自定义 Governance 字段**（通过 `X-Governance-*` header + App Insights customDimensions）：

| Header | 说明 | 由谁设置 |
|---|---|---|
| `X-Governance-Target-Type` | 目标对象类型（`rag_service` 等）| APIM inbound policy |
| `X-Governance-Request-Id` | 透传 APIM RequestId | APIM inbound policy |
| `X-Governance-Trace-Id` | 透传 W3C trace ID | 客户端或 APIM 自动 |

---

## 10. Named Values 设计

Named Values 用于存储跨 API 共享的配置值（含 Secrets）。

| Named Value 名 | 值 | 类型 | 用途 | 状态 |
|---|---|---|---|---|
| `aoai-api-version` | `2025-01-01-preview` | Plain | AOAI API version | ⬜ 待创建 |
| `copilot-directline-secret` | `<L4_COPILOT_DIRECTLINE_SECRET>` | Secret | Copilot Studio Direct Line token | ⬜ 待创建（Bot 创建后）|
| `rag-webapp-endpoint` | `https://aigoverntrustworthyragapp-hchcfae9hpczcrcx.canadaeast-01.azurewebsites.net` | Plain | RAG Web App `/responses` endpoint | ✅ 已配置（policy 内 `set-backend-service` 内联，无需 Named Value）|

---

## 11. 依赖关系与配置顺序

```
已完成 ──────────────────────────────────────────────────────────
 ✅ APIM 实例创建（VNet Internal、NSG、Succeeded）
 ✅ App Insights logger + gateway diagnostics
 ✅ APIM MSI 启用（旧 Foundry Project 已授权）

等 RAG Web App 步骤就绪（步骤 2）───────────────────────────────
 ✅ 创建 `AIGovernTrustworthyRAGApp`（v1.0.4，VNet 集成，WEBSITE_DNS_SERVER）
 ✅ rag-service backend 更新到 Web App /responses endpoint（traceparent 注入策略）
 ✅ rag-service API diagnostics 复核（App Insights 三方写入，trace_id 非空）

等 AOAI 相关步骤就绪（步骤 3、4）──────────────────────────────
 ✅ APIM MSI → Cognitive Services OpenAI User on AIGovernTrustworthyAOAI
 ✅ native-model API 配置
 ⬜ finetune-model API 配置（步骤 4 完成后）

等 Foundry 步骤就绪（步骤 7）───────────────────────────────────
 ⬜ foundry-agent API 配置

等 Copilot Studio 步骤就绪（步骤 8）────────────────────────────
 ⬜ Named Value: copilot-directline-secret
 ⬜ copilot-studio API 配置

等 VM 步骤就绪（步骤 5）────────────────────────────────────────
 ⬜ vm-model API 配置（填入 L4_VM_PRIVATE_IP）
 ⬜ NSG 规则：subnet-APIM → VM subnet: 11434/TCP

等 App Service 步骤就绪（步骤 9、10）───────────────────────────
 ⬜ tier1-app API 配置
 ⬜ tier2-app API 配置
```

---

## 12. 实现状态汇总

| 类别 | 项目 | 状态 |
|---|---|---|
| **实例** | APIM 创建、VNet Internal、NSG | ✅ 完成 |
| **实例** | MSI 启用 + RBAC（旧 Foundry Project）| ✅ 完成 |
| **实例** | MSI RBAC（AOAI）| ✅ 完成 |
| **观测** | App Insights logger | ✅ 完成 |
| **观测** | Gateway-level diagnostics | ✅ 完成 |
| **API** | `rag-service` Web App backend + policy + diagnostics | ✅ 完成 |
| **API** | `native-model` | ✅ 完成 |
| **API** | `finetune-model` | ⬜ 待配置（后端未就绪）|
| **API** | `foundry-agent` | ⬜ 待配置（Agent 未创建）|
| **API** | `copilot-studio` | ⬜ 待配置（Agent 未创建）|
| **API** | `vm-model` | ⬜ 待配置（VM 已创建；待部署服务并绑定 backend）|
| **API** | `tier1-app` | ⬜ 待配置（App 未部署）|
| **API** | `tier2-app` | ⬜ 待配置（App 未部署）|
| **产品** | Products 设计 | ⬜ 待创建（当前 `subscriptionRequired: false`）|
| **Named Values** | API version constants | ⬜ 待创建（当前 policy 内硬编码）|
| **Named Values** | DirectLine secret | ⬜ 待创建（Bot 创建后）|
| **Global Policy** | X-APIM-Request-Id header | ⬜ 待实施 |
| **测试** | `test_via_apim.py` | ✅ 完成（rag-service 验证）|
