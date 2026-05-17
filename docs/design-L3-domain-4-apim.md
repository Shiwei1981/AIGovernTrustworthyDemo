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
- `design-L3-domain-4-monitoring-tracing-logging.md` — monitoring / tracing / logging 主规范
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
| `native-model` | `/native-model` | `aigoverntrustworthyfoundry` cognitiveservices 直连 Native Model deployment；当前 deployment 为 `AIGovernTrustworthyDemoNativeModelGPT5.4mini`，底层模型 `gpt-5.4-mini` `2026-03-17` | `https://cognitiveservices.azure.com` | ✅ 已配置；2026-05-17 已切换到 cognitiveservices 直连路径并验证通过 |
| `finetune-model` | `/finetune-model` | `AIGovernTrustworthyRAGProject` project-backed Fine-tune Model path；当前 deployment 解析到 `gpt-4.1-2025-04-14.ft-ae456ec3dc4d468b87ecb8512ad33f86-aigovtrustdemo` | `https://ai.azure.com` | ✅ 已配置（当前 MSI + `traceparent` + API diagnostics）；2026-05-17 已切换并验证通过 |
| `foundry-agent` | `/foundry-agent` | Foundry 自定义 Agent assistant/thread API | `https://ai.azure.com` | ✅ 已配置并通过 assistants + thread/run smoke test |
| `copilot-studio` | `/copilot-studio` | Direct Line（Copilot Studio） | DirectLine secret | 🟡 脚本已就绪，待 Agent 创建后执行 |
| `vm-model` | `/vm-model` | VM llama.cpp API（Phi-3-mini-4k-instruct） | 无（VNet 内访问）| ✅ 已配置（`http://10.1.1.8:11434`，policy + diagnostics 已应用，VNet smoke test 通过）|
| `tier1-app` | `/tier1` | Tier 1 Consumer App Service | 透传客户端 Bearer token，不做 MSI scope 注入 | ✅ 已配置（2026-05-17 已创建 consumer UI/API operations，policy + diagnostics 已应用）|
| `tier2-app` | `/tier2` | Tier 2 Consumer App Service | 透传客户端 Bearer token，不做 MSI scope 注入 | ✅ 已配置（2026-05-17 已创建 consumer UI/API operations，policy + diagnostics 已应用）|

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
| `rag-webapp` | `https://aigoverntrustworthyragapp-hchcfae9hpczcrcx.canadaeast-01.azurewebsites.net` | 无（APIM -> Web App 直接 HTTPS） | ✅ 已配置（`set-backend-service` 内联策略）|
| `aoai-native-model` | `https://aigoverntrustworthyfoundry.cognitiveservices.azure.com/openai/deployments/AIGovernTrustworthyDemoNativeModelGPT5.4mini` | MSI，scope=`https://cognitiveservices.azure.com` | ✅ 当前 `/native-model/chat/completions` live backend；deployment `gpt-5.4-mini` `2026-03-17` |
| `aoai-finetune-model` | `https://aigoverntrustworthyaoai.openai.azure.com/openai/deployments/AIGovernTrustworthyDemoFineTuneModel` | MSI，scope=`https://cognitiveservices.azure.com` | ✅ 当前已配置；保留为底层烟测和排障 backend |
| `project-native-model` | `https://aigoverntrustworthyfoundry.services.ai.azure.com/api/projects/AIGovernTrustworthyRAGProject/openai/v1` | MSI，scope=`https://ai.azure.com` | ✅ 已配置；当前 `/native-model/chat/completions` live backend |
| `project-finetune-model` | `https://aigoverntrustworthyfoundry.services.ai.azure.com/api/projects/AIGovernTrustworthyRAGProject/openai/v1` | MSI，scope=`https://ai.azure.com` | ✅ 已配置；当前 `/finetune-model/chat/completions` live backend |
| `foundry-custom-agent` | `https://aigoverntrustworthyfoundry.services.ai.azure.com/api/projects/AIGovernTrustworthyRAGProject` | MSI，scope=`https://ai.azure.com` | ✅ APIM `/foundry-agent` 已接入 project-level assistants / threads / messages / runs API；2026-05-17 smoke test 通过 |
| `copilot-studio-directline` | `https://directline.botframework.com/v3/directline` | Named Value `copilot-directline-secret`（Header `Authorization: Bearer {{copilot-directline-secret}}`）| 🟡 脚本已就绪，待 Agent 创建后执行 |
| `vm-llama-server` | `http://10.1.1.8:11434` | 无 | ✅ 已配置（API `serviceUrl` 内联，VM sidecar 运行中）|
| `tier1-app-service` | `https://aigoverntrustworthydemotier1app-f8ayhddzcce3g2gd.canadaeast-01.azurewebsites.net` | Entra（透传客户端 token）| ✅ EasyAuth 已启用；当前 `/tier1` live backend |
| `tier2-app-service` | `https://aigoverntrustworthydemotier2app-gvfxdna2btc5h4af.canadaeast-01.azurewebsites.net` | Entra（透传客户端 token）| ✅ EasyAuth 已启用；当前 `/tier2` live backend |

