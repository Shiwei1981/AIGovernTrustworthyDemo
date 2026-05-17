#!/usr/bin/env bash
# =============================================================================
# setup-foundry-agent-api.sh
#
# Configures the APIM "foundry-agent" API to proxy requests to the Domain 4
# Azure AI Foundry custom Agent.
#
# What this script does:
#   1. Loads the existing Domain 4 environment contract from .env.local.L4
#   2. Creates or updates the /foundry-agent API
#   3. Creates assistant / thread / message / run operations used by Agent callers
#   4. Applies API policy (APIM MSI auth + api-version + trace context)
#   5. Ensures API diagnostics flow to the existing App Insights logger
#   6. Updates targets.json to reflect the APIM-ready state
#
# Important boundary:
#   - This script does NOT create or modify Foundry Project RBAC because the
#     exact data-plane role depends on how the existing project is authorized.
#   - Per current design, APIM MSI access to the Foundry Project is a
#     precondition that should already be satisfied before this script runs.
#
# Prerequisites:
#   - az login has already been performed
#   - Run from the repo root: bash infra/apim/setup-foundry-agent-api.sh
#   - .env.local.L4 contains real values for:
#       L4_AI_FOUNDRY_PROJECT_NAME
#       L4_AI_FOUNDRY_PROJECT_ENDPOINT
#       L4_FOUNDRY_AGENT_ID
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env.local.L4"
TARGETS_FILE="${REPO_ROOT}/infra/target-registry/targets.json"

RESOURCE_GROUP="AIGovernTrustworthyRG"
APIM_NAME="AIGovernTrustworthyDemoAPIM"
API_ID="foundry-agent"
API_PATH="foundry-agent"
API_VERSION="v1"
DIAGNOSTIC_ID="applicationinsights"
APIM_GATEWAY_URL="https://aigoverntrustworthydemoapim.azure-api.net"
DEFAULT_FOUNDRY_PROJECT_ENDPOINT="https://aigoverntrustworthyfoundry.services.ai.azure.com/api/projects/AIGovernTrustworthyRAGProject"

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

is_placeholder() {
  local value="${1:-}"
  [[ -z "$value" || "$value" == "<to-be-created>" || "$value" == "<to-be-confirmed>" || "$value" == "<to-be-deployed>" ]]
}

create_or_update_operation() {
  local operation_id="$1"
  local display_name="$2"
  local method="$3"
  local url_template="$4"
  local description="$5"
  local template_parameters=("${@:6}")

  if az apim api operation show \
       --resource-group "$RESOURCE_GROUP" \
       --service-name "$APIM_NAME" \
       --api-id "$API_ID" \
       --operation-id "$operation_id" \
       --output none 2>/dev/null; then
    az apim api operation update \
      --resource-group "$RESOURCE_GROUP" \
      --service-name "$APIM_NAME" \
      --api-id "$API_ID" \
      --operation-id "$operation_id" \
      --display-name "$display_name" \
      --method "$method" \
      --url-template "$url_template" \
      --output none
  else
    az apim api operation create \
      --resource-group "$RESOURCE_GROUP" \
      --service-name "$APIM_NAME" \
      --api-id "$API_ID" \
      --operation-id "$operation_id" \
      --display-name "$display_name" \
      --method "$method" \
      --url-template "$url_template" \
      --description "$description" \
      "${template_parameters[@]}" \
      --output none
  fi
}

