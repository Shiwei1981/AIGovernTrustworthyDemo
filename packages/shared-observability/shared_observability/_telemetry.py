"""App Insights thin evidence event emitter."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from azure.core.credentials import TokenCredential

from .errors import TelemetryEmitError


def emit_evidence_event(
    *,
    connection_string: str,
    credential: "TokenCredential",
    event_name: str,
    attributes: dict[str, object],
    trace_id: str | None = None,
    span_id: str | None = None,
) -> None:
    """Emit a thin evidence index event to Application Insights.

    The event lands in the ``customEvents`` table with ``operation_Id`` set to
    ``trace_id`` so it can be joined with APIM and Foundry traces (R-006).

    If ``trace_id`` / ``span_id`` are provided the event is emitted as a child
    of that trace context so that App Insights correctly correlates it with the
    platform trace.  Otherwise the event is emitted with its own new trace.

    Raises ``TelemetryEmitError`` on import or network-level failure (R-013).
    HTTP-level warnings from the exporter are logged to stderr by the SDK but
    do not surface as exceptions at the application level.
    """
    try:
        from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags
    except ImportError as exc:
        raise TelemetryEmitError(
            "azure-monitor-opentelemetry-exporter and opentelemetry-sdk are required; "
            "pip install azure-monitor-opentelemetry-exporter opentelemetry-sdk"
        ) from exc

    try:
        resource = Resource({"service.name": "shared_observability.telemetry"})
        # Build the provider first so we can pass it into the exporter.
        # The exporter stores self._tracer_provider and uses it in export() to
        # resolve the Resource.  Without this, the exporter falls back to
        # opentelemetry.trace.get_tracer_provider() which may return the global
        # ProxyTracerProvider (no .resource attribute) and log an error.
        provider = TracerProvider(resource=resource)
        exporter = AzureMonitorTraceExporter(
            connection_string=connection_string,
            credential=credential,
            tracer_provider=provider,
        )
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("shared_observability.telemetry")

        # Reconstruct the parent span context so the evidence event shares the
        # same trace_id as the surrounding APIM / Foundry trace.
        ctx = None
        if trace_id and span_id:
            try:
                parent_ctx = SpanContext(
                    trace_id=int(trace_id, 16),
                    span_id=int(span_id, 16),
                    is_remote=True,
                    trace_flags=TraceFlags(TraceFlags.SAMPLED),
                )
                parent_span = NonRecordingSpan(parent_ctx)
                ctx = trace.set_span_in_context(parent_span)
            except ValueError:
                pass  # malformed IDs — emit without correlation context

        # OTel attributes must be scalar (str | int | float | bool); filter None
        # and complex values which are already represented in the Blob archive.
        clean_attrs: dict[str, str | int | float | bool] = {
            k: v  # type: ignore[assignment]
            for k, v in attributes.items()
            if isinstance(v, (str, int, float, bool))
        }

        # The span itself is a transport carrier; the span event becomes a
        # customEvent row in App Insights with the event_name as its name and
        # clean_attrs as customDimensions.
        with tracer.start_as_current_span("AIGovernEvidenceCapture", context=ctx) as span:
            span.add_event(event_name, attributes=clean_attrs)
        # SimpleSpanProcessor exports synchronously on span end — no flush needed.

    except TelemetryEmitError:
        raise
    except Exception as exc:
        raise TelemetryEmitError(
            f"Failed to emit evidence event to App Insights: {exc}"
        ) from exc
