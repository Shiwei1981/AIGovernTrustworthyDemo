#!/usr/bin/env bash
# deploy_hosted_agent.sh — Build, push, and deploy the RAG Hosted Agent.
#
# Usage:
#   bash apps/rag-service/scripts/deploy_hosted_agent.sh [--version <tag>]
#
# Prerequisites:
#   - .env.local.L4 present at repo root (script sources it)
#   - `az acr login` already done, or AcrPush role on the deploy SPN
#   - L4_RAG_VECTOR_STORE_ID filled in .env.local.L4
#   - azure-ai-projects>=2.1.0 installed (pip install azure-ai-projects)
#
# What it does:
#   1. Builds the container image from repo root.
#   2. Pushes to ACR.
#   3. Creates a new Hosted Agent version via azure-ai-projects SDK.
#   4. Waits for provisioning to complete.
#   5. Prints agent version, instance identity principal_id, and endpoint.
#   6. Shows the RBAC commands you must run to grant the agent identity access.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env.local.L4"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: ${ENV_FILE} not found." >&2
  exit 1
fi

# Source env (skip comments and secrets intentionally not shown)
# shellcheck disable=SC1090
set -a
while IFS= read -r line; do
  line="${line%%#*}"       # strip inline comments
  line="${line//\"/}"      # strip quotes
  [[ -z "${line}" || "${line}" != *=* ]] && continue
  export "${line?}"
done < "${ENV_FILE}"
set +a

# ── Defaults ──────────────────────────────────────────────────────────────────
VERSION=""
if [[ "${1:-}" == "--version" ]]; then
  VERSION="${2:-}"
elif [[ -n "${1:-}" ]]; then
  VERSION="${1}"
fi
[[ -z "${VERSION}" ]] && VERSION="v$(date -u +%Y%m%d%H%M%S)"

AGENT_NAME="${L4_RAG_HOSTED_AGENT_DEPLOY_NAME:-aigovern-rag-agent-official}"
PROJECT_ENDPOINT="${L4_RAG_FOUNDRY_PROJECT_ENDPOINT:?L4_RAG_FOUNDRY_PROJECT_ENDPOINT not set}"
MODEL_DEPLOYMENT="${L4_RAG_MODEL_DEPLOYMENT:?L4_RAG_MODEL_DEPLOYMENT not set}"
VECTOR_STORE_ID="${L4_RAG_VECTOR_STORE_ID:?L4_RAG_VECTOR_STORE_ID not set — run upload_knowledge_foundry.py first}"
ACR_LOGIN_SERVER="${L4_RAG_ACR_LOGIN_SERVER:-aigoverndemoacr.azurecr.io}"
IMAGE_TAG="${ACR_LOGIN_SERVER}/rag-hosted-agent:${VERSION}"

BLOB_ACCOUNT="${L4_OBSERVABILITY_BLOB_STORAGE_ACCOUNT_NAME:-aigoverntrustworthysa}"
BLOB_CONTAINER="${L4_OBSERVABILITY_BLOB_CONTAINER:-ai-invocation-archive}"
BLOB_PREFIX="${L4_OBSERVABILITY_BLOB_PREFIX:-aigoverntrustworthy}"
OBS_PACKAGE="${L4_OBSERVABILITY_PACKAGE_NAME:-shared_observability}"
SERVICE_NAME="${L4_OTEL_SERVICE_NAME_RAG_SERVICE:-AIGovernTrustworthyDemo.RAGService}"

echo "============================================================"
echo " RAG Hosted Agent Deploy"
echo " Version : ${VERSION}"
echo " Agent   : ${AGENT_NAME}"
echo " Image   : ${IMAGE_TAG}"
echo " Project : ${PROJECT_ENDPOINT}"
echo "============================================================"

# ── Step 1: Build image ───────────────────────────────────────────────────────
echo
echo "[1/4] Building container image..."
docker build \
  -f "${REPO_ROOT}/apps/rag-service/Dockerfile" \
  -t "${IMAGE_TAG}" \
  "${REPO_ROOT}"
echo "  Built: ${IMAGE_TAG}"

# ── Step 2: Push to ACR ───────────────────────────────────────────────────────
echo
echo "[2/4] Pushing to ACR..."
docker push "${IMAGE_TAG}"
echo "  Pushed: ${IMAGE_TAG}"

# ── Step 3: Deploy Hosted Agent version ──────────────────────────────────────
echo
echo "[3/4] Deploying Hosted Agent version..."

AGENT_IDENTITY_PRINCIPAL_ID=$(python3 - <<PYEOF
import sys, json, time
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    HostedAgentDefinition,
    ProtocolVersionRecord,
    AgentProtocol,
)
from azure.identity import AzureCliCredential

try:
    from opentelemetry.sdk.trace.export.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
except ImportError:
    OTLPSpanExporter = None  # optional

PROJECT_ENDPOINT = "${PROJECT_ENDPOINT}"
AGENT_NAME       = "${AGENT_NAME}"
IMAGE_TAG        = "${IMAGE_TAG}"
VERSION_TAG      = "${VERSION}"
MODEL            = "${MODEL_DEPLOYMENT}"
VECTOR_STORE_ID  = "${VECTOR_STORE_ID}"
BLOB_ACCOUNT     = "${BLOB_ACCOUNT}"
BLOB_CONTAINER   = "${BLOB_CONTAINER}"
BLOB_PREFIX      = "${BLOB_PREFIX}"
OBS_PACKAGE      = "${OBS_PACKAGE}"
SERVICE_NAME     = "${SERVICE_NAME}"

