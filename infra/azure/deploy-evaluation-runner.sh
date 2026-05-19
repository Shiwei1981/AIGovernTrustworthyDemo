#!/usr/bin/env bash
# deploy-evaluation-runner.sh — Build evaluation-runner image in ACR and deploy to Azure Web App.
# Usage: bash infra/azure/deploy-evaluation-runner.sh [image-tag]

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="$REPO_ROOT/.env.local.L4"
APP_NAME="AIGovernTrustworthyEvaluationDashboard"
IMAGE_REPO="aigoverntrustworthyevaluationdashboard"
APP_PORT="8010"

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

require_vars() {
  local name
  for name in \
    AZ_DEPLOY_TENANT_ID \
    AZ_DEPLOY_CLIENT_ID \
    AZ_DEPLOY_CLIENT_SECRET \
    AZ_SUBSCRIPTION_ID \
    AZURE_TENANT_ID \
    APPLICATIONINSIGHTS_CONNECTION_STRING \
    PROD_ACR_LOGIN_SERVER \
    L4_RESOURCE_GROUP \
    L4_AI_FOUNDRY_PROJECT_ENDPOINT \
    L4_AOAI_ENDPOINT \
    L4_STORAGE_ACCOUNT_NAME \
    L4_EVALUATION_RUNNER_CLIENT_ID \
    L4_EVALUATION_RUNNER_CLIENT_SECRET \
    L4_FOUNDRY_AGENT_ID \
    L4_FOUNDRY_NATIVE_MODEL_DEPLOYMENT \
    L4_FOUNDRY_FINETUNE_MODEL_DEPLOYMENT \
    L4_FOUNDRY_FINETUNE_MODEL_ENDPOINT
  do
    : "${!name:?Missing required env var: $name}"
  done
}

ensure_vnet_integration() {
  local rag_subnet_id rag_vnet_id current_subnet
  rag_subnet_id="$(az webapp vnet-integration list \
    --resource-group "$L4_RESOURCE_GROUP" \
    --name "$L4_RAG_APP_NAME" \
    --query '[0].vnetResourceId' \
    -o tsv)"
  current_subnet="$(az webapp vnet-integration list \
    --resource-group "$L4_RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --query '[0].vnetResourceId' \
    -o tsv 2>/dev/null || true)"
  if [[ -n "$rag_subnet_id" && "$current_subnet" != "$rag_subnet_id" ]]; then
    rag_vnet_id="${rag_subnet_id%/subnets/*}"
    echo "==> Attaching $APP_NAME to VNet subnet used by $L4_RAG_APP_NAME ..."
    az webapp vnet-integration add \
      --resource-group "$L4_RESOURCE_GROUP" \
      --name "$APP_NAME" \
      --vnet "$rag_vnet_id" \
      --subnet "$rag_subnet_id" \
      --skip-delegation-check \
      --output none
  fi
}

load_env
require_vars

ACR_NAME="${PROD_ACR_LOGIN_SERVER%%.*}"
IMAGE_TAG="${1:-$(date -u +%Y%m%d%H%M%S)-$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo manual)}"
IMAGE_NAME="${PROD_ACR_LOGIN_SERVER}/${IMAGE_REPO}:${IMAGE_TAG}"

echo "==> Logging in as deploy SPN ..."
az login --service-principal \
  --tenant "$AZ_DEPLOY_TENANT_ID" \
  --username "$AZ_DEPLOY_CLIENT_ID" \
  --password "$AZ_DEPLOY_CLIENT_SECRET" \
  --output none
az account set --subscription "$AZ_SUBSCRIPTION_ID"

ensure_vnet_integration

echo "==> Building image locally: $IMAGE_NAME"
docker build \
  -f "$REPO_ROOT/apps/evaluation-runner/Dockerfile" \
  -t "$IMAGE_NAME" \
  "$REPO_ROOT"

echo "==> Logging into ACR ..."
az acr login --name "$ACR_NAME" --output none

echo "==> Pushing image to ACR: $IMAGE_NAME"
docker push "$IMAGE_NAME"

