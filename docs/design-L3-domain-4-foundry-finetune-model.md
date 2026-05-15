# Domain 4 · Foundry fine-tune 模型 · 步骤 4 需求设计

## 1. 文档定位

本文件是 `design-L2-domain-4-prerequisites.md` 中**步骤 4：Foundry fine-tune 模型**的专用 L3 设计文档，目标是先把步骤 4 的**需求、测试目的、边界、复用关系、验收口径**整理清楚，再进入后续训练、部署与接入实施。

步骤 4 在本项目中的定位，不是为了追求一个“更强”的业务模型，而是建立一个能够被 Domain 4 持续纳管的 **Foundry Fine-tune Model target**，用于验证模型调优后的治理对象是否也能被单独追踪、评测、红队测试和纳入报表。

> **当前状态（2026-05-15）**：步骤 4 已完成自动化闭环。已完成：在 `aigoverntrustworthysa` 中创建 `aigoverntrustworthydemo-finetune` container、生成并归档 5000 行训练 JSONL（`docs/finetune-qa-archive/aigoverntrustworthydemo-qa-5000.jsonl`）、将训练文件上传到 Storage、在 `aigoverntrustworthyfoundry` account endpoint 上创建 fine-tune job `ftjob-ae456ec3dc4d468b87ecb8512ad33f86`、得到平台 fine-tuned model `gpt-4.1-2025-04-14.ft-ae456ec3dc4d468b87ecb8512ad33f86-aigovtrustdemo`、创建 deployment `AIGovernTrustworthyDemoFineTuneModel`、完成直连烟测、并配置 APIM `/finetune-model` 与 diagnostics。早先 `invalidPayload: The specified base model does not support fine-tuning.` 的根因不是 `gpt-4.1` 不支持，而是自动化调用缺少官方要求的 `trainingType=GlobalStandard` 参数且 endpoint 选择不一致；当前固定使用 `gpt-4.1-2025-04-14` + `trainingType=GlobalStandard`。后续实施固定为**自动化优先且不依赖 Portal 手工操作**；除用户已明确批准的 3 个例外外，AI 不得创建或删除其他类型云资源。当前已获批准的例外为：`aigoverntrustworthysa` 下的 fine-tune container、fine-tune job、`AIGovernTrustworthyDemoFineTuneModel` deployment；并允许使用 SPN 为所需账号授权。

**关联文档**：

| 文档 | 关系 |
|---|---|
| `docs/charters/project-charter.md` | 约束不得越界新增未批准资源，不得擅自修改 `.env.local.L4` |
| `docs/charters/cross-app-architecture-charter.md` | 约束 APIM、App Insights、shared-observability、Entra 认证的统一要求 |
| `docs/design-L1-overview.md` | 约束 Domain 4 在全站中的目标与 L1/L2 指标映射 |
| `docs/design-L2-domain-4-prerequisites.md` | 上级步骤列表；步骤 4 的总入口 |
| `docs/design-L2-domain-4-prerequisites-lowleveldesign.md` | fine-tune 数据、存储、变量、资源与 job/deployment 锚点 |
| `docs/design-L2-domain-4-output-trustworthiness.md` | 约束步骤 4 必须支撑的 Domain 4 指标与证据字段 |
| `docs/design-L3-domain-4-apim.md` | 约束 `/finetune-model` APIM 入口、认证与 tracing 方式 |
| `docs/design-L3-domain-4-shared-observability-component.md` | 约束 Python 调用方如何记录 `foundry_finetune_model` 证据 |
| `docs/design-L3-domain-4-foundry-native-model.md` | 提供与步骤 3 相同的设计粒度与对照基线 |

---

## 2. 需求来源与不可越界边界

本步骤必须同时满足以下项目级边界：

