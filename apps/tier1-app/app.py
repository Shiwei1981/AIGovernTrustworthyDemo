"""AIGovernTrustworthyDemo Tier 1 consumer app for local development and APIM-backed testing."""

from __future__ import annotations

import json
import logging
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
    extract_foundry_assistant_text,
    http_call,
    is_callable_status,
    load_local_env,
    load_targets,
    make_request_id,
    mirror_governance_headers,
    parse_body_json,
    poll_foundry_run,
    repo_root,
    request_headers_map,
    resolve_app_credential,
    resolve_response_identity,
)
from apps.trace_chain_backend import query_trace_chain  # noqa: E402
from shared_observability import SourceType, TargetType, log_llm_call  # noqa: E402


load_local_env()

APP_NAME = os.getenv("L4_TIER1_APP_NAME", "AIGovernTrustworthyDemoTier1App")
SERVICE_NAME = os.getenv("L4_OTEL_SERVICE_NAME_TIER1_APP", "AIGovernTrustworthyDemo.Tier1App")
APIM_GATEWAY_URL = os.getenv("L4_APIM_GATEWAY_URL", "").rstrip("/")
APP_URL = os.getenv("L4_TIER1_APP_URL", "").strip().strip('"')
FOUNDY_ASSISTANT_ID = os.getenv("L4_FOUNDRY_AGENT_ID", "").strip().strip('"')
HTML_FILE = Path(__file__).with_name("mock-tier1-ui.html")

os.environ["OTEL_SERVICE_NAME"] = SERVICE_NAME

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)

ROUTES: dict[str, RouteDefinition] = {
    "rag": RouteDefinition(
        tab_id="rag",
        display_name="RAG API",
        target_id="AIGovernTrustworthyDemoRAGService",
        target_type="rag_service",
        downstream_path="/rag/responses",
        default_prompts=(
            "Summarize the NIST AI RMF govern function.",
            "Explain the difference between risk identification and mitigation.",
            "What governance evidence should be archived for an LLM app?",
        ),
    ),
    "foundry-agent": RouteDefinition(
        tab_id="foundry-agent",
        display_name="Foundry Agent API",
        target_id="AIGovernTrustworthyDemoFoundryAgent",
        target_type="foundry_agent",
        downstream_path="/foundry-agent",
        default_prompts=(
            "Outline an AI governance review workflow.",
            "Draft a policy summary for output trustworthiness.",
            "List evidence objects used in this project.",
        ),
        foundry_assistant_id=FOUNDY_ASSISTANT_ID,
    ),
    "vm-model": RouteDefinition(
        tab_id="vm-model",
        display_name="VM Model API",
        target_id="AIGovernTrustworthyDemoPhi3VM",
        target_type="vm_huggingface_model",
        downstream_path="/vm-model/v1/chat/completions",
        default_prompts=(
            "What are three important model governance controls?",
            "Explain why trace continuity matters for AI calls.",
            "Describe how a VM model differs from a project-backed model.",
        ),
    ),
    "native-model": RouteDefinition(
        tab_id="native-model",
        display_name="Native Model via Foundry Project",
        target_id="AIGovernTrustworthyDemoNativeModel",
        target_type="foundry_native_model",
        downstream_path="/native-model/chat/completions",
        default_prompts=(
            "Explain the core functions of NIST AI RMF.",
            "Summarize the EU AI Act risk categories.",
            "List three controls for trustworthy output handling.",
        ),
        model_name="gpt-5.4-mini",
    ),
    "finetune-model": RouteDefinition(
        tab_id="finetune-model",
        display_name="FineTune Model via Foundry Project",
        target_id="AIGovernTrustworthyDemoFineTuneModel",
        target_type="foundry_finetune_model",
        downstream_path="/finetune-model/chat/completions",
        default_prompts=(
            "Classify the governance maturity of this AI workflow.",
            "Provide a concise trustworthiness checklist.",
            "Write a governance-ready summary of the current call chain.",
        ),
        model_name="AIGovernTrustworthyDemoFineTuneModel",
    ),
}

_targets = load_targets()
_credential = resolve_app_credential(
    client_id_env="L4_TIER1_APP_CLIENT_ID",
    client_secret_env="L4_TIER1_APP_CLIENT_SECRET",
)

app = fastapi.FastAPI(title=APP_NAME)


def _target_record(route_id: str) -> Any:
    return _targets[ROUTES[route_id].target_id]


def _request_user(request: Request) -> dict[str, Any]:
    return current_user(request_headers_map(request.headers))


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
                "target_id": route.target_id,
                "target_type": route.target_type,
                "status": target.status,
                "default_prompts": list(route.default_prompts),
                "downstream_path": route.downstream_path,
                "assistant_id": route.foundry_assistant_id,
            }
        )
    return {
        "app": {
            "app_name": APP_NAME,
            "target_id": "AIGovernTrustworthyDemoTier1App",
            "target_type": "tier1_consumer",
            "service_name": SERVICE_NAME,
            "otel_service_name": SERVICE_NAME,
            "environment": app_environment(),
            "version": "step7-v1",
        },
        "user": user,
        "gateway": {
            "public_base_path": "/tier1",
            "apim_base_url": f"{APIM_GATEWAY_URL}/tier1" if APIM_GATEWAY_URL else "",
            "runtime_url": str(request.base_url).rstrip("/"),
        },
        "tabs": tabs,
    }