> **注意**：APIM Internal VNet 模式下，`vm-llama-server` 后端使用 VM 私有 IP，  
> 需要 APIM 子网和 VM 子网之间的 VNet Peering 或同一 VNet 内可路由。

### 6.2 MSI 认证说明

APIM 对需要 Azure 身份的后端使用 System-Assigned MSI 自动获取 token：

| 后端资源类型 | Token Scope | MSI 所需 RBAC |
|---|---|---|
| Azure AI Foundry Project OpenAI data plane | `https://ai.azure.com` | `Cognitive Services OpenAI User` on `aigoverntrustworthyfoundry` ✅ |
| App Service（Tier1/Tier2） | 透传客户端 token（不由 MSI 注入）| — |
| Copilot Studio Direct Line | DirectLine secret（Named Value）| — |
| VM llama.cpp | 无 auth | — |

**Project-backed MSI RBAC（已执行）**：
```bash
az role assignment create \
  --assignee 32195307-0138-49c1-b36f-381928efcd5d \
  --role "Cognitive Services OpenAI User" \
  --scope /subscriptions/47da4b42-0493-49ff-b3c8-45df3ae06821/resourceGroups/AIGovernTrustworthyRG/providers/Microsoft.CognitiveServices/accounts/aigoverntrustworthyfoundry
```

---

## 7. API 详细设计

### 7.1 `rag-service` — RAG 治理问答服务（Web App）

**状态**：步骤 2 已改为 RAG Web App 方案，后端不再使用 Hosted Agent。

**前端**：
```
path:        /rag
serviceUrl:  https://aigoverntrustworthyragapp-hchcfae9hpczcrcx.canadaeast-01.azurewebsites.net
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

### 7.2 `native-model` — 当前控制面为 gpt-5.4-mini 的原生模型 ✅

**状态**：✅ 已配置；2026-05-17 切换到 project-backed 路径，后再次切换到 cognitiveservices 直连路径；当前使用 deployment `AIGovernTrustworthyDemoNativeModelGPT5.4mini`，底层模型 `gpt-5.4-mini` `2026-03-17`

> **当前状态说明**：`native-model` API 的 live backend 为 `https://aigoverntrustworthyfoundry.cognitiveservices.azure.com/openai/deployments/AIGovernTrustworthyDemoNativeModelGPT5.4mini`，认证 scope 为 `https://cognitiveservices.azure.com`。APIM policy 会注入 `api-version=2025-01-01-preview` 查询参数；若请求体缺失 `model` 字段，自动补齐 `AIGovernTrustworthyDemoNativeModelGPT5.4mini`。已验证返回 200，实际模型标识为 `gpt-5.4-mini-2026-03-17`。