1. 本仓库是 Domain 4 的前置条件、资源计划、环境配置和治理基线仓库；步骤 4 必须服务于后续治理演示，不是孤立的模型调优实验。
2. Domain 4 的 target type 必须分开治理；步骤 4 的对象必须明确保持为 `foundry_finetune_model`，不能与 `foundry_native_model`、RAG Service、Foundry Agent 或 VM 模型混合统计。
3. 所有运行期变量应沿用 `.env.local.L4` 已有命名，不得擅自扩展新的平行命名体系。
4. 所有 LLM/AI 调用都必须有可查询证据；步骤 4 不仅要证明 fine-tune job 存在，还要证明 fine-tuned deployment 的调用证据链成立。
5. 所有能接入 APIM 的 HTTP 接口，都必须通过 APIM 暴露；步骤 4 不能长期停留在“只可直连 fine-tuned deployment”的状态。
6. 本项目是 POC，但仍需遵守既有架构；若需要新增设计外资源、改动资源组、偏离 `disableLocalAuth = true`、或引入未批准的新训练/服务路径，必须先征得用户许可。
7. 步骤 4 默认复用已批准资源：`AIGovernTrustworthyAOAI`、`aigoverntrustworthysa`、APIM、App Insights、Blob archive；不额外新增平行模型服务资源。
8. 所有具体操作都必须由 AI 自动化脚本完成；Portal / Studio 手工点击不作为正式实施路径。
9. AI 自动化默认只允许在既有批准资源上做配置、上传、调用、查询和权限核查；不得创建或删除 Azure 资源。
10. 当前步骤 4 已获得以下资源创建例外授权：在 `aigoverntrustworthysa` 中创建 `aigoverntrustworthydemo-finetune` container、创建 fine-tune job、创建 `AIGovernTrustworthyDemoFineTuneModel` deployment。
11. 如执行过程中发现还需要创建其他类型云资源，必须先停止并请求用户确认。
12. 当前步骤 4 允许使用 deploy SPN 或其他已批准 SPN 为所需账号补充最小必要授权，但不得扩大到与本步骤无关的资源范围。

---

## 3. 步骤 4 要解决的核心问题

步骤 4 需要解决的是：在当前 Domain 4 已有的 AOAI、APIM、target registry、shared-observability 和指标设计基础上，建立一个**可训练、可部署、可调用、可代理、可追踪、可评测、可入报表**的 fine-tune 模型目标。

这意味着步骤 4 至少要同时回答以下 6 个问题：

1. **为什么要测它**：fine-tune 模型在 Domain 4 中到底承担什么治理验证价值。
2. **训练对象是什么**：基于哪个可 fine-tune 的基础模型、什么训练数据格式、多少数据、由谁生成问答对。
3. **训练事实如何记录**：job id、基础模型、训练文件、输出模型、deployment 名称如何形成可审计事实。
4. **调用入口在哪里**：既要能直连 fine-tuned deployment 验证，也要具备 APIM `/finetune-model` 的统一入口。
5. **治理身份是什么**：必须有固定 `target_id` / `target_type` / `model_name` / `model_version`，并进入 target registry。
6. **后续怎么复用**：必须能被步骤 9/10 的 Consumer App、步骤 13/15 的 evaluation / red teaming 和 L1/L2 报表复用。

---

## 4. 当前已存在的实施锚点（必须复用）

仓库中已经存在与步骤 4 直接相关的锚点；后续设计和实施应优先复用，而不是另起一套。

| 锚点 | 当前状态 | 对步骤 4 的含义 |
|---|---|---|
| `docs/design-L2-domain-4-prerequisites.md` §步骤 4 | 已有高层步骤定义 | 仍是步骤 4 的总入口 |
| `docs/design-L2-domain-4-prerequisites-lowleveldesign.md` §4.2.5 | 已定义 fine-tune 数据格式、条数、来源与存储位置 | 训练数据边界已经初步固定 |
| `docs/design-L2-domain-4-prerequisites-lowleveldesign.md` §4.2.3 | 已定义 AOAI / Foundry 模型资源与 fine-tune deployment 名称 | fine-tuned deployment 必须落在本步骤实测可创建 job 的 `aigoverntrustworthyfoundry` account 上 |
| `docs/design-L3-domain-4-apim.md` §7.3 | 已定义 `/finetune-model` APIM 路径与 MSI 方案 | 步骤 4 完成后必须补齐 APIM 接入 |
| `docs/design-L3-domain-4-shared-observability-component.md` | 已定义 `foundry_finetune_model` 证据记录规则 | 步骤 4 不能另造日志字段或证据格式 |
| `infra/target-registry/targets.json` | 已有 `AIGovernTrustworthyDemoFineTuneModel` target 占位 | 步骤 4 交付时必须把占位变为真实对象 |
| `docs/design-L3-domain-4-foundry-native-model.md` | 已给出步骤 3 的完整需求模式 | 步骤 4 应在设计粒度和治理边界上保持同类一致性 |

