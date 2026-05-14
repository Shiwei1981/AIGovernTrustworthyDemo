# infra/apim

APIM 配置脚本目录，管理 `AIGovernTrustworthyDemoAPIM` 中各 AI 服务的 API 定义。

## 当前状态

| API | Path | Backend | 状态 |
|---|---|---|---|
| RAG Governance Service | `/rag` | `AIGovernTrustworthyRAGApp` Web App | ✅ 脚本就绪，待执行 |
| Native Model | `/native-model` | Azure OpenAI (via APIM MSI) | 🔲 待配置（MSI RBAC 需授权） |

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

## 验证（执行后）

```bash
# 在 VNet 内或配好 DNS override 后：
curl -s https://aigoverntrustworthydemoapim.azure-api.net/rag/health

curl -s -X POST https://aigoverntrustworthydemoapim.azure-api.net/rag/responses \
  -H "Content-Type: application/json" \
  -d '{"input": "What are the four core functions of NIST AI RMF?"}'
```

## 后续未完成项

- Native Model `/native-model` API：需先给 APIM MSI 授 `Cognitive Services OpenAI User` on `AIGovernTrustworthyAOAI`
- 可选：在 `POST /responses` 上加 JWT 验证策略（`<validate-jwt>`），要求调用方持有有效 Entra token
- 可选：通过 Azure Front Door / App Gateway 为 Internal VNet APIM 提供公网入口