**前端**：
```
displayName:  Native Model (gpt-5.4-mini)
path:         /native-model
serviceUrl:   https://aigoverntrustworthyfoundry.cognitiveservices.azure.com/openai/deployments/AIGovernTrustworthyDemoNativeModelGPT5.4mini
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
    <!-- 注入 APIM MSI token，scope=ai.azure.com -->
    <authentication-managed-identity
      resource="https://ai.azure.com"
      output-token-variable-name="msi-token" />
    <set-header name="Authorization" exists-action="override">
      <value>@("Bearer " + (string)context.Variables["msi-token"])</value>
    </set-header>
    <set-body>@{
      var requestBody = context.Request.Body?.As<JObject>(preserveContent: true);
      if (requestBody == null)
      {
        return context.Request.Body?.As<string>(preserveContent: true) ?? string.Empty;
      }

      if (requestBody["model"] == null || string.IsNullOrEmpty((string)requestBody["model"]))
      {
        requestBody["model"] = "AIGovernTrustworthyDemoNativeModelGPT5.4mini";
      }

      return requestBody.ToString();
    }</set-body>
    <set-backend-service base-url="https://aigoverntrustworthyfoundry.cognitiveservices.azure.com/openai/deployments/AIGovernTrustworthyDemoNativeModelGPT5.4mini" />
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
- `aigoverntrustworthyfoundry` account / deployment `AIGovernTrustworthyDemoNativeModelGPT5.4mini` 可用 ✅ 已验证
- APIM MSI 需要 `Cognitive Services OpenAI User` on `aigoverntrustworthyfoundry` ✅ 已完成

**已执行**：
```bash
bash infra/apim/setup-native-model-api.sh
```

**验证结果**：
- 直连 AOAI：`apps/native-model/scripts/test_native_model.py` 返回 200 且 response 非空
- APIM `/native-model/chat/completions`：2026-05-14 返回 200，model=`gpt-5.4-nano-2026-03-17`（当时的 native model）
- API-level diagnostics：`applicationinsights` 已绑定，`httpCorrelationProtocol = W3C`
- App Insights：出现 APIM → AOAI dependency 记录，`OperationName = native-model;rev=1 - chat-completions`
- AOAI 平台诊断：`AzureDiagnostics` 中可见 `modelDeploymentName = AIGovernTrustworthyDemoNativeModelGPT5.4mini`、`modelName = gpt-5.4-mini`、`modelVersion = 2026-03-17`
- 2026-05-17 控制面复核：`AIGovernTrustworthyDemoNativeModel` deployment 已删除；新 deployment `AIGovernTrustworthyDemoNativeModelGPT5.4mini` 在 `aigoverntrustworthyfoundry` account 下，底层模型 `gpt-5.4-mini` `2026-03-17`
- 2026-05-17 配置修复：`/native-model` API 切换到 cognitiveservices 直连路径；MSI scope 改为 `https://cognitiveservices.azure.com`；policy 注入 `api-version=2025-01-01-preview` 和默认 `model=AIGovernTrustworthyDemoNativeModelGPT5.4mini`
- 2026-05-17 runtime 验证：`/native-model/chat/completions` 返回 200，实际模型标识为 `gpt-5.4-mini-2026-03-17` ✅

> **说明**：`APIM -> aigoverntrustworthyfoundry/AIGovernTrustworthyDemoNativeModelGPT5.4mini` 直连路径已替代早期的 project-backed 路径；当前核心目标是通过 APIM 统一治理入口调用 `gpt-5.4-mini` 并记录 APIM diagnostics + App Insights evidence。

> **步骤 7 详细设计说明**：Consumer app 统一通过 APIM `/native-model/chat/completions` 调用 native model；Tier 1/2 在请求体中显式传 `model=AIGovernTrustworthyDemoNativeModelGPT5.4mini`，不依赖 APIM 兼容注入。

---

### 7.3 `finetune-model` — 当前 project-backed 的 Fine-tune 模型 ✅

**状态**：✅ 已配置；2026-05-17 已切换到 project-backed live path 并验证通过

**前端**：
```
 displayName:  Fine-tune Model (Foundry Project-backed gpt-4.1)
path:         /finetune-model
serviceUrl:   https://aigoverntrustworthyfoundry.services.ai.azure.com/api/projects/AIGovernTrustworthyRAGProject/openai/v1
```

**Operations**：与 `native-model` 相同（`POST /chat/completions`）

**Inbound Policy**：与 `native-model` 相同（`https://ai.azure.com` scope + 缺失 `model` 时自动注入 `AIGovernTrustworthyDemoFineTuneModel`）

**API-level diagnostics**：与 `native-model` 相同（`applicationinsights`、100% sampling、W3C、verbosity=`information`）

**已执行**：
```bash
bash infra/apim/setup-finetune-model-api.sh
```

