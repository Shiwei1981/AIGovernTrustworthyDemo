"""Internal evidence schema for the shared observability package."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


TelemetryScalar = str | int | float | bool | None


class TargetType(StrEnum):
    """Discriminator that identifies *what kind of AI component* was called.

    Used as the ``target_type`` argument to ``log_llm_call()`` and stored in
    Blob evidence metadata + App Insights event attribute ``aigov.target.type``.

    **Choosing the right value**

    The value describes the *downstream target*, not the caller.  Ask:
    "What did I call?" and pick accordingly.

    Recording party examples
    ------------------------
    * A Tier 1 App calls the RAG service API → ``RAG_SERVICE``
    * The RAG service calls Azure OpenAI (Foundry native model) → ``FOUNDRY_NATIVE_MODEL``
    * A Tier 1 App calls a Foundry Agent API → ``FOUNDRY_AGENT``
    * An evaluation runner calls a Tier 1 Consumer App API → ``TIER1_CONSUMER``
    * An evaluation runner calls a Tier 2 Consumer App API → ``TIER2_CONSUMER``

    Layered recording note
    ----------------------
    When a Tier 1 App calls the RAG service, *two* evidence records are written:

    1. Tier 1 App records: ``target_type=RAG_SERVICE``, its own ``service_name``.
    2. RAG service records: ``target_type=FOUNDRY_NATIVE_MODEL``, its own ``service_name``.

    Both records share the same ``trace_id``, enabling full call-chain reconstruction
    in App Insights.

    Value catalogue
    ---------------
    ``rag_service``
        A RAG (Retrieval-Augmented Generation) service API endpoint.
        Used when any caller (App, eval runner) invokes a RAG API.
        Also used by the RAG service *itself* when logging its internal LLM call
        if no more specific ``foundry_*`` value applies at the RAG layer.

    ``foundry_native_model``
        Direct call to an Azure AI Foundry–hosted base or chat-completion model
        (no fine-tuning; standard deployment).

    ``foundry_finetune_model``
        Direct call to an Azure AI Foundry–hosted fine-tuned model deployment.

    ``foundry_agent``
        Call to an Azure AI Foundry Agent API (``/agents/...``).

    ``copilot_studio_agent``
        Call to a Microsoft Copilot Studio published agent endpoint.

    ``vm_huggingface_model``
        Call to a Hugging Face model served on an Azure VM (custom REST endpoint).

    ``tier1_consumer``
        The recording party is calling a **Tier 1 Consumer Application** as the
        target under test.  Typically used by evaluation runners or test scripts
        that drive the consumer app and want to archive the request/response pair.

    ``tier2_consumer``
        Same as ``tier1_consumer`` but for a **Tier 2 Consumer Application**.
    """

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