resolve_foundry_service_url() {
  local project_name="$1"
  local project_endpoint="$3"
  local override_url="${2:-}"

  if ! is_placeholder "$override_url"; then
    printf '%s' "${override_url%/}"
    return
  fi

  if [[ "$project_endpoint" == https://*.services.ai.azure.com/api/projects/* ]]; then
    printf '%s' "${project_endpoint%/}"
    return
  fi

  if [[ "$project_name" == "AIGovernTrustworthyRAGProject" ]]; then
    printf '%s' "$DEFAULT_FOUNDRY_PROJECT_ENDPOINT"
    return
  fi

  echo "[ERROR] Foundry Agent APIM requires the services.ai project endpoint, not the old AzureML workspace endpoint."
  echo "        Set L4_AI_FOUNDRY_PROJECT_NAME=AIGovernTrustworthyRAGProject and"
  echo "        L4_AI_FOUNDRY_PROJECT_ENDPOINT=$DEFAULT_FOUNDRY_PROJECT_ENDPOINT"
  exit 1
}

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[ERROR] Missing $ENV_FILE"
  exit 1
fi

L4_AI_FOUNDRY_PROJECT_NAME="$(get_env_value L4_AI_FOUNDRY_PROJECT_NAME)"
L4_AI_FOUNDRY_PROJECT_ENDPOINT="$(get_env_value L4_AI_FOUNDRY_PROJECT_ENDPOINT)"
L4_FOUNDRY_AGENT_ID="$(get_env_value L4_FOUNDRY_AGENT_ID)"
L4_APIM_GATEWAY_URL="$(get_env_value L4_APIM_GATEWAY_URL)"
L4_FOUNDRY_AGENT_API_BASE_URL="$(get_env_value L4_FOUNDRY_AGENT_API_BASE_URL)"

require_value L4_AI_FOUNDRY_PROJECT_NAME
require_value L4_AI_FOUNDRY_PROJECT_ENDPOINT
require_value L4_FOUNDRY_AGENT_ID

SUBSCRIPTION_ID="$(az account show --query id -o tsv)"
APIM_PRINCIPAL_ID="$(az apim show --resource-group "$RESOURCE_GROUP" --name "$APIM_NAME" --query identity.principalId -o tsv)"
FOUNDRY_SERVICE_URL="$(resolve_foundry_service_url "$L4_AI_FOUNDRY_PROJECT_NAME" "${L4_FOUNDRY_AGENT_API_BASE_URL:-}" "$L4_AI_FOUNDRY_PROJECT_ENDPOINT")"

if ! is_placeholder "${L4_APIM_GATEWAY_URL:-}"; then
  APIM_GATEWAY_URL="$L4_APIM_GATEWAY_URL"
fi

echo "=== APIM Foundry Agent API Setup ==="
echo "APIM:        $APIM_NAME"
echo "API ID:      $API_ID"
echo "Agent ID:    $L4_FOUNDRY_AGENT_ID"
echo "Project:     $L4_AI_FOUNDRY_PROJECT_NAME"
echo "Backend URL: $FOUNDRY_SERVICE_URL"
echo "APIM MSI:    $APIM_PRINCIPAL_ID"
echo ""

echo "[1/6] Validating Foundry access precondition..."
echo "    APIM MSI project/data-plane RBAC is not changed by this script."
echo "    Current design assumes AIGovernTrustworthyRAGProject already authorizes APIM MSI."

echo "[2/6] Creating or updating APIM API '$API_ID'..."
if az apim api show \
     --resource-group "$RESOURCE_GROUP" \
     --service-name "$APIM_NAME" \
     --api-id "$API_ID" \
     --output none 2>/dev/null; then
  az apim api update \
    --resource-group "$RESOURCE_GROUP" \
    --service-name "$APIM_NAME" \
    --api-id "$API_ID" \
    --display-name "Foundry Custom Agent" \
    --path "$API_PATH" \
    --service-url "$FOUNDRY_SERVICE_URL" \
    --output none
else
  az apim api create \
    --resource-group "$RESOURCE_GROUP" \
    --service-name "$APIM_NAME" \
    --api-id "$API_ID" \
    --display-name "Foundry Custom Agent" \
    --path "$API_PATH" \
    --protocols https \
    --service-url "$FOUNDRY_SERVICE_URL" \
    --subscription-required false \
    --output none
fi

echo "[3/6] Creating or updating Agent operations..."
create_or_update_operation \
  "list-assistants" \
  "List Assistants" \
  "GET" \
  "/assistants" \
  "List Foundry assistant objects in the project."
create_or_update_operation \
  "get-assistant" \
  "Get Assistant" \
  "GET" \
  "/assistants/{assistantId}" \
  "Fetch the configured Foundry assistant metadata." \
  --template-parameters name=assistantId type=string required=true
create_or_update_operation \
  "threads" \
  "Create Thread" \
  "POST" \
  "/threads" \
  "Create a new Foundry Agent thread."
create_or_update_operation \
  "create-and-run" \
  "Create And Run" \
  "POST" \
  "/threads/runs" \
  "Create a thread and immediately start a run. Caller supplies assistant_id in the request body if this API shape is used."
create_or_update_operation \
  "add-message" \
  "Add Message" \
  "POST" \
  "/threads/{threadId}/messages" \
  "Add a user or tool message to an existing Foundry Agent thread." \
  --template-parameters name=threadId type=string required=true
create_or_update_operation \
  "create-run" \
  "Create Run" \
  "POST" \
  "/threads/{threadId}/runs" \
  "Start an Agent run for an existing thread. Caller supplies assistant_id in the request body." \
  --template-parameters name=threadId type=string required=true
create_or_update_operation \
  "get-run" \
  "Get Run" \
  "GET" \
  "/threads/{threadId}/runs/{runId}" \
  "Fetch Foundry Agent run status and output metadata." \
  --template-parameters name=threadId type=string required=true \
  --template-parameters name=runId type=string required=true
create_or_update_operation \
  "list-messages" \
  "List Messages" \
  "GET" \
  "/threads/{threadId}/messages" \
  "List messages for an existing Foundry Agent thread." \
  --template-parameters name=threadId type=string required=true

echo "[4/6] Applying API policy..."
POLICY_XML='<policies>
  <inbound>
    <base />
    <set-header name="traceparent" exists-action="skip">
      <value>@("00-" + context.RequestId.ToString("N") + "-" + context.RequestId.ToString("N").Substring(16, 16) + "-01")</value>
    </set-header>
    <set-header name="X-Governance-Target-Type" exists-action="override">
      <value>foundry_agent</value>
    </set-header>
    <set-header name="X-Governance-Request-Id" exists-action="override">
      <value>@(context.RequestId.ToString())</value>
    </set-header>
    <authentication-managed-identity
      resource="https://ai.azure.com"
      output-token-variable-name="msi-token" />
    <set-header name="Authorization" exists-action="override">
      <value>@("Bearer " + (string)context.Variables["msi-token"])</value>
    </set-header>
    <set-query-parameter name="api-version" exists-action="override">
      <value>'"$API_VERSION"'</value>
    </set-query-parameter>
    <set-backend-service base-url="'"$FOUNDRY_SERVICE_URL"'" />
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
POLICY_FILE="$(mktemp /tmp/foundry-agent-policy-XXXX.json)"
echo "$POLICY_BODY" > "$POLICY_FILE"
az rest --method put \
  --url "$POLICY_URL" \
  --headers "Content-Type=application/json" \
  --body "@$POLICY_FILE" \
  --output none 1>/dev/null
rm -f "$POLICY_FILE"

echo "[5/6] Ensuring API diagnostics flow to App Insights..."
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
            "request": {"dataMasking": {"queryParams": [{"mode": "Hide", "value": "*"}]}},
            "response": None,
        },
        "backend": {
            "request": {"dataMasking": {"queryParams": [{"mode": "Hide", "value": "*"}]}},
            "response": None,
        },
    }
}

