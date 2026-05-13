"""Internal evidence schema for the shared observability package."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


TelemetryScalar = str | int | float | bool | None


class TargetType(StrEnum):
    RAG_SERVICE = "rag_service"
    FOUNDRY_NATIVE_MODEL = "foundry_native_model"
    FOUNDRY_FINETUNE_MODEL = "foundry_finetune_model"
    FOUNDRY_AGENT = "foundry_agent"
    COPILOT_STUDIO_AGENT = "copilot_studio_agent"
    VM_HUGGINGFACE_MODEL = "vm_huggingface_model"
    TIER1_CONSUMER = "tier1_consumer"
    TIER2_CONSUMER = "tier2_consumer"


class AIInvocationStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class EventNames:
    LLM_EVIDENCE = "AIGovernTrustworthyLLMEvidence"
    EVALUATION_RUN = "AIGovernTrustworthyEvaluationRun"
    RED_TEAM_RUN = "AIGovernTrustworthyRedTeamRun"
    MODEL_IDENTITY_OBSERVED = "AIGovernTrustworthyModelIdentityObserved"
    CITATION_OBSERVED = "AIGovernTrustworthyCitationObserved"
    FINDING_CREATED = "AIGovernTrustworthyFindingCreated"


@dataclass(slots=True)
class AIInvocationArchiveRef:
    container: str
    prefix: str
    input_blob_path: str
    output_blob_path: str
    metadata_blob_path: str


@dataclass(slots=True)
class BlobArchiveLayout:
    prefix: str

    def build_paths(
        self,
        *,
        service_name: str,
        target_type: TargetType,
        archive_id: str,
        occurred_at: datetime,
    ) -> tuple[str, str, str]:
        timestamp = occurred_at.astimezone(UTC)
        base = (
            f"{self.prefix}/"
            f"{timestamp:%Y/%m/%d}/"
            f"{service_name}/"
            f"{target_type.value}/"
            f"{archive_id}"
        )
        return (
            f"{base}/input.json",
            f"{base}/output.json",
            f"{base}/metadata.json",
        )


@dataclass(slots=True)
class AIInvocationRecord:
    service_name: str
    target_type: TargetType
    target_id: str
    target_endpoint: str
    trace_id: str | None
    span_id: str | None
    archive_id: str
    response_id: str | None
    status: AIInvocationStatus
    occurred_at: datetime
    payload_ref: AIInvocationArchiveRef
    model_name: str | None = None
    model_version: str | None = None
    test_tool: str | None = None
    test_run_id: str | None = None
    citations_count: int | None = None
    extra_properties: dict[str, TelemetryScalar] = field(default_factory=dict)


@dataclass(slots=True)
class EvidenceRecord:
    invocation: AIInvocationRecord
    event_name: str
    event_attributes: dict[str, TelemetryScalar]
    input_payload: bytes
    output_payload: bytes
    metadata_payload: bytes