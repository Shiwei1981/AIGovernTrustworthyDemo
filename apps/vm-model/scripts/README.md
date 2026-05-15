# scripts/

本目录存放步骤 5 的可执行脚本，按执行阶段分：

| 脚本 | 阶段 | 说明 |
|---|---|---|
| `01_create_vm.sh` | VM 创建（参考） | 当前 VM 已手动创建；脚本仅保留为重建参考 |
| `02_init_vm.sh` | VM 初始化 | SSH 进 VM，安装运行时依赖（huggingface-cli、llama.cpp server）|
| `03_download_model.sh` | 模型下载 | 从 HuggingFace 下载 Phi-3-mini-4k-instruct GGUF |
| `04_start_service.sh` | 服务启动 | 配置 systemd unit，启动 llama-server |
| `05_smoke_test.sh` | 验证 | 内网 smoke test：GET /health + POST /v1/chat/completions |

> 脚本待开发，当前目录为占位结构。
