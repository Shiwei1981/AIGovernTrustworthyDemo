#!/usr/bin/env bash
# deploy-tier-apps.sh — Build and deploy Tier 1 + Tier 2 apps to Azure Web App.
# Usage: bash infra/azure/deploy-tier-apps.sh
# Reads all values from .env.local.L4 at the repo root.

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="$REPO_ROOT/.env.local.L4"

# ── Load env ──────────────────────────────────────────────────────────────────
load_env() {
  while IFS= read -r raw; do
    line="${raw%%#*}"
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ -z "$line" || "$line" != *=* ]] && continue
    name="${line%%=*}"
    value="${line#*=}"
    value="${value#\"}" ; value="${value%\"}"
    value="${value#\'}" ; value="${value%\'}"
    export "$name=$value"
  done < "$ENV_FILE"
}
load_env

# ── Required vars ─────────────────────────────────────────────────────────────
: "${AZ_DEPLOY_TENANT_ID:?}"
: "${AZ_DEPLOY_CLIENT_ID:?}"
: "${AZ_DEPLOY_CLIENT_SECRET:?}"
: "${AZ_SUBSCRIPTION_ID:?}"
: "${L4_RESOURCE_GROUP:?}"
: "${L4_RAG_APP_NAME:?}"
: "${L4_TIER1_APP_NAME:?}"
: "${L4_TIER2_APP_NAME:?}"
: "${L4_OBSERVABILITY_PACKAGE_NAME:?}"

# ── Azure login ───────────────────────────────────────────────────────────────
echo "==> Logging in as deploy SPN..."
az login --service-principal \
  --tenant "$AZ_DEPLOY_TENANT_ID" \
  --username "$AZ_DEPLOY_CLIENT_ID" \
  --password "$AZ_DEPLOY_CLIENT_SECRET" \
  --output none
az account set --subscription "$AZ_SUBSCRIPTION_ID"

RG="$L4_RESOURCE_GROUP"

ensure_private_apim_network() {
  local rag_subnet_id rag_vnet_id current_subnet app
  rag_subnet_id="$(az webapp vnet-integration list \
    --name "$L4_RAG_APP_NAME" \
    --resource-group "$RG" \
    --query '[0].vnetResourceId' \
    -o tsv)"
  if [[ -z "$rag_subnet_id" ]]; then
    echo "ERROR: Could not resolve VNet integration from $L4_RAG_APP_NAME."
    exit 1
  fi
  rag_vnet_id="${rag_subnet_id%/subnets/*}"

  for app in "$L4_TIER1_APP_NAME" "$L4_TIER2_APP_NAME"; do
    current_subnet="$(az webapp vnet-integration list \
      --name "$app" \
      --resource-group "$RG" \
      --query '[0].vnetResourceId' \
      -o tsv 2>/dev/null || true)"
    if [[ "$current_subnet" != "$rag_subnet_id" ]]; then
      echo "==> [$app] Attaching to VNet subnet used by $L4_RAG_APP_NAME ..."
      az webapp vnet-integration add \
        --name "$app" \
        --resource-group "$RG" \
        --vnet "$rag_vnet_id" \
        --subnet "$rag_subnet_id" \
        --skip-delegation-check \
        --output none
    fi
  done
}

# ── Build deployment zip ──────────────────────────────────────────────────────
DEPLOY_DIR="$(mktemp -d)"
echo "==> Building deployment package in $DEPLOY_DIR ..."

# Shared source files (must live under apps/ so REPO_ROOT/apps/... imports work)
mkdir -p "$DEPLOY_DIR/apps/tier1-app" "$DEPLOY_DIR/apps/tier2-app"
cp "$REPO_ROOT/apps/consumer_common.py"     "$DEPLOY_DIR/apps/consumer_common.py"
cp "$REPO_ROOT/apps/trace_chain_backend.py" "$DEPLOY_DIR/apps/trace_chain_backend.py"
cp "$REPO_ROOT/apps/tier1-app/app.py"           "$DEPLOY_DIR/apps/tier1-app/app.py"
cp "$REPO_ROOT/apps/tier1-app/mock-tier1-ui.html" "$DEPLOY_DIR/apps/tier1-app/mock-tier1-ui.html"
cp "$REPO_ROOT/apps/tier2-app/app.py"           "$DEPLOY_DIR/apps/tier2-app/app.py"
cp "$REPO_ROOT/apps/tier2-app/mock-tier2-ui.html" "$DEPLOY_DIR/apps/tier2-app/mock-tier2-ui.html"

# Shared-observability package (bundled — no editable install on Web App)
mkdir -p "$DEPLOY_DIR/packages"
cp -r "$REPO_ROOT/packages/shared-observability" "$DEPLOY_DIR/packages/"

# Target registry (read at startup)
mkdir -p "$DEPLOY_DIR/infra/target-registry"
cp "$REPO_ROOT/infra/target-registry/targets.json" "$DEPLOY_DIR/infra/target-registry/targets.json"

