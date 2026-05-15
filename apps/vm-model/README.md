# vm-model

Domain 4 · 步骤 5 — VM Hugging Face 模型 + API

本目录存放与 `AIGovernTrustworthyDemoVM` 相关的初始化脚本、部署命令和验证脚本。

## 目录结构

```
vm-model/
└── scripts/           # VM 初始化、模型下载、服务启动、smoke test 脚本
```

## 相关文档

- 需求设计：`docs/design-L3-domain-4-vm-huggingface-model-api.md`
- 上级步骤列表：`docs/design-L2-domain-4-prerequisites.md` §步骤 5
- APIM 接入设计：`docs/design-L3-domain-4-apim.md` §7.6 `/vm-model`
- Target registry：`infra/target-registry/targets.json`

## 关键参数（来自 `.env.local.L4`）

| 变量 | 用途 |
|---|---|
| `L4_VM_NAME` | VM 资源名 |
| `L4_VM_ADMIN_USERNAME` | SSH 登录用户名 |
| `L4_VM_PRIVATE_IP` | VM 私网 IP（创建后填入）|
| `L4_VM_MODEL_NAME` | 模型名称（llama-server alias）|
| `L4_VM_MODEL_API_PORT` | 推理 API 端口（默认 11434）|
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | App Insights 连接串 |

## 当前状态

⬜ 待开始 — VM 尚未创建，脚本待开发。
