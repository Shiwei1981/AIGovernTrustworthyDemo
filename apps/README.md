# Apps

本目录用于放项目内各个可独立演进的应用。

当前规划应用：

- `dashboard-web/`：面向治理人员的主 dashboard 网站
- `rag-service/`：RAG 服务与知识检索 API
- `tier1-app/`：直接调用 AI 服务的一级消费应用
- `tier2-app/`：通过 Tier 1 间接使用 AI 的二级消费应用
- `evaluation-runner/`：评测执行入口或服务
- `pyrit-runner/`：红队运行入口或服务

规则：

- 每个应用独立维护自己的 README、配置、入口代码和局部实现说明。
- 跨应用统一规则不要写在这里，统一写入 `docs/charters/`。