print(json.dumps(payload))
PYEOF
)"
DIAGNOSTIC_FILE="$(mktemp /tmp/foundry-agent-diagnostic-XXXX.json)"
echo "$DIAGNOSTIC_BODY" > "$DIAGNOSTIC_FILE"
az rest --method put \
  --url "$DIAGNOSTIC_URL" \
  --headers "Content-Type=application/json" \
  --body "@$DIAGNOSTIC_FILE" \
  --output none 1>/dev/null
rm -f "$DIAGNOSTIC_FILE"

echo "[6/6] Updating target registry..."
python3 - <<PYEOF
import json

path = "$TARGETS_FILE"
with open(path) as f:
    data = json.load(f)

for target in data["targets"]:
    if target["target_id"] == "AIGovernTrustworthyDemoFoundryAgent":
        target["agent_id"] = "$L4_FOUNDRY_AGENT_ID"
        target["agent_name"] = "AIGovernTrustworthyDemoFoundryAgent"
        target["model_name"] = "gpt-5.4-mini"
        target["model_version"] = "2026-03-17"
        target["endpoint"] = "$APIM_GATEWAY_URL/foundry-agent"
        target["backend_url"] = "$FOUNDRY_SERVICE_URL"
        target["status"] = "active"
        target["apim_note"] = (
            "VNet Internal — APIM foundry-agent API configured at /foundry-agent. "
            "APIM uses MSI to request https://ai.azure.com token and proxies to the "
            "AIGovernTrustworthyRAGProject assistant/thread API."
        )
        target["notes"] = (
            "Step 6. Foundry Custom Agent verified as assistant "
            "asst_qPEQxZ6Gc894gcxQjaIOkdF6 / AIGovernTrustworthyDemoFoundryAgent. "
            "Legacy hosted agent aigovern-rag-agent was deleted. APIM /foundry-agent "
            "proxies project-level assistants, threads, messages, and runs; callers supply "
            "assistant_id in run requests. Foundry tracing remains the internal platform evidence source."
        )
        break

with open(path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PYEOF

echo ""
echo "=== Setup complete ==="
echo ""
echo "Test examples:"
echo "  Create thread:"
echo "    curl -s -X POST ${APIM_GATEWAY_URL}/foundry-agent/threads -H 'Content-Type: application/json' -d '{}'"
echo ""
echo "  Create and run:"
echo "    curl -s -X POST ${APIM_GATEWAY_URL}/foundry-agent/threads/runs \\\\"
echo "      -H 'Content-Type: application/json' \\\\" 
echo "      -d '{\"assistant_id\": \"${L4_FOUNDRY_AGENT_ID}\", \"thread\": {\"messages\": [{\"role\": \"user\", \"content\": \"Summarize the key ideas in NIST AI RMF.\"}]}}'"
echo ""
echo "NOTE: If APIM calls return 401/403 from the Foundry backend, project/data-plane RBAC for APIM MSI still needs confirmation in the existing Foundry Project."