def _metadata_payload(request: Request) -> dict[str, Any]:
    bootstrap = _bootstrap_payload(request)
    return {
        "app": bootstrap["app"],
        "user": bootstrap["user"],
        "endpoints": {
            "health": "/api/health",
            "chat_rag": "/api/chat/rag",
            "chat_foundry_agent": "/api/chat/foundry-agent",
            "chat_vm_model": "/api/chat/vm-model",
            "chat_native_model": "/api/chat/native-model",
            "chat_finetune_model": "/api/chat/finetune-model",
            "targets": "/api/targets",
            "metadata": "/api/metadata",
        },
        "gateway": {
            **bootstrap["gateway"],
            "native_model_mode": "project_backed",
            "finetune_model_mode": "project_backed",
        },
        "targets": [
            {
                "tab_id": route_id,
                "display_name": route.display_name,
                "target_id": target.target_id,
                "target_type": target.target_type,
                "status": target.status,
                "apim_path": target.apim_path,
                "downstream_path": route.downstream_path,
                "endpoint": target.endpoint,
                "model_name": target.model_name,
                "model_version": target.model_version,
                "agent_id": target.agent_id,
            }
            for route_id, route in ROUTES.items()
            for target in [_target_record(route_id)]
        ],
    }


def _invocation_route(request: Request) -> str:
    return request.headers.get("X-Governance-Invocation-Route", "public_api")


def _forward_headers(request: Request, trace_context: Any, content_type: str = "application/json") -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Content-Type": content_type,
        "traceparent": trace_context.traceparent,
    }
    if trace_context.tracestate:
        headers["tracestate"] = trace_context.tracestate
    return headers


def _invoke_foundry_agent(raw_body: bytes, trace_context: Any) -> tuple[Any, Any, dict[str, str]]:
    base_url = f"{APIM_GATEWAY_URL}{ROUTES['foundry-agent'].downstream_path}"
    headers = _forward_headers(request=None, trace_context=trace_context)  # type: ignore[arg-type]
    create_run_result = http_call(
        url=f"{base_url}/threads/runs",
        method="POST",
        headers=headers,
        body=raw_body,
        timeout=120,
    )
    create_run_json = parse_body_json(create_run_result.body)
    if create_run_result.status_code >= 400:
        return create_run_result, create_run_json, {}
    if not isinstance(create_run_json, dict):
        return create_run_result, create_run_json, {}
    run_id = create_run_json.get("id")
    thread_id = create_run_json.get("thread_id")
    if not run_id or not thread_id:
        return create_run_result, create_run_json, {}
    run_result = poll_foundry_run(
        base_url=base_url,
        thread_id=thread_id,
        run_id=run_id,
        headers=headers,
        timeout_seconds=120,
    )
    run_json = parse_body_json(run_result.body)
    if run_result.status_code >= 400:
        return run_result, run_json, {"run_id": run_id, "thread_id": thread_id}
    if isinstance(run_json, dict) and run_json.get("status") != "completed":
        return run_result, run_json, {"run_id": run_id, "thread_id": thread_id}
    messages_result = http_call(
        url=f"{base_url}/threads/{thread_id}/messages",
        method="GET",
        headers=headers,
        timeout=60,
    )
    messages_json = parse_body_json(messages_result.body)
    return messages_result, messages_json, {"run_id": run_id, "thread_id": thread_id}


