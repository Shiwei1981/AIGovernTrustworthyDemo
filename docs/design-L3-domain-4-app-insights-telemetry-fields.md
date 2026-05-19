# Domain 4 · App Insights 遥测字段配置（步骤 8）设计

## 1. 文档定位

本文件是 `docs/design-L2-domain-4-prerequisites.md` 中 **步骤 8：App Insights 遥测字段配置** 的独立 L3 设计文档。

本文件只聚焦以下问题：

1. 步骤 8 当前到底已经完成了什么。
2. 本期步骤 8 的目标是否仍然是 troubleshooting。
3. 如果本期只证明 tracing capability，应该做哪些查询、图表和可视化展示。
4. Foundry UI 中的 tracing 栏目是否可以作为演示型 tracing 可视化的一部分。

> **边界说明**  
> 本文件不替代 `docs/design-L3-domain-4-monitoring-tracing-logging.md` 的统一 observability 主规范。  
> 本文件当前优先服务于 **tracing capability 展示**，不以 troubleshooting 字段治理为本期主目标。

---

## 2. 关联文档

| 文档 | 关系 |
|---|---|
| `docs/design-L2-domain-4-prerequisites.md` | 步骤 8 的上层步骤定义 |
| `docs/design-L3-domain-4-monitoring-tracing-logging.md` | Domain 4 observability 主规范 |
| `docs/design-L3-domain-4-shared-observability-component.md` | shared-observability 组件设计 |
| `docs/design-L2-domain-4-output-trustworthiness.md` | Domain 4 指标侧查询诉求 |
| `packages/shared-observability/shared_observability/api.py` | shared-observability 实际事件属性实现 |
| `packages/shared-observability/shared_observability/_telemetry.py` | App Insights evidence 事件实际发射实现 |
| `packages/shared-observability/shared_observability/schema.py` | 字段与事件名枚举定义 |
| `apps/rag-service/app.py` | RAG 服务写 evidence 的现状 |
| `apps/tier1-app/app.py` | Tier 1 写 evidence 的现状 |
| `apps/tier2-app/app.py` | Tier 2 写 evidence 的现状 |
| `apps/vm-model/sidecar.py` | VM sidecar 轻量 App Insights 事件实现 |
| `apps/trace_chain_backend.py` | 当前 Trace Chain 查询口径实现 |

---

## 3. 步骤 8 的目标与范围

### 3.1 当前目标

步骤 8 当前不再把“统一 troubleshooting 字段合同”作为本期主目标，并已被标记为 **部分完成**。

当前已确认的关键决定是：

1. **本期步骤 8 先不做以 troubleshooting 为目标的字段整理。**
2. **本期步骤 8 已交付 App Insights 查询与 Workbook 报表，但展示不全面，且调用链图仍可能存在可读性或稳定性问题。**
3. **tracing chain 的正式演示入口改为使用步骤 7 已开发的 Trace Chain UI。**
4. **Foundry UI tracing 深入集成、字段主合同收敛、troubleshooting 能力建设等剩余步骤 8 能力暂时跳过。**

本步当前最终落地范围固定为：

1. 保留一组可复用的 App Insights / Azure Monitor Logs 查询。
2. 保留已部署的 App Insights Workbook 报表，作为辅助观察入口。
3. 记录 Foundry UI tracing 的适用边界。
4. 明确本期不再继续补齐 App Insights 图形展示、Foundry UI 展示或 troubleshooting 字段治理。

### 3.2 当前纳入范围

步骤 8 当前已完成/保留的范围：

1. App Insights / Azure Monitor Logs 查询设计
2. App Insights Workbook 报表部署
3. 基础统计图与单 trace 调用链图尝试
4. Foundry UI tracing 栏目可视化研究与边界说明
5. 与步骤 7 Trace Chain UI 的职责切分说明

### 3.3 当前不作为阻塞项的对象

以下对象本步不作为当前 tracing 展示验收阻塞项：

1. Copilot Studio Agent
2. Evaluation runner
3. PyRIT runner

---

## 4. 本期关键取舍

### 4.1 本期要做的事

1. 用 App Insights / Azure Monitor Logs 展示当前链路**已经可见**。
2. 设计适合演示的 tracing query、图表和调用链展示方式。
3. 研究 Foundry UI tracing 的可视化能力与适用边界。

### 4.2 本期先不做的事

1. 不把步骤 8 做成 troubleshooting 字段治理项目。
2. 不要求当前把所有概念字段都收敛成统一实现。
3. 不要求本期统一 VM sidecar 与 shared-observability 的全部字段命名。
4. 不为了步骤 8 去修改已有应用代码。

### 4.3 保留为未来可能扩展的事

1. 统一“概念字段名 -> 实际 App Insights 存储键名”主合同。
2. 把 `model_version`、`test_tool`、`test_run_id` 等补齐到 thin event。
3. 把 `traces` / `customEvents` 等查询口径彻底定版。
4. 形成 troubleshooting 导向的字段覆盖率和排障查询包。

---

### 4.4 本期 tracing query 需求总览

本期步骤 8 先不追求“字段治理完成”，而是优先交付一组**能直接证明 tracing capability 的 query**。

当前建议的 query 包固定为以下 5 条：