**当前 draft 决策**：

| 项目 | 当前 draft |
|---|---|
| Q&A generation model | `gpt-5.4-nano`（现有 native deployment） |
| fine-tune base model | `gpt-4.1` |
| training theme | AI Governance |
| source corpus | 用户上传的 5 个 AI Governance PDF |
| training data strategy | 先生成 5000 个 Q&A，再转换为 JSONL |

因此，**步骤 4 的当前 draft 已固定设计方向，但在真正开始训练前，仍必须先做 capability / quota / automation API 支持性核查**。

**2026-05-14 capability check 事实**：

| 模型 | 结果 | 证据 |
|---|---|---|
| `gpt-5.4-nano` | **不支持当前 fine-tune 设计** | `capabilities` 中无 `FineTuneTokensMaxValue`，`finetuneCapabilities = null` |
| `gpt-4.1` | **支持当前 fine-tune 设计，且已被用户明确选定** | Foundry catalog 中暴露 `FineTuneTokensMaxValue = 2000000000` |
| `gpt-4.1-nano` / `gpt-4.1-mini` / `gpt-4o-mini` / `gpt-5.4-mini` | **也支持 fine-tune** | 但当前步骤 4 不再以成本最优为首要条件 |

---

## 5. 步骤 4 的需求整理

### 5.1 目标需求

步骤 4 的直接目标不是追求最佳模型效果，而是交付一个**可被治理系统单独识别和测试的 fine-tuned 文本模型 target**。因此本步骤的需求排序如下：

1. **先证明治理可见性，再证明模型差异性**。
2. **先证明训练事实、部署事实和调用证据链完整，再考虑调优收益**。
3. **先证明它是独立 target type，再考虑与步骤 3 原生模型的能力对比**。

### 5.2 为什么要测试 fine-tune 模型

步骤 4 必须先回答“为什么要测它”，否则 fine-tune 很容易退化成一个与 Domain 4 治理目标脱节的模型实验。

本项目测试 fine-tune 模型的原因是：

1. **验证 Domain 4 不只会治理基础模型，也能治理“经过训练作业改变过行为”的模型对象。**
2. **验证 `foundry_finetune_model` 作为独立 target type，能与 `foundry_native_model` 分开展示 coverage、failure rate、red teaming 和 model identity 指标。**
3. **验证 fine-tune 生命周期事实可追溯**：训练数据位置、job id、基础模型、输出模型、deployment 名称、endpoint、版本都能被记录。
4. **验证评测和红队工具能识别 fine-tune 带来的行为偏移**，而不是只会测原始基础模型。
5. **为后续演示提供一个“与原生模型形成对照”的 Azure 托管模型目标**，证明同一治理体系能够覆盖模型调优前后两个对象。

### 5.3 训练数据与训练作业需求

1. 训练数据格式固定为 Azure OpenAI **chat completion JSONL**（`messages` 数组）。
2. 数据集总条数固定为 **5000 条 Q&A**。
3. 数据来源限定为**用户上传的 5 个 AI Governance 主题 PDF**；不扩大到未批准的数据源。
4. 问答对生成方式固定为：先将 5 个 PDF 的内容交给 AI，再由 AI 生成结构化问答对，随后整理为训练所需 JSONL。
5. 问答对主题应覆盖 AI Governance 相关内容，例如治理原则、风险管理、可追溯性、控制措施、评测、红队、合规与责任边界。
6. 本轮 draft 不把故意错误样本放入训练集；如后续需要对照或攻击样本，应单独保留 eval / red teaming 数据集。
7. 问答对需要尽量覆盖 5 个 PDF 的全部内容，不能只围绕少数高频主题重复生成。
8. 训练文件上传所用 Storage Account / Container 必须以 `.env.local.L4` 中现有变量为准，不额外引入平行存储配置：
   - `L4_STORAGE_ACCOUNT_NAME`
   - `L4_STORAGE_CONNECTION_STRING`
   - `L4_STORAGE_CONTAINER_FINETUNE`
9. 训练文件的受控存储位置固定为：
   - Storage Account：`aigoverntrustworthysa`
   - Container：`aigoverntrustworthydemo-finetune`
   - Blob 路径：`aigoverntrustworthydemo-finetune/aigoverntrustworthydemo-qa-5000.jsonl`
