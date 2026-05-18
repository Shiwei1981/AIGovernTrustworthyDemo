#!/usr/bin/env bash
# =============================================================================
# setup-copilot-studio-api.sh
#
# Configures the APIM "copilot-studio" API to proxy requests to the Domain 4
# Copilot Studio Agent through Direct Line.
#
# What this script does:
#   1. Loads the existing Domain 4 environment contract from .env.local.L4
#   2. Creates or updates the secret Named Value for Direct Line
#   3. Creates or updates the /copilot-studio API
#   4. Creates Direct Line conversation / activity operations
#   5. Applies API policy (Named Value auth + trace context)
#   6. Ensures API diagnostics flow to the existing App Insights logger
#   7. Updates targets.json to reflect the APIM-ready state
#
# Prerequisites:
#   - az login has already been performed
#   - Run from the repo root: bash infra/apim/setup-copilot-studio-api.sh
#   - .env.local.L4 contains real values for:
#       L4_COPILOT_STUDIO_DIRECTLINE_SECRET
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env.local.L4"
TARGETS_FILE="${REPO_ROOT}/infra/target-registry/targets.json"

RESOURCE_GROUP="AIGovernTrustworthyRG"
APIM_NAME="AIGovernTrustworthyDemoAPIM"
API_ID="copilot-studio"
API_PATH="copilot-studio"
BACKEND_URL="https://directline.botframework.com/v3/directline"
DIAGNOSTIC_ID="applicationinsights"
NAMED_VALUE_ID="copilot-directline-secret"
APIM_GATEWAY_URL="https://aigoverntrustworthydemoapim.azure-api.net"

get_env_value() {
  local key="$1"
  python3 - "$ENV_FILE" "$key" <<'PYEOF'
import sys

env_path, key = sys.argv[1:3]

try:
  with open(env_path, encoding="utf-8") as handle:
    for raw_line in handle:
      line = raw_line.strip()
      if not line or line.startswith("#") or "=" not in line:
        continue
      name, value = line.split("=", 1)
      if name.strip() != key:
        continue
      value = value.strip()
      if value[:1] in {'"', "'"}:
        quote = value[0]
        end = value.rfind(quote)
        if end > 0:
          value = value[1:end]
      else:
        value = value.split("#", 1)[0].strip()
      print(value)
      break
except FileNotFoundError:
  sys.exit(2)
PYEOF
}

require_value() {
  local name="$1"
  local value="${!name:-}"

  if [[ -z "$value" ]]; then
    echo "[ERROR] Required variable $name is empty."
    exit 1
  fi

  case "$value" in
    "<to-be-created>"|"<to-be-confirmed>"|"<to-be-deployed>")
      echo "[ERROR] Variable $name still contains placeholder value: $value"
      exit 1
      ;;
  esac
}

create_or_update_operation() {
  local operation_id="$1"
  local display_name="$2"
  local method="$3"
  local url_template="$4"
  local description="$5"

  az apim api operation create \
    --resource-group "$RESOURCE_GROUP" \
    --service-name "$APIM_NAME" \
    --api-id "$API_ID" \
    --operation-id "$operation_id" \
    --display-name "$display_name" \
    --method "$method" \
    --url-template "$url_template" \
    --description "$description" \
    --output none 2>/dev/null || \
  az apim api operation update \
    --resource-group "$RESOURCE_GROUP" \
    --service-name "$APIM_NAME" \
    --api-id "$API_ID" \
    --operation-id "$operation_id" \
    --display-name "$display_name" \
    --method "$method" \
    --url-template "$url_template" \
    --output none
}

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[ERROR] Missing $ENV_FILE"
  exit 1
fi

L4_COPILOT_STUDIO_DIRECTLINE_SECRET="$(get_env_value L4_COPILOT_STUDIO_DIRECTLINE_SECRET)"
L4_APIM_GATEWAY_URL="$(get_env_value L4_APIM_GATEWAY_URL)"

require_value L4_COPILOT_STUDIO_DIRECTLINE_SECRET

SUBSCRIPTION_ID="$(az account show --query id -o tsv)"

if ! is_placeholder "${L4_APIM_GATEWAY_URL:-}"; then
  APIM_GATEWAY_URL="$L4_APIM_GATEWAY_URL"