| Query ID | 目标 | 主要数据来源 | 主要输入 | 主要输出 | 推荐展示 |
|---|---|---|---|---|---|
| Q1 | 展示最近可见的 trace 总览 | `requests`、`dependencies`、`traces` | 时间范围、服务过滤 | trace 列表、持续时间、状态、涉及服务数 | Grid / Summary table |
| Q2 | 展示单个 trace 的调用链顺序 | `requests`、`dependencies`、`traces` | `trace_id` | 单条 trace 的时间顺序链路 | Ordered table / Timeline |
| Q3 | 展示 APIM 到下游目标的链路能力 | APIM diagnostics 对应查询表 | 时间范围、route/path | route、backend、状态、延迟、样例 trace | Bar + detail grid |
| Q4 | 展示 Python evidence 已进入统一观测面 | `traces` 或 `customEvents` + Blob 索引字段 | 时间范围、target_type、service_name | `trace_id`、`response_id`、`archive_id`、`payload_ref` | Grid |
| Q5 | 展示跨组件 tracing 覆盖面 | `requests`、`dependencies`、`traces` | 时间范围 | 各组件的 telemetry 发射情况 | Stacked column / Matrix |

这些 query 的共同原则：

1. 以**演示链路可见**为目标，不以排障深挖为目标。
2. 优先使用当前仓库中已经落地的链路：APIM、Tier 1、Tier 2、RAG、VM、Foundry。
3. 允许某些 query 先采用“当前可查即可”的表与字段，不要求本期统一到最终 troubleshooting 口径。

### 4.5 每一个 query 的需求与设计

#### Q1：Recent Trace Overview

**需求**

1. 证明最近一段时间内，系统里已经存在可查询的 trace。
2. 让演示人员能快速挑选一个 trace 进入后续下钻。
3. 适合作为步骤 8 演示的首页 query。

**设计**

- **输入**：时间范围；可选服务过滤（如 Tier 1 / Tier 2 / RAG / VM / Foundry）
- **主要来源**：`requests`、`dependencies`、`traces`
- **输出字段建议**：
  - `trace_id`
  - `start_time`
  - `end_time`
  - `duration_ms`
  - `success_or_status`
  - `services_involved`
  - `items_count`
- **展示方式**：表格为主；可附加一个最近 24h / 7d trace 数趋势小图
- **演示价值**：先证明“trace 已经存在，而且不是单点日志”

**KQL 草案（Recent Trace Overview）**

```kusto
union isfuzzy=true requests, dependencies, traces
| where timestamp > ago(24h)
| extend trace_id = operation_Id
| where isnotempty(trace_id)
| summarize
    start_time = min(timestamp),
    end_time = max(timestamp),
    items_count = count(),
    services_involved = dcountif(cloud_RoleName, isnotempty(cloud_RoleName)),
    has_failure = maxif(1, success == false),
    sample_roles = make_set(cloud_RoleName, 5)
  by trace_id
| extend
    duration_ms = datetime_diff("millisecond", end_time, start_time),
    success_or_status = iff(has_failure == 1, "has_failure", "all_success_or_unknown")
| order by start_time desc
```

**使用说明**

1. 默认时间窗口先用 `ago(24h)`，演示时可改为 `ago(7d)`。
2. 如果只看某个服务，可在 `where isnotempty(trace_id)` 后加：
   `| where cloud_RoleName == "<service-name>"`
3. 该 query 的重点不是完整排障，而是快速证明“最近确实有 trace，且 trace 覆盖多个组件”。

**推荐图表**

1. 主视图：Grid
2. 辅助视图：按小时聚合 trace 数的 time chart

#### Q2：Single Trace Chain Detail

**需求**

1. 对指定 `trace_id`，按时间顺序展示完整调用链。
2. 证明同一个 trace 可以跨 APIM、应用层、VM sidecar、evidence 记录联动。
3. 适合作为“链路可追踪”的核心证明 query。

**设计**

- **输入**：`trace_id`
- **主要来源**：`requests`、`dependencies`、`traces`
- **输出字段建议**：
  - `timestamp`
  - `trace_id`
  - `itemType`
  - `cloud_RoleName`
  - `name`
  - `operation_Id`
  - `operation_ParentId`
  - `resultCode`
  - `success`
  - `duration`
- **展示方式**：按时间排序的详细表；如 Workbook 能支持，可用 timeline 风格增强展示
- **演示价值**：直接展示“一个请求是怎么一步一步流过来的”

**KQL 草案（Single Trace Chain Detail）**

```kusto
let trace_id = "<trace_id>";
union isfuzzy=true requests, dependencies, traces
| where timestamp > ago(7d)
| where operation_Id == trace_id
| project
    timestamp,
    trace_id = operation_Id,
    itemType,
    cloud_RoleName,
    name,
    message,
    id,
    operation_ParentId,
    resultCode,
    success,
    duration
| order by timestamp asc
```

**使用说明**

1. `trace_id` 直接替换成 Q1 返回的一条样例 trace。
2. 当前仓库里的 `apps/trace_chain_backend.py` 也是按 `operation_Id` / `trace_id` 来串链路，因此这条 query 与现有实现口径一致。
3. 这条 query 适合做“演示下钻”：先在 Q1 选一条 trace，再在 Q2 展开详细链路。

**推荐图表**

1. 主视图：Ordered table
2. 如 Workbook 能支持：按 `timestamp` 的 timeline / sequence 展示

**建议补充视图**

若希望更强调“跨组件顺序”，可加一个简化版视图：

```kusto
let trace_id = "<trace_id>";
union isfuzzy=true requests, dependencies, traces
| where timestamp > ago(7d)
| where operation_Id == trace_id
| extend step_name = coalesce(name, message, itemType)
| project timestamp, cloud_RoleName, itemType, step_name, success, resultCode
| order by timestamp asc
```