client = AIProjectClient(
    endpoint=PROJECT_ENDPOINT,
    credential=AzureCliCredential(),
    allow_preview=True,
)

env_vars = {
    "RAG_MODEL_DEPLOYMENT":     MODEL,
    "RAG_VECTOR_STORE_ID":      VECTOR_STORE_ID,
    "SERVICE_NAME":             SERVICE_NAME,
    "HOSTED_AGENT_NAME":        AGENT_NAME,
    "HOSTED_AGENT_VERSION":     VERSION_TAG,
    "L4_OBSERVABILITY_PACKAGE_NAME":              OBS_PACKAGE,
    "L4_OBSERVABILITY_BLOB_STORAGE_ACCOUNT_NAME": BLOB_ACCOUNT,
    "L4_OBSERVABILITY_BLOB_CONTAINER":            BLOB_CONTAINER,
    "L4_OBSERVABILITY_BLOB_PREFIX":               BLOB_PREFIX,
    "LOG_LEVEL": "INFO",
}

definition = HostedAgentDefinition(
    cpu="1",
    memory="2Gi",
    image=IMAGE_TAG,
    environment_variables=env_vars,
    container_protocol_versions=[
        ProtocolVersionRecord(protocol=AgentProtocol.RESPONSES, version="1.0.0"),
    ],
)

print(f"Creating agent version for '{AGENT_NAME}'...", file=sys.stderr)
agent_version = client.agents.create_version(
    agent_name=AGENT_NAME,
    definition=definition,
    description=f"RAG Governance Service Hosted Agent {VERSION_TAG}",
    metadata={"version": VERSION_TAG},
)
print(f"Agent version created: {agent_version.id} (status: {agent_version.status})", file=sys.stderr)

# Wait for provisioning
for attempt in range(60):
    av = client.agents.get_version(AGENT_NAME, agent_version.version)
    status = str(av.status)
    print(f"  [{attempt+1:02d}] status={status}", file=sys.stderr)
    if status == "active":
        print(f"Agent version active: {av.version}", file=sys.stderr)
        # Print instance identity principal ID for RBAC grants
        identity = getattr(av, "instance_identity", None)
        if identity:
            print(identity.principal_id)
        else:
            print("NO_IDENTITY")
        break
    elif status in ("failed", "deleted"):
        print(f"ERROR: Agent version failed with status: {status}", file=sys.stderr)
        sys.exit(1)
    time.sleep(10)
else:
    print("TIMEOUT", file=sys.stderr)
    sys.exit(1)
PYEOF
)

echo "  Agent identity principal_id: ${AGENT_IDENTITY_PRINCIPAL_ID}"

# ── Step 4: Summary ───────────────────────────────────────────────────────────
echo
echo "[4/4] Deployment complete."
echo
echo "============================================================"
echo " Update .env.local.L4 with:"
echo "   L4_RAG_HOSTED_AGENT_VERSION=${VERSION}"
AGENT_ENDPOINT="${PROJECT_ENDPOINT}/agents/${AGENT_NAME}/endpoint/protocols/openai/responses"
echo "   L4_RAG_HOSTED_AGENT_ENDPOINT=${AGENT_ENDPOINT}"
echo
echo " Grant RBAC to agent identity (principal_id=${AGENT_IDENTITY_PRINCIPAL_ID}):"
echo
echo "   # 1. Azure AI User on Foundry Account"
echo "   az role assignment create \\"
echo "     --assignee ${AGENT_IDENTITY_PRINCIPAL_ID} \\"
echo "     --role 'Azure AI User' \\"
echo "     --scope /subscriptions/${AZ_SUBSCRIPTION_ID}/resourceGroups/${L4_RESOURCE_GROUP}/providers/Microsoft.CognitiveServices/accounts/${L4_RAG_FOUNDRY_ACCOUNT_NAME}"
echo
echo "   # 2. Storage Blob Data Contributor on observability storage account"
echo "   az role assignment create \\"
echo "     --assignee ${AGENT_IDENTITY_PRINCIPAL_ID} \\"
echo "     --role 'Storage Blob Data Contributor' \\"
echo "     --scope /subscriptions/${AZ_SUBSCRIPTION_ID}/resourceGroups/${L4_RESOURCE_GROUP}/providers/Microsoft.Storage/storageAccounts/${BLOB_ACCOUNT}"
echo
echo "   # 3. AcrPull on ACR (for platform to pull image)"
echo "   FOUNDRY_PROJECT_MI=$(az cognitiveservices account project show \\"
echo "     -n ${L4_RAG_FOUNDRY_ACCOUNT_NAME} -g ${L4_RESOURCE_GROUP} \\"
echo "     --project-name ${L4_RAG_FOUNDRY_PROJECT_NAME} \\"
echo "     --query identity.principalId -o tsv)"
echo "   az role assignment create \\"
echo "     --assignee \"\$FOUNDRY_PROJECT_MI\" \\"
echo "     --role 'AcrPull' \\"
echo "     --scope /subscriptions/${AZ_SUBSCRIPTION_ID}/resourceGroups/AIGovernDemoRG/providers/Microsoft.ContainerRegistry/registries/${L4_RAG_ACR_NAME}"
echo "============================================================"
