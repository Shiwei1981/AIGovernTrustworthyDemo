#!/usr/bin/env bash
# =============================================================================
# setup-rag-api.sh
#
# Configures the APIM "rag-service" API to proxy requests to the RAG Web App.
#
# What this script does:
#   1. Updates the API backend (serviceUrl) to the RAG Web App
#   2. Removes old Hosted Agent thread operations
#   3. Creates POST /responses and GET /health operations
#   4. Sets the inbound/outbound policy (pass-through + W3C traceparent + diagnostics)
#   5. Updates targets.json backend_url and status
#
# Prerequisites:
#   - az login (or az login --use-device-code if in CI)
#   - jq installed
#   - Run from the repo root: bash infra/apim/setup-rag-api.sh
#
# APIM is in VNet-Internal mode; this script assumes the caller has network
# access to the APIM management plane (ARM API) which is always accessible
# regardless of VNet mode.
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Config (sourced from .env.local.L4 values — no secrets used here)
# ---------------------------------------------------------------------------
RESOURCE_GROUP="AIGovernTrustworthyRG"
APIM_NAME="AIGovernTrustworthyDemoAPIM"
API_ID="rag-service"
RAG_BACKEND_URL="https://aigoverntrustworthyragapp-hchcfae9hpczcrcx.canadaeast-01.azurewebsites.net"

echo "=== APIM RAG API Setup ==="
echo "APIM:        $APIM_NAME"
echo "API ID:      $API_ID"
echo "Backend URL: $RAG_BACKEND_URL"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Update API backend serviceUrl
# ---------------------------------------------------------------------------
echo "[1/5] Updating API backend serviceUrl → $RAG_BACKEND_URL"
az apim api update \
  --resource-group "$RESOURCE_GROUP" \
  --service-name "$APIM_NAME" \
  --api-id "$API_ID" \
  --service-url "$RAG_BACKEND_URL" \
  --display-name "RAG Governance Service" \
  --description "AI Governance knowledge Q&A service (BM25 + Azure OpenAI). Proxied from AIGovernTrustworthyRAGApp Web App." \
  --output none

echo "    Done."

# ---------------------------------------------------------------------------
# Step 2: Remove old Hosted Agent operations
# ---------------------------------------------------------------------------
echo "[2/5] Removing stale Hosted Agent operations..."
OLD_OPS=("add-message" "create-run" "threads" "get-run" "list-messages")
for op in "${OLD_OPS[@]}"; do
  if az apim api operation show \
       --resource-group "$RESOURCE_GROUP" \
       --service-name "$APIM_NAME" \
       --api-id "$API_ID" \
       --operation-id "$op" \
       --output none 2>/dev/null; then
    az apim api operation delete \
      --resource-group "$RESOURCE_GROUP" \
      --service-name "$APIM_NAME" \
      --api-id "$API_ID" \
      --operation-id "$op" \
      --output none
    echo "    Deleted: $op"
  else
    echo "    Skipped (not found): $op"
  fi
done

# ---------------------------------------------------------------------------
# Step 3a: Create POST /responses operation
# ---------------------------------------------------------------------------
echo "[3/5] Creating POST /responses operation..."
az apim api operation create \
  --resource-group "$RESOURCE_GROUP" \
  --service-name "$APIM_NAME" \
  --api-id "$API_ID" \
  --operation-id "query-rag" \
  --display-name "Query RAG Service" \
  --method "POST" \
  --url-template "/responses" \
  --description "Submit a question to the RAG Governance Service. Returns an AI-generated answer, citations from the knowledge base, and an archive_id for evidence lookup." \
  --output none 2>/dev/null || \
az apim api operation update \
  --resource-group "$RESOURCE_GROUP" \
  --service-name "$APIM_NAME" \
  --api-id "$API_ID" \
  --operation-id "query-rag" \
  --display-name "Query RAG Service" \
  --method "POST" \
  --url-template "/responses" \
  --output none
echo "    Done: POST /responses"