#### Q3：APIM Route-to-Backend Trace Proof

**需求**

1. 证明 APIM 的 tracing 已经对关键 route 生效。
2. 证明可代理 HTTP hop 当前已经被受控网关记录。
3. 让演示时可以按 route 展示，不要求先知道具体 trace_id。

**设计**

- **输入**：时间范围；route/path 过滤（如 `/tier1`、`/tier2`、`/rag`、`/native-model`、`/finetune-model`、`/vm-model`、`/foundry-agent`）
- **主要来源**：APIM diagnostics 对应的 App Insights / Azure Monitor Logs 查询表
- **输出字段建议**：
  - `route`
  - `backend_target`
  - `calls`
  - `success_rate`
  - `avg_duration_ms`
  - `p95_duration_ms`
  - `sample_trace_id`
- **展示方式**：按 route 的柱状图 + 明细表
- **演示价值**：证明“所有关键 hop 都经过 APIM 并留下 trace”

**KQL 草案**

```kusto
requests
| where timestamp > ago(24h)
| where cloud_RoleName == "AIGovernTrustworthyDemoAPIM"
| extend route = extract(
    "/(tier1|tier2|rag|native-model|finetune-model|vm-model|foundry-agent|copilot-studio)",
    0,
    url
)
| where isnotempty(route)
| summarize
    calls = count(),
    success_count = countif(success == true),
    avg_duration_ms = round(avg(duration), 0),
    p95_duration_ms = round(percentile(duration, 95), 0),
    sample_trace_id = take_any(operation_Id)
  by route
| extend success_rate_pct = round(100.0 * success_count / calls, 1)
| project route, calls, success_rate_pct, avg_duration_ms, p95_duration_ms, sample_trace_id
| order by calls desc
```

**使用说明**

1. 主目标是证明 APIM route 已经留下可下钻的 trace，不是做故障排查。
2. 如果 `cloud_RoleName` 的实际值和这里不同，可放宽成 `cloud_RoleName contains "APIM"`。
3. `sample_trace_id` 可以复制到 Q2，直接演示某条 route 的完整链路。
4. 如果 APIM 后端 hop 主要落在 `dependencies`，可把同样逻辑平移到 `dependencies` 表。

**推荐图表**

1. 按 `route` 的 bar chart
2. 带 `sample_trace_id` 的 grid，便于下钻

#### Q4：Evidence-Linked Trace Proof

**需求**

1. 证明 tracing 不只有平台 hop，还有 Python evidence 能被查到。
2. 证明 trace 可以与 `response_id`、`archive_id`、`payload_ref` 建立关联。
3. 适合作为“平台 trace + evidence 共存”的证明 query。

**设计**

- **输入**：时间范围；可选 `target_type`、`service_name`
- **主要来源**：当前 evidence 事件所在查询表（现阶段允许按 `traces` / `customEvents` 的实际可用情况设计）
- **输出字段建议**：
  - `trace_id`
  - `service_name`
  - `target_type`
  - `target_id`
  - `response_id`
  - `archive_id`
  - `payload_ref`
  - `status`
- **展示方式**：明细表
- **演示价值**：证明“trace 不只是时序，还能关联到 evidence”

**KQL 草案**

```kusto
traces
| where timestamp > ago(24h)
| where message == "AIGovernTrustworthyLLMEvidence"
| extend
    trace_id = operation_Id,
    service_name = tostring(customDimensions["service.name"]),
    source_type = tostring(customDimensions["aigov.source.type"]),
    target_type = tostring(customDimensions["aigov.target.type"]),
    target_id = tostring(customDimensions["aigov.target.id"]),
    response_id = tostring(customDimensions["gen_ai.response.id"]),
    archive_id = tostring(customDimensions["aigov.archive.id"]),
    payload_ref = tostring(customDimensions["aigov.payload.ref"]),
    status = tostring(customDimensions["status"])
| project
    timestamp,
    trace_id,
    service_name,
    source_type,
    target_type,
    target_id,
    response_id,
    archive_id,
    payload_ref,
    status
| order by timestamp desc
```

**使用说明**

1. 当前仓库里，shared-observability 的 evidence 事件实际按这个口径查 `traces` 更贴近现状。
2. 这条 query 的价值是证明：trace 不只是平台 hop，还能连到 Python evidence 与 Blob archive 引用。
3. 如需聚焦某一类对象，可增加过滤，如 `| where target_type == "rag_service"`。
4. 未来如果仓库统一改成 `customEvents` 为主入口，再同步改这里即可；本期先以可展示 tracing capability 为准。

**推荐图表**

1. 详细 grid
2. 如需摘要，可按 `target_type` 做 count chart

#### Q5：Cross-Component Telemetry Coverage

**需求**

1. 证明多个组件已经在同一查询面留下 telemetry。
2. 让演示时快速看到哪些组件当前已接入、哪些组件只有部分接入。
3. 不要求本期把字段完全统一，只要求把覆盖面展示清楚。

**设计**

- **输入**：时间范围
- **主要来源**：`requests`、`dependencies`、`traces`
- **输出字段建议**：
  - `cloud_RoleName`
  - `itemType`
  - `count`
  - `latest_timestamp`
- **展示方式**：stacked column 或 matrix
- **演示价值**：证明当前不是单一组件在发日志，而是跨组件 tracing 已经具备

**KQL 草案**

