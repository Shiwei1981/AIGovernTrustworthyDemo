# vm-model

Domain 4 · 步骤 5 — VM Hugging Face 模型 + API

本目录存放与 `AIGovernTrustworthyDemoPhi3VM` 相关的初始化脚本、部署命令和验证脚本。

## 目录结构

```
vm-model/
└── scripts/           # VM 初始化、模型下载、服务启动、smoke test 脚本
```

## 相关文档

- 设计文档：`docs/design-L3-domain-4-vm-huggingface-model-api.md`
- 上级步骤列表：`docs/design-L2-domain-4-prerequisites.md` §步骤 5
- APIM 接入设计：`docs/design-L3-domain-4-apim.md` §7.6 `/vm-model`
- Target registry：`infra/target-registry/targets.json`

## 关键参数（来自 `.env.local.L4`）

| 变量 | 用途 |
|---|---|
| `L4_VM_NAME` | VM 资源名 |
| `L4_VM_ADMIN_USERNAME` | SSH 登录用户名 |
| `L4_VM_PRIVATE_IP` | VM 私网 IP（当前为 `10.1.1.8`）|
| `L4_VM_PUBLIC_DNS` | VM 公网 DNS（仅用于 SSH 管理）|
| `L4_VM_MODEL_NAME` | 模型名称（llama-server alias）|
| `L4_VM_MODEL_API_PORT` | 推理 API 端口（默认 11434）|
| `L4_OTEL_SERVICE_NAME_VM_MODEL` | VM 模型 sidecar 的 OTel `service.name` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | App Insights 连接串 |

## 当前状态

✅ 已完成最小可运行切片 — VM 已创建（`10.1.1.8` / `aigoverntrustworthydemophi3vm.canadaeast.cloudapp.azure.com`），`llama-server` + sidecar 已部署，`/health` 与 `/v1/chat/completions` smoke test 已通过。
