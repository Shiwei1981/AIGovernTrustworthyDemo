"""AIGovernTrustworthyDemoRAGHostedAgent — Foundry Hosted Agent entry point.

Implements the Hosted Agent Responses protocol using Microsoft's protocol
library. The Foundry platform routes requests to this container's
``POST /responses`` endpoint.

Flow:
  1. Receive Responses API request from Foundry platform.
  2. Call model via Foundry account endpoint with file_search tool (vector store).
  3. Capture LLM input / output.
  4. Write Blob evidence via shared_observability.log_llm_call().
  5. Return Responses API response to caller.

Only LLM input and output are logged — retrieved chunks and hidden context are NOT.
"""

import logging
import os
import asyncio
from typing import Any

from azure.identity import (
    AzureCliCredential,
    DefaultAzureCredential,
    get_bearer_token_provider,
)
from azure.ai.agentserver.responses import (
    CreateResponse,
    ResponseContext,
    ResponsesAgentServerHost,
    TextResponse,
)
from openai import OpenAI

import shared_observability

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)

# ── Environment ────────────────────────────────────────────────────────────────
FOUNDRY_PROJECT_ENDPOINT: str = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
RAG_VECTOR_STORE_ID: str = os.environ["RAG_VECTOR_STORE_ID"]
RAG_MODEL_DEPLOYMENT: str = os.environ["RAG_MODEL_DEPLOYMENT"]
SERVICE_NAME: str = os.environ.get(
    "SERVICE_NAME", "AIGovernTrustworthyDemo.RAGService"
)
HOSTED_AGENT_NAME: str = os.environ.get(
    "HOSTED_AGENT_NAME", "AIGovernTrustworthyDemoRAGHostedAgent"
)
HOSTED_AGENT_VERSION: str = os.environ.get("HOSTED_AGENT_VERSION", "")
PORT: int = int(os.environ.get("PORT", "8088"))

# Extract account endpoint from project endpoint.
# "https://<account>.services.ai.azure.com/api/projects/<project>"
# -> "https://<account>.services.ai.azure.com/"
FOUNDRY_ACCOUNT_ENDPOINT: str = FOUNDRY_PROJECT_ENDPOINT.split("/api/projects/")[0]

# ── Azure identity ─────────────────────────────────────────────────────────────
# In container: DefaultAzureCredential resolves to the Hosted Agent identity.
# Locally, prefer AzureCliCredential to avoid accidentally using the host VM MI.
_credential = (
    DefaultAzureCredential()
    if os.environ.get("FOUNDRY_AGENT_NAME") or os.environ.get("FOUNDRY_AGENT_SESSION_ID")
    else AzureCliCredential()
)
_token_provider = get_bearer_token_provider(
    _credential, "https://cognitiveservices.azure.com/.default"
)

# ── OpenAI client (calls model + file_search via Foundry account endpoint) ────
_oai_client = OpenAI(
    base_url=f"{FOUNDRY_ACCOUNT_ENDPOINT.rstrip('/')}/openai",
    default_query={"api-version": "2025-04-01-preview"},
    api_key=_token_provider,
)

# ── Hosted Agent Responses app ────────────────────────────────────────────────
app = ResponsesAgentServerHost()


def _extract_output_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text

    parts: list[str] = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", "") != "message":
            continue
        for content in getattr(item, "content", []) or []:
            if getattr(content, "type", "") == "output_text":
                parts.append(getattr(content, "text", ""))
    return "".join(parts)


@app.response_handler
async def handle_responses(
    request: CreateResponse,
    context: ResponseContext,
    cancellation_signal,
) -> TextResponse:
    input_text = await context.get_input_text()
    model: str = request.model or RAG_MODEL_DEPLOYMENT

    llm_input: dict = {
        "model": model,
        "input": input_text,
        "tools": [
            {
                "type": "file_search",
                "vector_store_ids": [RAG_VECTOR_STORE_ID],
            }
        ],
    }

    try:
        response = await asyncio.to_thread(
            _oai_client.responses.create,
            model=model,
            input=input_text,
            tools=[
                {
                    "type": "file_search",
                    "vector_store_ids": [RAG_VECTOR_STORE_ID],
                }
            ],
        )

        citations_count: int = sum(
            1
            for item in getattr(response, "output", [])
            for ann in getattr(item, "annotations", [])
            if getattr(ann, "type", "") in ("file_citation", "file_path")
        )

        shared_observability.log_llm_call(
            service_name=SERVICE_NAME,
            target_type="rag_service",
            target_id="AIGovernTrustworthyDemoRAGService",
            target_endpoint=FOUNDRY_PROJECT_ENDPOINT,
            llm_input=llm_input,
            credential=_credential,
            llm_output=response.model_dump(),
            model_name=getattr(response, "model", model),
            response_id=getattr(response, "id", None),
            citations_count=citations_count,
            extra_attributes={
                "hosted_agent_name": HOSTED_AGENT_NAME,
                "hosted_agent_version": HOSTED_AGENT_VERSION,
            },
        )

        return TextResponse(context, request, text=_extract_output_text(response))

    except Exception as exc:
        log.exception("Error processing RAG request")
        try:
            shared_observability.log_llm_call(
                service_name=SERVICE_NAME,
                target_type="rag_service",
                target_id="AIGovernTrustworthyDemoRAGService",
                target_endpoint=FOUNDRY_PROJECT_ENDPOINT,
                llm_input=llm_input,
                credential=_credential,
                error={"type": type(exc).__name__, "message": str(exc)},
                model_name=model,
                extra_attributes={
                    "hosted_agent_name": HOSTED_AGENT_NAME,
                    "hosted_agent_version": HOSTED_AGENT_VERSION,
                },
            )
        except Exception:
            log.warning("Failed to write error evidence to Blob")
        raise


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
