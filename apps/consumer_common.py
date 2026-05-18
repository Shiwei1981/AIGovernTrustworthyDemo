"""Shared local runtime helpers for Tier 1 and Tier 2 consumer apps."""

from __future__ import annotations

import base64
import json
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request
from uuid import uuid4

from azure.core.credentials import TokenCredential
from azure.identity import ClientSecretCredential, DefaultAzureCredential


REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env.local.L4"
TARGETS_FILE = REPO_ROOT / "infra" / "target-registry" / "targets.json"


@dataclass(frozen=True, slots=True)
class RouteDefinition:
    tab_id: str
    display_name: str
    target_id: str
    target_type: str
    downstream_path: str
    default_prompts: tuple[str, ...]
    model_name: str | None = None
    foundry_assistant_id: str | None = None


@dataclass(frozen=True, slots=True)
class TargetRecord:
    target_id: str
    target_type: str
    display_name: str
    endpoint: str | None
    apim_path: str | None
    status: str
    backend_url: str | None
    model_name: str | None
    model_version: str | None
    agent_id: str | None


@dataclass(frozen=True, slots=True)
class TraceContext:
    traceparent: str
    tracestate: str | None
    trace_id: str
    span_id: str


@dataclass(frozen=True, slots=True)
class HttpCallResult:
    status_code: int
    body: bytes
    headers: dict[str, str]


def load_local_env() -> None:
    if not ENV_FILE.exists():
        return
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name in os.environ:
            continue
        cleaned = value.strip()
        if cleaned[:1] in {'"', "'"}:
            quote = cleaned[0]
            end = cleaned.rfind(quote)
            cleaned = cleaned[1:end] if end > 0 else cleaned[1:]
        else:
            cleaned = cleaned.split("#", 1)[0].strip()
        os.environ[name] = cleaned


def load_targets() -> dict[str, TargetRecord]:
    data = json.loads(TARGETS_FILE.read_text(encoding="utf-8"))
    result: dict[str, TargetRecord] = {}
    for item in data["targets"]:
        record = TargetRecord(
            target_id=item["target_id"],
            target_type=item["target_type"],
            display_name=item.get("display_name", item["target_id"]),
            endpoint=item.get("endpoint"),
            apim_path=item.get("apim_path"),
            status=item.get("status", "pending"),
            backend_url=item.get("backend_url"),
            model_name=item.get("model_name"),
            model_version=item.get("model_version"),
            agent_id=item.get("agent_id"),
        )
        result[record.target_id] = record
    return result


def is_callable_status(status: str) -> bool:
    return status in {"active", "ready"}


def current_user(request_headers: dict[str, str]) -> dict[str, Any]:
    principal_name = request_headers.get("x-ms-client-principal-name", "").strip()
    if principal_name:
        return {
            "is_authenticated": True,
            "display_name": principal_name,
            "auth_mode": "easyauth",
        }
    encoded_principal = request_headers.get("x-ms-client-principal", "").strip()
    if encoded_principal:
        try:
            payload = json.loads(base64.b64decode(encoded_principal).decode("utf-8"))
            claims = payload.get("claims", [])
            preferred_username = next(
                (claim["val"] for claim in claims if claim.get("typ") in {"preferred_username", "upn"}),
                None,
            )
            if preferred_username:
                return {
                    "is_authenticated": True,
                    "display_name": preferred_username,
                    "auth_mode": "easyauth",
                }
        except Exception:
            pass
    local_user = os.getenv("USER", "local-dev")
    return {
        "is_authenticated": False,
        "display_name": local_user,
        "auth_mode": "local_dev",
    }


def request_headers_map(headers: Any) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in headers.items()}


def make_request_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def ensure_trace_context(request_headers: dict[str, str]) -> TraceContext:
    incoming = request_headers.get("traceparent", "").strip()
    tracestate = request_headers.get("tracestate", "").strip() or None
    if incoming:
        parts = incoming.split("-")
        if len(parts) == 4 and len(parts[1]) == 32 and len(parts[2]) == 16:
            return TraceContext(
                traceparent=incoming,
                tracestate=tracestate,
                trace_id=parts[1],
                span_id=parts[2],
            )
    trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)
    return TraceContext(
        traceparent=f"00-{trace_id}-{span_id}-01",
        tracestate=tracestate,
        trace_id=trace_id,
        span_id=span_id,
    )


def http_call(
    *,
    url: str,
    method: str,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = 90,
) -> HttpCallResult:
    request = urllib_request.Request(
        url,
        data=body,
        headers=headers or {},
        method=method,
    )
    try:
        with urllib_request.urlopen(request, timeout=timeout) as response:
            return HttpCallResult(
                status_code=response.status,
                body=response.read(),
                headers={key.lower(): value for key, value in response.headers.items()},
            )
    except urllib_error.HTTPError as exc:
        return HttpCallResult(
            status_code=exc.code,
            body=exc.read(),
            headers={key.lower(): value for key, value in exc.headers.items()},
        )


