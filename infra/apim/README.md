# infra/apim

APIM 配置脚本目录，管理 `AIGovernTrustworthyDemoAPIM` 中各 AI 服务的 API 定义。

## 当前状态

| API | Path | Backend | 状态 |
|---|---|---|---|
| RAG Governance Service | `/rag` | `AIGovernTrustworthyRAGApp` Web App | ✅ 脚本就绪，待执行 |
| Native Model | `/native-model` | Azure OpenAI (via APIM MSI) | ✅ 已配置（MSI RBAC + policy + diagnostics） |
| Fine-tune Model | `/finetune-model` | Azure OpenAI fine-tune deployment | ✅ 已配置（MSI + policy + diagnostics） |
| Foundry Agent | `/foundry-agent` | Azure AI Foundry Agent assistant/thread API | ✅ 已配置并通过 APIM smoke test |
| Copilot Studio Agent | `/copilot-studio` | Direct Line | ✅ 脚本就绪，待 Agent 创建后执行 |

## APIM 网络模式

`AIGovernTrustworthyDemoAPIM` 使用 **VNet Internal** 模式：

- Gateway URL：`https://aigoverntrustworthydemoapim.azure-api.net`（仅 VNet 内可达，或通过公网 IP `40.86.204.28` + DNS override）
- Management 面（ARM）：始终可从公网访问（az CLI 正常工作）

## 脚本

### `setup-rag-api.sh`

将 APIM `/rag` API 重新配置为代理 RAG Web App（替换旧的 Hosted Agent 路径）。

**执行一次即可；幂等（已存在的操作会 update 而非报错）。**

```bash
# 从仓库根执行
bash infra/apim/setup-rag-api.sh
```

该脚本完成：
1. 更新 API `serviceUrl` → RAG Web App 地址
2. 删除旧 Hosted Agent 操作（thread/run/messages）
3. 创建 `POST /responses`（主查询）和 `GET /health`（健康检查）
4. 设置 API 级策略：
   - 透传 `Authorization` 头
   - 注入 `traceparent`（W3C Trace Context）供 Web App OTEL 自动关联
   - `set-backend-service` 显式指定后端（防止 serviceUrl 漂移）
   - 出站加 `x-aigov-apim-request-id` 响应头
   - 错误处理：502 + JSON 错误体
5. 更新 `infra/target-registry/targets.json` 中的 `backend_url` 和 `status`

RAG Web App 自带的手动测试 UI 不让浏览器直连 Internal APIM；UI 调用先进入 Web App 的
`/ui/responses` 服务端代理，再由该代理读取 `L4_RAG_SERVICE_URL`（即 APIM `/rag` base URL）
发起后端调用。

### `setup-native-model-api.sh`

将 APIM `/native-model` API 配置为代理 Domain 4 Azure OpenAI 原生模型 deployment
`AIGovernTrustworthyDemoNativeModelGPT5.4mini`（`gpt-5.4-mini` `2026-03-17`）。

**执行一次即可；幂等（已存在的 API / operation / diagnostics 会 update 而非报错）。**

```bash
# 从仓库根执行
bash infra/apim/setup-native-model-api.sh
```

该脚本完成：
1. 给 APIM MSI 授 `Cognitive Services OpenAI User` on `AIGovernTrustworthyAOAI`
2. 创建或更新 API `native-model`
3. 创建或更新 `POST /chat/completions`
4. 设置 API 级策略：
   - 注入 `traceparent`（W3C Trace Context）
   - 用 APIM MSI 获取 `https://cognitiveservices.azure.com` token
   - 注入 `Authorization: Bearer <msi-token>`
   - 固定 `api-version=2025-01-01-preview`
   - 出站加 `x-aigov-apim-request-id`
   - 错误处理：502 + JSON 错误体
5. 为 `native-model` 创建 API-level App Insights diagnostics
6. 更新 `infra/target-registry/targets.json` 中 native model 条目的 APIM 状态说明

### `setup-finetune-model-api.sh`

将 APIM `/finetune-model` API 配置为代理 Domain 4 fine-tune deployment
`AIGovernTrustworthyDemoFineTuneModel`。

```bash
bash infra/apim/setup-finetune-model-api.sh
```

该脚本完成：
1. 给 APIM MSI 授 fine-tune 后端所需的 `Cognitive Services OpenAI User`
2. 创建或更新 API `finetune-model`
3. 创建或更新 `POST /chat/completions`
4. 设置 MSI 鉴权、`traceparent`、`api-version`、错误处理策略
5. 创建 API-level App Insights diagnostics
6. 更新 `infra/target-registry/targets.json`

