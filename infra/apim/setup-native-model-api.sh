#!/usr/bin/env bash
# =============================================================================
# setup-native-model-api.sh
#
# Configures the APIM "native-model" API to proxy requests to the Domain 4
# Azure OpenAI native model deployment.
#
# What this script does:
#   1. Grants APIM MSI the AOAI "Cognitive Services OpenAI User" role
#   2. Creates or updates the /native-model API
#   3. Creates or updates POST /chat/completions
#   4. Applies API policy (MSI auth + api-version + trace context)
#   5. Ensures API diagnostics flow to the existing App Insights logger
#   6. Updates targets.json to reflect the APIM-ready state
#
# Prerequisites:
#   - az login has already been performed
#   - Run from the repo root: bash infra/apim/setup-native-model-api.sh
#   - Caller has RBAC permission to assign roles and manage APIM
# =============================================================================

set -euo pipefail

RESOURCE_GROUP="AIGovernTrustworthyRG"
APIM_NAME="AIGovernTrustworthyDemoAPIM"
API_ID="native-model"
API_PATH="native-model"
AOAI_NAME="AIGovernTrustworthyAOAI"
DEPLOYMENT_NAME="AIGovernTrustworthyDemoNativeModel"
AOAI_BASE_URL="https://aigoverntrustworthyaoai.openai.azure.com/openai/deployments/AIGovernTrustworthyDemoNativeModel"
API_VERSION="2025-01-01-preview"
ROLE_NAME="Cognitive Services OpenAI User"
DIAGNOSTIC_ID="applicationinsights"
TARGETS_FILE="infra/target-registry/targets.json"

echo "=== APIM Native Model API Setup ==="
echo "APIM:        $APIM_NAME"
echo "API ID:      $API_ID"
echo "Deployment:  $DEPLOYMENT_NAME"
echo "Backend URL: $AOAI_BASE_URL"
echo ""

SUBSCRIPTION_ID="$(az account show --query id -o tsv)"
APIM_PRINCIPAL_ID="$(az apim show --resource-group "$RESOURCE_GROUP" --name "$APIM_NAME" --query identity.principalId -o tsv)"
AOAI_RESOURCE_ID="$(az cognitiveservices account show --resource-group "$RESOURCE_GROUP" --name "$AOAI_NAME" --query id -o tsv)"

# ---------------------------------------------------------------------------
# Step 1: Ensure APIM MSI RBAC on AOAI
# ---------------------------------------------------------------------------
echo "[1/6] Ensuring APIM MSI has '$ROLE_NAME' on $AOAI_NAME..."

if az role assignment list \
     --assignee "$APIM_PRINCIPAL_ID" \
     --scope "$AOAI_RESOURCE_ID" \
     --query "[?roleDefinitionName=='$ROLE_NAME'] | length(@)" \
     -o tsv | grep -qx "1"; then
  echo "    Role assignment already present."
else
  az role assignment create \
    --assignee-object-id "$APIM_PRINCIPAL_ID" \
    --assignee-principal-type ServicePrincipal \
    --role "$ROLE_NAME" \
    --scope "$AOAI_RESOURCE_ID" \
    --output none
  echo "    Role assignment created."
fi

# ---------------------------------------------------------------------------
# Step 2: Create or update API
# ---------------------------------------------------------------------------
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
    --display-name "Native Model (gpt-5.4-nano)" \
    --path "$API_PATH" \
    --service-url "$AOAI_BASE_URL" \
    --output none
else
  az apim api create \
    --resource-group "$RESOURCE_GROUP" \
    --service-name "$APIM_NAME" \
    --api-id "$API_ID" \
    --display-name "Native Model (gpt-5.4-nano)" \
    --path "$API_PATH" \
    --protocols https \
    --service-url "$AOAI_BASE_URL" \
    --subscription-required false \
    --output none
fi

echo "    API ready."

# ---------------------------------------------------------------------------
# Step 3: Create or update POST /chat/completions
# ---------------------------------------------------------------------------
echo "[3/6] Creating or updating POST /chat/completions..."

az apim api operation create \
  --resource-group "$RESOURCE_GROUP" \
  --service-name "$APIM_NAME" \
  --api-id "$API_ID" \
  --operation-id "chat-completions" \
  --display-name "Chat Completions" \
  --method "POST" \
  --url-template "/chat/completions" \
  --description "Proxy request to the Domain 4 Azure OpenAI native model deployment." \
  --output none 2>/dev/null || \
az apim api operation update \
  --resource-group "$RESOURCE_GROUP" \
  --service-name "$APIM_NAME" \
  --api-id "$API_ID" \
  --operation-id "chat-completions" \
  --display-name "Chat Completions" \
  --method "POST" \
  --url-template "/chat/completions" \
  --output none

