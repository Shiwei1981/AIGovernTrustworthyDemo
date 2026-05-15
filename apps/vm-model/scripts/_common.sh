#!/usr/bin/env bash
set -euo pipefail

vm_model_repo_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd
}

vm_model_load_env() {
  local env_file="$1"
  eval "$(
    python3 - "$env_file" <<'PY'
import shlex
import sys

env_file = sys.argv[1]
needed = {
    "AZ_DEPLOY_TENANT_ID",
    "AZ_DEPLOY_CLIENT_ID",
    "AZ_DEPLOY_CLIENT_SECRET",
    "AZ_SUBSCRIPTION_ID",
    "APPLICATIONINSIGHTS_CONNECTION_STRING",
    "L4_OTEL_SERVICE_NAME_VM_MODEL",
    "L4_VM_HF_TOKEN",
    "L4_VM_MODEL_NAME",
    "L4_VM_NAME",
}

with open(env_file, "r", encoding="utf-8") as handle:
    for raw_line in handle:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in needed:
            continue
        value = value.strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        print(f"export {key}={shlex.quote(value)}")
PY
  )"
}

vm_model_az_login() {
  az login --service-principal \
    --tenant "$AZ_DEPLOY_TENANT_ID" \
    --username "$AZ_DEPLOY_CLIENT_ID" \
    --password "$AZ_DEPLOY_CLIENT_SECRET" \
    --output none
  az account set --subscription "$AZ_SUBSCRIPTION_ID"
}