# Root requirements.txt — used by startup script (Oryx build disabled)
cat > "$DEPLOY_DIR/requirements.txt" <<'EOF'
fastapi
uvicorn[standard]
gunicorn
EOF

# Tell App Service to skip Oryx build
cat > "$DEPLOY_DIR/.deployment" <<'EOF'
[config]
SCM_DO_BUILD_DURING_DEPLOYMENT=false
EOF

# Startup scripts — use python3.12 explicitly (present in PYTHON:3.12 runtime container)
# pip install runs at container startup since Oryx build is disabled
cat > "$DEPLOY_DIR/startup_tier1.sh" <<'EOF'
#!/bin/bash
set -e
export PATH="/usr/local/bin:$HOME/.local/bin:$PATH"
cd /home/site/wwwroot
python3.12 -m pip install -q --user -r requirements.txt
python3.12 -m pip install -q --user packages/shared-observability
cd apps/tier1-app
exec python3.12 -m gunicorn --workers 2 --worker-class uvicorn.workers.UvicornWorker \
  --bind "0.0.0.0:${PORT:-8000}" --timeout 120 app:app
EOF
chmod +x "$DEPLOY_DIR/startup_tier1.sh"

cat > "$DEPLOY_DIR/startup_tier2.sh" <<'EOF'
#!/bin/bash
set -e
export PATH="/usr/local/bin:$HOME/.local/bin:$PATH"
cd /home/site/wwwroot
python3.12 -m pip install -q --user -r requirements.txt
python3.12 -m pip install -q --user packages/shared-observability
cd apps/tier2-app
exec python3.12 -m gunicorn --workers 2 --worker-class uvicorn.workers.UvicornWorker \
  --bind "0.0.0.0:${PORT:-8000}" --timeout 120 app:app
EOF
chmod +x "$DEPLOY_DIR/startup_tier2.sh"

ZIP_PATH="$(mktemp --suffix=.zip)"
rm -f "$ZIP_PATH"   # mktemp creates an empty file; zip needs a clean path
(cd "$DEPLOY_DIR" && zip -r "$ZIP_PATH" . -x "*.pyc" -x "*/__pycache__/*" -x "*/.git/*") > /dev/null
echo "==> Zip ready: $ZIP_PATH ($(du -sh "$ZIP_PATH" | cut -f1))"

# ── Common app settings ───────────────────────────────────────────────────────
COMMON_SETTINGS=(
  "APPLICATIONINSIGHTS_CONNECTION_STRING=$APPLICATIONINSIGHTS_CONNECTION_STRING"
  "AZURE_TENANT_ID=$AZURE_TENANT_ID"
  "L4_APIM_GATEWAY_URL=$L4_APIM_GATEWAY_URL"
  "L4_FOUNDRY_AGENT_ID=$L4_FOUNDRY_AGENT_ID"
  "L4_OBSERVABILITY_PACKAGE_NAME=$L4_OBSERVABILITY_PACKAGE_NAME"
  "L4_OBSERVABILITY_BLOB_STORAGE_ACCOUNT_NAME=$L4_OBSERVABILITY_BLOB_STORAGE_ACCOUNT_NAME"
  "L4_OBSERVABILITY_BLOB_CONTAINER=$L4_OBSERVABILITY_BLOB_CONTAINER"
  "L4_OBSERVABILITY_BLOB_PREFIX=$L4_OBSERVABILITY_BLOB_PREFIX"
  "WEBSITE_DNS_SERVER=168.63.129.16"
  "SCM_DO_BUILD_DURING_DEPLOYMENT=false"
  "DISABLE_ORYX_BUILD=true"
  "ENABLE_ORYX_BUILD=false"
  "WEBSITES_ENABLE_APP_SERVICE_STORAGE=true"
)

# ── Switch apps from Docker to Python runtime (pre-deploy once) ───────────────
for APP in "$L4_TIER1_APP_NAME" "$L4_TIER2_APP_NAME"; do
  CURRENT_FX=$(az webapp config show --resource-group "$RG" --name "$APP" \
    --query "linuxFxVersion" -o tsv 2>/dev/null || echo "")
  if [[ "$CURRENT_FX" == DOCKER* ]]; then
    echo "==> [$APP] Switching from Docker to Python:3.12 runtime..."
    az webapp config set --resource-group "$RG" --name "$APP" \
      --linux-fx-version "PYTHON:3.12" --output none
    az webapp config appsettings delete --resource-group "$RG" --name "$APP" \
      --setting-names DOCKER_REGISTRY_SERVER_URL DOCKER_REGISTRY_SERVER_USERNAME \
                      DOCKER_REGISTRY_SERVER_PASSWORD DOCKER_CUSTOM_IMAGE_NAME \
                      WEBSITES_ENABLE_APP_SERVICE_STORAGE \
      --output none 2>/dev/null || true
  fi
done

ensure_private_apim_network