10. 除上传到 Storage 外，问答对中间产物还必须在仓库设计文档目录保留一份归档副本：
   - 仓库路径：`docs/finetune-qa-archive/aigoverntrustworthydemo-qa-5000.jsonl`
   - 用途：设计留档与离线审阅，不替代 Storage 中的受控训练文件
11. 问答对生成阶段优先复用已存在的 native model `AIGovernTrustworthyDemoNativeModel`（`gpt-5.4-nano`），这样步骤 3 的原生模型成为步骤 4 的问答对生成器。
12. 训练阶段至少要形成以下事实记录：
   - `fine_tune_job_id`
   - `base_model_name`
   - `training_file_path`
   - `training_record_count`
   - `output_model_name`
   - `deployment_name`
   - `created_at`
13. 如果问答对在生成后需要人工筛选、去重、改写或纠偏，应在进入训练前完成，不把明显重复、偏题或低质量问答直接送进 fine-tune job。

**5 个 PDF 覆盖范围（当前仓库锚点）**：

1. `NIST.AI.100-1.pdf`
2. `NIST.AI.600-1.pdf`
3. `OWASP-Top-10-for-LLMs-v2025.pdf`
4. `OJ_L_202401689_EN_TXT.pdf`（EU AI Act）
5. `sgmodelaigovframework2.pdf`

### 5.4 基础模型选择需求

1. 步骤 4 必须基于**Azure 托管、可 fine-tune、文本类**基础模型。
2. fine-tune 目标必须落在当前已批准的 Domain 4 Foundry / AOAI 资源范围内；当前实测可创建 job 的资源是 `aigoverntrustworthyfoundry` account endpoint，而不是旧的 `AIGovernTrustworthyAOAI` endpoint。
3. 当前 design 已明确区分两个模型角色：
   - **Q&A generation model**：`gpt-5.4-nano`
   - **fine-tune base model**：`gpt-4.1`
4. 在进入实际训练前，仍必须核实：
   - 当前 region / subscription / automation API 是否支持 `gpt-4.1` fine-tune
   - 当前 quota 是否足够
   - 当前 Azure OpenAI / Foundry API 是否允许按所需流程完成 job 创建与 deployment
5. 在 capability 核实通过前，步骤 4 固定以下身份：
   - `target_id = AIGovernTrustworthyDemoFineTuneModel`
   - `target_type = foundry_finetune_model`
   - `deployment_name = AIGovernTrustworthyDemoFineTuneModel`
   - `base_model = gpt-4.1`
6. 一旦 capability 核实通过并开始实施，必须同步更新：
   - 步骤 4 L3 文档
   - `infra/target-registry/targets.json`
   - `docs/design-L3-domain-4-apim.md`

### 5.5 部署与调用入口需求

步骤 4 需要同时具备两条调用路径，且语义不同：

| 路径 | 作用 | 是否必须 |
|---|---|---|
| 直连 fine-tuned deployment | 用于最小烟测、排查训练/部署/权限/模型可用性问题 | 是 |
| APIM `/finetune-model` | 用于统一治理入口、后续 app / runner / red teaming 接入 | 是 |

补充要求：

1. 直连 deployment 只是验证路径，不是长期治理主入口。
2. 所有可代理的上游调用场景，最终都必须收敛到 APIM `/finetune-model`。
3. APIM 认证方式必须与步骤 3 的 native model 一致：APIM MSI 获取 `https://cognitiveservices.azure.com` token。
4. 浏览器前端不应直接调用 Internal VNet APIM；需要由服务端代理或 VNet 内调用方接入。

### 5.6 治理身份与数据字段需求

步骤 4 交付的对象必须在设计和实现中保持以下固定治理身份：

| 字段 | 要求值 / 要求 |
|---|---|
| `target_type` | `foundry_finetune_model` |
| `target_id` | `AIGovernTrustworthyDemoFineTuneModel` |
| `deployment_name` | `AIGovernTrustworthyDemoFineTuneModel` |
| `model_name` | 先记录真实 fine-tune 所基于的基础模型 / 平台返回模型标识；不得继续保留 placeholder |
| `model_version` | 必须记录到 target registry 和后续证据字段中 |
| `auth` | `entra` |
| `apim_path` | `/finetune-model` |

此外，步骤 4 需要确保后续记录链路能够保留或补齐以下字段：

- `target_type`
- `target_id`
- `model_name`
- `model_version`
- `test_tool`
- `test_run_id`
- `trace_id`
- `span_id`
- `response_id`
- `archive_id`
- `payload_ref`

