# AIGovernTrustworthyDemo

本项目用于构建一组演示程序和系统，展示企业在 AI Trustworthy Governance 领域的治理实践。

当前仓库的重点不是一次性落地所有演示对象，而是先明确 Domain 4 所需的前置条件、资源规划、环境契约和观测基线，后续再逐步补齐各个 target 的实现、接入、监控与验证。

## 当前设计中心

当前 Domain 4 已确认的观测方案是：

- 所有可代理的 HTTP hop 默认通过 APIM，并启用 APIM tracing。
- Foundry 原生模型、fine-tune 模型、Foundry Agent 全面开启 Foundry tracing。
- Python 侧的实际 LLM 调用通过 shared-observability 写入完整 Blob evidence，并补一条薄 Application Insights evidence 事件。
- Application Insights / Azure Monitor Logs 是 APIM tracing、Foundry tracing、Python evidence 的统一查询面。
- Blob archive 是完整 `input`、`output`、`metadata` 的唯一归档位置。

当前统一关联字段以 `trace_id`、`response_id`、`archive_id`、`payload_ref` 为主；不再把自定义 `correlation_id` 作为观测系统中心。

## 权威文档

Domain 4 相关工作应以以下文档为准：

- 环境契约：`.env.local.L4`
- 仓库级指令：`.github/copilot-instructions.md`
- 跨应用统一宪章：`docs/charters/`
- 一级概览：`docs/design-L1-overview.md`
- Domain 4 前置条件设计：`docs/design-L2-domain-4-prerequisites.md`
- Domain 4 低级别设计：`docs/design-L2-domain-4-prerequisites-lowleveldesign.md`
- Domain 4 输出可信设计：`docs/design-L2-domain-4-output-trustworthiness.md`
- Domain 4 shared-observability 组件设计：`docs/design-L3-domain-4-shared-observability-component.md`

根 README 不再重复维护 L2/L3 级别的矩阵、资源表和字段细节，避免与设计文档产生双份定义。

## 仓库结构

当前仓库按“规则、设计、实现、共享能力、基础设施”分层：

- `docs/`：需求、设计、统一约束和跨应用宪章
- `AIGovernDashboardDesign/`：Dashboard 调研、方法论、KPI 与原型记录
- `apps/`：各独立应用，例如 dashboard、RAG service、Tier 1、Tier 2、runner
- `packages/`：跨应用共享的数据契约与观测能力
- `infra/`：Azure、监控和基础设施脚本与配置

## 当前范围

当前优先覆盖以下内容：

1. Domain 4 前置条件、资源与环境契约落位。
2. APIM + Foundry tracing + Python evidence + Blob archive 的统一观测设计落位。
3. RAG Service、Tier 1、Tier 2、Foundry targets、VM model、runner 的接入基线定义。
4. 后续实现所需的跨应用共享约束与仓库骨架。

## 实施约束

- Domain 4 target types 必须分开展示和统计，不能把 AI apps、Foundry models、Foundry agents、Copilot Studio agents、VM models、Tier 1、Tier 2 混成一个总量。
- APIM 是受控网关与统一入口；Application Insights 是证据查询面；Blob archive 是完整证据存储。
- shared-observability 的职责是 Python evidence logging，不是自建 tracing backbone。
- 文档中的资源、步骤和字段定义应集中维护在 `docs/`，避免在 README 中重复维护细节表格。

## 后续工作

后续会在本仓库中逐步补充：

- 各 target 的应用代码与 connector
- Azure 资源自动化脚本
- 部署说明和环境配置
- 运行、验证、evaluation 与 red teaming 脚本
- KQL 查询、仪表板 API 和治理检查清单