echo "==> Updating app settings ..."
az webapp config appsettings set \
  --resource-group "$L4_RESOURCE_GROUP" \
  --name "$APP_NAME" \
  --settings \
    "APPLICATIONINSIGHTS_CONNECTION_STRING=$APPLICATIONINSIGHTS_CONNECTION_STRING" \
    "AZURE_TENANT_ID=$AZURE_TENANT_ID" \
    "AZ_RUNTIME_TENANT_ID=$AZURE_TENANT_ID" \
    "AZ_RUNTIME_CLIENT_ID=$L4_EVALUATION_RUNNER_CLIENT_ID" \
    "AZ_RUNTIME_CLIENT_SECRET=$L4_EVALUATION_RUNNER_CLIENT_SECRET" \
    "L4_EVALUATION_RUNNER_CLIENT_ID=$L4_EVALUATION_RUNNER_CLIENT_ID" \
    "L4_EVALUATION_RUNNER_CLIENT_SECRET=$L4_EVALUATION_RUNNER_CLIENT_SECRET" \
    "L4_AI_FOUNDRY_PROJECT_ENDPOINT=$L4_AI_FOUNDRY_PROJECT_ENDPOINT" \
    "L4_AOAI_ENDPOINT=$L4_AOAI_ENDPOINT" \
    "L4_AOAI_API_VERSION=${L4_AOAI_API_VERSION:-2025-01-01-preview}" \
    "L4_STORAGE_ACCOUNT_NAME=$L4_STORAGE_ACCOUNT_NAME" \
    "L4_FOUNDRY_AGENT_ID=$L4_FOUNDRY_AGENT_ID" \
    "L4_FOUNDRY_NATIVE_MODEL_DEPLOYMENT=$L4_FOUNDRY_NATIVE_MODEL_DEPLOYMENT" \
    "L4_FOUNDRY_FINETUNE_MODEL_DEPLOYMENT=$L4_FOUNDRY_FINETUNE_MODEL_DEPLOYMENT" \
    "L4_FOUNDRY_FINETUNE_MODEL_ENDPOINT=$L4_FOUNDRY_FINETUNE_MODEL_ENDPOINT" \
    "L4_EVALUATION_T1_DATASET_PATH=/app/docs/evaluation-data/quality_general_sample.jsonl" \
    "L4_EVALUATION_T1_DATASET_NAME=ai-governance-quality-general-sample" \
    "L4_EVALUATION_T1_DATASET_VERSION=1" \
    "L4_EVALUATION_T2_DATASET_PATH=/app/docs/evaluation-data/rag_pdf_groundedness_sample.jsonl" \
    "L4_EVALUATION_T2_DATASET_NAME=ai-governance-rag-pdf-groundedness-sample" \
    "L4_EVALUATION_T2_DATASET_VERSION=1" \
    "L4_EVALUATION_T3_DATASET_PATH=/app/docs/evaluation-data/safety_baseline_sample.jsonl" \
    "L4_EVALUATION_T3_DATASET_NAME=ai-governance-safety-baseline-sample" \
    "L4_EVALUATION_T3_DATASET_VERSION=1" \
    "L4_ENABLE_MOCK_UI=false" \
    "L4_OTEL_SERVICE_NAME_EVALUATION_RUNNER=${L4_OTEL_SERVICE_NAME_EVALUATION_RUNNER:-AIGovernTrustworthyDemo.EvaluationRunner}" \
    "LOG_LEVEL=${LOG_LEVEL:-INFO}" \
    "PORT=$APP_PORT" \
    "WEBSITES_PORT=$APP_PORT" \
    "WEBSITE_DNS_SERVER=168.63.129.16" \
    "WEBSITES_ENABLE_APP_SERVICE_STORAGE=false" \
  --output none

echo "==> Pointing Web App to image ..."
az webapp config set \
  --resource-group "$L4_RESOURCE_GROUP" \
  --name "$APP_NAME" \
  --linux-fx-version "DOCKER|$IMAGE_NAME" \
  --output none

APP_ID="$(az webapp show --resource-group "$L4_RESOURCE_GROUP" --name "$APP_NAME" --query id -o tsv)"
ACR_MI_CLIENT_ID="$(
  az webapp identity show \
    --resource-group "$L4_RESOURCE_GROUP" \
    --name "$APP_NAME" \
    -o json | python3 -c 'import json,sys; data=json.load(sys.stdin); ids=data.get("userAssignedIdentities") or {}; print(next(iter(ids.values())).get("clientId","") if ids else "")'
)"
az resource update \
  --ids "$APP_ID/config/web" \
  --set properties.acrUseManagedIdentityCreds=true properties.acrUserManagedIdentityID="$ACR_MI_CLIENT_ID" \
  --output none

az webapp config appsettings delete \
  --resource-group "$L4_RESOURCE_GROUP" \
  --name "$APP_NAME" \
  --setting-names DOCKER_CUSTOM_IMAGE_NAME \
  --output none 2>/dev/null || true

az webapp log config \
  --resource-group "$L4_RESOURCE_GROUP" \
  --name "$APP_NAME" \
  --docker-container-logging filesystem \
  --level information \
  --output none

echo "==> Restarting Web App ..."
az webapp restart --resource-group "$L4_RESOURCE_GROUP" --name "$APP_NAME" --output none

APP_HOST="$(az webapp show --resource-group "$L4_RESOURCE_GROUP" --name "$APP_NAME" --query defaultHostName -o tsv)"
HEALTH_URL="https://${APP_HOST}/health"

echo "==> Waiting for health endpoint: $HEALTH_URL"
status="000"
for _ in $(seq 1 30); do
  sleep 10
  status="$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 "$HEALTH_URL" || echo "000")"
  if [[ "$status" == "200" ]]; then
    break
  fi
done

if [[ "$status" != "200" ]]; then
  echo "ERROR: Health check failed for $HEALTH_URL (last status=$status)"
  exit 1
fi

echo "✅ Deployed $APP_NAME"
echo "   Image: $IMAGE_NAME"
echo "   Health: $HEALTH_URL"