**验证结果**：
- 直连 fine-tuned deployment：烟测通过，response 非空
- APIM `/finetune-model/chat/completions`：2026-05-15 烟测通过
- API-level diagnostics：`applicationinsights` 已绑定，`httpCorrelationProtocol = W3C`
- 平台侧证据链：设计口径与 `native-model` 相同，以 APIM dependency + AOAI 平台诊断为准
- 2026-05-17 配置修复：`/finetune-model` API 已切换到 `AIGovernTrustworthyRAGProject/openai/v1`，MSI scope 改为 `https://ai.azure.com`
- 2026-05-17 runtime 复核：带 `model=AIGovernTrustworthyDemoFineTuneModel` 和不显式传 `model` 两种请求形态都返回 200，实际模型标识均为 `gpt-4.1-2025-04-14.ft-ae456ec3dc4d468b87ecb8512ad33f86-aigovtrustdemo`

**前置条件**：
- Fine-tune 模型训练和部署完成（步骤 4）
- `AIGovernTrustworthyDemoFineTuneModel` deployment 处于 `Succeeded`
- `L4_FOUNDRY_FINETUNE_MODEL_ENDPOINT` 填入实际值
- APIM MSI 已具备对 `aigoverntrustworthyfoundry` 的 `Cognitive Services OpenAI User`（已满足，可直接复用）

> **当前状态说明**：`finetune-model` API 当前仍保留 `/finetune-model/chat/completions` public path，但 live `serviceUrl` 与 API policy 已切到 `https://aigoverntrustworthyfoundry.services.ai.azure.com/api/projects/AIGovernTrustworthyRAGProject/openai/v1`，认证 scope 为 `https://ai.azure.com`。为了兼容旧调用方，APIM policy 会在请求体缺失 `model` 字段时自动注入 `AIGovernTrustworthyDemoFineTuneModel`。

---

### 7.4 `foundry-agent` — Foundry 自定义 Agent ✅

**状态**：2026-05-17 已完成 APIM `/foundry-agent` 配置。已确认 `AIGovernTrustworthyRAGProject` 下正确对象是 project-level assistant `AIGovernTrustworthyDemoFoundryAgent` / `asst_qPEQxZ6Gc894gcxQjaIOkdF6`；旧 hosted agent `aigovern-rag-agent` 已删除。deploy SPN 与 APIM gateway 均已完成 assistants + thread/run smoke test。

**前端**：
```
displayName:  Foundry Custom Agent
path:         /foundry-agent
serviceUrl:   https://aigoverntrustworthyfoundry.services.ai.azure.com/api/projects/AIGovernTrustworthyRAGProject
```

**Operations**：

| Operation ID | 方法 | 路径模板 | 说明 |
|---|---|---|---|
| `list-assistants` | GET | `/assistants` | 列出 project-level assistant 对象 |
| `get-assistant` | GET | `/assistants/{assistantId}` | 读取目标 assistant metadata |
| `threads` | POST | `/threads` | 创建 Agent thread |
| `create-and-run` | POST | `/threads/runs` | 一次请求内创建 thread 并启动 run；调用方在 body 中传 `assistant_id` |
| `add-message` | POST | `/threads/{threadId}/messages` | 向现有 thread 添加消息 |
| `create-run` | POST | `/threads/{threadId}/runs` | 对现有 thread 启动 run；调用方在 body 中传 `assistant_id` |
| `get-run` | GET | `/threads/{threadId}/runs/{runId}` | 查询 run 状态 |
| `list-messages` | GET | `/threads/{threadId}/messages` | 获取 thread 消息 |

**Inbound Policy**（API 级别）:
```xml
<policies>
  <inbound>
    <base />
    <set-header name="traceparent" exists-action="skip">
      <value>@("00-" + context.RequestId.ToString("N") + "-" + context.RequestId.ToString("N").Substring(16, 16) + "-01")</value>
    </set-header>
    <authentication-managed-identity
      resource="https://ai.azure.com"
      output-token-variable-name="msi-token" />
    <set-header name="Authorization" exists-action="override">
      <value>@("Bearer " + (string)context.Variables["msi-token"])</value>
    </set-header>
    <set-query-parameter name="api-version" exists-action="override">
      <value>v1</value>
    </set-query-parameter>
    <set-backend-service base-url="https://aigoverntrustworthyfoundry.services.ai.azure.com/api/projects/AIGovernTrustworthyRAGProject" />
  </inbound>
  <backend><base /></backend>
  <outbound><base /></outbound>
  <on-error><base /></on-error>
</policies>
```