# ── Deploy Tier 1 ─────────────────────────────────────────────────────────────
echo ""
echo "==> [Tier 1] Setting app settings..."
az webapp config appsettings set \
  --resource-group "$RG" --name "$L4_TIER1_APP_NAME" \
  --settings \
    "${COMMON_SETTINGS[@]}" \
    "L4_TIER1_APP_NAME=$L4_TIER1_APP_NAME" \
    "L4_TIER1_APP_URL=$L4_TIER1_APP_URL" \
    "L4_OTEL_SERVICE_NAME_TIER1_APP=$L4_OTEL_SERVICE_NAME_TIER1_APP" \
    "L4_TIER1_APP_CLIENT_ID=$L4_TIER1_APP_CLIENT_ID" \
    "L4_TIER1_APP_CLIENT_SECRET=$L4_TIER1_APP_CLIENT_SECRET" \
    "AZ_RUNTIME_TENANT_ID=$AZURE_TENANT_ID" \
    "AZ_RUNTIME_CLIENT_ID=$L4_TIER1_APP_CLIENT_ID" \
    "AZ_RUNTIME_CLIENT_SECRET=$L4_TIER1_APP_CLIENT_SECRET" \
  --output none

echo "==> [Tier 1] Setting startup command..."
az webapp config set \
  --resource-group "$RG" --name "$L4_TIER1_APP_NAME" \
  --startup-file "/bin/bash /home/site/wwwroot/startup_tier1.sh" \
  --output none

echo "==> [Tier 1] Deploying zip..."
az webapp deploy \
  --resource-group "$RG" --name "$L4_TIER1_APP_NAME" \
  --src-path "$ZIP_PATH" --type zip \
  --output none
echo "==> [Tier 1] Deploy submitted."

# ── Deploy Tier 2 ─────────────────────────────────────────────────────────────
echo ""
echo "==> [Tier 2] Setting app settings..."
az webapp config appsettings set \
  --resource-group "$RG" --name "$L4_TIER2_APP_NAME" \
  --settings \
    "${COMMON_SETTINGS[@]}" \
    "L4_TIER2_APP_NAME=$L4_TIER2_APP_NAME" \
    "L4_TIER2_APP_URL=$L4_TIER2_APP_URL" \
    "L4_OTEL_SERVICE_NAME_TIER2_APP=$L4_OTEL_SERVICE_NAME_TIER2_APP" \
    "L4_TIER2_APP_CLIENT_ID=$L4_TIER2_APP_CLIENT_ID" \
    "L4_TIER2_APP_CLIENT_SECRET=$L4_TIER2_APP_CLIENT_SECRET" \
    "AZ_RUNTIME_TENANT_ID=$AZURE_TENANT_ID" \
    "AZ_RUNTIME_CLIENT_ID=$L4_TIER2_APP_CLIENT_ID" \
    "AZ_RUNTIME_CLIENT_SECRET=$L4_TIER2_APP_CLIENT_SECRET" \
    "L4_TIER1_APP_CLIENT_ID=$L4_TIER1_APP_CLIENT_ID" \
    "L4_TIER1_DOWNSTREAM_BASE_URL=$L4_TIER1_APP_URL" \
  --output none

echo "==> [Tier 2] Setting startup command..."
az webapp config set \
  --resource-group "$RG" --name "$L4_TIER2_APP_NAME" \
  --startup-file "/bin/bash /home/site/wwwroot/startup_tier2.sh" \
  --output none

echo "==> [Tier 2] Deploying zip..."
az webapp deploy \
  --resource-group "$RG" --name "$L4_TIER2_APP_NAME" \
  --src-path "$ZIP_PATH" --type zip \
  --output none
echo "==> [Tier 2] Deploy submitted."

# ── Smoke test ────────────────────────────────────────────────────────────────
echo ""
echo "==> Waiting 30s for apps to start..."
sleep 30

T1_URL="${L4_TIER1_APP_URL%/}"
T2_URL="${L4_TIER2_APP_URL%/}"

echo "==> [Tier 1] Health check: $T1_URL/api/health"
STATUS_T1=$(curl -s -o /dev/null -w "%{http_code}" --max-time 20 "$T1_URL/api/health" || echo "000")
echo "    HTTP $STATUS_T1"

echo "==> [Tier 2] Health check: $T2_URL/api/health"
STATUS_T2=$(curl -s -o /dev/null -w "%{http_code}" --max-time 20 "$T2_URL/api/health" || echo "000")
echo "    HTTP $STATUS_T2"

# ── Cleanup ───────────────────────────────────────────────────────────────────
rm -rf "$DEPLOY_DIR" "$ZIP_PATH"

if [[ "$STATUS_T1" == "200" && "$STATUS_T2" == "200" ]]; then
  echo ""
  echo "✅  Both apps healthy."
  echo "   Tier 1: $T1_URL"
  echo "   Tier 2: $T2_URL"
else
  echo ""
  echo "⚠️  Deploy submitted but health check not yet 200 (T1=$STATUS_T1, T2=$STATUS_T2)."
  echo "    Apps may still be starting. Check:"
  echo "    az webapp log tail --resource-group $RG --name $L4_TIER1_APP_NAME"
  echo "    az webapp log tail --resource-group $RG --name $L4_TIER2_APP_NAME"
  exit 1
fi
