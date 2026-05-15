#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
vm_model_load_env "$ROOT_DIR/.env.local.L4"

vm_model_az_login

read -r -d '' REMOTE_SCRIPT <<'REMOTE' || true
set -eu
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y curl ca-certificates tar python3 python3-venv python3-pip

install -d -m 755 /opt/models/phi3
install -d -m 755 /opt/vm-model/bin
install -d -m 755 /opt/vm-model/sidecar
install -d -m 755 /var/log/vm-model

python3 -m venv /opt/vm-model/venv
/opt/vm-model/venv/bin/pip install --upgrade pip
/opt/vm-model/venv/bin/pip install "huggingface-hub>=0.32.0"

cd /tmp
curl -fsSL -o llama-b9159-bin-ubuntu-x64.tar.gz \
  https://github.com/ggerganov/llama.cpp/releases/download/b9159/llama-b9159-bin-ubuntu-x64.tar.gz
rm -rf /opt/vm-model/bin/llama-b9159
tar -xzf llama-b9159-bin-ubuntu-x64.tar.gz
mv llama-b9159 /opt/vm-model/bin/
test -x /opt/vm-model/bin/llama-b9159/llama-server
ls -l /opt/vm-model/bin/llama-b9159/llama-server
REMOTE

az vm run-command invoke \
  --resource-group AIGovernTrustworthyRG \
  --name "$L4_VM_NAME" \
  --command-id RunShellScript \
  --scripts "$REMOTE_SCRIPT" \
  --query "value[0].message" \
  --output tsv