# ---------------------------------------------------------------------------
# Step 3b: Create GET /health operation
# ---------------------------------------------------------------------------
echo "[3/5] Creating GET /health operation..."
az apim api operation create \
  --resource-group "$RESOURCE_GROUP" \
  --service-name "$APIM_NAME" \
  --api-id "$API_ID" \
  --operation-id "health-check" \
  --display-name "Health Check" \
  --method "GET" \
  --url-template "/health" \
  --description "Returns service health status and number of loaded document chunks." \
  --output none 2>/dev/null || \
az apim api operation update \
  --resource-group "$RESOURCE_GROUP" \
  --service-name "$APIM_NAME" \
  --api-id "$API_ID" \
  --operation-id "health-check" \
  --display-name "Health Check" \
  --method "GET" \
  --url-template "/health" \
  --output none
echo "    Done: GET /health"

# ---------------------------------------------------------------------------
# Step 4: Set API-level inbound policy
#
# Policy intent:
#   - Pass through Authorization header to backend (Web App handles auth at
#     app level; APIM does not validate the JWT, keeping this flexible for now)
#   - Inject W3C traceparent header so the Web App OTEL SDK picks up the
#     APIM-generated trace context automatically
#   - Set backend to the RAG Web App (set-backend-service ensures any future
#     serviceUrl override is explicit)
#   - Outbound: pass response through unchanged
#   - On-error: return 502 with a structured JSON error body
# ---------------------------------------------------------------------------
echo "[4/5] Applying API-level policy..."

POLICY_XML='<policies>
  <inbound>
    <base />
    <!-- Forward caller Authorization header to backend unchanged -->
    <!-- (RAG Web App currently does not enforce AAD auth; Easy Auth can be
         enabled later without changing this policy) -->

    <!-- Inject W3C traceparent so the Web App OTEL SDK correlates to APIM trace -->
    <set-header name="traceparent" exists-action="skip">
      <value>@{
        var traceId = context.RequestId.ToString("N");
        return $"00-{traceId.PadLeft(32, '"'"'0'"'"')}-{traceId.Substring(0, 16).PadLeft(16, '"'"'0'"'"')}-01";
      }</value>
    </set-header>

    <!-- Explicitly route to RAG Web App (guard against serviceUrl drift) -->
    <set-backend-service base-url="https://aigoverntrustworthyragapp-hchcfae9hpczcrcx.canadaeast-01.azurewebsites.net" />
  </inbound>
  <backend>
    <base />
  </backend>
  <outbound>
    <base />
    <!-- Expose APIM request ID as a response header for correlation -->
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

az apim api policy create \
  --resource-group "$RESOURCE_GROUP" \
  --service-name "$APIM_NAME" \
  --api-id "$API_ID" \
  --value "$POLICY_XML" \
  --output none
echo "    Policy applied."

# ---------------------------------------------------------------------------
# Step 5: Update targets.json backend_url and status
# ---------------------------------------------------------------------------
echo "[5/5] Updating targets.json..."
TARGETS_FILE="infra/target-registry/targets.json"
python3 - <<PYEOF
import json, sys

path = "$TARGETS_FILE"
with open(path) as f:
    data = json.load(f)

for t in data["targets"]:
    if t["target_id"] == "AIGovernTrustworthyDemoRAGService":
        t["backend_url"] = "$RAG_BACKEND_URL"
        t["status"] = "active"
        t["notes"] = (
            "Step 2. Web App v1.0.2 deployed to canadaeast. "
            "APIM /rag path configured to proxy POST /responses and GET /health. "
            "APIM internal VNet — access via VNet or APIM gateway URL."
        )
        break

with open(path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")

print("    targets.json updated.")
PYEOF

echo ""
echo "=== Setup complete ==="
echo ""
echo "Test endpoints:"
echo "  Health:  curl -s https://aigoverntrustworthydemoapim.azure-api.net/rag/health"
echo "  Query:   curl -s -X POST https://aigoverntrustworthydemoapim.azure-api.net/rag/responses \\"
echo '           -H "Content-Type: application/json" \'
echo '           -d '"'"'{"input": "What are the four core functions of NIST AI RMF?"}'"'"
echo ""
echo "NOTE: APIM is VNet-Internal. The gateway URL is only reachable from within"
echo "      the VNet or via the public IP (40.86.204.28) with DNS override."
echo "      For external access, add a public front-end (App Gateway / Front Door)"
echo "      or test from a VM inside the VNet."