fi

echo "=== APIM Copilot Studio API Setup ==="
echo "APIM:        $APIM_NAME"
echo "API ID:      $API_ID"
echo "Backend URL: $BACKEND_URL"
echo ""

echo "[1/7] Creating or updating Direct Line Named Value..."
NAMED_VALUE_URL="https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.ApiManagement/service/${APIM_NAME}/namedValues/${NAMED_VALUE_ID}?api-version=2022-08-01"
NAMED_VALUE_BODY="$(python3 - <<PYEOF
import json

payload = {
    "properties": {
        "displayName": "copilot-directline-secret",
        "value": "${L4_COPILOT_STUDIO_DIRECTLINE_SECRET}",
        "secret": True,
        "tags": ["domain4", "copilot-studio", "directline"]
    }
}

print(json.dumps(payload))
PYEOF
)"
NAMED_VALUE_FILE="$(mktemp /tmp/copilot-directline-nv-XXXX.json)"
echo "$NAMED_VALUE_BODY" > "$NAMED_VALUE_FILE"
az rest --method put \
  --url "$NAMED_VALUE_URL" \
  --headers "Content-Type=application/json" \
  --body "@$NAMED_VALUE_FILE" \
  --output none 1>/dev/null
rm -f "$NAMED_VALUE_FILE"

echo "[2/7] Creating or updating APIM API '$API_ID'..."
if az apim api show \
     --resource-group "$RESOURCE_GROUP" \
     --service-name "$APIM_NAME" \
     --api-id "$API_ID" \
     --output none 2>/dev/null; then
  az apim api update \
    --resource-group "$RESOURCE_GROUP" \
    --service-name "$APIM_NAME" \
    --api-id "$API_ID" \
    --display-name "Copilot Studio Agent" \
    --path "$API_PATH" \
    --service-url "$BACKEND_URL" \
    --output none
else
  az apim api create \
    --resource-group "$RESOURCE_GROUP" \
    --service-name "$APIM_NAME" \
    --api-id "$API_ID" \
    --display-name "Copilot Studio Agent" \
    --path "$API_PATH" \
    --protocols https \
    --service-url "$BACKEND_URL" \
    --subscription-required false \
    --output none
fi

echo "[3/7] Creating or updating Direct Line operations..."
create_or_update_operation \
  "start-conversation" \
  "Start Conversation" \
  "POST" \
  "/conversations" \
  "Create a new Direct Line conversation for the Copilot Studio Agent."
create_or_update_operation \
  "send-activity" \
  "Send Activity" \
  "POST" \
  "/conversations/{conversationId}/activities" \
  "Send a user activity into an existing Direct Line conversation."
create_or_update_operation \
  "get-activities" \
  "Get Activities" \
  "GET" \
  "/conversations/{conversationId}/activities" \
  "Fetch activities and replies for an existing Direct Line conversation."

echo "[4/7] Applying API policy..."
POLICY_XML='<policies>
  <inbound>
    <base />
    <set-header name="traceparent" exists-action="skip">
      <value>@("00-" + context.RequestId.ToString("N") + "-" + context.RequestId.ToString("N").Substring(16, 16) + "-01")</value>
    </set-header>
    <set-header name="X-Governance-Target-Type" exists-action="override">
      <value>copilot_studio_agent</value>
    </set-header>
    <set-header name="X-Governance-Request-Id" exists-action="override">
      <value>@(context.RequestId.ToString())</value>
    </set-header>
    <set-header name="Authorization" exists-action="override">
      <value>Bearer {{copilot-directline-secret}}</value>
    </set-header>
    <set-backend-service base-url="'"$BACKEND_URL"'" />
  </inbound>
  <backend>
    <base />
  </backend>
  <outbound>
    <base />
    <set-header name="x-aigov-apim-request-id" exists-action="override">
      <value>@(context.RequestId.ToString())</value>
    </set-header>
  </outbound>
  <on-error>
    <base />
    <set-status code="502" reason="Bad Gateway" />
    <set-header name="Content-Type" exists-action="override">
      <value>application/json</value>
    </set-header>
    <set-body>@{
      return new JObject(
        new JProperty("error", context.LastError.Message),
        new JProperty("source", context.LastError.Source),
        new JProperty("apim_request_id", context.RequestId.ToString())
      ).ToString();
    }</set-body>
  </on-error>
