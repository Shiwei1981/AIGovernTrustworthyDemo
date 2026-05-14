"""Minimal public API for shared observability evidence logging."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import urlparse
from uuid import uuid4

if TYPE_CHECKING:
    from azure.core.credentials import TokenCredential

from .config import ObservabilitySettings, load_settings_from_env
from ._archive import write_evidence_archive
from ._telemetry import emit_evidence_event
from .schema import (
    AIInvocationArchiveRef,
    AIInvocationRecord,
    AIInvocationStatus,
    BlobArchiveLayout,
    EvidenceRecord,
    EventNames,
    SourceType,
    TargetType,
    TelemetryScalar,
)
from .errors import ValidationError
from .serializers import to_stable_json_bytes, to_jsonable


def log_llm_call(
    *,
    service_name: str,
    target_type: str | TargetType,
    target_id: str,
    target_endpoint: str,
    llm_input: object,
    credential: "TokenCredential",
    llm_output: object | None = None,
    error: object | None = None,
    model_name: str | None = None,
    model_version: str | None = None,
    source_type: str | SourceType | None = None,
    response_id: str | None = None,
    settings: ObservabilitySettings | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
    occurred_at: datetime | None = None,
    test_tool: str | None = None,
    test_run_id: str | None = None,
    citations_count: int | None = None,
    extra_attributes: dict[str, TelemetryScalar] | None = None,
) -> EvidenceRecord:
    """Build evidence payloads and event attributes for a single LLM call.

    ``credential`` must be supplied by the calling application.  This component
    does not own an Azure identity and does not read SPN information from the
    environment.  The caller constructs the appropriate ``TokenCredential``
    (e.g. ``ClientSecretCredential`` or ``ManagedIdentityCredential``) and
    passes it here.  The component only consumes it; it does not cache or renew
    it.
    """

    if (llm_output is None) == (error is None):
        raise ValidationError("Exactly one of llm_output or error must be provided")

    active_settings = settings or load_settings_from_env()
    active_time = (occurred_at or datetime.now(UTC)).astimezone(UTC)
    resolved_target_type = TargetType(target_type)
    resolved_source_type = SourceType(source_type) if source_type is not None else None
    current_trace_id, current_span_id = _read_current_trace_context()
    archive_id = uuid4().hex
    blob_layout = BlobArchiveLayout(prefix=active_settings.blob.prefix)
    input_blob_path, output_blob_path, metadata_blob_path = blob_layout.build_paths(
        service_name=service_name,
        target_type=resolved_target_type,
        archive_id=archive_id,
        occurred_at=active_time,
    )
    archive_ref = AIInvocationArchiveRef(
        container=active_settings.blob.container,
        prefix=active_settings.blob.prefix,
        input_blob_path=input_blob_path,
        output_blob_path=output_blob_path,
        metadata_blob_path=metadata_blob_path,
    )
    record = AIInvocationRecord(
        service_name=service_name,
        target_type=resolved_target_type,
        target_id=target_id,
        target_endpoint=target_endpoint,
        trace_id=trace_id or current_trace_id,
        span_id=span_id or current_span_id,
        archive_id=archive_id,
        response_id=response_id,
        status=AIInvocationStatus.SUCCEEDED if error is None else AIInvocationStatus.FAILED,
        occurred_at=active_time,
        payload_ref=archive_ref,
        model_name=model_name,
        model_version=model_version,
        source_type=resolved_source_type,
        test_tool=test_tool,
        test_run_id=test_run_id,
        citations_count=citations_count,
        extra_properties=dict(extra_attributes or {}),
    )
    metadata_payload = {
        **to_jsonable(asdict(record)),
        "event_name": EventNames.LLM_EVIDENCE,
    }
    ev_record = EvidenceRecord(
        invocation=record,
        event_name=EventNames.LLM_EVIDENCE,
        event_attributes=_build_event_attributes(record),
        input_payload=to_stable_json_bytes(llm_input),
        output_payload=to_stable_json_bytes(llm_output if error is None else {"error": error}),
        metadata_payload=to_stable_json_bytes(metadata_payload),
    )

    # Write full evidence payloads to Blob archive (Blob first — R-013)
    write_evidence_archive(
        account_name=active_settings.blob.account_name,
        container=active_settings.blob.container,
        credential=credential,
        input_path=archive_ref.input_blob_path,
        output_path=archive_ref.output_blob_path,
        metadata_path=archive_ref.metadata_blob_path,
        input_bytes=ev_record.input_payload,
        output_bytes=ev_record.output_payload,
        metadata_bytes=ev_record.metadata_payload,
    )

    # Emit thin index event to App Insights so it can be joined with traces (R-006)
    emit_evidence_event(
        connection_string=active_settings.telemetry.connection_string,
        credential=credential,
        event_name=EventNames.LLM_EVIDENCE,
        attributes=ev_record.event_attributes,
        trace_id=record.trace_id,
        span_id=record.span_id,
    )

    return ev_record


def _build_event_attributes(record: AIInvocationRecord) -> dict[str, TelemetryScalar]:
    server_address = urlparse(record.target_endpoint).netloc or None
    archive_root = record.payload_ref.input_blob_path.rsplit("/", 1)[0] + "/"
    return {
        "trace_id": record.trace_id,
        "span_id": record.span_id,
        "service.name": record.service_name,
        "server.address": server_address,
        "gen_ai.operation.name": _infer_operation_name(record.target_endpoint),
        "gen_ai.request.model": record.model_name,
        "gen_ai.response.id": record.response_id,
        "aigov.archive.id": record.archive_id,
        "aigov.payload.ref": archive_root,
        "aigov.target.type": record.target_type.value,
        "aigov.target.id": record.target_id,
        "aigov.source.type": record.source_type.value if record.source_type is not None else None,
        "status": record.status.value,
    }


def _infer_operation_name(target_endpoint: str) -> str:
    path = urlparse(target_endpoint).path.strip("/")
    if not path:
        return "invoke"
    segments = [segment for segment in path.split("/") if segment]
    if len(segments) >= 2:
        return "/".join(segments[-2:])
    return segments[0]


def _read_current_trace_context() -> tuple[str | None, str | None]:
    try:
        from opentelemetry.trace import get_current_span
    except ImportError:
        return None, None

    span = get_current_span()
    if span is None:
        return None, None
    context = span.get_span_context()
    if not getattr(context, "is_valid", False):
        return None, None
    return f"{context.trace_id:032x}", f"{context.span_id:016x}"