```kusto
union isfuzzy=true requests, dependencies, traces
| where timestamp > ago(7d)
| where isnotempty(cloud_RoleName)
| summarize
    requests_count = countif(itemType == "request"),
    dependencies_count = countif(itemType == "dependency"),
    traces_count = countif(itemType == "trace"),
    total = count(),
    latest_telemetry = max(timestamp)
  by cloud_RoleName
| order by total desc
```

```kusto
traces
| where timestamp > ago(7d)
| where message in ("AIGovernTrustworthyLLMEvidence", "AIGovernTrustworthyVMModelTrace")
| extend target_type = coalesce(
    tostring(customDimensions["aigov.target.type"]),
    tostring(customDimensions["target_type"])
)
| summarize evidence_count = count(), latest = max(timestamp) by message, target_type
| order by evidence_count desc
```

**使用说明**

1. 第一条 query 看“哪些组件已经有平台 telemetry”。
2. 第二条 query 看“哪些 tracing 来源已经写出了 evidence 类事件”。
3. 两条一起展示，就能说明当前步骤 8 的覆盖面，而不需要先完成字段统一治理。
4. 这也符合本期范围：展示 tracing capability，而不是做 troubleshooting 字段主合同收敛。

**推荐图表**

1. 第一条：stacked bar，按 `cloud_RoleName` 展示 request / dependency / trace
2. 第二条：按 `target_type` 或 `message` 的 bar chart

### 4.6 微软官方文档研究：Foundry UI 是否可作为 tracing query / 展示 UI

以下结论基于 2026-05-18 读取的微软官方文档：

1. **View Trace Results for AI Applications using OpenAI SDK (classic) - Microsoft Foundry (classic) portal**
2. **Monitor your Generative AI Applications (preview) (classic) - Microsoft Foundry (classic) portal**

#### 4.6.1 官方文档明确说明了什么

根据官方文档，Foundry UI 当前明确支持以下能力：

1. 在 Foundry 项目中启用 tracing，并把 trace 存到 **Azure Application Insights**。
2. 在 Foundry 门户的 **Tracing** 栏目中查看 trace 列表。
3. 在 Tracing 详情中查看：
   - trace id
   - start time
   - duration
   - status
   - operations/span 数
   - execution timeline
   - input / output data
   - performance metrics
   - error details
   - custom attributes / metadata
4. 在 Foundry 门户的 **Monitoring / Application analytics** 中查看 built-in dashboard。
5. 这些 monitoring 视图本质上是基于 **Application Insights + Azure Workbooks** 构建。
6. 门户中可以直接打开支撑这些视图的 KQL，并跳转到 **Azure Monitor Application Insights** 做进一步自定义。

#### 4.6.2 可以做哪些事情

结合官方文档与当前项目范围，Foundry UI **可以**作为以下用途：

1. **平台原生 tracing 可视化入口**
   - 特别适合演示 Foundry 支持路径上的 trace list、timeline 和 span 细节
2. **Foundry 项目内置 monitoring dashboard**
   - 适合演示平台提供的现成可视化能力
3. **Application Insights 视图的补充入口**
   - 因为官方文档明确说明其 monitoring 视图基于 App Insights / Workbooks
4. **Foundry Agent / SDK tracing 路径的展示 UI**
   - 对使用 Foundry SDK / Foundry tracing 的对象尤其有价值

#### 4.6.3 不可以做哪些事情

基于官方文档与当前项目边界，Foundry UI **不应被视为**以下能力的替代：

1. **不能作为 Domain 4 全部 tracing 的唯一展示 UI**
   - 官方文档描述的是 Foundry 项目及其支持路径，不是 APIM、Tier 1、Tier 2、VM、全部自定义 evidence 的统一门户
2. **不能替代 Azure Monitor / Application Insights 的自定义 query 能力**
   - 官方文档明确把更深入的自定义与 advanced capabilities 指向 Azure Monitor Application Insights
3. **不能假设所有受管路径都会自动出现在 Foundry UI**
   - 只有 Foundry tracing 支持的路径，才适合在 Foundry UI 中稳定展示
4. **不能把 Foundry UI 当作 troubleshooting 字段治理工具**
   - 门户擅长 trace 浏览和内置 dashboard，不等于它能替代本项目未来的字段主合同整理

#### 4.6.4 当前项目里的落地判断

对本项目步骤 8 来说，更合理的定位是：

1. **App Insights / Azure Monitor Logs** 仍然是本期 tracing query 设计的主查询面
2. **Foundry UI tracing** 作为平台侧可视化补充入口来研究和展示
3. 对 **Foundry Agent / SDK tracing 支持路径**，优先评估 Foundry UI 是否足够“漂亮且可解释”
4. 对 **APIM -> AOAI REST、Tier 1、Tier 2、VM、shared-observability evidence** 等跨组件路径，仍应以 App Insights query / Workbook 图表为主

#### 4.6.5 当前研究限制

微软官方文档当前可直接读取到的详细说明主要落在 **Foundry (classic) portal** 文档上，并且文档中明确提示某些文章**不适用于 new Foundry portal**。

因此，本期研究结论应保持以下保守边界：

1. 可以确认 **Foundry UI 具备 tracing / monitoring 可视化能力**
2. 可以确认它**依赖或复用 Application Insights / Azure Workbooks**
3. 但对于 **new Foundry portal** 的最终可视化体验、查询入口一致性和功能完整度，仍需以后续实际验证为准

#### 4.6.6 当前 8 个 target 的展示面建议

