# evaluation-runner

本目录承载 Domain 4 evaluation 的单一应用。

职责边界：

- 组织 evaluation runs 与后台任务状态
- 承载 dashboard 页面与 mock UI
- 直连目标后端，不经 APIM
- 将官方 evaluator 结果写入 Foundry evaluation run
- 将 supplemental sample data 写入 Blob

当前 live implementation：

- T1：RAG / Foundry Agent / Native / Fine-tune / VM
- T2：RAG / Foundry Agent
- T3：RAG / Foundry Agent / Native / Fine-tune / VM
- Live 首页：`/`（自动跳转到 `/dashboard/`）
  - `/dashboard/` / `/dashboard/index.html`：Run Matrix
  - `/dashboard/overview.html`：Overview
  - `/dashboard/quality.html`：T1 Quality
  - `/dashboard/rag-contrast.html`：T2 RAG Contrast
  - `/dashboard/safety.html`：T3 Safety
  - `/dashboard/target-detail.html?target_id=...`：Target Detail
  - 默认会从 Blob latest index + run manifest 恢复上一次 test 状态与结果
  - 点击 `Run` 不跳页
  - 通过 `/api/dashboard/matrix` 每 5 秒刷新状态
- Mock 原型页：默认**不发布**
  - `mock-ui/` 仅用于视觉设计评审
  - Azure Web App 默认不挂载 `/mock-ui`
  - 只有显式设置 `L4_ENABLE_MOCK_UI=true` 时才提供本地原型访问
- 结果页：`/evaluations/{test_run_id}`、`/quality`、`/targets/{target_id}`

恢复链路：

- 不在本机保存 run 状态或结果
- 每次 run 会写入 Blob run manifest：`aigoverntrustworthy/evaluations/ai-governance-baseline/{test_run_id}/run-manifest.json`
- 每个 `target_id × test_item` 会写入 Blob latest index：`aigoverntrustworthy/evaluations/ai-governance-baseline/latest/{target_id}/{test_item}.json`
- manifest 保存 `test_run_id`、`target_id`、`test_item`、`supplemental_blob_path`、Foundry evaluation name、Foundry Studio URL、`oai_eval_run_ids`，用于恢复并关联官方 Foundry evaluation run
- `per-sample.jsonl` 继续保存 supplemental evidence，并补充 `response_id`、`model_name`、`model_version`

可通过以下环境变量将 T1/T2/T3 指向测试 sample JSONL：

- `L4_EVALUATION_T1_DATASET_PATH` / `L4_EVALUATION_T1_DATASET_NAME` / `L4_EVALUATION_T1_DATASET_VERSION`
- `L4_EVALUATION_T2_DATASET_PATH` / `L4_EVALUATION_T2_DATASET_NAME` / `L4_EVALUATION_T2_DATASET_VERSION`
- `L4_EVALUATION_T3_DATASET_PATH` / `L4_EVALUATION_T3_DATASET_NAME` / `L4_EVALUATION_T3_DATASET_VERSION`
