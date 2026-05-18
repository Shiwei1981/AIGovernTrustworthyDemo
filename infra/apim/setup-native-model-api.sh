#!/usr/bin/env bash
# =============================================================================
# setup-native-model-api.sh
#
# Configures the APIM "native-model" API to proxy requests to the Domain 4
# project-backed native model path exposed through AIGovernTrustworthyRAGProject.
#
# What this script does:
#   1. Grants APIM MSI the AI Foundry/OpenAI data-plane role on the project account
#   2. Creates or updates the /native-model API
#   3. Creates or updates POST /chat/completions
#   4. Applies API policy (MSI auth + trace context)
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
PROJECT_ACCOUNT_NAME="aigoverntrustworthyfoundry"
PROJECT_NAME="AIGovernTrustworthyRAGProject"
DEPLOYMENT_NAME="AIGovernTrustworthyDemoNativeModelGPT5.4mini"
MODEL_NAME="gpt-5.4-mini"
MODEL_VERSION="2026-03-17"
COGNITIVE_BASE_URL="https://aigoverntrustworthyfoundry.cognitiveservices.azure.com"
DEPLOYMENT_BASE_URL="${COGNITIVE_BASE_URL}/openai/deployments/${DEPLOYMENT_NAME}"
TOKEN_SCOPE="https://cognitiveservices.azure.com"
ROLE_NAME="Cognitive Services OpenAI User"
DIAGNOSTIC_ID="applicationinsights"
TARGETS_FILE="infra/target-registry/targets.json"

echo "=== APIM Native Model API Setup ==="
echo "APIM:        $APIM_NAME"
echo "API ID:      $API_ID"
echo "Project:     $PROJECT_NAME"
echo "Deployment:  $DEPLOYMENT_NAME"
echo "Backend URL: $DEPLOYMENT_BASE_URL"
echo ""

SUBSCRIPTION_ID="$(az account show --query id -o tsv)"
APIM_PRINCIPAL_ID="$(az apim show --resource-group "$RESOURCE_GROUP" --name "$APIM_NAME" --query identity.principalId -o tsv)"
PROJECT_ACCOUNT_RESOURCE_ID="$(az cognitiveservices account show --resource-group "$RESOURCE_GROUP" --name "$PROJECT_ACCOUNT_NAME" --query id -o tsv)"

# ---------------------------------------------------------------------------
# Step 1: Ensure APIM MSI RBAC on project account
# ---------------------------------------------------------------------------
echo "[1/6] Ensuring APIM MSI has '$ROLE_NAME' on $PROJECT_ACCOUNT_NAME..."

if az role assignment list \
     --assignee "$APIM_PRINCIPAL_ID" \
     --scope "$PROJECT_ACCOUNT_RESOURCE_ID" \
     --query "[?roleDefinitionName=='$ROLE_NAME'] | length(@)" \
     -o tsv | grep -qx "1"; then
  echo "    Role assignment already present."
else
  az role assignment create \
    --assignee-object-id "$APIM_PRINCIPAL_ID" \
    --assignee-principal-type ServicePrincipal \
    --role "$ROLE_NAME" \
    --scope "$PROJECT_ACCOUNT_RESOURCE_ID" \
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
    --display-name "Native Model (Foundry gpt-5.4-mini)" \
    --path "$API_PATH" \
    --service-url "$DEPLOYMENT_BASE_URL" \
    --output none
else
  az apim api create \
    --resource-group "$RESOURCE_GROUP" \
    --service-name "$APIM_NAME" \
    --api-id "$API_ID" \
    --display-name "Native Model (Foundry gpt-5.4-mini)" \
    --path "$API_PATH" \
    --protocols https \
    --service-url "$DEPLOYMENT_BASE_URL" \
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
  --description "Proxy request to the Domain 4 native model deployment on the Foundry cognitiveservices endpoint." \
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

POLICY_XML=$(cat <<EOF
<policies>
  <inbound>
    <base />
    <set-header name="traceparent" exists-action="skip">
      <value>@("00-" + context.RequestId.ToString("N") + "-" + context.RequestId.ToString("N").Substring(16, 16) + "-01")</value>
    </set-header>
    <authentication-managed-identity
      resource="${TOKEN_SCOPE}"
      output-token-variable-name="msi-token" />
    <set-header name="Authorization" exists-action="override">
      <value>@("Bearer " + (string)context.Variables["msi-token"])</value>
    </set-header>
    <set-query-parameter name="api-version" exists-action="override">
      <value>2025-01-01-preview</value>
    </set-query-parameter>
    <set-body>@{
      var requestBody = context.Request.Body?.As<JObject>(preserveContent: true);
      if (requestBody == null)
      {
        return context.Request.Body?.As<string>(preserveContent: true) ?? string.Empty;
      }

      if (requestBody["model"] == null || string.IsNullOrEmpty((string)requestBody["model"]))
      {
        requestBody["model"] = "${DEPLOYMENT_NAME}";
      }

      return requestBody.ToString();
    }</set-body>
    <set-backend-service base-url="${DEPLOYMENT_BASE_URL}" />
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
</policies>
EOF
)

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
        target["display_name"] = "Foundry Native Model (gpt-5.4-mini)"
        target["model_name"] = "${MODEL_NAME}"
        target["model_version"] = "${MODEL_VERSION}"
        target["deployment_name"] = "${DEPLOYMENT_NAME}"
        target["aoai_resource"] = "aigoverntrustworthyfoundry"
        target["endpoint"] = (
            "https://aigoverntrustworthyfoundry.cognitiveservices.azure.com/openai/deployments/"
            "${DEPLOYMENT_NAME}/chat/completions?api-version=2025-01-01-preview"
        )
        target["apim_note"] = (
            "VNet Internal — APIM native-model API configured at /native-model. "
            "APIM MSI has Cognitive Services OpenAI User on aigoverntrustworthyfoundry "
            "and proxies to the cognitiveservices deployment path for ${DEPLOYMENT_NAME}."
        )
        target["notes"] = (
            "Step 3. 2026-05-17 native deployment moved to ${DEPLOYMENT_NAME}. "
            "APIM /native-model now proxies the cognitiveservices deployment path with "
            "MSI auth, W3C trace context, and explicit api-version injection."
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
echo '    -d '"'"'{"messages":[{"role":"user","content":"What does NIST AI RMF stand for?"}],"max_tokens":128}'"'"''
echo ""
echo "NOTE: APIM is VNet-Internal. The gateway URL must be resolved and reachable"
echo "      from the current machine or another host inside the connected VNet."
