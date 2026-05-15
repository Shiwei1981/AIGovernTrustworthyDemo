#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SIDE_CAR_SRC="$ROOT_DIR/apps/vm-model/sidecar.py"
REQUIREMENTS_SRC="$ROOT_DIR/apps/vm-model/requirements.txt"

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
vm_model_load_env "$ROOT_DIR/.env.local.L4"

SIDECAR_B64="$(base64 -w0 "$SIDE_CAR_SRC")"
REQUIREMENTS_B64="$(base64 -w0 "$REQUIREMENTS_SRC")"
APPINSIGHTS_B64="$(printf '%s' "$APPLICATIONINSIGHTS_CONNECTION_STRING" | base64 -w0)"
SERVICE_NAME_B64="$(printf '%s' "$L4_OTEL_SERVICE_NAME_VM_MODEL" | base64 -w0)"
VM_NAME_B64="$(printf '%s' "$L4_VM_NAME" | base64 -w0)"
MODEL_NAME_B64="$(printf '%s' "$L4_VM_MODEL_NAME" | base64 -w0)"

vm_model_az_login

read -r -d '' REMOTE_SCRIPT <<REMOTE || true
set -eu

install -d -m 755 /opt/vm-model/sidecar

printf '%s' '$SIDECAR_B64' | base64 -d > /opt/vm-model/sidecar/sidecar.py
printf '%s' '$REQUIREMENTS_B64' | base64 -d > /opt/vm-model/sidecar/requirements.txt

/opt/vm-model/venv/bin/pip install -r /opt/vm-model/sidecar/requirements.txt

cat > /opt/vm-model/sidecar/sidecar.env <<EOF
APPLICATIONINSIGHTS_CONNECTION_STRING=\$(printf '%s' '$APPINSIGHTS_B64' | base64 -d)
L4_OTEL_SERVICE_NAME_VM_MODEL=\$(printf '%s' '$SERVICE_NAME_B64' | base64 -d)
L4_VM_NAME=\$(printf '%s' '$VM_NAME_B64' | base64 -d)
L4_VM_MODEL_NAME=\$(printf '%s' '$MODEL_NAME_B64' | base64 -d)
L4_VM_MODEL_VERSION=unknown
LLAMA_SERVER_BASE_URL=http://127.0.0.1:11435
LOG_LEVEL=INFO
EOF

cat > /etc/systemd/system/llama-server.service <<'EOF'
[Unit]
Description=llama.cpp server for Domain 4 VM model
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/vm-model/bin/llama-b9159
Environment=LD_LIBRARY_PATH=/opt/vm-model/bin/llama-b9159
ExecStart=/opt/vm-model/bin/llama-b9159/llama-server --model /opt/models/phi3/Phi-3-mini-4k-instruct-q4.gguf --alias Phi-3-mini-4k-instruct --host 127.0.0.1 --port 11435
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/vm-model-sidecar.service <<'EOF'
[Unit]
Description=Domain 4 VM model FastAPI sidecar
After=network-online.target llama-server.service
Requires=llama-server.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/vm-model/sidecar
EnvironmentFile=/opt/vm-model/sidecar/sidecar.env
ExecStart=/opt/vm-model/venv/bin/uvicorn sidecar:app --host 0.0.0.0 --port 11434
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable llama-server.service
systemctl enable vm-model-sidecar.service
systemctl restart llama-server.service
systemctl restart vm-model-sidecar.service
sleep 3
systemctl --no-pager --full status llama-server.service | sed -n '1,20p'
echo '---'
systemctl --no-pager --full status vm-model-sidecar.service | sed -n '1,20p'
REMOTE

az vm run-command invoke \
  --resource-group AIGovernTrustworthyRG \
  --name "$L4_VM_NAME" \
  --command-id RunShellScript \
  --scripts "$REMOTE_SCRIPT" \
  --query "value[0].message" \
  --output tsv