基于当前目标清单、接入方式和微软官方文档，步骤 8 可先按下表决定展示面：

| target_type | 当前目标 | 推荐主展示面 | Foundry UI 是否建议纳入步骤 8 展示 | 判断理由 |
|---|---|---|---|---|
| `foundry_agent` | `AIGovernTrustworthyDemoFoundryAgent` | **Foundry UI + App Insights** | **建议** | 当前走 Foundry project assistants/threads/runs 路径，最符合官方 tracing UI 的适用场景，适合展示 trace list、timeline、span 细节 |
| `foundry_finetune_model` | `AIGovernTrustworthyDemoFineTuneModel` | **App Insights 为主，Foundry UI 可试验** | **可研究，但不作为主依赖** | 当前 endpoint 是 project-backed `services.ai.azure.com/api/projects/.../openai/v1/chat/completions`，理论上更接近 Foundry 项目路径，但是否稳定出现在 Foundry tracing UI 仍需实测 |
| `foundry_native_model` | `AIGovernTrustworthyDemoNativeModel` | **App Insights** | **不建议作为步骤 8 主展示面** | 当前通过 APIM 代理到 `cognitiveservices.azure.com/openai/deployments/...` 路径，更像 AOAI deployment 调用；步骤 8 不应把 Foundry UI 作为此路径的验收依赖 |
| `rag_service` | `AIGovernTrustworthyDemoRAGService` | **App Insights** | **不建议** | 这是自建 Web App + shared-observability evidence 路径，核心展示价值在跨组件 trace 与 evidence，不在 Foundry 门户 |
| `vm_huggingface_model` | `AIGovernTrustworthyDemoPhi3VM` | **App Insights** | **不建议** | 明确不属于 Foundry tracing 支持路径，当前证据来自 APIM + VM sidecar 自定义 telemetry |
| `tier1_consumer` | `AIGovernTrustworthyDemoTier1App` | **App Insights** | **不建议** | 属于上层消费应用，重点是调用链证明，不是 Foundry 平台内部 trace 浏览 |
| `tier2_consumer` | `AIGovernTrustworthyDemoTier2App` | **App Insights** | **不建议** | 同上；适合在 App Insights 里展示 Tier2 -> Tier1 -> downstream 的跨组件链路 |
| `copilot_studio_agent` | `AIGovernTrustworthyDemoCopilotStudioAgent` | **暂不纳入** | **本期不做** | 当前目标仍是 pending，且不属于步骤 8 本期验收阻塞项 |

**步骤 8 的具体落地建议**

1. **主展示面固定为 App Insights / Azure Monitor Logs**，覆盖全部目标，避免步骤 8 依赖某个单一平台 UI。
2. **Foundry UI 只挑一个最合适的正样本**：优先选 `foundry_agent` 做 tracing UI 展示。
3. `foundry_finetune_model` 可作为“可选研究项”，如果实测也能稳定展示，再补充为第二个 Foundry UI 样本。
4. `foundry_native_model`、`rag_service`、`vm_huggingface_model`、`tier1_consumer`、`tier2_consumer` 不把 Foundry UI 作为本期设计目标。
5. 这样步骤 8 的展示结构就比较清晰：
   - **App Insights**：统一演示全链路 tracing capability
   - **Foundry UI**：补充演示 Foundry 原生 tracing 可视化能力

#### 4.6.7 可部署交付物（当前已补充）

步骤 8 现已补充 Workbook 形式的可部署产物：

1. `infra/monitoring/domain4-step8-tracing.workbook.json`
2. `infra/monitoring/deploy-step8-tracing-workbook.template.json`
3. `infra/monitoring/deploy-step8-tracing-workbook.sh`

这意味着本期 tracing query 不再要求每次手工拷贝到 App Insights。默认做法改为：

1. 用部署脚本把 Workbook 挂到现有 Application Insights
2. 在 **Application Insights -> Workbooks** 中直接打开
3. 仅在需要临时调试 KQL 时，再单独复制 query 到 Logs

#### 4.6.8 调用链图展示方案（App Insights 与 Foundry UI）

步骤 8 当前把“统计图”和“真正 tracing 调用链图”明确分开：

| 展示面 | 当前落地项 | 说明 |
|---|---|---|
| App Insights Workbook | **Q2a Single Trace Sequence Graph** | 输入 `TraceId` 后，按时间顺序把同一 trace 的 `requests`、`dependencies`、`traces` 串成顺序图。它回答“这个请求先后经过了哪些步骤”。 |
| App Insights Workbook | **Q2b Single Trace Parent/Child Topology Graph** | 输入 `TraceId` 后，基于 `id` 与 `operation_ParentId` 尝试画父子 span 拓扑图；缺失父节点时挂到 synthetic trace root。它回答“span 之间的父子关系是什么”。 |
| Foundry UI | **Tracing -> trace detail timeline/spans** | 适合 Foundry Agent / Foundry SDK tracing 路径。官方文档说明 Foundry Portal 的 Tracing 详情可查看 execution timeline、spans、input/output、performance metrics、error details 与 custom attributes。 |

**App Insights 操作方式**

1. 打开 `AIGovernTrustworthyDemo Step 8 Tracing Showcase` Workbook。
2. 在 Q1 或 Q3 里复制一条 `trace_id` / `sample_trace_id`。
3. 粘贴到顶部 `TraceId` 参数。
4. 查看：
   - Q2：明细表
   - Q2a：按时间顺序串起的调用链图
   - Q2b：基于 parent/child span 的拓扑图