</policies>'

POLICY_URL="https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.ApiManagement/service/${APIM_NAME}/apis/${API_ID}/policies/policy?api-version=2022-08-01"
POLICY_BODY="$(python3 -c "import json,sys; print(json.dumps({'properties': {'value': open('/dev/stdin').read(), 'format': 'rawxml'}}))" <<< "$POLICY_XML")"
POLICY_FILE="$(mktemp /tmp/copilot-studio-policy-XXXX.json)"
echo "$POLICY_BODY" > "$POLICY_FILE"
az rest --method put \
  --url "$POLICY_URL" \
  --headers "Content-Type=application/json" \
  --body "@$POLICY_FILE" \
  --output none 1>/dev/null
rm -f "$POLICY_FILE"

echo "[5/7] Ensuring API diagnostics flow to App Insights..."
DIAGNOSTIC_URL="https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.ApiManagement/service/${APIM_NAME}/apis/${API_ID}/diagnostics/${DIAGNOSTIC_ID}?api-version=2022-08-01"
DIAGNOSTIC_BODY="$(python3 - <<PYEOF
import json

payload = {
    "properties": {
        "loggerId": f"/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.ApiManagement/service/${APIM_NAME}/loggers/${DIAGNOSTIC_ID}",
        "alwaysLog": "allErrors",
        "sampling": {"samplingType": "fixed", "percentage": 100.0},
        "httpCorrelationProtocol": "W3C",
        "verbosity": "information",
        "logClientIp": True,
        "frontend": {
            "request": {"dataMasking": {"headers": [{"mode": "Hide", "value": "Authorization"}]}},
            "response": None,
        },
        "backend": {
            "request": {"dataMasking": {"headers": [{"mode": "Hide", "value": "Authorization"}]}},
            "response": None,
        },
    }
}

print(json.dumps(payload))
PYEOF
)"
DIAGNOSTIC_FILE="$(mktemp /tmp/copilot-studio-diagnostic-XXXX.json)"
echo "$DIAGNOSTIC_BODY" > "$DIAGNOSTIC_FILE"
az rest --method put \
  --url "$DIAGNOSTIC_URL" \
  --headers "Content-Type=application/json" \
  --body "@$DIAGNOSTIC_FILE" \
  --output none 1>/dev/null
rm -f "$DIAGNOSTIC_FILE"

echo "[6/7] Updating target registry..."
python3 - <<PYEOF
import json

path = "$TARGETS_FILE"
with open(path) as f:
    data = json.load(f)

for target in data["targets"]:
    if target["target_id"] == "AIGovernTrustworthyDemoCopilotStudioAgent":
        target["endpoint"] = "$APIM_GATEWAY_URL/copilot-studio"
    target["backend_url"] = "$BACKEND_URL"
    target["status"] = "active"
    target["apim_note"] = (
      "VNet Internal — APIM copilot-studio API configured at /copilot-studio. "
      "Direct Line secret is stored as APIM Named Value copilot-directline-secret."
    )
    target["notes"] = (
      "Step 6. APIM /copilot-studio configured to proxy Direct Line conversation/activity APIs. "
      "Direct Line auth is injected by APIM Named Value so callers do not need to hold the secret."
    )
    break

with open(path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PYEOF

echo "[7/7] Completed APIM Copilot Studio API configuration."
echo ""
echo "Test examples:"
echo "  Start conversation:"
echo "    curl -s -X POST ${APIM_GATEWAY_URL}/copilot-studio/conversations -H 'Content-Type: application/json' -d '{}'"
echo ""
echo "  Send activity:"
echo "    curl -s -X POST ${APIM_GATEWAY_URL}/copilot-studio/conversations/<conversation-id>/activities \\\\" 
echo "      -H 'Content-Type: application/json' \\\\" 
echo "      -d '{\"type\": \"message\", \"from\": {\"id\": \"domain4-smoke\"}, \"text\": \"What information is available in the SalesTeamSite file?\"}'"