> **当前实现说明**：APIM backend 指向 project-level API，目标 agent 由请求体中的 `assistant_id=asst_qPEQxZ6Gc894gcxQjaIOkdF6` 指定。Tier 1 / 后续调用方不得使用旧 hosted `/agents/aigovern-rag-agent/endpoint/protocols/openai` 路径。

**前置条件**：
- 实际 project 中必须存在 assistant `asst_qPEQxZ6Gc894gcxQjaIOkdF6`
- APIM MSI 需要能对 `aigoverntrustworthyfoundry / AIGovernTrustworthyRAGProject` 获取 `https://ai.azure.com` audience token，并通过 project/group 权限访问 Agent data plane
- `.env.local.L4` 中 `L4_FOUNDRY_AGENT_ID` 必须保持为真实 assistant id

---

### 7.5 `copilot-studio` — Copilot Studio Agent（Direct Line）⬜

**状态**：脚本已就绪，待 Agent 创建并回填 `.env.local.L4` 后执行。

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
      <value>Bearer {{copilot-directline-secret}}</value>
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
| `copilot-directline-secret` | `<L4_COPILOT_STUDIO_DIRECTLINE_SECRET>` | Secret |

**前置条件**：
- Copilot Studio Agent 在 Power Platform 中创建（步骤 6）
- Direct Line channel 已启用，secret 已获取 → 存入 APIM Named Value
- `L4_COPILOT_STUDIO_DIRECTLINE_SECRET` 已填入 `.env.local.L4`

> **注意**：Direct Line 认证不支持 MSI，必须使用 DirectLine secret 或 Token。  
> APIM 需要保存 Named Value（Secret 类型），由 policy 在运行时注入。

> `bot_id`、`environment_id` 属于人工登记元数据，不是当前 APIM Direct Line proxy 的程序必需输入，可记录在步骤 6 设计文档而不是 `.env.local.L4`。

---

### 7.6 `vm-model` — VM Hugging Face 模型（Phi-3-mini-4k-instruct via llama.cpp server）✅

**状态**：✅ 已配置（2026-05-15）。API 已创建，serviceUrl=`http://10.1.1.8:11434`，policy + App Insights diagnostics 已应用，VNet 内 `/vm-model/health` smoke test 通过。

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

### 7.7 `tier1-app` — Tier 1 Consumer App Service ✅

**状态**：已配置（2026-05-17 已创建 `/tier1` API、operations、policy 与 App Insights diagnostics）

**前端**：
```
displayName:  Tier 1 Consumer App
path:         /tier1
serviceUrl:   https://aigoverntrustworthydemotier1app-f8ayhddzcce3g2gd.canadaeast-01.azurewebsites.net
```

**Operations**：

| Operation ID | 方法 | 路径模板 | 说明 |
|---|---|---|---|
| `ui-root` | GET | `/` | Tier 1 页面根入口 |
| `ui-app` | GET | `/app` | Tier 1 单页应用入口 |
| `ui-static` | GET | `/static/{assetPath}` | Tier 1 静态资源 |
| `api-metadata` | GET | `/api/metadata` | 对外暴露应用元数据、target 状态、当前路由模式 |
| `chat-rag` | POST | `/api/chat/rag` | Tier 1 RAG tab 对应的纯转发 API |
| `chat-foundry-agent` | POST | `/api/chat/foundry-agent` | Tier 1 Foundry Agent tab 对应的纯转发 API |
| `chat-vm-model` | POST | `/api/chat/vm-model` | Tier 1 VM Model tab 对应的纯转发 API |
| `chat-native-model` | POST | `/api/chat/native-model` | Tier 1 Native Model tab 对应的纯转发 API |
| `chat-finetune-model` | POST | `/api/chat/finetune-model` | Tier 1 FineTune Model tab 对应的纯转发 API |
| `health` | GET | `/api/health` | 健康检查 |
| `bootstrap` | GET | `/ui/bootstrap` | 页面启动配置 |
| `ui-metadata` | GET | `/ui/metadata` | 页面读取元数据 |

> 页面入口 `GET /`、`GET /app` 与静态资源 `GET /static/{assetPath}` 已在 live APIM 中显式建成 operation，便于 diagnostics 与路由核对。