**Foundry UI 操作方式**

1. 进入 `https://ai.azure.com/`。
2. 打开当前 Foundry project（当前项目目标优先使用 `AIGovernTrustworthyDemoFoundryAgent`）。
3. 左侧选择 **Tracing**。
4. 若提示未连接数据源，则连接当前项目统一使用的 Application Insights。
5. 触发一次 Foundry Agent 调用。
6. 回到 **Tracing**，选择一条 trace。
7. 在 trace detail 中查看 execution timeline 与 spans。

**边界说明**

1. App Insights Workbook 可以做全项目统一查询面上的调用链图，覆盖 APIM、App、VM sidecar 与 evidence 事件。
2. Foundry UI 的 tracing 视图适合 Foundry Agent / SDK tracing，不应被当成 APIM、VM、Tier1/Tier2 的统一链路图。
3. Foundry UI 是否能显示完整拓扑，取决于调用是否通过 Foundry SDK / Agent instrumentation 生成符合语义的 spans；仅通过 APIM 代理的 HTTP 调用不一定会自动出现在 Foundry Tracing UI。
4. 当前步骤 8 的主验收仍以 App Insights Workbook 为准；Foundry UI 是 Foundry 原生 tracing 能力的补充展示面。

---

## 5. 步骤 8 当前完成度结论

| 项目 | 当前状态 | 已实际完成的部分 | 还需要设计/实施的部分 |
|---|---|---|---|
| **1. 字段主合同** | **部分完成** | L2/L3 文档已经定义了概念字段；`shared-observability` 已实现部分实际键名：`trace_id`、`span_id`、`service.name`、`gen_ai.request.model`、`gen_ai.response.id`、`aigov.archive.id`、`aigov.payload.ref`、`aigov.target.type`、`aigov.target.id`、`aigov.source.type`、`status` | **还没有权威的“概念字段名 -> App Insights 实际存储键名”映射表**；`model_version`、`test_tool`、`test_run_id` 已在 schema/metadata 中出现，但**没有进入 shared-observability 的 App Insights thin event**；VM sidecar 使用的是另一套平铺键名（如 `model_name`、`target_type`），尚未和 shared-observability 收敛 |
| **2. 只收敛已完成写入方** | **部分完成** | `shared-observability` 已被 `rag-service`、`tier1-app`、`tier2-app` 接入；VM sidecar 已写 `AIGovernTrustworthyVMModelTrace`；APIM 脚本已启用 W3C trace 注入与 App Insights diagnostics | **还没有“来源覆盖矩阵”**，明确每个来源写哪些字段、哪些字段必填/可空/不适用；APIM/AOAI/Foundry 平台侧字段与自定义 evidence 字段的对齐关系仍停留在分散描述里 |
| **3. 查询口径定死** | **未完成** | 设计文档已经明确统一查询面是 App Insights / Azure Monitor Logs；Trace Chain 已有可运行查询 | **evidence 事件落表口径未定**：`_telemetry.py` 明确写的是 `customEvents`，但 `trace_chain_backend.py` 实际查的是 `traces`；这两者目前不一致，是步骤 8 最直接的待收敛点 |
| **4. 可执行交付物** | **部分完成** | **事件名矩阵**已有雏形：文档 `docs/design-L3-domain-4-monitoring-tracing-logging.md` §10.1 和 `schema.py` 的 `EventNames`；字段字典已有雏形：文档 §11 | **字段矩阵**缺少实际存储键映射；**来源覆盖矩阵**缺少独立成品；**KQL 验证包**未见独立文件或脚本，`infra/monitoring/` 目前只有 README；**helper/写入点对齐清单**未见独立产物 |

> **说明**  
> 上表仍然保留，因为它解释了“如果未来要做 troubleshooting 字段治理，还缺什么”。  
> 但这些缺口**不再作为本期步骤 8 的主交付目标**。

---

## 6. 步骤 8 的字段主合同（当前保留为后续参考）

### 6.1 当前固定的核心字段

步骤 8 当前要保证的核心字段固定为：

| 字段 | 说明 |
|---|---|
| `trace_id` | 链路主关联键 |
| `span_id` | 当前 span 标识 |
| `response_id` | 具体响应标识 |
| `model_name` | 模型名称 |
| `model_version` | 模型版本 |
| `target_type` | 被调治理对象类型 |
| `target_id` | 被调治理对象标识 |
| `archive_id` | Blob archive 主键 |
| `payload_ref` | Blob archive 路径引用 |

### 6.2 当前固定的强关联补充字段

| 字段 | 说明 |
|---|---|
| `service_name` | 当前记录方服务名 |
| `source_type` | 当前记录方类型 |
| `status` | 调用结果状态 |
| `test_tool` | 触发调用的测试/执行工具 |
| `test_run_id` | 一次测试运行的唯一标识 |

### 6.3 当前设计原则

1. 核心字段优先保证 **可查询、可 join、可用于后续 Domain 4 指标**。
2. 强关联补充字段优先保证 **来源分层、测试分层和状态分层**。
3. 本步优先收敛 **App Insights 中实际可查的键名**，而不是只停留在概念字段名层面。

---

## 7. 概念字段与实际 App Insights 键名映射（当前保留为后续参考）

### 7.1 shared-observability thin event

下表仅基于当前 `packages/shared-observability/shared_observability/api.py` 的实际实现整理。

