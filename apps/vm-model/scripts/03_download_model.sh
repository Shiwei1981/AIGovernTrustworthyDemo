#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
vm_model_load_env "$ROOT_DIR/.env.local.L4"

if [[ -z "${L4_VM_HF_TOKEN:-}" ]]; then
  echo "Missing L4_VM_HF_TOKEN in .env.local.L4" >&2
  exit 1
fi

HF_TOKEN_B64="$(printf '%s' "$L4_VM_HF_TOKEN" | base64 -w0)"

vm_model_az_login

read -r -d '' REMOTE_SCRIPT <<REMOTE || true
set -eu
export HF_TOKEN="\$(printf '%s' '$HF_TOKEN_B64' | base64 -d)"
/opt/vm-model/venv/bin/python - <<'PY'
import os
from huggingface_hub import hf_hub_download

path = hf_hub_download(
    repo_id="microsoft/Phi-3-mini-4k-instruct-gguf",
    filename="Phi-3-mini-4k-instruct-q4.gguf",
    local_dir="/opt/models/phi3",
    token=os.environ["HF_TOKEN"],
)
print(path)
PY
ls -lh /opt/models/phi3/Phi-3-mini-4k-instruct-q4.gguf
REMOTE

az vm run-command invoke \
  --resource-group AIGovernTrustworthyRG \
  --name "$L4_VM_NAME" \
  --command-id RunShellScript \
  --scripts "$REMOTE_SCRIPT" \
  --query "value[0].message" \
  --output tsv
