#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$REPO_ROOT/.env.local.L4"
PYTHON_BIN="${PYTHON_BIN:-$REPO_ROOT/apps/rag-service/.venv/bin/python}"
RESOURCE_GROUP="AIGovernTrustworthyRG"
ACCOUNT_NAME="aigoverntrustworthyfoundry"
DEPLOYMENT_NAME="$(awk -F= '/^L4_FOUNDRY_FINETUNE_MODEL_DEPLOYMENT=/{print $2; exit}' "$ENV_FILE")"
JOB_ID="$(awk -F= '/^L4_FOUNDRY_FINETUNE_JOB_ID=/{print $2; exit}' "$ENV_FILE" | tr -d '"')"

if [[ -z "$JOB_ID" || "$JOB_ID" == "<to-be-created>" ]]; then
  echo "[ERROR] L4_FOUNDRY_FINETUNE_JOB_ID is not set." >&2
  exit 1
fi

echo "[1/3] Polling fine-tune job until completion..."
job_json="$("$PYTHON_BIN" - "$REPO_ROOT" "$JOB_ID" <<'PY'
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from azure.identity import AzureCliCredential, get_bearer_token_provider
from openai import AzureOpenAI

repo_root = Path(sys.argv[1])
job_id = sys.argv[2]

env = repo_root / ".env.local.L4"
for line in env.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, _, value = line.partition("=")
    value = value.strip().strip('"').strip("'")
    if value and value not in ("<to-be-created>", "<to-be-deployed>", "<to-be-configured>"):
        os.environ.setdefault(key.strip(), value)

credential = AzureCliCredential()
token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
client = AzureOpenAI(
    azure_endpoint="https://aigoverntrustworthyfoundry.cognitiveservices.azure.com/",
    azure_ad_token_provider=token_provider,
    api_version="2025-04-01-preview",
)

terminal = {"succeeded", "failed", "cancelled"}
while True:
    job = client.fine_tuning.jobs.retrieve(job_id)
    status = (job.status or "").lower()
    print(f"[INFO] fine-tune job status: {status}", file=sys.stderr)
    if status in terminal:
        if status != "succeeded":
            raise RuntimeError(f"Fine-tune job ended with status={job.status}")
        payload = {
            "job_id": job.id,
            "status": job.status,
            "fine_tuned_model": getattr(job, "fine_tuned_model", ""),
        }
        print(json.dumps(payload))
        break
    time.sleep(60)
PY
)"

echo "$job_json"
fine_tuned_model="$("$PYTHON_BIN" - "$job_json" <<'PY'
import json, sys
print(json.loads(sys.argv[1])["fine_tuned_model"])
PY
)"

if [[ -z "$fine_tuned_model" ]]; then
  echo "[ERROR] Fine-tuned model identifier was empty." >&2
  exit 1
fi

echo "[2/3] Creating AOAI deployment..."
if az cognitiveservices account deployment show -g "$RESOURCE_GROUP" -n "$ACCOUNT_NAME" --deployment-name "$DEPLOYMENT_NAME" --output none 2>/dev/null; then
  echo "    Deployment already exists."
else
  az cognitiveservices account deployment create \
    -g "$RESOURCE_GROUP" \
    -n "$ACCOUNT_NAME" \
    --deployment-name "$DEPLOYMENT_NAME" \
    --model-format OpenAI \
    --model-name "$fine_tuned_model" \
    --model-version "1" \
    --sku-name GlobalStandard \
    --sku-capacity 1 \
    --output none
fi

echo "[3/3] Updating .env.local.L4 and target registry..."
"$PYTHON_BIN" - "$ENV_FILE" "$REPO_ROOT/infra/target-registry/targets.json" "$fine_tuned_model" "$DEPLOYMENT_NAME" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

env_path = Path(sys.argv[1])
targets_path = Path(sys.argv[2])
fine_tuned_model = sys.argv[3]
deployment_name = sys.argv[4]
endpoint = (
    f"https://aigoverntrustworthyfoundry.cognitiveservices.azure.com/openai/deployments/"
    f"{deployment_name}/chat/completions?api-version=2025-01-01-preview"
)

lines = env_path.read_text().splitlines()
updated_lines = []
for line in lines:
    if line.startswith("L4_FOUNDRY_FINETUNE_MODEL_ENDPOINT="):
        updated_lines.append(f'L4_FOUNDRY_FINETUNE_MODEL_ENDPOINT="{endpoint}"')
    else:
        updated_lines.append(line)
env_path.write_text("\n".join(updated_lines) + "\n")

data = json.loads(targets_path.read_text())
for target in data["targets"]:
    if target["target_id"] == "AIGovernTrustworthyDemoFineTuneModel":
        target["model_name"] = fine_tuned_model
        target["model_version"] = "1"
        target["endpoint"] = endpoint
        target["status"] = "active"
        target["notes"] = (
            f"Step 4. Fine-tune job created and deployment {deployment_name} provisioned. "
            f"Base model gpt-4.1; platform fine-tuned model id: {fine_tuned_model}."
        )
targets_path.write_text(json.dumps(data, indent=2) + "\n")
PY

echo "[RESULT] Fine-tuned deployment is ready."