| 概念字段 | 当前 App Insights 实际键名 | 当前状态 | 备注 |
|---|---|---|---|
| `trace_id` | `trace_id` | 已实现 | thin event 已写出 |
| `span_id` | `span_id` | 已实现 | thin event 已写出 |
| `service_name` | `service.name` | 已实现 | thin event 已写出 |
| `response_id` | `gen_ai.response.id` | 已实现 | thin event 已写出 |
| `model_name` | `gen_ai.request.model` | 已实现 | thin event 已写出 |
| `model_version` | 无 | 未实现 | 当前未进入 thin event |
| `target_type` | `aigov.target.type` | 已实现 | thin event 已写出 |
| `target_id` | `aigov.target.id` | 已实现 | thin event 已写出 |
| `source_type` | `aigov.source.type` | 已实现 | thin event 已写出 |
| `archive_id` | `aigov.archive.id` | 已实现 | thin event 已写出 |
| `payload_ref` | `aigov.payload.ref` | 已实现 | thin event 已写出 |
| `status` | `status` | 已实现 | thin event 已写出 |
| `test_tool` | 无 | 未实现 | schema 中有，thin event 中没有 |
| `test_run_id` | 无 | 未实现 | schema 中有，thin event 中没有 |

### 7.2 VM sidecar 轻量事件

下表仅基于当前 `apps/vm-model/sidecar.py` 的实际实现整理。

| 概念字段 | 当前 App Insights 实际键名 | 当前状态 | 备注 |
|---|---|---|---|
| `trace_id` | `trace_id` | 已实现 | 轻量事件已写出 |
| `span_id` | `span_id` | 已实现 | 轻量事件已写出 |
| `response_id` | `response_id` | 已实现 | 轻量事件已写出 |
| `model_name` | `model_name` | 已实现 | 与 shared-observability 命名风格不同 |
| `model_version` | `model_version` | 已实现 | 与 shared-observability 命名风格不同 |
| `target_type` | `target_type` | 已实现 | 与 shared-observability 命名风格不同 |
| `target_id` | `target_id` | 已实现 | 与 shared-observability 命名风格不同 |
| `service_name` | `service_name` | 已实现 | 与 shared-observability 命名风格不同 |
| `status` | `status` | 已实现 | 轻量事件已写出 |
| `archive_id` | 无 | 不适用 | VM sidecar 不写 Blob evidence |
| `payload_ref` | 无 | 不适用 | VM sidecar 不写 Blob evidence |
| `source_type` | 无 | 未实现 | 当前未单独记录 |
| `test_tool` | 无 | 未实现 | 当前未记录 |
| `test_run_id` | 无 | 未实现 | 当前未记录 |

### 7.3 APIM / Foundry / AOAI 平台侧记录

基于当前仓库证据，平台侧已确认“存在并启用”，但**平台原生字段名在仓库中尚未收敛成权威映射表**。

| 概念字段 | 当前状态 | 当前仓库内证据 |
|---|---|---|
| `trace_id` | 已存在，但键名待实测确认 | APIM policy 已注入 `traceparent`；diagnostics 已启用 |
| `span_id` | 已存在，但键名待实测确认 | 平台 tracing / diagnostics 范围内 |
| `response_id` | 部分存在，但键名待实测确认 | AOAI/Foundry 平台侧应可见；仓库未给出最终 KQL 字段名 |
| `model_name` | 部分存在，但键名待实测确认 | AOAI 平台诊断与 Foundry tracing 设计上应可见 |
| `model_version` | 部分存在，但键名待实测确认 | 设计文档要求存在；仓库未给出最终 KQL 字段名 |
| `target_type` / `target_id` | 通常需要通过调用路径或 join 补齐 | 平台侧不保证天然按本项目 target registry 口径输出 |
| `archive_id` / `payload_ref` | 不适用 | 这两个字段属于 Python evidence / Blob archive 范围 |

**当前结论**：步骤 8 需要把平台侧字段纳入同一份查询说明，但不应假设平台侧天然直接输出与 `shared-observability` 完全一致的自定义键名。

---

## 8. 事件名矩阵

| 来源 | 事件名 / 查询对象 | 当前状态 | 备注 |
|---|---|---|---|
| shared-observability | `AIGovernTrustworthyLLMEvidence` | 已实现 | 由 `EventNames.LLM_EVIDENCE` 定义 |
| VM sidecar | `AIGovernTrustworthyVMModelTrace` | 已实现 | VM 轻量事件，不替代 Blob evidence |
| Evaluation runner | `AIGovernTrustworthyEvaluationRun` | 预留 | 当前不作为步骤 8 验收阻塞项 |
| PyRIT runner | `AIGovernTrustworthyRedTeamRun` | 预留 | 当前不作为步骤 8 验收阻塞项 |
| Finding writer | `AIGovernTrustworthyFindingCreated` | 预留 | 当前不作为步骤 8 验收阻塞项 |

---

## 9. 来源覆盖矩阵

| 来源 | 当前是否已落地 | 当前负责写什么 | 当前缺什么 |
|---|---|---|---|
| `shared-observability` | 是 | Blob archive 三件套 + thin evidence event | `model_version`、`test_tool`、`test_run_id` 未进入 thin event；最终查询入口未定 |
| VM sidecar | 是 | VM 轻量 trace 事件 | 字段命名未与 shared-observability 收敛；不含 archive 关联字段 |
| APIM diagnostics | 是 | HTTP hop / trace context / request id | 未形成步骤 8 的字段映射说明 |
| AOAI 平台诊断 | 是 | deployment / model / 结果状态类平台证据 | 未形成步骤 8 的字段映射说明 |
| Foundry tracing | 设计已就位，步骤 9 扩展 | Foundry 内部 span / tool / latency | 当前不应作为步骤 8 完成前提 |

