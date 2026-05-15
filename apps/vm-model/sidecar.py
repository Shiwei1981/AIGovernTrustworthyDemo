from __future__ import annotations

import json
import logging
import os
import time
from typing import Mapping
from urllib import error as urllib_error
from urllib import request as urllib_request

from fastapi import FastAPI, HTTPException, Request, Response
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)

EVENT_NAME = "AIGovernTrustworthyVMModelTrace"
TARGET_TYPE = "vm_huggingface_model"
TARGET_ID = os.getenv("L4_VM_NAME", "AIGovernTrustworthyDemoPhi3VM")
MODEL_NAME = os.getenv("L4_VM_MODEL_NAME", "Phi-3-mini-4k-instruct")
MODEL_VERSION = os.getenv("L4_VM_MODEL_VERSION", "unknown")
SERVICE_NAME = os.getenv("L4_OTEL_SERVICE_NAME_VM_MODEL", "AIGovernTrustworthyDemo.VMModel")
LLAMA_SERVER_BASE_URL = os.getenv("LLAMA_SERVER_BASE_URL", "http://127.0.0.1:11435").rstrip("/")
APPLICATIONINSIGHTS_CONNECTION_STRING = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()

os.environ["OTEL_SERVICE_NAME"] = SERVICE_NAME

app = FastAPI(title="AIGovernTrustworthyDemo VM Model Sidecar")


def _require_env(name: str, value: str) -> str:
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _build_tracer():
    from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

    connection_string = _require_env(
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        APPLICATIONINSIGHTS_CONNECTION_STRING,
    )
    resource = Resource.create({"service.name": SERVICE_NAME})
    provider = TracerProvider(resource=resource)
    exporter = AzureMonitorTraceExporter(
        connection_string=connection_string,
        tracer_provider=provider,
    )
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("vm-model.sidecar")


TRACER = _build_tracer()


def _trace_context_from_headers(headers: Mapping[str, str]):
    traceparent = headers.get("traceparent", "").strip()
    if not traceparent:
        return None

    parts = traceparent.split("-")
    if len(parts) != 4:
        return None

    _, trace_id, span_id, flags = parts
    if len(trace_id) != 32 or len(span_id) != 16 or len(flags) != 2:
        return None

    try:
        parent_ctx = SpanContext(
            trace_id=int(trace_id, 16),
            span_id=int(span_id, 16),
            is_remote=True,
            trace_flags=TraceFlags(int(flags, 16)),
        )
    except ValueError:
        return None

    return trace.set_span_in_context(NonRecordingSpan(parent_ctx))


def _downstream_headers(headers: Mapping[str, str]) -> dict[str, str]:
    blocked = {
        "accept-encoding",
        "authorization",
        "connection",
        "content-length",
        "host",
        "transfer-encoding",
    }
    return {name: value for name, value in headers.items() if name.lower() not in blocked}


def _proxy_request(*, method: str, path: str, body: bytes | None, headers: Mapping[str, str]):
    url = f"{LLAMA_SERVER_BASE_URL}{path}"
    request_headers = _downstream_headers(headers)
    proxy_request = urllib_request.Request(url, data=body, headers=request_headers, method=method)

    try:
        with urllib_request.urlopen(proxy_request, timeout=300) as upstream:
            return upstream.status, upstream.headers.get("Content-Type", "application/octet-stream"), upstream.read()
    except urllib_error.HTTPError as exc:
        return exc.code, exc.headers.get("Content-Type", "text/plain; charset=utf-8"), exc.read()
    except urllib_error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise HTTPException(status_code=502, detail=f"Downstream llama-server unavailable: {reason}") from exc


def _extract_response_id(content_type: str, payload: bytes) -> str | None:
    if "application/json" not in content_type.lower():
        return None
    try:
        body = json.loads(payload)
    except json.JSONDecodeError:
        return None

    response_id = body.get("id")
    return response_id if isinstance(response_id, str) else None


def _emit_trace_event(*, headers: Mapping[str, str], response_id: str | None, status_code: int, latency_ms: int) -> None:
    parent_context = _trace_context_from_headers(headers)
    attrs: dict[str, str | int] = {
        "target_type": TARGET_TYPE,
        "target_id": TARGET_ID,
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "service_name": SERVICE_NAME,
        "status": "success" if 200 <= status_code < 400 else "error",
        "status_code": status_code,
        "latency_ms": latency_ms,
    }

    with TRACER.start_as_current_span("vm-model.chat_completions", context=parent_context) as span:
        span_context = span.get_span_context()
        attrs["trace_id"] = f"{span_context.trace_id:032x}"
        attrs["span_id"] = f"{span_context.span_id:016x}"
        if response_id:
            attrs["response_id"] = response_id
        span.add_event(EVENT_NAME, attributes=attrs)


@app.get("/health")
async def health(request: Request) -> Response:
    status_code, content_type, body = _proxy_request(
        method="GET",
        path="/health",
        body=None,
        headers=request.headers,
    )
    return Response(content=body, status_code=status_code, headers={"content-type": content_type})


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Response:
    body = await request.body()
    start = time.perf_counter()
    status_code, content_type, response_body = _proxy_request(
        method="POST",
        path="/v1/chat/completions",
        body=body,
        headers=request.headers,
    )
    latency_ms = int((time.perf_counter() - start) * 1000)
    response_id = _extract_response_id(content_type, response_body)

    try:
        _emit_trace_event(
            headers=request.headers,
            response_id=response_id,
            status_code=status_code,
            latency_ms=latency_ms,
        )
    except Exception:
        log.exception("Failed to emit App Insights trace event")

    return Response(content=response_body, status_code=status_code, headers={"content-type": content_type})
