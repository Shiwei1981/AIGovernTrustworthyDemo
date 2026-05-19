#!/usr/bin/env bash
# deploy-step8-tracing-workbook.sh — Deploy the Step 8 tracing workbook to Application Insights.
# Usage:
#   bash infra/monitoring/deploy-step8-tracing-workbook.sh
# Optional overrides:
#   APP_INSIGHTS_NAME=appinsights
#   WORKBOOK_DISPLAY_NAME="AIGovernTrustworthyDemo Step 8 Tracing Showcase"
#   WORKBOOK_ID=<existing-workbook-guid>

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="$REPO_ROOT/.env.local.L4"
TEMPLATE_FILE="$REPO_ROOT/infra/monitoring/deploy-step8-tracing-workbook.template.json"
WORKBOOK_FILE="$REPO_ROOT/infra/monitoring/domain4-step8-tracing.workbook.json"

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

serialize_workbook_json() {
  python3 - "$WORKBOOK_FILE" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as fh:
    payload = json.load(fh)
print(json.dumps(payload, separators=(",", ":")))
PY
}

new_uuid() {
  python3 - <<'PY'
import uuid
print(uuid.uuid4())
PY
}

login_azure() {
  echo "==> Logging in as deploy SPN..."
  if az login --service-principal \
    --tenant "$AZ_DEPLOY_TENANT_ID" \
    --username "$AZ_DEPLOY_CLIENT_ID" \
    --password "$AZ_DEPLOY_CLIENT_SECRET" \
    --output none >/dev/null 2>&1; then
    az account set --subscription "$AZ_SUBSCRIPTION_ID"
    return
  fi

  echo "==> Deploy SPN login unavailable; falling back to current Azure CLI session..."
  if ! az account show --query id -o tsv >/dev/null 2>&1; then
    echo "ERROR: Deploy SPN login failed and there is no active Azure CLI session to reuse."
    exit 1
  fi

  if ! az account set --subscription "$AZ_SUBSCRIPTION_ID"; then
    echo "ERROR: Current Azure CLI session cannot access the configured subscription."
    exit 1
  fi
}

resolve_app_insights() {
  local component_json
  component_json="$(az resource show \
    --resource-group "$RG" \
    --resource-type "Microsoft.Insights/components" \
    --name "$APP_INSIGHTS_NAME" \
    --query "{id:id,resourceGroup:resourceGroup}" \
    -o json 2>/dev/null || true)"

  if [[ -z "$component_json" || "$component_json" == "null" ]]; then
    component_json="$(az resource list \
      --resource-type "Microsoft.Insights/components" \
      --name "$APP_INSIGHTS_NAME" \
      --query "[0].{id:id,resourceGroup:resourceGroup}" \
      -o json)"
  fi

  if [[ -z "$component_json" || "$component_json" == "null" ]]; then
    echo "ERROR: Could not resolve Application Insights resource named $APP_INSIGHTS_NAME."
    exit 1
  fi

  WORKBOOK_SOURCE_ID="$(python3 - <<'PY' "$component_json"
import json
import sys
data = json.loads(sys.argv[1])
print(data.get("id", ""))
PY
)"
  APP_INSIGHTS_RG="$(python3 - <<'PY' "$component_json"
import json
import sys
data = json.loads(sys.argv[1])
print(data.get("resourceGroup", ""))
PY
)"

  if [[ -z "$WORKBOOK_SOURCE_ID" || -z "$APP_INSIGHTS_RG" ]]; then
    echo "ERROR: Resolved Application Insights resource is missing id or resource group."
    exit 1
  fi
}

load_env

: "${AZ_DEPLOY_TENANT_ID:?}"
: "${AZ_DEPLOY_CLIENT_ID:?}"
: "${AZ_DEPLOY_CLIENT_SECRET:?}"
: "${AZ_SUBSCRIPTION_ID:?}"
: "${L4_RESOURCE_GROUP:?}"

RG="${L4_RESOURCE_GROUP}"
APP_INSIGHTS_NAME="${APP_INSIGHTS_NAME:-appinsights}"
WORKBOOK_DISPLAY_NAME="${WORKBOOK_DISPLAY_NAME:-AIGovernTrustworthyDemo Step 8 Tracing Showcase}"

login_azure

echo "==> Resolving Application Insights resource..."
resolve_app_insights

SERIALIZED_DATA="$(serialize_workbook_json)"

EXISTING_WORKBOOK_ID="$(az resource list \
  --resource-group "$APP_INSIGHTS_RG" \
  --resource-type "Microsoft.Insights/workbooks" \
  --query "[?properties.displayName=='$WORKBOOK_DISPLAY_NAME' && properties.sourceId=='$WORKBOOK_SOURCE_ID'].name | [0]" \
  -o tsv)"

WORKBOOK_ID="${WORKBOOK_ID:-${EXISTING_WORKBOOK_ID:-$(new_uuid)}}"

echo "==> Deploying workbook..."
WORKBOOK_RESOURCE_ID="$(az deployment group create \
  --resource-group "$APP_INSIGHTS_RG" \
  --template-file "$TEMPLATE_FILE" \
  --parameters \
    workbookDisplayName="$WORKBOOK_DISPLAY_NAME" \
    workbookSourceId="$WORKBOOK_SOURCE_ID" \
    workbookId="$WORKBOOK_ID" \
    serializedData="$SERIALIZED_DATA" \
  --query properties.outputs.workbookResourceId.value \
  -o tsv)"

echo "==> Workbook deployed."
echo "Display name : $WORKBOOK_DISPLAY_NAME"
echo "Resource id  : $WORKBOOK_RESOURCE_ID"
echo "Open it from : Application Insights -> Workbooks"