echo "    Operation ready."

# ---------------------------------------------------------------------------
# Step 4: Apply API policy
# ---------------------------------------------------------------------------
echo "[4/6] Applying API policy..."

POLICY_XML='<policies>
  <inbound>
    <base />
    <set-header name="traceparent" exists-action="skip">
      <value>@("00-" + context.RequestId.ToString("N") + "-" + context.RequestId.ToString("N").Substring(16, 16) + "-01")</value>
    </set-header>
    <authentication-managed-identity
      resource="https://cognitiveservices.azure.com"
      output-token-variable-name="msi-token" />
    <set-header name="Authorization" exists-action="override">
      <value>@("Bearer " + (string)context.Variables["msi-token"])</value>
    </set-header>
    <set-query-parameter name="api-version" exists-action="override">
      <value>'"$API_VERSION"'</value>
    </set-query-parameter>
    <set-backend-service base-url="'"$AOAI_BASE_URL"'" />
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
POLICY_FILE="$(mktemp /tmp/native-model-policy-XXXX.json)"
echo "$POLICY_BODY" > "$POLICY_FILE"
az rest --method put \
  --url "$POLICY_URL" \
  --headers "Content-Type=application/json" \
  --body "@$POLICY_FILE" \
  --output none 1>/dev/null
rm -f "$POLICY_FILE"

echo "    Policy applied."

# ---------------------------------------------------------------------------
# Step 5: Ensure API diagnostics use the existing App Insights logger
# ---------------------------------------------------------------------------
echo "[5/6] Ensuring API diagnostics flow to App Insights..."

DIAGNOSTIC_URL="https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.ApiManagement/service/${APIM_NAME}/apis/${API_ID}/diagnostics/${DIAGNOSTIC_ID}?api-version=2022-08-01"
DIAGNOSTIC_BODY="$(python3 - <<PYEOF
import json

payload = {
    "properties": {
        "loggerId": f"/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.ApiManagement/service/${APIM_NAME}/loggers/${DIAGNOSTIC_ID}",
        "alwaysLog": "allErrors",
        "sampling": {
            "samplingType": "fixed",
            "percentage": 100.0,
        },
        "httpCorrelationProtocol": "W3C",
        "verbosity": "information",
        "logClientIp": True,
        "frontend": {
            "request": {
                "dataMasking": {
                    "queryParams": [
                        {"mode": "Hide", "value": "*"}
                    ]
                }
            },
            "response": None,
        },
        "backend": {
            "request": {
                "dataMasking": {
                    "queryParams": [
                        {"mode": "Hide", "value": "*"}
                    ]
                }
            },
            "response": None,
        },
    }
}

print(json.dumps(payload))
PYEOF
)"
DIAGNOSTIC_FILE="$(mktemp /tmp/native-model-diagnostic-XXXX.json)"
echo "$DIAGNOSTIC_BODY" > "$DIAGNOSTIC_FILE"
az rest --method put \
  --url "$DIAGNOSTIC_URL" \
  --headers "Content-Type=application/json" \
  --body "@$DIAGNOSTIC_FILE" \
  --output none 1>/dev/null
rm -f "$DIAGNOSTIC_FILE"

echo "    API diagnostics ready."

# ---------------------------------------------------------------------------
# Step 6: Update target registry
# ---------------------------------------------------------------------------
echo "[6/6] Updating target registry..."

python3 - <<PYEOF
import json

path = "$TARGETS_FILE"
with open(path) as f:
    data = json.load(f)

for target in data["targets"]:
    if target["target_id"] == "AIGovernTrustworthyDemoNativeModel":
        target["apim_note"] = (
            "VNet Internal — APIM native-model API configured at /native-model. "
            "APIM MSI has Cognitive Services OpenAI User on AIGovernTrustworthyAOAI."
        )
        target["notes"] = (
            "Step 3. Direct AOAI endpoint verified 2026-05-13. "
            "APIM /native-model configured to proxy POST /chat/completions with MSI auth, "
            "W3C trace context, and App Insights diagnostics."
        )
        break

with open(path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\\n")
PYEOF

echo "    targets.json updated."
echo ""
echo "=== Setup complete ==="
echo ""
echo "Test endpoint:"
echo "  curl -s -X POST https://aigoverntrustworthydemoapim.azure-api.net/native-model/chat/completions \\"
echo '    -H "Content-Type: application/json" \'
echo '    -d '"'"'{"messages":[{"role":"user","content":"What does NIST AI RMF stand for?"}],"max_completion_tokens":128}'"'"
echo ""
echo "NOTE: APIM is VNet-Internal. The gateway URL must be resolved and reachable"
echo "      from the current machine or another host inside the connected VNet."
