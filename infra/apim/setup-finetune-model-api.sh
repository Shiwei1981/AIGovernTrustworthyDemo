#!/usr/bin/env bash
set -euo pipefail

RESOURCE_GROUP="AIGovernTrustworthyRG"
APIM_NAME="AIGovernTrustworthyDemoAPIM"
API_ID="finetune-model"
API_PATH="finetune-model"
UPSTREAM_ACCOUNT_NAME="aigoverntrustworthyfoundry"
DEPLOYMENT_NAME="AIGovernTrustworthyDemoFineTuneModel"
AOAI_BASE_URL="https://aigoverntrustworthyfoundry.cognitiveservices.azure.com/openai/deployments/AIGovernTrustworthyDemoFineTuneModel"
API_VERSION="2025-01-01-preview"
ROLE_NAME="Cognitive Services OpenAI User"
DIAGNOSTIC_ID="applicationinsights"
TARGETS_FILE="infra/target-registry/targets.json"

echo "=== APIM Fine-tune Model API Setup ==="

SUBSCRIPTION_ID="$(az account show --query id -o tsv)"
APIM_PRINCIPAL_ID="$(az apim show --resource-group "$RESOURCE_GROUP" --name "$APIM_NAME" --query identity.principalId -o tsv)"
UPSTREAM_RESOURCE_ID="$(az cognitiveservices account show --resource-group "$RESOURCE_GROUP" --name "$UPSTREAM_ACCOUNT_NAME" --query id -o tsv)"

echo "[1/6] Ensuring APIM MSI RBAC on AOAI..."
if az role assignment list \
     --assignee "$APIM_PRINCIPAL_ID" \
     --scope "$UPSTREAM_RESOURCE_ID" \
     --query "[?roleDefinitionName=='$ROLE_NAME'] | length(@)" \
     -o tsv | grep -qx "1"; then
  echo "    Role assignment already present."
else
  az role assignment create \
    --assignee-object-id "$APIM_PRINCIPAL_ID" \
    --assignee-principal-type ServicePrincipal \
    --role "$ROLE_NAME" \
    --scope "$UPSTREAM_RESOURCE_ID" \
    --output none
fi

echo "[2/6] Creating or updating APIM API..."
if az apim api show \
     --resource-group "$RESOURCE_GROUP" \
     --service-name "$APIM_NAME" \
     --api-id "$API_ID" \
     --output none 2>/dev/null; then
  az apim api update \
    --resource-group "$RESOURCE_GROUP" \
    --service-name "$APIM_NAME" \
    --api-id "$API_ID" \
    --display-name "Fine-tune Model (gpt-4.1)" \
    --path "$API_PATH" \
    --service-url "$AOAI_BASE_URL" \
    --output none
else
  az apim api create \
    --resource-group "$RESOURCE_GROUP" \
    --service-name "$APIM_NAME" \
    --api-id "$API_ID" \
    --display-name "Fine-tune Model (gpt-4.1)" \
    --path "$API_PATH" \
    --protocols https \
    --service-url "$AOAI_BASE_URL" \
    --subscription-required false \
    --output none
fi

echo "[3/6] Creating or updating POST /chat/completions..."
az apim api operation create \
  --resource-group "$RESOURCE_GROUP" \
  --service-name "$APIM_NAME" \
  --api-id "$API_ID" \
  --operation-id "chat-completions" \
  --display-name "Chat Completions" \
  --method "POST" \
  --url-template "/chat/completions" \
  --description "Proxy request to the Domain 4 fine-tuned Azure OpenAI deployment." \
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
POLICY_FILE="$(mktemp /tmp/finetune-model-policy-XXXX.json)"
echo "$POLICY_BODY" > "$POLICY_FILE"
az rest --method put \
  --url "$POLICY_URL" \
  --headers "Content-Type=application/json" \
  --body "@$POLICY_FILE" \
  --output none 1>/dev/null
rm -f "$POLICY_FILE"

echo "[5/6] Ensuring API diagnostics..."
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
DIAGNOSTIC_FILE="$(mktemp /tmp/finetune-model-diagnostic-XXXX.json)"
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
    if target["target_id"] == "AIGovernTrustworthyDemoFineTuneModel":
        target["apim_note"] = (
            "VNet Internal — APIM finetune-model API configured at /finetune-model. "
            "APIM MSI has Cognitive Services OpenAI User on aigoverntrustworthyfoundry."
        )
        target["notes"] = (
            "Step 4. Fine-tune deployment ready and APIM /finetune-model configured to proxy "
            "POST /chat/completions with MSI auth, W3C trace context, and App Insights diagnostics."
        )

with open(path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PYEOF

echo "[RESULT] APIM fine-tune API ready."