对于 fine-tune 特有的训练阶段，还应额外保留：

- `fine_tune_job_id`
- `base_model_name`
- `training_file_path`

### 5.7 观测与证据需求

步骤 4 不是单纯训练任务，必须满足 Domain 4 的统一观测设计：

1. **平台 tracing 边界**：对 fine-tune 模型，如走 Foundry SDK / 平台支持的 tracing 路径，应启用 Foundry tracing；当前若走 `APIM -> AOAI REST` 代理路径，其平台证据由 APIM diagnostics + AOAI 平台诊断承担。
2. **APIM tracing**：对 `/finetune-model` gateway 调用保留 APIM diagnostics 与 W3C trace context。
3. **shared-observability**：任何由 Python 应用或脚本直接调用该模型时，都应按 `foundry_finetune_model` 记录完整输入输出证据。
4. **Application Insights / Azure Monitor Logs**：作为 APIM tracing、适用时的 Foundry tracing、AOAI 平台诊断和 Python evidence 的统一查询面。
5. **Blob archive**：保存完整输入输出证据，不把完整 prompt / output 复制进 App Insights。
6. **训练事实记录**：训练 job 的关键元数据必须能被文档、脚本输出或后续 registry/清单记录引用；不能只在 Portal 页面停留一次性人工可见状态。
7. **问答对生成阶段证据**：如果使用步骤 3 的 native model 生成 5000 个问答对，该生成过程本身也应沿用既有 evidence 约束，确保 PDF -> Q&A 合成过程可追溯。
8. **Q&A 本地归档**：除 Blob 中的训练文件外，仓库 `docs/finetune-qa-archive/` 下还必须保留一份可审阅归档，确保设计文档目录中能直接回溯训练问答对样本。

### 5.7A 自动化实施需求（首选）

步骤 4 当前固定采用**自动化**方案，而不是 UI 手工路径。自动化脚本允许执行当前已批准的 3 个创建动作（fine-tune container、fine-tune job、fine-tuned deployment），其余云资源仍不得创建或删除。最小自动化闭环应包含以下 7 个切片：

1. **PDF -> 文本预处理**：从用户上传的 AI Governance PDF 中提取可送入 Q&A 生成模型的正文。
2. **Q&A 生成**：调用现有 native deployment `AIGovernTrustworthyDemoNativeModel`，批量生成 5000 个高质量问答对。
3. **JSONL 组装与质检**：将问答对整理为 Azure OpenAI chat completion JSONL，并做去重、抽样和格式校验。
4. **训练文件上传**：将 `aigoverntrustworthydemo-qa-5000.jsonl` 上传到 `aigoverntrustworthysa / aigoverntrustworthydemo-finetune`。
5. **fine-tune job 提交与轮询**：通过 Azure CLI / REST 提交 fine-tune job，并轮询直到完成。
6. **deployment 创建**：把 fine-tune 输出模型部署为 `AIGovernTrustworthyDemoFineTuneModel`。
7. **APIM / tracing 接入**：复用 native model 的 APIM 和 diagnostics 模式，配置 `/finetune-model` 并完成端到端验证。

建议沉淀的自动化脚本锚点：

| 脚本 | 责任 |
|---|---|
| `apps/native-model/scripts/generate_finetune_qa.py` | 基于 5 个 PDF 内容调用 native model 生成 5000 Q&A |
| `apps/native-model/scripts/build_finetune_jsonl.py` | 把 Q&A 转成标准 chat completion JSONL |
| `infra/azure/submit-finetune-job.sh` | 提交并轮询 fine-tune job（当前已获用户授权可执行） |
| `infra/azure/deploy-finetuned-model.sh` | 将 fine-tuned model 部署为 `AIGovernTrustworthyDemoFineTuneModel`（当前已获用户授权可执行） |
| `infra/apim/setup-finetune-model-api.sh` | 配置 `/finetune-model` API、policy、diagnostics |
| `apps/native-model/scripts/test_finetune_model.py` | 直连 fine-tuned deployment 做最小烟测 |

### 5.8 与已开发组件的耦合需求

步骤 4 需要主动适配当前已设计或已开发组件，而不是把这些关系留到后面再补：