**Inbound Policy**（API 级别）：
```xml
<policies>
  <inbound>
    <base />
    <set-header name="traceparent" exists-action="skip">
      <value>@("00-" + context.RequestId.ToString("N") + "-" + context.RequestId.ToString("N").Substring(16, 16) + "-01")</value>
    </set-header>
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
- `AIGovernTrustworthyDemoTier1App` App Service 已创建并运行（Linux container；ACR 镜像 `aigoverndemoacr.azurecr.io/AIGovernTrustworthyDemoTier1App:v1.0.0`）
- `L4_TIER1_APP_URL` 已填入实际值
- App Service 已启用 Entra 认证（EasyAuth），issuer / clientId 已与 Tier 1 App Registration 对齐
- Tier 1 内部 forwarding route 到 `/native-model` 的调用直接转发至 APIM；`/native-model` 的 live backend 为 cognitiveservices 直连 `AIGovernTrustworthyDemoNativeModelGPT5.4mini`（`gpt-5.4-mini`）

**部署级责任**：

1. `/tier1` 是 Browser、外部程序、Tier 2 后端进入 Tier 1 的唯一受控 gateway path。
2. APIM 对 `/tier1` 只做路由、诊断、trace 透传或补齐，不注入 MSI，也不替换调用方 Bearer token。
3. Browser -> `/tier1` 使用用户 token；Tier 2 -> `/tier1` 使用 app-only token；这两类 token 都由 Tier 1 App Service 自己完成鉴权判定。
4. 若调用方未带 `traceparent`，APIM 负责生成；若已带 `traceparent` / `tracestate`，APIM 必须保留原值，保证 Tier 1 能延续同一主 trace。
5. APIM 可以补充 `X-Governance-Target-Type`、`X-Governance-Request-Id` 这类治理辅助 header，但不得改写业务请求体。

---

### 7.8 `tier2-app` — Tier 2 Consumer App Service ✅

**状态**：已配置（2026-05-17 已创建 `/tier2` API、operations、policy 与 App Insights diagnostics）

**前端**：
```
displayName:  Tier 2 Consumer App
path:         /tier2
serviceUrl:   https://aigoverntrustworthydemotier2app-gvfxdna2btc5h4af.canadaeast-01.azurewebsites.net
```

**Operations**：

| Operation ID | 方法 | 路径模板 | 说明 |
|---|---|---|---|
| `ui-root` | GET | `/` | Tier 2 页面根入口 |
| `ui-app` | GET | `/app` | Tier 2 单页应用入口 |
| `ui-static` | GET | `/static/{assetPath}` | Tier 2 静态资源 |
| `api-metadata` | GET | `/api/metadata` | 对外暴露应用元数据与下游 Tier 1 依赖摘要 |
| `chat-rag` | POST | `/api/chat/rag` | Tier 2 RAG tab 对应的纯转发 API |
| `chat-foundry-agent` | POST | `/api/chat/foundry-agent` | Tier 2 Foundry Agent tab 对应的纯转发 API |
| `chat-vm-model` | POST | `/api/chat/vm-model` | Tier 2 VM Model tab 对应的纯转发 API |
| `chat-native-model` | POST | `/api/chat/native-model` | Tier 2 Native Model tab 对应的纯转发 API |
| `chat-finetune-model` | POST | `/api/chat/finetune-model` | Tier 2 FineTune Model tab 对应的纯转发 API |
| `health` | GET | `/api/health` | 健康检查 |
| `bootstrap` | GET | `/ui/bootstrap` | 页面启动配置 |
| `ui-metadata` | GET | `/ui/metadata` | 页面读取元数据 |

> 页面入口 `GET /`、`GET /app` 与静态资源 `GET /static/{assetPath}` 已在 live APIM 中显式建成 operation。

**Inbound Policy**（API 级别）：
```xml
<policies>
  <inbound>
    <base />
    <set-header name="traceparent" exists-action="skip">
      <value>@("00-" + context.RequestId.ToString("N") + "-" + context.RequestId.ToString("N").Substring(16, 16) + "-01")</value>
    </set-header>
    <set-header name="X-Governance-Target-Type" exists-action="override">
      <value>tier2_consumer</value>
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

**前置条件**：Tier 1 / Tier 2 同属步骤 7；其中 Tier 2 依赖 Tier 1 先完成。当前已完成 Tier 2 App Registration 对 Tier 1 application appRole 的请求与 service principal assignment，且已实测能签发 `api://{L4_TIER1_APP_CLIENT_ID}/.default` app-only token。

