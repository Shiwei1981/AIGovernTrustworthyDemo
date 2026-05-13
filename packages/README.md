# Packages

本目录用于放多个应用共享的代码或契约。

建议仅放真正跨应用复用的内容，例如：

- 共享数据契约
- 共享观测封装
- 共享客户端或工具库

当前已预留：

- `shared-observability/`：跨应用统一观测组件，负责 Application Insights 事件、OpenTelemetry 字段、Blob archive 写入契约