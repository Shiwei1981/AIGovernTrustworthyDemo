#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/../.." && pwd)
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/.env.local.L4}"

log() {
  printf '[INFO] %s\n' "$*"
}

warn() {
  printf '[WARN] %s\n' "$*" >&2
}

fail() {
  printf '[ERROR] %s\n' "$*" >&2
  exit 1
}

on_error() {
  local exit_code=$?
  local line_no="$1"
  fail "Command failed at line ${line_no}: ${BASH_COMMAND} (exit=${exit_code})"
}

trap 'on_error "$LINENO"' ERR

usage() {
  cat <<'EOF'
Usage: create-domain4-spns.sh

Creates or reuses all Domain 4 runtime service principals defined in
docs/design-L2-domain-4-prerequisites-lowleveldesign.md, adds them to the
aigoverndemogroup Entra group, assigns RBAC roles, rotates a long-lived client
secret for each app registration, and writes the resulting values back to
.env.local.L4.

Notes:
  - The script logs in with the deploy SPN from .env.local.L4.
  - Re-running the script rotates each client secret and overwrites the secret
    values in the env file.
  - For Domain 4 resources that are planned but not created yet inside
    L4_RESOURCE_GROUP, the script falls back to RG-scope role assignment and
    logs a warning instead of silently skipping the role.
  - Existing cross-resource-group dependencies (OpenAI / Foundry Project) are
    mandatory and must already exist.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

require_command() {
  local command_name="$1"
  command -v "$command_name" >/dev/null 2>&1 || fail "Required command not found: $command_name"
}

require_env_var() {
  local var_name="$1"
  [[ -n "${!var_name:-}" ]] || fail "Required value is missing from ${ENV_FILE}: ${var_name}"
}

update_env_var() {
  local key="$1"
  local value="$2"
  local escaped_value

  printf -v escaped_value '%q' "$value"

  python3 - "$ENV_FILE" "$key" "$escaped_value" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
lines = path.read_text(encoding="utf-8").splitlines()
prefix = f"{key}="

for index, line in enumerate(lines):
    if line.startswith(prefix):
        lines[index] = f"{key}={value}"
        break
else:
    lines.append(f"{key}={value}")

path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

load_env() {
  [[ -f "$ENV_FILE" ]] || fail "Env file not found: $ENV_FILE"
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
}

login_as_deploy_spn() {
  log "Logging into Azure with deploy SPN"
  az login \
    --service-principal \
    --username "$AZ_DEPLOY_CLIENT_ID" \
    --password "$AZ_DEPLOY_CLIENT_SECRET" \
    --tenant "$AZ_DEPLOY_TENANT_ID" \
    >/dev/null

  az account set --subscription "$AZ_SUBSCRIPTION_ID"

  local current_identity
  current_identity=$(az account show --query 'user.name' -o tsv)
  [[ "$current_identity" == "$AZ_DEPLOY_CLIENT_ID" ]] || fail "Azure session is not running under the deploy SPN"
}

resolve_resource_scope() {
  local resource_group="$1"
  local resource_type="$2"
  local resource_name="$3"
  local label="$4"
  local resource_id

  resource_id=$(az resource show \
    --resource-group "$resource_group" \
    --resource-type "$resource_type" \
    --name "$resource_name" \
    --query id \
    -o tsv 2>/dev/null || true)

  [[ -n "$resource_id" ]] || fail "Required resource not found for ${label}: ${resource_group}/${resource_type}/${resource_name}"
  printf '%s' "$resource_id"
}

resolve_or_fallback_scope() {
  local resource_group="$1"
  local resource_type="$2"
  local resource_name="$3"
  local label="$4"
  local resource_id

  resource_id=$(az resource show \
    --resource-group "$resource_group" \
    --resource-type "$resource_type" \
    --name "$resource_name" \
    --query id \
    -o tsv 2>/dev/null || true)

  if [[ -n "$resource_id" ]]; then
    printf '%s' "$resource_id"
    return 0
  fi

  warn "Resource not found for ${label}; falling back to resource-group scope ${L4_RESOURCE_GROUP_SCOPE}"
  printf '%s' "$L4_RESOURCE_GROUP_SCOPE"
}

resolve_group_id() {
  GROUP_OBJECT_ID=$(az ad group show --group "$L4_SPN_GROUP_NAME" --query id -o tsv 2>/dev/null || true)
  [[ -n "$GROUP_OBJECT_ID" ]] || fail "Entra group not found: ${L4_SPN_GROUP_NAME}"
}

patch_graph_tags() {
  local graph_path="$1"
  local attempt max_attempts=6 wait_secs=5

  for ((attempt=1; attempt<=max_attempts; attempt++)); do
    if az rest \
        --method PATCH \
        --uri "https://graph.microsoft.com/v1.0/${graph_path}" \
        --headers Content-Type=application/json \
        --body "{\"tags\":[\"AI:${L4_SPN_TAG_AI}\",\"Owner:${L4_SPN_TAG_OWNER}\"]}" \
        >/dev/null 2>&1; then
      return 0
    fi
    [[ $attempt -lt $max_attempts ]] && sleep "$wait_secs"
  done

  warn "Could not patch Graph tags on ${graph_path} after ${max_attempts} attempts; continuing"
}

ensure_application() {
  local display_name="$1"
  local app_count

  app_count=$(az ad app list \
    --display-name "$display_name" \
    --query "length([?displayName=='${display_name}'])" \
    -o tsv)

  local _ids
  if [[ "$app_count" == "0" ]]; then
    log "Creating app registration: ${display_name}"
    mapfile -t _ids < <(az ad app create \
      --display-name "$display_name" \
      --sign-in-audience AzureADMyOrg \
      --query '[appId,id]' \
      -o tsv)
  elif [[ "$app_count" == "1" ]]; then
    log "Reusing app registration: ${display_name}"
    mapfile -t _ids < <(az ad app list \
      --display-name "$display_name" \
      --query "[?displayName=='${display_name}'] | [0].[appId,id]" \
      -o tsv)
  else
    fail "Multiple app registrations found with display name ${display_name}; clean up duplicates before rerunning"
  fi

  APP_ID="${_ids[0]:-}"
  APP_OBJECT_ID="${_ids[1]:-}"

  [[ -n "$APP_ID" && -n "$APP_OBJECT_ID" ]] || fail "Failed to resolve application IDs for ${display_name}"
  patch_graph_tags "applications/${APP_OBJECT_ID}"
}

ensure_service_principal() {
  local display_name="$1"
  local attempt max_attempts=6 wait_secs=5

  SP_OBJECT_ID=$(az ad sp list \
    --filter "appId eq '${APP_ID}'" \
    --query '[0].id' \
    -o tsv)

  if [[ -z "$SP_OBJECT_ID" ]]; then
    log "Creating service principal: ${display_name}"
    for ((attempt=1; attempt<=max_attempts; attempt++)); do
      SP_OBJECT_ID=$(az ad sp create --id "$APP_ID" --query id -o tsv 2>/dev/null || true)
      [[ -n "$SP_OBJECT_ID" ]] && break
      [[ $attempt -lt $max_attempts ]] && sleep "$wait_secs"
    done
  else
    log "Reusing service principal: ${display_name}"
  fi

  [[ -n "$SP_OBJECT_ID" ]] || fail "Failed to resolve service principal object ID for ${display_name}"
  patch_graph_tags "servicePrincipals/${SP_OBJECT_ID}"
}

ensure_group_membership() {
  local sp_object_id="$1"
  local display_name="$2"
  local is_member attempt max_attempts=6 wait_secs=5

  for ((attempt=1; attempt<=max_attempts; attempt++)); do
    is_member=$(az ad group member check \
      --group "$GROUP_OBJECT_ID" \
      --member-id "$sp_object_id" \
      --query value \
      -o tsv 2>/dev/null || true)
    [[ -n "$is_member" ]] && break
    [[ $attempt -lt $max_attempts ]] && sleep "$wait_secs"
  done

  if [[ "$is_member" == "true" ]]; then
    log "Group membership already exists for ${display_name}"
    return 0
  fi

  log "Adding ${display_name} to group ${L4_SPN_GROUP_NAME}"
  local add_attempt max_add=6 add_wait=5
  for ((add_attempt=1; add_attempt<=max_add; add_attempt++)); do
    az ad group member add --group "$GROUP_OBJECT_ID" --member-id "$sp_object_id" >/dev/null 2>&1 && return 0
    [[ $add_attempt -lt $max_add ]] && sleep "$add_wait"
  done
  warn "Could not add ${display_name} to group after ${max_add} attempts; continuing"
}

ensure_role_assignment() {
  local sp_object_id="$1"
  local role_name="$2"
  local scope="$3"
  local exists

  exists=$(az role assignment list \
    --assignee-object-id "$sp_object_id" \
    --scope "$scope" \
    --query "[?roleDefinitionName=='${role_name}'] | length(@)" \
    -o tsv)

  if [[ "${exists:-0}" == "0" ]]; then
    log "Assigning role ${role_name} at scope ${scope}"
    az role assignment create \
      --assignee-object-id "$sp_object_id" \
      --assignee-principal-type ServicePrincipal \
      --role "$role_name" \
      --scope "$scope" \
      >/dev/null
    return 0
  fi

  log "Role ${role_name} already assigned at scope ${scope}"
}

rotate_secret() {
  local app_id="$1"
  local display_name="$2"
  local attempt max_attempts=6 wait_secs=10

  log "Rotating client secret for ${display_name}"
  for ((attempt=1; attempt<=max_attempts; attempt++)); do
    SECRET_VALUE=$(az ad app credential reset \
      --id "$app_id" \
      --display-name "${display_name}-bootstrap-key" \
      --years "$L4_SPN_SECRET_YEARS" \
      --query password \
      -o tsv 2>/dev/null || true)
    [[ -n "$SECRET_VALUE" ]] && return 0
    [[ $attempt -lt $max_attempts ]] && sleep "$wait_secs"
  done

  fail "Failed to generate a client secret for ${display_name}"
}

provision_spn() {
  local display_name_var="$1"
  local client_id_var="$2"
  local secret_var="$3"
  shift 3

  local display_name="${!display_name_var:-}"
  [[ -n "$display_name" ]] || fail "Missing display name variable ${display_name_var}"

  ensure_application "$display_name"
  ensure_service_principal "$display_name"
  ensure_group_membership "$SP_OBJECT_ID" "$display_name"

  local role_spec role_name scope
  for role_spec in "$@"; do
    role_name="${role_spec%%|*}"
    scope="${role_spec#*|}"
    ensure_role_assignment "$SP_OBJECT_ID" "$role_name" "$scope"
  done

  rotate_secret "$APP_ID" "$display_name"

  update_env_var "$display_name_var" "$display_name"
  update_env_var "$client_id_var" "$APP_ID"
  update_env_var "$secret_var" "$SECRET_VALUE"
}

require_command az
require_command python3
load_env

require_env_var AZ_DEPLOY_TENANT_ID
require_env_var AZ_DEPLOY_CLIENT_ID
require_env_var AZ_DEPLOY_CLIENT_SECRET
require_env_var AZ_SUBSCRIPTION_ID
require_env_var L4_RESOURCE_GROUP
require_env_var L4_AI_FOUNDRY_RESOURCE_GROUP
require_env_var L4_AI_FOUNDRY_PROJECT_NAME
require_env_var L4_AI_SEARCH_NAME
require_env_var L4_STORAGE_ACCOUNT_NAME
require_env_var L4_OBSERVABILITY_BLOB_STORAGE_ACCOUNT_NAME
require_env_var L4_RAG_SERVICE_SPN_DISPLAY_NAME
require_env_var L4_TIER1_APP_SPN_DISPLAY_NAME
require_env_var L4_TIER2_APP_SPN_DISPLAY_NAME
require_env_var L4_EVALUATION_RUNNER_SPN_DISPLAY_NAME
require_env_var L4_PYRIT_RUNNER_SPN_DISPLAY_NAME

L4_SPN_GROUP_NAME="${L4_SPN_GROUP_NAME:-aigoverndemogroup}"
L4_SPN_TAG_AI="${L4_SPN_TAG_AI:-SPN}"
L4_SPN_TAG_OWNER="${L4_SPN_TAG_OWNER:-ITBob@MngEnvMCAP029189.onmicrosoft.com}"
L4_SPN_SECRET_YEARS="${L4_SPN_SECRET_YEARS:-99}"
L4_RESOURCE_GROUP_SCOPE="/subscriptions/${AZ_SUBSCRIPTION_ID}/resourceGroups/${L4_RESOURCE_GROUP}"

login_as_deploy_spn
resolve_group_id

FOUNDRY_PROJECT_SCOPE=$(resolve_resource_scope \
  "$L4_AI_FOUNDRY_RESOURCE_GROUP" \
  "Microsoft.MachineLearningServices/workspaces" \
  "$L4_AI_FOUNDRY_PROJECT_NAME" \
  "Azure AI Foundry Project")

SEARCH_SCOPE=$(resolve_or_fallback_scope \
  "$L4_RESOURCE_GROUP" \
  "Microsoft.Search/searchServices" \
  "$L4_AI_SEARCH_NAME" \
  "Azure AI Search")

STORAGE_SCOPE=$(resolve_or_fallback_scope \
  "$L4_RESOURCE_GROUP" \
  "Microsoft.Storage/storageAccounts" \
  "$L4_STORAGE_ACCOUNT_NAME" \
  "Domain 4 storage account")

OBSERVABILITY_STORAGE_SCOPE=$(resolve_or_fallback_scope \
  "$L4_RESOURCE_GROUP" \
  "Microsoft.Storage/storageAccounts" \
  "$L4_OBSERVABILITY_BLOB_STORAGE_ACCOUNT_NAME" \
  "Observability storage account")

log "Provisioning Domain 4 runtime SPNs"

provision_spn \
  L4_RAG_SERVICE_SPN_DISPLAY_NAME \
  L4_RAG_SERVICE_CLIENT_ID \
  L4_RAG_SERVICE_CLIENT_SECRET \
  "Azure AI User|${FOUNDRY_PROJECT_SCOPE}" \
  "Search Index Data Reader|${SEARCH_SCOPE}" \
  "Search Index Data Contributor|${SEARCH_SCOPE}" \
  "Monitoring Metrics Publisher|${L4_RESOURCE_GROUP_SCOPE}" \
  "Storage Blob Data Reader|${STORAGE_SCOPE}" \
  "Storage Blob Data Contributor|${OBSERVABILITY_STORAGE_SCOPE}"

provision_spn \
  L4_TIER1_APP_SPN_DISPLAY_NAME \
  L4_TIER1_APP_CLIENT_ID \
  L4_TIER1_APP_CLIENT_SECRET \
  "Monitoring Metrics Publisher|${L4_RESOURCE_GROUP_SCOPE}" \
  "Storage Blob Data Contributor|${OBSERVABILITY_STORAGE_SCOPE}"

provision_spn \
  L4_TIER2_APP_SPN_DISPLAY_NAME \
  L4_TIER2_APP_CLIENT_ID \
  L4_TIER2_APP_CLIENT_SECRET \
  "Monitoring Metrics Publisher|${L4_RESOURCE_GROUP_SCOPE}" \
  "Storage Blob Data Contributor|${OBSERVABILITY_STORAGE_SCOPE}"

provision_spn \
  L4_EVALUATION_RUNNER_SPN_DISPLAY_NAME \
  L4_EVALUATION_RUNNER_CLIENT_ID \
  L4_EVALUATION_RUNNER_CLIENT_SECRET \
  "Azure AI User|${FOUNDRY_PROJECT_SCOPE}" \
  "Monitoring Metrics Publisher|${L4_RESOURCE_GROUP_SCOPE}" \
  "Storage Blob Data Contributor|${OBSERVABILITY_STORAGE_SCOPE}"

provision_spn \
  L4_PYRIT_RUNNER_SPN_DISPLAY_NAME \
  L4_PYRIT_RUNNER_CLIENT_ID \
  L4_PYRIT_RUNNER_CLIENT_SECRET \
  "Monitoring Metrics Publisher|${L4_RESOURCE_GROUP_SCOPE}" \
  "Storage Blob Data Contributor|${OBSERVABILITY_STORAGE_SCOPE}"

log "Domain 4 SPN bootstrap completed successfully"
