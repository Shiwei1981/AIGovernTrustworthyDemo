#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$REPO_ROOT/.env.local.L4"
PYTHON_BIN="${PYTHON_BIN:-$REPO_ROOT/apps/rag-service/.venv/bin/python}"
JSONL_PATH="${1:-$REPO_ROOT/docs/finetune-qa-archive/aigoverntrustworthydemo-qa-5000.jsonl}"

if [[ ! -f "$JSONL_PATH" ]]; then
  echo "[ERROR] JSONL file not found: $JSONL_PATH" >&2
  exit 1
fi

storage_account="$(awk -F= '/^L4_STORAGE_ACCOUNT_NAME=/{print $2; exit}' "$ENV_FILE")"
storage_container="$(awk -F= '/^L4_STORAGE_CONTAINER_FINETUNE=/{print $2; exit}' "$ENV_FILE")"
training_blob="$(awk -F= '/^L4_FINETUNE_TRAINING_FILE=/{print $2; exit}' "$ENV_FILE")"
base_model="$(awk -F= '/^L4_FINETUNE_BASE_MODEL=/{print $2; exit}' "$ENV_FILE")"

echo "[1/3] Uploading training JSONL to Storage..."
az storage blob upload \
  --account-name "$storage_account" \
  --container-name "$storage_container" \
  --name "${training_blob##*/}" \
  --file "$JSONL_PATH" \
  --auth-mode login \
  --overwrite true \
  --output none

echo "[2/3] Uploading training file to Azure OpenAI fine-tune files endpoint and creating job..."
job_json="$("$PYTHON_BIN" - "$REPO_ROOT" "$JSONL_PATH" "$base_model" <<'PY'
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from azure.identity import AzureCliCredential, get_bearer_token_provider
from openai import AzureOpenAI

repo_root = Path(sys.argv[1])
jsonl_path = Path(sys.argv[2])
base_model = sys.argv[3]

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

with jsonl_path.open("rb") as fh:
    training_file = client.files.create(file=fh, purpose="fine-tune")

job = client.fine_tuning.jobs.create(
    model=base_model,
    training_file=training_file.id,
    suffix="aigovtrustdemo",
    seed=105,
    metadata={
        "project": "AIGovernTrustworthyDemo",
        "target_id": "AIGovernTrustworthyDemoFineTuneModel",
    },
    extra_body={"trainingType": "GlobalStandard"},
)

print(json.dumps({"job_id": job.id, "file_id": training_file.id, "status": job.status}))
PY
)"

echo "$job_json"

echo "[3/3] Writing fine-tune job id into .env.local.L4..."
"$PYTHON_BIN" - "$ENV_FILE" "$job_json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

env_path = Path(sys.argv[1])
payload = json.loads(sys.argv[2])
lines = env_path.read_text().splitlines()
updated = []
for line in lines:
    if line.startswith("L4_FOUNDRY_FINETUNE_JOB_ID="):
        updated.append(f'L4_FOUNDRY_FINETUNE_JOB_ID="{payload["job_id"]}"')
    else:
        updated.append(line)
env_path.write_text("\n".join(updated) + "\n")
PY

echo "[RESULT] Fine-tune job created."