def parse_body_json(body: bytes) -> Any:
    if not body:
        return None
    text = body.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_text": text}


def resolve_response_identity(target_type: str, body_json: Any) -> tuple[str | None, str | None, str | None, int | None]:
    if not isinstance(body_json, dict):
        return None, None, None, None
    response_id = body_json.get("id") or body_json.get("response_id")
    model_name = body_json.get("model")
    model_version = body_json.get("model_version")
    citations_count: int | None = None
    citations = body_json.get("citations")
    if isinstance(citations, list):
        citations_count = len(citations)
    if target_type == "foundry_agent":
        data = body_json.get("data")
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("role") == "assistant":
                    response_id = item.get("id") or response_id
                    break
    return response_id, model_name, model_version, citations_count


def extract_foundry_assistant_text(messages_payload: Any) -> str | None:
    if not isinstance(messages_payload, dict):
        return None
    items = messages_payload.get("data")
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict) or item.get("role") != "assistant":
            continue
        contents = item.get("content")
        if not isinstance(contents, list):
            continue
        parts: list[str] = []
        for content in contents:
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, dict) and isinstance(text.get("value"), str):
                parts.append(text["value"])
        if parts:
            return "\n".join(parts)
    return None


def build_governance_headers(
    *,
    request_id: str,
    trace_id: str,
    target_id: str,
    target_type: str,
    service_name: str,
    archive_id: str | None = None,
    payload_ref: str | None = None,
    response_id: str | None = None,
    model_name: str | None = None,
    model_version: str | None = None,
    invocation_route: str | None = None,
    downstream_status_code: int | None = None,
    downstream_request_id: str | None = None,
    prefix: str = "X-Governance",
) -> dict[str, str]:
    values = {
        f"{prefix}-Request-Id": request_id,
        f"{prefix}-Trace-Id": trace_id,
        f"{prefix}-Target-Id": target_id,
        f"{prefix}-Target-Type": target_type,
        f"{prefix}-Service-Name": service_name,
        f"{prefix}-Archive-Id": archive_id,
        f"{prefix}-Payload-Ref": payload_ref,
        f"{prefix}-Response-Id": response_id,
        f"{prefix}-Model-Name": model_name,
        f"{prefix}-Model-Version": model_version,
        f"{prefix}-Invocation-Route": invocation_route,
        f"{prefix}-Downstream-Status-Code": str(downstream_status_code) if downstream_status_code is not None else None,
        f"{prefix}-Downstream-Request-Id": downstream_request_id,
    }
    return {key: value for key, value in values.items() if value}


def mirror_governance_headers(downstream_headers: dict[str, str], *, prefix: str) -> dict[str, str]:
    mirrored: dict[str, str] = {}
    for key, value in downstream_headers.items():
        lowered = key.lower()
        if not lowered.startswith("x-governance-"):
            continue
        suffix = lowered[len("x-governance-") :]
        mirrored[f"{prefix}-{suffix.title()}"] = value
    return mirrored


def app_environment() -> str:
    if os.getenv("WEBSITE_INSTANCE_ID"):
        return "webapp"
    return "local"


def repo_root() -> Path:
    return REPO_ROOT


def resolve_app_credential(*, client_id_env: str, client_secret_env: str) -> TokenCredential:
    runtime_tenant_id = os.getenv("AZ_RUNTIME_TENANT_ID", "").strip()
    runtime_client_id = os.getenv("AZ_RUNTIME_CLIENT_ID", "").strip()
    runtime_client_secret = os.getenv("AZ_RUNTIME_CLIENT_SECRET", "").strip()
    if runtime_tenant_id and runtime_client_id and runtime_client_secret:
        return ClientSecretCredential(
            tenant_id=runtime_tenant_id,
            client_id=runtime_client_id,
            client_secret=runtime_client_secret,
        )

    tenant_id = os.getenv("AZURE_TENANT_ID", "").strip()
    client_id = os.getenv(client_id_env, "").strip()
    client_secret = os.getenv(client_secret_env, "").strip()
    if tenant_id and client_id and client_secret:
        return ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )

    return DefaultAzureCredential(
        exclude_visual_studio_code_credential=True,
        exclude_shared_token_cache_credential=True,
    )


def read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def poll_foundry_run(
    *,
    base_url: str,
    thread_id: str,
    run_id: str,
    headers: dict[str, str],
    timeout_seconds: int = 120,
) -> HttpCallResult:
    deadline = time.time() + timeout_seconds
    last_result: HttpCallResult | None = None
    while time.time() < deadline:
        last_result = http_call(
            url=f"{base_url}/threads/{thread_id}/runs/{run_id}",
            method="GET",
            headers=headers,
            timeout=60,
        )
        if last_result.status_code >= 400:
            return last_result
        payload = parse_body_json(last_result.body)
        if isinstance(payload, dict) and payload.get("status") in {"completed", "failed", "cancelled", "expired"}:
            return last_result
        time.sleep(2)
    return last_result or HttpCallResult(status_code=504, body=b'{"error":"run poll timeout"}', headers={})