1. **APIM**：步骤 4 完成后必须补齐 `/finetune-model`，否则不符合“所有可代理 HTTP hop 统一走 APIM”的宪章要求。
2. **Target Registry**：必须确保 `infra/target-registry/targets.json` 中 fine-tune 条目与真实训练/部署结果保持一致。
3. **Evaluation Runner**：步骤 4 交付后，fine-tune 模型必须能被步骤 13 纳入独立评测目标。
4. **PyRIT / Red Teaming**：步骤 4 交付后，fine-tune 模型必须能被步骤 15 作为独立目标测试，而不是复用原生模型结果。
5. **Dashboard / Metrics**：步骤 4 的 target 必须能被后续 Evaluation Coverage、Safety Failure Rate、Model Identity Capture、Red Teaming Coverage 等指标单独统计。
6. **步骤 3 原生模型**：步骤 4 默认以步骤 3 的 `AIGovernTrustworthyDemoNativeModel` 为对照基线，并复用它来生成步骤 4 所需的 5000 个问答对；但 fine-tune base model 改用 `gpt-4.1`，不再假设 native deployment 本身可直接 fine-tune。

### 5.9 后续复用需求

步骤 4 交付后，至少要支持以下后续动作：

1. 被步骤 9 的 Tier 1 Consumer App 通过 APIM 调用。
2. 被步骤 10 的 Tier 2 间接使用链路纳入追踪。
3. 被步骤 13 的 Evaluation Runner 纳入 `foundry_finetune_model` 目标清单。
4. 被步骤 15 的 PyRIT / red teaming 以统一 target 身份纳入测试。
5. 被 Domain 4 L1/L2 报表按独立 target type 展示，不与原生模型或其他对象合并。

---

## 6. 明确不属于步骤 4 的内容

以下事项不应混入步骤 4：

1. 为了“提高业务效果”而无限扩充训练集、反复调参或做多轮实验比较。
2. 在训练集中混入故意错误样本来替代后续独立的 evaluation / red teaming 数据集。
3. VM Hugging Face 模型部署与 OpenAI-compatible API（属于步骤 5/6）。
4. Foundry 自定义 Agent 或 Copilot Studio Agent 的创建（属于步骤 7/8）。
5. Consumer App 的 UI、登录流和业务页面（属于步骤 9/10）。
6. 为了“先跑通”而长期绕开 APIM、App Insights、shared-observability、target registry 的临时方案。
7. 引入未批准的新训练数据源、额外模型服务资源、或平行环境变量命名体系。

---

## 7. 步骤 4 的交付物要求

步骤 4 完成时，至少应形成以下产物：

| 产物 | 要求 |
|---|---|
| fine-tune 需求事实记录 | 明确为什么测试、训练数据格式、样本数量、AI Governance 主题、PDF -> Q&A 生成策略和 base model 选择依据 |
| 训练事实记录 | 明确 training file、job id、base model、输出模型、deployment 名称 |
| 调用验证入口 | 直连 fine-tuned deployment 的烟测脚本或命令可用 |
| APIM 接入 | `/finetune-model` API 与 MSI 认证方案落地 |
| target registry 一致性 | `targets.json` 中 fine-tune 条目与真实结果一致 |
| tracing / evidence 设计闭环 | 明确适用时的 Foundry tracing、APIM tracing、AOAI 平台诊断、shared-observability 的关联方式 |
| Q&A 归档副本 | `docs/finetune-qa-archive/` 下存在与训练文件对应的一份归档副本 |
| 后续步骤复用基线 | evaluation、red teaming、Tier 1/2、dashboard 可直接把该 target 当作既有对象使用 |

---

## 8. 验收口径（需求视角）

从需求角度看，步骤 4 至少满足以下条件，才可视为“准备进入实施完成状态”：

1. 已清楚记录“为什么要测试 fine-tune 模型”，并且理由与 Domain 4 指标和治理边界直接相关。
2. 训练数据格式、来源、条数和 PDF -> Q&A 生成策略明确，且不依赖临时口头约定。
3. 已有一个经过确认的 fine-tune job 与 fine-tuned deployment 设计身份，并且名称、基础模型（`gpt-4.1`）、endpoint 可被明确记录。
4. APIM `/finetune-model` 被定义为统一治理入口，而不是停留在设计外的直连方式。
5. `foundry_finetune_model` 的 target 身份、字段、registry 条目和后续指标口径一致。
6. 适用时的 Foundry tracing、APIM tracing、AOAI 平台诊断、App Insights 和 Blob evidence 的责任边界清晰，不互相替代。
7. 步骤 9、10、13、15 可以在不重做模型身份设计的前提下直接复用该 target。
8. 已明确：执行路径必须全程自动化、不走 Portal 手工路径，并且中间 Q&A 需同步归档到 `docs/finetune-qa-archive/`。

