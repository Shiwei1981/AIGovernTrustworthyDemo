#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
vm_model_load_env "$ROOT_DIR/.env.local.L4"

vm_model_az_login

read -r -d '' REMOTE_SCRIPT <<'REMOTE' || true
set -eu

echo '== llama-server /health =='
curl -fsS http://127.0.0.1:11435/health
echo
echo '== sidecar /health =='
curl -fsS http://127.0.0.1:11434/health
echo
echo '== chat completions =='
RESPONSE="$(curl -fsS http://127.0.0.1:11434/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"Phi-3-mini-4k-instruct","messages":[{"role":"user","content":"Reply with exactly OK."}],"max_tokens":16,"temperature":0}')"
printf '%s' "$RESPONSE"
echo
echo '== parsed response =='
python3 - "$RESPONSE" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
message = payload["choices"][0]["message"]["content"]
print("id=", payload.get("id"))
print("content=", message[:200])
PY
REMOTE

az vm run-command invoke \
  --resource-group AIGovernTrustworthyRG \
  --name "$L4_VM_NAME" \
  --command-id RunShellScript \
  --scripts "$REMOTE_SCRIPT" \
  --query "value[0].message" \
  --output tsv