**补充要求**：Tier 2 的唯一业务下游是 `APIM /tier1/api/chat/{tab_id}`，不得从 Tier 2 直接调用 `/rag`、`/native-model`、`/finetune-model`、`/foundry-agent` 或 `/vm-model`

**部署级责任**：

1. `/tier2` 是 Browser 进入 Tier 2 页面与 API 的唯一受控 gateway path。
2. APIM 对 `/tier2` 同样只做路由、诊断、trace 透传或补齐，不注入 MSI，也不替换浏览器带来的用户 token。
3. Tier 2 后端后续调用 `/tier1/api/chat/{tab_id}` 时，属于应用内第二跳，不经由 `/tier2` 的 APIM policy 做 token 交换；token 获取与调用职责完全属于 Tier 2 应用自身。
4. `/tier2` 的 APIM 责任是保证 Browser -> Tier 2 这一跳的 trace 连续性，并把 `context.RequestId` 暴露给后续应用日志关联。

### 7.8A Consumer App 相关 APIM path 的部署级调用 / 认证 / Trace 责任矩阵

步骤 7 进入部署时，Consumer App 相关 path 的 APIM 责任固定如下。

| APIM path | 主要调用方 | APIM 对认证的责任 | APIM 对 trace 的责任 | APIM 不负责的事项 |
|---|---|---|---|---|
| `/tier1` | Browser、Tier 2、外部程序 | 透传 Bearer token；不注入 MSI；不替调用方换 token | 若无 `traceparent` 则生成；若已存在则保留并继续传给 Tier 1 App | 不做 Tier 1 业务鉴权决策；不决定用户 token 与 app-only token 哪种合法 |
| `/tier2` | Browser | 透传 Bearer token；不注入 MSI | 若无 `traceparent` 则生成；若已存在则保留并继续传给 Tier 2 App | 不负责 Tier 2 -> Tier 1 第二跳的 token 获取 |
| `/rag` | Tier 1 | 走 Web App pass-through；不依赖调用方 token 透传到后端 | 透传或补齐 `traceparent` / `tracestate`，使 RAG App 能延续同一 trace | 不负责 RAG 内部 retrieval / model orchestration |
| `/foundry-agent` | Tier 1 | 注入 MSI token，scope=`https://ai.azure.com` | 透传或补齐 `traceparent` / `tracestate`，使 Foundry tracing 能关联到上游 | 不负责替 Tier 1 决定最终 `assistant_id`；步骤 7 固定使用 `asst_qPEQxZ6Gc894gcxQjaIOkdF6` |
| `/vm-model` | Tier 1 | 删除调用方 `Authorization` header；不注入 MSI | 透传或补齐 `traceparent` / `tracestate`，使 VM sidecar telemetry 能关联到上游 | 不负责推断 VM 支持哪些模型参数 |
| `/native-model` | Tier 1 | 注入 MSI token，scope=`https://ai.azure.com` | 透传或补齐 `traceparent` / `tracestate`，使 Foundry Project tracing 能关联到上游 | 不负责替 Tier 1 决定最终业务 target；兼容性 `model` 注入仅作兜底 |
| `/finetune-model` | Tier 1 | 注入 MSI token，scope=`https://ai.azure.com` | 透传或补齐 `traceparent` / `tracestate`，使 Foundry Project tracing 能关联到上游 | 不负责替 Tier 1 决定最终业务 target；兼容性 `model` 注入仅作兜底 |

部署验收时，至少要逐项核对以下规则：