---

## 10. 查询口径待收敛项（当前不作为本期主阻塞项）

### 10.1 当前已识别的不一致

当前仓库存在以下直接不一致：

1. `packages/shared-observability/shared_observability/_telemetry.py` 的注释说明 evidence 事件落在 `customEvents`
2. `apps/trace_chain_backend.py` 当前查询 evidence 时使用的是 `traces`

这意味着：

- 当前链路可能“能查到东西”，但**步骤 8 还没有正式固定 evidence 事件的主查询入口**
- 后续 KQL、Trace Chain、dashboard 若继续并行使用不同入口，会导致维护成本和语义漂移

### 10.2 当前处理原则

当前阶段对此问题的处理原则是：

1. **承认存在不一致**，但本期不把它作为步骤 8 必须收口的实现阻塞项。
2. 当前优先设计**能演示 tracing capability** 的查询，而不是统一 troubleshooting 查询入口。
3. 未来若步骤 8 扩展为 troubleshooting 能力建设，再正式收敛 `traces` / `customEvents` 口径。

---

## 11. 当前需要做的事 / 可以不做的事

### 11.1 本步当前必做

| 项目 | 是否应做 | 原因 |
|---|---|---|
| 输出事件名矩阵 | 是 | 后续步骤 9-11 需要复用 |
| 输出一组演示型 App Insights tracing query | 是 | 这是本期“证明 tracing capability”的主交付 |
| 设计适合演示的 tracing 图表或调用链展示方式 | 是 | 需要让 tracing 能力可视化、可讲解 |
| 研究 Foundry UI tracing 是否可用于可视化展示 | 是 | 平台原生 tracing UI 可能成为演示亮点 |
| 输出演示说明和适用范围说明 | 是 | 需要清楚说明哪些路径可展示、哪些路径只部分展示 |

### 11.2 本步建议做，但当前不要求改代码

| 项目 | 是否建议做 | 说明 |
|---|---|---|
| 输出“推荐观察字段”列表 | 建议做 | 即使不做 troubleshooting 主合同，也建议列出 query 常用字段 |
| 为不同链路准备单独 query 样例 | 建议做 | 方便演示 Tier1、Tier2、RAG、VM、Foundry 各路径 |
| 设计 query 对应的图表类型 | 建议做 | 例如 timeline、dependency list、topology 说明 |

### 11.3 本步当前可以明确不做

| 项目 | 当前是否做 | 原因 |
|---|---|---|
| 做 troubleshooting 导向的字段主合同定版 | 否 | 当前项目目标只要求证明 tracing capability |
| 统一“概念字段名 -> 实际存储键名”主合同 | 否 | 可留待未来需要 troubleshooting 时再做 |
| 收敛 `traces` / `customEvents` 为单一标准入口 | 否 | 当前不是 tracing capability 的前置条件 |
| 修改现有应用代码以补齐字段 | 否 | 当前已明确本期不改已有代码 |
| 把 Copilot Studio 完整纳入字段验收 | 否 | 当前仍受步骤 6 license 阻塞 |
| 把 Evaluation runner 作为本步完成前提 | 否 | 属于步骤 10 |
| 把 PyRIT runner 作为本步完成前提 | 否 | 属于步骤 11 |
| 在本步扩展 Foundry tracing 全能力收尾 | 否 | 属于步骤 9 |

---

## 12. 当前待决策清单

以下问题建议在步骤 8 实施前先由用户确认：

1. **演示重点**：本期优先展示哪些链路，是否固定为 Tier 1、Tier 2、RAG、VM、Foundry 这几类？
2. **App Insights 展示方式**：是否需要同时给出 query 文本和推荐图表形式？
3. **Foundry UI tracing**：是否把 Foundry UI tracing 栏目作为正式演示路径之一，还是只做可行性研究？
4. **交付粒度**：本步是否先完成文档 + query 设计 + 图表示意，不进入任何代码修改？

---

## 13. 当前建议的最小交付顺序

1. 先确认本期步骤 8 的目标是 tracing capability 展示，而不是 troubleshooting。
2. 再列出演示对象和链路清单。
3. 再设计 App Insights tracing query 和推荐图表。
4. 再研究 Foundry UI tracing 是否可以补充为平台侧可视化展示。
5. 最后输出演示说明，不修改已有代码。

---

## 14. 当前结论

步骤 8 当前标记为 **部分完成**。

当前最准确的判断是：

1. **已完成**：App Insights query / Workbook 报表、基础图表、单 trace 调用链图尝试、Foundry UI tracing 边界研究。
2. **未完成**：完整 troubleshooting 字段治理、字段主合同收敛、来源覆盖矩阵落地、Foundry UI 深入集成、稳定且全面的 App Insights tracing chain 图形展示。
3. **当前结论**：App Insights Workbook 可作为辅助报表，但展示不全面且可能存在 bug，不作为正式 tracing chain 演示主入口。
4. **正式 tracing chain 展示入口**：改用步骤 7 已开发的 Tier 1 / Tier 2 Trace Chain UI。
5. **剩余步骤 8 能力**：暂时跳过，后续如有明确需求再单独恢复。

因此，步骤 8 不再继续扩大范围。本期状态固定为：**部分完成，剩余能力暂时跳过**。