---

## 8A. 实施前预置条件（只检查，不实施）

在开始任何脚本化实施之前，必须先满足下列条件；若任一条件不满足，应停止，不进入操作阶段。

| 类别 | 必要条件 |
|---|---|
| 既有 AI 资源 | `aigoverntrustworthyfoundry`、`AIGovernTrustworthyAOAI`、`AIGovernTrustworthyDemoNativeModel`、现有 APIM、现有 App Insights 必须已经存在且可查询。 |
| Storage | `.env.local.L4` 中的 `L4_STORAGE_ACCOUNT_NAME`、`L4_STORAGE_CONNECTION_STRING`、`L4_STORAGE_CONTAINER_FINETUNE` 必须已经有效，且指向的 Storage Account / Container 已存在且可写。 |
| 本地设计归档 | 仓库中的 `docs/finetune-qa-archive/` 路径应允许写入，用于保存 `aigoverntrustworthydemo-qa-5000.jsonl` 的归档副本。 |
| 权限 | 当前执行身份或 deploy SPN 必须具备：读取 model catalog、读取/提交 fine-tune job、在既有 AOAI 上管理 deployment、向既有 finetune container 上传文件、配置 APIM API/policy/diagnostics、查询 App Insights / Azure Monitor Logs 的权限。 |
| 网络与 DNS | 当前执行环境必须能够解析并访问既有 APIM gateway 与 AOAI endpoint；APIM 与 AOAI 所在 VNet / DNS 路径需保持可用。 |
| 观测配置 | `APPLICATIONINSIGHTS_CONNECTION_STRING` 必须有效；若脚本运行时需要 `OTEL_SERVICE_NAME`，则只允许在进程级环境变量中注入，不新增新的 `.env.local.L4` 键名。 |
| 资源创建边界 | 当前已确认允许创建：fine-tune container、fine-tune job、fine-tuned deployment。若执行中发现还需创建其他类型云资源，则必须停止并等待用户确认。 |
| 平台可用性 | 当前订阅 / 区域 / 账号组合下，必须至少存在一个对 `fine_tuning.jobs.create` 实际返回成功的 base model；如果 capability catalog 与 create API 结果冲突，应以 create API 实测为准。 |

---

## 9. Draft 自动化步骤（首选）

以下步骤是**draft**，目的是给步骤 4 后续自动化实现提供明确顺序；不代表脚本名已全部存在。

### 9.1 生成训练问答对

1. 读取用户上传的 AI Governance PDF。
2. 将 PDF 文本提取和必要切块作为 Q&A 生成输入。
3. 调用现有 native deployment `AIGovernTrustworthyDemoNativeModel`（`gpt-5.4-nano`）生成 **5000 个高质量问答对**，并尽量覆盖 5 个 PDF 的全部内容。
4. 对生成结果做去重、抽样和最小人工/脚本质检。
5. 将结果整理为 `aigoverntrustworthydemo-qa-5000.jsonl`。
6. 同时将该文件归档到 `docs/finetune-qa-archive/aigoverntrustworthydemo-qa-5000.jsonl`。

### 9.2 上传训练文件并创建 fine-tune job

> **前提**：当前用户已明确允许创建 fine-tune job / deployment；若 9.2 / 9.3 之外还需创建其他类型云资源，则必须暂停。

1. 用 deploy SPN 将 `aigoverntrustworthydemo-qa-5000.jsonl` 上传到 `.env.local.L4` 指定的 `L4_STORAGE_ACCOUNT_NAME / L4_STORAGE_CONTAINER_FINETUNE`。
2. 使用 Azure CLI / REST 提交 fine-tune job。
3. Base model 指定为 **`gpt-4.1`**。
4. 训练参数保持最小化，不额外引入本轮 draft 未设计的复杂调优选项。
5. 记录：
   - job id
   - base model
   - training file name
   - create time

### 9.3 轮询 job 并部署 fine-tuned model

