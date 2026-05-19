# monitoring

本目录用于统一观测与监控配置。

当前已提供的 Step 8 tracing 展示产物：

- `domain4-step8-tracing.workbook.json`：Workbook 内容定义，内置 Q1-Q5 tracing demo queries，并包含 Q2a/Q2b 单 trace 调用链图
- `deploy-step8-tracing-workbook.template.json`：ARM 模板，用于部署 Workbook 实例
- `deploy-step8-tracing-workbook.sh`：一键部署脚本，默认把 Workbook 挂到现有 Application Insights

## Step 8 Workbook 部署

默认部署命令：

```bash
bash infra/monitoring/deploy-step8-tracing-workbook.sh
```

可选覆盖参数：

```bash
APP_INSIGHTS_NAME=appinsights \
WORKBOOK_DISPLAY_NAME="AIGovernTrustworthyDemo Step 8 Tracing Showcase" \
bash infra/monitoring/deploy-step8-tracing-workbook.sh
```

脚本行为：

1. 读取仓库根目录 `.env.local.L4`
2. 使用 deploy SPN 登录 Azure
3. 解析目标 Application Insights 资源
4. 部署或更新 Step 8 Workbook

部署完成后，可在 **Application Insights -> Workbooks** 中打开，不需要每次手工拷贝 KQL。

## Step 8 调用链图使用方式

1. 打开 `AIGovernTrustworthyDemo Step 8 Tracing Showcase`
2. 在 Q1 或 Q3 找一条 `trace_id` / `sample_trace_id`
3. 粘贴到顶部 `TraceId`
4. 查看：
   - Q2：单 trace 明细表
   - Q2a：按时间顺序串起的调用链图，节点用短组件名显示
   - Q2b：基于 `id` / `operation_ParentId` 的父子 span 拓扑图，节点用短组件名显示
