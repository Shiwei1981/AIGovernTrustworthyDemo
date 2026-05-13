# apim

本目录当前仅保留为后续可选扩展位。

当前 POC 的统一观测方案不使用该目录，主路径为：

- `packages/shared-observability/` 统一写入代码
- `Application Insights` 作为查询与调用链入口
- `Blob archive` 保存完整 AI input / output / metadata

如果未来需要演示网关治理、统一入口或不可改后端代理，再在此目录补充相关网关配置。
