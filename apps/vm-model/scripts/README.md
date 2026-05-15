# scripts/

本目录存放步骤 5 的可执行脚本，按执行阶段分：

| 脚本 | 阶段 | 说明 |
|---|---|---|
| `01_create_vm.sh` | VM 创建（参考） | 当前 VM 已手动创建；脚本仅保留为重建参考 |
| `02_init_vm.sh` | VM 初始化 | 通过 `az vm run-command` 安装 Python venv、HF 依赖和 `llama.cpp` 预编译二进制 |
| `03_download_model.sh` | 模型下载 | 通过 `az vm run-command` 从 HuggingFace 下载 Phi-3-mini-4k-instruct GGUF |
| `04_start_service.sh` | 服务启动 | 上传 sidecar、安装依赖、写 systemd unit，并启动 `llama-server` + sidecar |
| `05_smoke_test.sh` | 验证 | 通过 `az vm run-command` 验证 `GET /health` + `POST /v1/chat/completions` |

> 这些脚本默认从仓库根目录读取 `.env.local.L4`，并使用 deploy SPN + `az vm run-command` 在 VM 上执行实际动作。
> 占位值（如 `<to-be-deployed>`）不会被直接 `source`；脚本只读取当前实施所需的最小变量集合。