### `setup-foundry-agent-api.sh`

将 APIM `/foundry-agent` API 配置为代理步骤 6 的 Azure AI Foundry Agent。

```bash
bash infra/apim/setup-foundry-agent-api.sh
```

该脚本完成：
1. 从 `.env.local.L4` 读取 `L4_AI_FOUNDRY_PROJECT_NAME`、`L4_AI_FOUNDRY_PROJECT_ENDPOINT`、`L4_FOUNDRY_AGENT_ID`
2. 创建或更新 API `foundry-agent`
3. 创建 assistant / 线程 / 消息 / 运行相关操作：
  - `GET /assistants`
  - `GET /assistants/{assistantId}`
  - `POST /threads`
  - `POST /threads/runs`
  - `POST /threads/{threadId}/messages`
  - `POST /threads/{threadId}/runs`
  - `GET /threads/{threadId}/runs/{runId}`
  - `GET /threads/{threadId}/messages`
4. 设置 API 级策略：
  - 注入 `traceparent`
  - 用 APIM MSI 获取 `https://ai.azure.com` token
  - 注入 `Authorization: Bearer <msi-token>`
  - 固定 `api-version=v1`
  - 透传治理头与 APIM request id
5. 创建 API-level App Insights diagnostics
6. 更新 `infra/target-registry/targets.json`

**注意**：该脚本不替你修改 Foundry Project 的 RBAC。当前设计要求 APIM MSI 对 Foundry Agent 数据面访问的授权已在项目侧具备；如果运行后后端返回 `401/403`，需要回到 Foundry Project 检查 APIM MSI 的实际权限。

### `setup-copilot-studio-api.sh`

将 APIM `/copilot-studio` API 配置为代理步骤 6 的 Copilot Studio Agent Direct Line 通道。

```bash
bash infra/apim/setup-copilot-studio-api.sh
```

该脚本完成：
1. 从 `.env.local.L4` 读取 `L4_COPILOT_STUDIO_DIRECTLINE_SECRET`
2. 在 APIM 中创建或更新 Secret Named Value `copilot-directline-secret`
3. 创建或更新 API `copilot-studio`
4. 创建 Direct Line 操作：
  - `POST /conversations`
  - `POST /conversations/{conversationId}/activities`
  - `GET /conversations/{conversationId}/activities`
5. 设置 API 级策略：
  - 注入 `traceparent`
  - 使用 APIM Named Value 注入 `Authorization: Bearer {{copilot-directline-secret}}`
  - 透传治理头与 APIM request id
6. 创建 API-level App Insights diagnostics
7. 更新 `infra/target-registry/targets.json`

`bot_id`、`environment_id` 等手工创建元数据不再要求放入 `.env.local.L4`；若需保留，记录在步骤 6 设计文档即可。

## 验证（执行后）

```bash
# 在 VNet 内或配好 DNS override 后：
curl -s https://aigoverntrustworthydemoapim.azure-api.net/rag/health

curl -s -X POST https://aigoverntrustworthydemoapim.azure-api.net/rag/responses \
  -H "Content-Type: application/json" \
  -d '{"input": "What are the four core functions of NIST AI RMF?"}'

curl -s -X POST https://aigoverntrustworthydemoapim.azure-api.net/native-model/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"What does NIST AI RMF stand for?"}],"max_completion_tokens":128}'

curl -s -X POST https://aigoverntrustworthydemoapim.azure-api.net/foundry-agent/threads/runs \
  -H "Content-Type: application/json" \
  -d '{"assistant_id":"<foundry-agent-id>","thread":{"messages":[{"role":"user","content":"Summarize the key ideas in NIST AI RMF."}]}}'

curl -s -X POST https://aigoverntrustworthydemoapim.azure-api.net/copilot-studio/conversations \
  -H "Content-Type: application/json" \
  -d '{}'
```

## 后续未完成项

- 可选：在 `POST /responses` 上加 JWT 验证策略（`<validate-jwt>`），要求调用方持有有效 Entra token
- 可选：在 `POST /native-model/chat/completions` 上加 JWT 验证策略（`<validate-jwt>`），要求调用方持有有效 Entra token
- 可选：在 `foundry-agent` 与 `copilot-studio` API 上加 `validate-jwt` 或来源限制策略
- 可选：通过 Azure Front Door / App Gateway 为 Internal VNet APIM 提供公网入口