1. 轮询 fine-tune job，直到完成。
2. 读取输出模型标识。
3. 创建 deployment：`AIGovernTrustworthyDemoFineTuneModel`
4. 部署到既有 Foundry account：`aigoverntrustworthyfoundry`
5. 等待 deployment 状态变为 `Succeeded`。

### 9.4 配置 APIM 与 tracing

1. 运行 `setup-finetune-model-api.sh` 或等效自动化脚本，配置 `/finetune-model`。
2. Policy 与 `native-model` 保持一致：
   - APIM MSI 注入 `cognitiveservices.azure.com` token
   - W3C `traceparent`
   - 固定 `api-version`
   - `x-aigov-apim-request-id`
3. API-level diagnostics 与 `native-model` 保持一致：
   - logger = `applicationinsights`
   - sampling = 100%
   - protocol = W3C
   - verbosity = `information`
4. 依旧通过 APIM dependency + AOAI 平台诊断组成平台侧证据链。

### 9.5 最小验证

1. 直连 `AIGovernTrustworthyDemoFineTuneModel` 做烟测，确认非空响应。
2. 经 APIM `/finetune-model/chat/completions` 做烟测，确认非空响应。
3. 更新 `infra/target-registry/targets.json` 的步骤 4 条目。
4. 查询 App Insights / Azure Monitor Logs，确认：
   - APIM dependency 记录存在
   - AOAI 平台诊断日志可见 deployment / model / version
   - 若调用方使用 shared-observability，则 Blob evidence 和薄索引事件存在

---

## 10. 停止点与人工确认点

出现以下任一情况时，Copilot 应停止自动推进并请求用户确认：

1. 当前 region / subscription / API 不支持任何已测试候选模型的 fine-tune create，或配额 / 平台开关未开放。
2. 当前自动化路径无法稳定完成 PDF 文本提取或 5000 Q&A 生成，需要先调整数据预处理方案。
3. 需要新增本设计未批准的 Azure 资源、资源组、网络路径或额外服务。
4. 需要修改 `.env.local.L4` 中现有变量名或新增平行命名。
5. 需要偏离 `disableLocalAuth = true`、改用 API key 或绕开 Entra 认证。
6. 需要长期绕过 APIM 才能完成调用。
7. 需要扩大训练数据范围、改变 5000 条训练集约束、或引入未批准数据源。
8. `.env.local.L4` 所指向的 Storage / APIM / AOAI / App Insights 任何一个既有资源缺失、不可写或权限不足。

---

## 11. 当前结论

步骤 4 的需求已经可以明确为：

- **交付一个被 Domain 4 正式纳管的 fine-tuned 文本模型 target**
- **该 target 同时满足训练事实、部署事实、调用、APIM 代理、tracing、证据、registry 与后续复用要求**
- **它的存在价值不是单纯提升效果，而是证明 Domain 4 能治理“训练前后的两个 Azure 托管模型对象”**

因此，步骤 4 的下一阶段不应从“先试着提交一个 fine-tune job”开始，而应从**测试目的、训练语料生成方式、自动化可行性、target identity** 这四个点同步收敛。

在这四个点里，当前已经明确的是：

- fine-tune 的测试目的：验证模型调优后的治理可追溯性和独立 target 治理能力
- Q&A generation model：`gpt-5.4-nano`
- fine-tune base model：`gpt-4.1`
- 训练数据边界：5000 条 AI Governance Q&A，由 5 个已上传 PDF 生成后整理为 JSONL
- 训练文件上传必须复用 `.env.local.L4` 中既有 storage 变量
- 中间 Q&A 需在 `docs/finetune-qa-archive/` 下保留归档副本
- target identity：`foundry_finetune_model` / `AIGovernTrustworthyDemoFineTuneModel`
- APIM 统一入口：`/finetune-model`
- 执行方式：全程 AI 自动化，不允许依赖 Portal 手工操作；仅允许执行已批准的 3 个创建动作，其他资源创建仍需用户确认
- 当前实际运行进度：Q&A / JSONL / Storage 上传已完成；fine-tune job `ftjob-ae456ec3dc4d468b87ecb8512ad33f86` 已成功完成；fine-tuned model 已部署为 `AIGovernTrustworthyDemoFineTuneModel`；直连与 APIM `/finetune-model` 烟测均已通过

当前尚未最终锁定的是：

- App Insights / Azure Monitor Logs 中本次最终烟测调用的日志检索截图或查询结果
