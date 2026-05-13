# shared-contracts

本目录预留给跨应用共享的数据契约，例如：

- target registry 结构
- telemetry 字段定义
- API 请求与响应模型
- evaluation 或 red teaming 结果模型

## 与 shared-observability 的关系

`shared-contracts` 用于定义跨项目、跨组件复用的统一契约。

对 `shared-observability` 来说，它的关系应当是：

- 可以约束字段语义和命名。
- 可以作为未来的统一契约来源。
- 但不应成为 `shared-observability` 的运行时硬依赖。

也就是说，`shared-observability` 必须能够在没有 `shared-contracts` 的情况下独立运行；只有在宿主项目明确选择时，才通过适配或对齐机制与这里的契约联动。