def _log_and_build_response(
    *,
    request: Request,
    route: RouteDefinition,
    raw_request_body: bytes,
    downstream_result: Any,
    downstream_json: Any,
    invocation_route: str,
    trace_context: Any,
    extra_attributes: dict[str, Any] | None = None,
) -> Response:
    target = _target_record(route.tab_id)
    parsed_request = parse_body_json(raw_request_body)
    response_id, model_name, model_version, citations_count = resolve_response_identity(route.target_type, downstream_json)
    if not model_name:
        model_name = target.model_name or route.model_name
    if not model_version:
        model_version = target.model_version

    if downstream_result.status_code >= 400:
        evidence = log_llm_call(
            service_name=SERVICE_NAME,
            source_type=SourceType.TIER1_CONSUMER,
            target_type=TargetType(route.target_type),
            target_id=route.target_id,
            target_endpoint=f"{APIM_GATEWAY_URL}{route.downstream_path}",
            llm_input=parsed_request,
            credential=_credential,
            error=downstream_json,
            model_name=model_name,
            model_version=model_version,
            trace_id=trace_context.trace_id,
            span_id=trace_context.span_id,
            citations_count=citations_count,
            extra_attributes={
                "invocation_route": invocation_route,
                "downstream_status_code": downstream_result.status_code,
                **(extra_attributes or {}),
            },
        )
    else:
        evidence = log_llm_call(
            service_name=SERVICE_NAME,
            source_type=SourceType.TIER1_CONSUMER,
            target_type=TargetType(route.target_type),
            target_id=route.target_id,
            target_endpoint=f"{APIM_GATEWAY_URL}{route.downstream_path}",
            llm_input=parsed_request,
            credential=_credential,
            llm_output=downstream_json,
            model_name=model_name,
            model_version=model_version,
            response_id=response_id,
            trace_id=trace_context.trace_id,
            span_id=trace_context.span_id,
            citations_count=citations_count,
            extra_attributes={
                "invocation_route": invocation_route,
                "downstream_status_code": downstream_result.status_code,
                **(extra_attributes or {}),
            },
        )

    governance_headers = build_governance_headers(
        request_id=make_request_id("tier1"),
        trace_id=trace_context.trace_id,
        target_id=route.target_id,
        target_type=route.target_type,
        service_name=SERVICE_NAME,
        archive_id=evidence.invocation.archive_id,
        payload_ref=evidence.invocation.payload_ref.input_blob_path.rsplit("/", 1)[0] + "/",
        response_id=response_id,
        model_name=model_name,
        model_version=model_version,
        invocation_route=invocation_route,
        downstream_status_code=downstream_result.status_code,
        downstream_request_id=downstream_result.headers.get("x-aigov-apim-request-id"),
    )
    content_type = downstream_result.headers.get("content-type", "application/json")
    return Response(
        content=downstream_result.body,
        status_code=downstream_result.status_code,
        media_type=content_type.split(";", 1)[0],
        headers=governance_headers,
    )


def _chat_impl(request: Request, route_id: str) -> Response:
    if route_id not in ROUTES:
        return JSONResponse({"error": f"Unsupported route: {route_id}"}, status_code=404)
    route = ROUTES[route_id]
    target = _target_record(route_id)
    if not is_callable_status(target.status):
        return JSONResponse(
            {
                "error": "Target is not ready",
                "target_id": target.target_id,
                "target_type": target.target_type,
                "status": target.status,
            },
            status_code=409,
        )
    raw_body = request.scope.get("_body")
    if raw_body is None:
        raw_body = b""
    trace_context = ensure_trace_context(request_headers_map(request.headers))
    invocation_route = _invocation_route(request)

    if route_id == "foundry-agent":
        downstream_result, downstream_json, extra = _invoke_foundry_agent(raw_body, trace_context)
        assistant_preview = extract_foundry_assistant_text(downstream_json)
        if assistant_preview:
            log.info("Foundry Agent response preview: %s", assistant_preview[:160])
        return _log_and_build_response(
            request=request,
            route=route,
            raw_request_body=raw_body,
            downstream_result=downstream_result,
            downstream_json=downstream_json,
            invocation_route=invocation_route,
            trace_context=trace_context,
            extra_attributes=extra,
        )

    downstream_result = http_call(
        url=f"{APIM_GATEWAY_URL}{route.downstream_path}",
        method="POST",
        headers=_forward_headers(request, trace_context, request.headers.get("content-type", "application/json")),
        body=raw_body,
        timeout=120,
    )
    downstream_json = parse_body_json(downstream_result.body)
    return _log_and_build_response(
        request=request,
        route=route,
        raw_request_body=raw_body,
        downstream_result=downstream_result,
        downstream_json=downstream_json,
        invocation_route=invocation_route,
        trace_context=trace_context,
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


@app.get("/api/targets")
def api_targets(request: Request) -> JSONResponse:
    return JSONResponse(_metadata_payload(request)["targets"])


@app.get("/api/health")
@app.get("/health")
def api_health() -> JSONResponse:
    return JSONResponse(
        {
            "status": "healthy",
            "app_name": APP_NAME,
            "service_name": SERVICE_NAME,
            "environment": app_environment(),
            "target_count": len(ROUTES),
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


_APP_INSIGHTS_NAME = os.getenv("L4_APP_INSIGHTS_NAME", "appinsights")
_APP_INSIGHTS_RG = os.getenv("L4_APP_INSIGHTS_RG", "AIGovernDemoRG")


@app.get("/api/trace/{trace_id}")
def api_trace(trace_id: str) -> JSONResponse:
    """Query App Insights + Blob for a trace and return structured call-chain data."""
    try:
        payload = query_trace_chain(trace_id=trace_id, credential=_credential, logger=log)
    except ValueError:
        return JSONResponse({"error": "Invalid trace_id"}, status_code=400)
    return JSONResponse(payload)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8011"))
    uvicorn.run(app, host="0.0.0.0", port=port)