1. `/tier1`、`/tier2` 不得配置 `authentication-managed-identity` 覆盖调用方 token。
2. `/native-model`、`/finetune-model`、`/foundry-agent` 必须使用各自规定的 MSI scope，而不是复用 Consumer App 的 token 透传语义。
3. `/vm-model` 不得把调用方 Bearer token 继续带到 VM。
4. 所有这些 path 都必须满足“有上游 trace 就保留，无上游 trace 就补齐”的统一规则。
5. APIM diagnostics、Consumer App 日志、shared-observability evidence 必须能通过 `trace_id` 和 APIM request id 互相跳转。

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
| `finetune-model` | ✅ 已启用（100% sampling，W3C，information） |
| `foundry-agent` | ✅ 已启用（100% sampling，W3C，information） |
| `copilot-studio` | ⬜ 待配置 |
| `vm-model` | ✅ 已启用（100% sampling，W3C，information）|
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
| `copilot-directline-secret` | `<L4_COPILOT_STUDIO_DIRECTLINE_SECRET>` | Secret | Copilot Studio Direct Line token | ⬜ 待创建（Bot 创建后）|
| `rag-webapp-endpoint` | `https://aigoverntrustworthyragapp-hchcfae9hpczcrcx.canadaeast-01.azurewebsites.net` | Plain | RAG Web App `/responses` endpoint | ✅ 已配置（policy 内 `set-backend-service` 内联，无需 Named Value）|

---

## 11. 依赖关系与配置顺序

```
已完成 ──────────────────────────────────────────────────────────
 ✅ APIM 实例创建（VNet Internal、NSG、Succeeded）
 ✅ App Insights logger + gateway diagnostics
 ✅ APIM MSI 启用（AIGovernTrustworthyRAGProject 已授权）

等 RAG Web App 步骤就绪（步骤 2）───────────────────────────────
 ✅ 创建 `AIGovernTrustworthyRAGApp`（v1.0.4，VNet 集成，WEBSITE_DNS_SERVER）
 ✅ rag-service backend 更新到 Web App /responses endpoint（traceparent 注入策略）
 ✅ rag-service API diagnostics 复核（App Insights 三方写入，trace_id 非空）

等 AOAI 相关步骤就绪（步骤 3、4）──────────────────────────────
 ✅ APIM MSI → Cognitive Services OpenAI User on AIGovernTrustworthyAOAI
 ✅ native-model API 配置
 ✅ finetune-model API 配置

等 Agent 步骤就绪（步骤 6）─────────────────────────────────────
 ✅ foundry-agent API 配置（project-level assistants / threads / runs）

等 Copilot Studio 子对象就绪（步骤 6）──────────────────────────
 ⬜ Named Value: copilot-directline-secret
 ⬜ copilot-studio API 配置

等 VM 步骤就绪（步骤 5）────────────────────────────────────────
 ✅ vm-model API 配置（http://10.1.1.8:11434）
 ✅ NSG 规则：VirtualNetwork → VM:11434/TCP（Allow-VNet-TCP-11434-VMModel）

等 Consumer Apps 步骤就绪（步骤 7）─────────────────────────────
 ⬜ tier1-app API 配置
 ⬜ tier2-app API 配置
```

---

## 12. 实现状态汇总

| 类别 | 项目 | 状态 |
|---|---|---|
| **实例** | APIM 创建、VNet Internal、NSG | ✅ 完成 |
| **实例** | MSI 启用 + RBAC（AIGovernTrustworthyRAGProject）| ✅ 完成 |
| **实例** | MSI RBAC（AOAI）| ✅ 完成 |
| **观测** | App Insights logger | ✅ 完成 |
| **观测** | Gateway-level diagnostics | ✅ 完成 |
| **API** | `rag-service` Web App backend + policy + diagnostics | ✅ 完成 |
| **API** | `native-model` | ✅ 完成 |
| **API** | `finetune-model` | ✅ 完成 |
| **API** | `foundry-agent` | ✅ 已完成（assistant `asst_qPEQxZ6Gc894gcxQjaIOkdF6`，policy + diagnostics + APIM smoke test）|
| **API** | `copilot-studio` | ⬜ 待配置（等待 publish / Direct Line secret）|
| **API** | `vm-model` | ✅ 已完成（`http://10.1.1.8:11434`，policy + diagnostics + VNet smoke test）|
| **API** | `tier1-app` | ⬜ 待配置（App 未部署）|
| **API** | `tier2-app` | ⬜ 待配置（App 未部署）|
| **产品** | Products 设计 | ⬜ 待创建（当前 `subscriptionRequired: false`）|
| **Named Values** | API version constants | ⬜ 待创建（当前 policy 内硬编码）|
| **Named Values** | DirectLine secret | ⬜ 待创建（Bot 创建后）|
| **Global Policy** | X-APIM-Request-Id header | ⬜ 待实施 |
| **测试** | `test_via_apim.py` | ✅ 完成（rag-service 验证）|
