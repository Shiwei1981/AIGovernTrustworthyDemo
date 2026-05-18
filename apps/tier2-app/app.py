"""AIGovernTrustworthyDemo Tier 2 consumer app for local development and two-hop testing."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import fastapi
import uvicorn
from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SHARED_OBSERVABILITY_ROOT = REPO_ROOT / "packages" / "shared-observability"
if str(SHARED_OBSERVABILITY_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_OBSERVABILITY_ROOT))

from apps.consumer_common import (  # noqa: E402
    RouteDefinition,
    app_environment,
    build_governance_headers,
    current_user,
    ensure_trace_context,
    http_call,
    load_local_env,
    load_targets,
    make_request_id,
    parse_body_json,
    request_headers_map,
    resolve_app_credential,
    resolve_response_identity,
)
from apps.trace_chain_backend import query_trace_chain  # noqa: E402
from shared_observability import SourceType, TargetType, log_llm_call  # noqa: E402


load_local_env()

APP_NAME = os.getenv("L4_TIER2_APP_NAME", "AIGovernTrustworthyDemoTier2App")
SERVICE_NAME = os.getenv("L4_OTEL_SERVICE_NAME_TIER2_APP", "AIGovernTrustworthyDemo.Tier2App")
APP_URL = os.getenv("L4_TIER2_APP_URL", "").strip().strip('"')
TIER1_LOCAL_BASE_URL = os.getenv("L4_TIER1_LOCAL_BASE_URL", "http://127.0.0.1:8011").rstrip("/")
TIER1_APIM_BASE_URL = f"{os.getenv('L4_APIM_GATEWAY_URL', '').rstrip('/')}/tier1"
TIER1_DOWNSTREAM_BASE_URL = os.getenv("L4_TIER1_DOWNSTREAM_BASE_URL", TIER1_LOCAL_BASE_URL).rstrip("/")
HTML_FILE = Path(__file__).with_name("mock-tier2-ui.html")
FOUNDRY_ASSISTANT_ID = os.getenv("L4_FOUNDRY_AGENT_ID", "").strip().strip('"')

os.environ["OTEL_SERVICE_NAME"] = SERVICE_NAME

ROUTES: dict[str, RouteDefinition] = {
    "rag": RouteDefinition(
        tab_id="rag",
        display_name="RAG API",
        target_id="AIGovernTrustworthyDemoRAGService",
        target_type="rag_service",
        downstream_path="/api/chat/rag",
        default_prompts=(
            "Summarize the govern function of NIST AI RMF.",
            "What evidence should be retained for a RAG answer?",
            "How should retrieval governance be explained to auditors?",
        ),
    ),
    "foundry-agent": RouteDefinition(
        tab_id="foundry-agent",
        display_name="Foundry Agent API",
        target_id="AIGovernTrustworthyDemoFoundryAgent",
        target_type="foundry_agent",
        downstream_path="/api/chat/foundry-agent",
        default_prompts=(
            "Draft a governance review summary.",
            "Outline a human-in-the-loop escalation flow.",
            "Explain why downstream API shapes must stay explicit.",
        ),
        foundry_assistant_id=FOUNDRY_ASSISTANT_ID,
    ),
    "vm-model": RouteDefinition(
        tab_id="vm-model",
        display_name="VM Model API",
        target_id="AIGovernTrustworthyDemoPhi3VM",
        target_type="vm_huggingface_model",
        downstream_path="/api/chat/vm-model",
        default_prompts=(
            "Compare VM-hosted model governance with managed model governance.",
            "Why should authorization headers be removed before forwarding to the VM?",
            "Explain a trace_id based debugging workflow.",
        ),
    ),
    "native-model": RouteDefinition(
        tab_id="native-model",
        display_name="Native Model via Foundry Project",
        target_id="AIGovernTrustworthyDemoNativeModel",
        target_type="foundry_native_model",
        downstream_path="/api/chat/native-model",
        default_prompts=(
            "Explain the core functions of NIST AI RMF.",
            "Summarize the AI Act risk categories.",
            "List three governance controls for LLM apps.",
        ),
    ),
    "finetune-model": RouteDefinition(
        tab_id="finetune-model",
        display_name="FineTune Model via Foundry Project",
        target_id="AIGovernTrustworthyDemoFineTuneModel",
        target_type="foundry_finetune_model",
        downstream_path="/api/chat/finetune-model",
        default_prompts=(
            "Classify a governance failure scenario.",
            "Generate a concise trustworthiness checklist.",
            "Explain why app-only auth is used for Tier 2 to Tier 1.",
        ),
    ),
}

_targets = load_targets()
_observability_credential = resolve_app_credential(
    client_id_env="L4_TIER2_APP_CLIENT_ID",
    client_secret_env="L4_TIER2_APP_CLIENT_SECRET",
)

app = fastapi.FastAPI(title=APP_NAME)


def _target_record(route_id: str) -> Any:
    return _targets[ROUTES[route_id].target_id]


def _request_user(request: Request) -> dict[str, Any]:
    return current_user(request_headers_map(request.headers))


def _tier1_forward_headers(request: Request, trace_context: Any) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Content-Type": request.headers.get("content-type", "application/json"),
        "traceparent": trace_context.traceparent,
        "X-Governance-Upstream-App": "tier2_consumer",
        "X-Governance-Invocation-Route": "public_api",
    }
    if trace_context.tracestate:
        headers["tracestate"] = trace_context.tracestate
    scope = f"api://{os.getenv('L4_TIER1_APP_CLIENT_ID', '').strip()}/.default"
    if scope != "api:///.default":
        token = _observability_credential.get_token(scope).token
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _bootstrap_payload(request: Request) -> dict[str, Any]:
    user = _request_user(request)
    tabs = []
    for route_id, route in ROUTES.items():
        target = _target_record(route_id)
        tabs.append(
            {
                "tab_id": route_id,
                "display_name": route.display_name,
                "api_path": f"/api/chat/{route_id}",
                "tier1_forward_path": f"/tier1/api/chat/{route_id}",
                "target_id": route.target_id,
                "final_target_type": route.target_type,
                "status": target.status,
                "default_prompts": list(route.default_prompts),
                "assistant_id": route.foundry_assistant_id,
            }
        )
    return {
        "app": {
            "app_name": APP_NAME,
            "target_id": "AIGovernTrustworthyDemoTier2App",
            "target_type": "tier2_consumer",
            "service_name": SERVICE_NAME,
            "otel_service_name": SERVICE_NAME,
            "environment": app_environment(),
            "version": "step7-v1",
        },
        "user": user,
        "gateway": {
            "public_base_path": "/tier2",
            "tier1_base_url": TIER1_DOWNSTREAM_BASE_URL,
            "tier1_apim_base_url": TIER1_APIM_BASE_URL,
            "runtime_url": str(request.base_url).rstrip("/"),
        },
        "tier1_dependency": {
            "target_id": "AIGovernTrustworthyDemoTier1App",
            "target_type": "tier1_consumer",
            "status": _targets["AIGovernTrustworthyDemoTier1App"].status,
        },
        "tabs": tabs,
    }


def _metadata_payload(request: Request) -> dict[str, Any]:
    bootstrap = _bootstrap_payload(request)
    return {
        "app": bootstrap["app"],
        "user": bootstrap["user"],
        "gateway": bootstrap["gateway"],
        "tier1_dependency": bootstrap["tier1_dependency"],
        "endpoints": {
            "health": "/api/health",
            "chat_rag": "/api/chat/rag",
            "chat_foundry_agent": "/api/chat/foundry-agent",
            "chat_vm_model": "/api/chat/vm-model",
            "chat_native_model": "/api/chat/native-model",
            "chat_finetune_model": "/api/chat/finetune-model",
            "metadata": "/api/metadata",
        },
        "targets": [
            {
                "tab_id": route_id,
                "display_name": route.display_name,
                "tier1_forward_path": f"/tier1/api/chat/{route_id}",
                "target_id": target.target_id,
                "target_type": target.target_type,
                "status": target.status,
                "model_name": target.model_name,
                "model_version": target.model_version,
                "assistant_id": route.foundry_assistant_id,
            }
            for route_id, route in ROUTES.items()
            for target in [_target_record(route_id)]
        ],
    }


def _downstream_headers_for_ui(downstream_headers: dict[str, str]) -> dict[str, str]:
    mappings = {
        "x-governance-request-id": "X-Governance-Downstream-Request-Id",
        "x-governance-trace-id": "X-Governance-Downstream-Trace-Id",
        "x-governance-target-id": "X-Governance-Downstream-Target-Id",
        "x-governance-target-type": "X-Governance-Downstream-Target-Type",
        "x-governance-service-name": "X-Governance-Downstream-Service-Name",
        "x-governance-archive-id": "X-Governance-Downstream-Archive-Id",
        "x-governance-payload-ref": "X-Governance-Downstream-Payload-Ref",
        "x-governance-response-id": "X-Governance-Downstream-Response-Id",
        "x-governance-model-name": "X-Governance-Downstream-Model-Name",
        "x-governance-model-version": "X-Governance-Downstream-Model-Version",
    }
    return {
        target_name: downstream_headers[source_name]
        for source_name, target_name in mappings.items()
        if source_name in downstream_headers and downstream_headers[source_name]
    }


def _invocation_route(request: Request) -> str:
    return request.headers.get("X-Governance-Invocation-Route", "public_api")


def _chat_impl(request: Request, route_id: str) -> Response:
    route = ROUTES[route_id]
    raw_body = request.scope.get("_body") or b""
    trace_context = ensure_trace_context(request_headers_map(request.headers))
    invocation_route = _invocation_route(request)
    downstream_url = f"{TIER1_DOWNSTREAM_BASE_URL}{route.downstream_path}"
    downstream_result = http_call(
        url=downstream_url,
        method="POST",
        headers=_tier1_forward_headers(request, trace_context),
        body=raw_body,
        timeout=180,
    )
    downstream_json = parse_body_json(downstream_result.body)
    response_id, model_name, model_version, citations_count = resolve_response_identity(
        route.target_type,
        downstream_json,
    )
    parsed_request = parse_body_json(raw_body)

    if downstream_result.status_code >= 400:
        evidence = log_llm_call(
            service_name=SERVICE_NAME,
            source_type=SourceType.TIER2_CONSUMER,
            target_type=TargetType.TIER1_CONSUMER,
            target_id="AIGovernTrustworthyDemoTier1App",
            target_endpoint=downstream_url,
            llm_input=parsed_request,
            credential=_observability_credential,
            error=downstream_json,
            trace_id=trace_context.trace_id,
            span_id=trace_context.span_id,
            extra_attributes={
                "invocation_route": invocation_route,
                "final_target_id": route.target_id,
                "final_target_type": route.target_type,
                "downstream_status_code": downstream_result.status_code,
            },
        )
    else:
        evidence = log_llm_call(
            service_name=SERVICE_NAME,
            source_type=SourceType.TIER2_CONSUMER,
            target_type=TargetType.TIER1_CONSUMER,
            target_id="AIGovernTrustworthyDemoTier1App",
            target_endpoint=downstream_url,
            llm_input=parsed_request,
            credential=_observability_credential,
            llm_output=downstream_json,
            response_id=response_id,
            model_name=model_name,
            model_version=model_version,
            trace_id=trace_context.trace_id,
            span_id=trace_context.span_id,
            citations_count=citations_count,
            extra_attributes={
                "invocation_route": invocation_route,
                "final_target_id": route.target_id,
                "final_target_type": route.target_type,
                "downstream_status_code": downstream_result.status_code,
            },
        )

    governance_headers = build_governance_headers(
        request_id=make_request_id("tier2"),
        trace_id=trace_context.trace_id,
        target_id="AIGovernTrustworthyDemoTier1App",
        target_type="tier1_consumer",
        service_name=SERVICE_NAME,
        archive_id=evidence.invocation.archive_id,
        payload_ref=evidence.invocation.payload_ref.input_blob_path.rsplit("/", 1)[0] + "/",
        response_id=response_id,
        model_name=model_name,
        model_version=model_version,
        invocation_route=invocation_route,
        downstream_status_code=downstream_result.status_code,
        downstream_request_id=downstream_result.headers.get("x-governance-request-id"),
    )
    governance_headers.update(_downstream_headers_for_ui(downstream_result.headers))
    content_type = downstream_result.headers.get("content-type", "application/json")
    return Response(
        content=downstream_result.body,
        status_code=downstream_result.status_code,
        media_type=content_type.split(";", 1)[0],
        headers=governance_headers,
    )


@app.middleware("http")
async def capture_body(request: Request, call_next: Any) -> Response:
    request.scope["_body"] = await request.body()
    return await call_next(request)


@app.get("/", response_class=HTMLResponse)
def root() -> RedirectResponse:
    return RedirectResponse(url="/app", status_code=307)


@app.get("/app", response_class=HTMLResponse)
def app_page() -> FileResponse:
    return FileResponse(HTML_FILE)


@app.get("/static/{path:path}")
def static_file(path: str) -> Response:
    file_path = Path(__file__).parent / "static" / path
    if not file_path.exists():
        return JSONResponse({"error": "Static file not found"}, status_code=404)
    return FileResponse(file_path)


@app.get("/ui/bootstrap")
def ui_bootstrap(request: Request) -> JSONResponse:
    return JSONResponse(_bootstrap_payload(request))


@app.get("/ui/metadata")
def ui_metadata(request: Request) -> JSONResponse:
    return JSONResponse(_metadata_payload(request))


@app.get("/api/metadata")
def api_metadata(request: Request) -> JSONResponse:
    return JSONResponse(_metadata_payload(request))


@app.get("/api/health")
@app.get("/health")
def api_health() -> JSONResponse:
    return JSONResponse(
        {
            "status": "healthy",
            "app_name": APP_NAME,
            "service_name": SERVICE_NAME,
            "environment": app_environment(),
            "tier1_base_url": TIER1_DOWNSTREAM_BASE_URL,
            "app_url": APP_URL,
        }
    )


@app.post("/api/chat/rag")
def chat_rag(request: Request) -> Response:
    return _chat_impl(request, "rag")


@app.post("/api/chat/foundry-agent")
def chat_foundry_agent(request: Request) -> Response:
    return _chat_impl(request, "foundry-agent")


@app.post("/api/chat/vm-model")
def chat_vm_model(request: Request) -> Response:
    return _chat_impl(request, "vm-model")


@app.post("/api/chat/native-model")
def chat_native_model(request: Request) -> Response:
    return _chat_impl(request, "native-model")


@app.post("/api/chat/finetune-model")
def chat_finetune_model(request: Request) -> Response:
    return _chat_impl(request, "finetune-model")


@app.get("/api/trace/{trace_id}")
def api_trace(trace_id: str) -> Response:
    """Query App Insights + Blob directly for a trace and return structured call-chain data."""
    try:
        payload = query_trace_chain(trace_id=trace_id, credential=_observability_credential)
    except ValueError:
        return JSONResponse({"error": "Invalid trace_id"}, status_code=400)
    return JSONResponse(payload)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8012"))
    uvicorn.run(app, host="0.0.0.0", port=port)
