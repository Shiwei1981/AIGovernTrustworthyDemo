"""AIGovernTrustworthyRAGApp — lightweight BM25-based RAG service."""

from __future__ import annotations

import json
import logging
import os
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

import fastapi
import pypdf
from azure.core.credentials import TokenCredential
from azure.identity import ClientSecretCredential, DefaultAzureCredential, get_bearer_token_provider
from fastapi import HTTPException
from fastapi.responses import JSONResponse, Response
from openai import AzureOpenAI
from pydantic import BaseModel
from rank_bm25 import BM25Okapi
from shared_observability import log_llm_call

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)

KNOWLEDGE_BASE_DIR = Path(__file__).parent / "knowledge-base"
RAG_TARGET_ID = "AIGovernTrustworthyDemoRAGService"
RETRIEVAL_MODE = os.getenv("L4_RAG_RETRIEVAL_MODE", "local_lexical_in_memory")
RAG_APP_NAME = os.getenv("L4_RAG_APP_NAME", "AIGovernTrustworthyRAGApp")
RAG_APP_URL = os.getenv("L4_RAG_APP_URL", "").strip()
SERVICE_NAME = os.getenv("L4_OTEL_SERVICE_NAME_RAG_SERVICE", "AIGovernTrustworthyDemo.RAGService")
os.environ["OTEL_SERVICE_NAME"] = SERVICE_NAME
os.environ["AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING"] = "true"

CHUNK_SIZE = 200
CHUNK_OVERLAP = 50
TOP_K = 5

DOCUMENT_ALIASES: dict[str, tuple[str, ...]] = {
    "NIST.AI.100-1": (
        "nist ai rmf",
        "nist ai risk management framework",
    ),
    "NIST.AI.600-1": (
        "nist ai rmf generative ai profile",
        "nist generative ai profile",
    ),
    "OJ_L_202401689_EN_TXT": (
        "eu ai act",
        "european union ai act",
    ),
    "OWASP-Top-10-for-LLMs-v2025": (
        "owasp llm top 10",
        "owasp top 10 for llm applications",
        "owasp prompt injection",
    ),
    "sgmodelaigovframework2": (
        "singapore model ai governance framework",
        "singapore model artificial intelligence governance framework",
        "singapore ai governance framework",
        "model ai governance framework",
    ),
}

SYSTEM_PROMPT = (
    "You are an AI Governance expert assistant. "
    "Answer the user's question strictly based on the provided context excerpts "
    "from AI Governance standards (NIST AI RMF, EU AI Act, OWASP LLM Top 10, "
    "Singapore Model AI Governance Framework). "
    "If the context does not contain enough information, say so clearly. "
    "Cite the source document for each claim using square brackets, e.g. [NIST.AI.100-1]."
)

@dataclass(frozen=True, slots=True)
class Chunk:
    source: str
    chunk_id: int
    page_number: int | None
    text: str


_chunks: list[Chunk] = []
_bm25: BM25Okapi | None = None


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


def _source_alias_tokens(source: str) -> list[str]:
    tokens: list[str] = _tokenize(source)
    for alias in DOCUMENT_ALIASES.get(source, ()):
        tokens.extend(_tokenize(alias))
    return tokens


def _matching_sources(query: str) -> set[str]:
    lowered_query = query.lower()
    query_tokens = set(_tokenize(query))
    matched_sources: set[str] = set()

    for source, aliases in DOCUMENT_ALIASES.items():
        alias_token_set = set(_source_alias_tokens(source))
        if source.lower() in lowered_query:
            matched_sources.add(source)
            continue
        if any(alias in lowered_query for alias in aliases):
            matched_sources.add(source)
            continue
        if len(query_tokens & alias_token_set) >= 3:
            matched_sources.add(source)

    return matched_sources


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _parse_pdf(path: Path) -> list[tuple[int, str]]:
    reader = pypdf.PdfReader(str(path))
    pages: list[tuple[int, str]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = _normalize_whitespace(page.extract_text() or "")
        if text:
            pages.append((page_number, text))
    return pages


def _chunk_text(
    *,
    text: str,
    source: str,
    page_number: int | None,
    start_chunk_id: int,
) -> list[Chunk]:
    words = text.split()
    result: list[Chunk] = []
    start = 0
    chunk_id = start_chunk_id
    while start < len(words):
        end = start + CHUNK_SIZE
        chunk_text = " ".join(words[start:end]).strip()
        if chunk_text:
            result.append(
                Chunk(
                    source=source,
                    chunk_id=chunk_id,
                    page_number=page_number,
                    text=chunk_text,
                )
            )
            chunk_id += 1
        if end >= len(words):
            break
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return result


def _build_index() -> None:
    global _chunks, _bm25
    pdf_paths = sorted(KNOWLEDGE_BASE_DIR.glob("*.pdf"))
    if not pdf_paths:
        raise RuntimeError(f"No PDF files found in knowledge base directory: {KNOWLEDGE_BASE_DIR}")

    all_chunks: list[Chunk] = []
    for pdf_path in pdf_paths:
        next_chunk_id = 1
        for page_number, page_text in _parse_pdf(pdf_path):
            page_chunks = _chunk_text(
                text=page_text,
                source=pdf_path.stem,
                page_number=page_number,
                start_chunk_id=next_chunk_id,
            )
            all_chunks.extend(page_chunks)
            next_chunk_id += len(page_chunks)

    if not all_chunks:
        raise RuntimeError(f"No text could be extracted from PDF files in {KNOWLEDGE_BASE_DIR}")

    _chunks = all_chunks
    _bm25 = BM25Okapi(
        [
            _tokenize(" ".join((*_source_alias_tokens(chunk.source), chunk.text)))
            for chunk in _chunks
        ]
    )
    log.info("Loaded %s PDF chunks from %s files", len(_chunks), len(pdf_paths))


def _retrieve(query: str) -> list[Chunk]:
    if _bm25 is None or not _chunks:
        return []

    scores = _bm25.get_scores(_tokenize(query))
    matched_sources = _matching_sources(query)
    if matched_sources:
        for index, chunk in enumerate(_chunks):
            if chunk.source in matched_sources:
                scores[index] += 100.0
    ranked_indices = [
        index for index in sorted(range(len(scores)), key=lambda i: scores[i], reverse=True) if scores[index] > 0
    ]
    top_indices = ranked_indices[:TOP_K]
    return [_chunks[i] for i in top_indices]


_credential: TokenCredential | None = None
_aoai_client: Any | None = None
_telemetry_configured = False


def _get_credential() -> TokenCredential:
    global _credential
    if _credential is None:
        tenant_id = os.getenv("AZURE_TENANT_ID", "").strip()
        client_id = (os.getenv("AZURE_CLIENT_ID") or os.getenv("L4_RAG_SERVICE_CLIENT_ID") or "").strip()
        client_secret = (
            os.getenv("AZURE_CLIENT_SECRET") or os.getenv("L4_RAG_SERVICE_CLIENT_SECRET") or ""
        ).strip()
        if tenant_id and client_id and client_secret:
            _credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
            )
            log.info("Using client secret credential for RAG service identity")
        elif os.getenv("WEBSITE_INSTANCE_ID") or os.getenv("IDENTITY_ENDPOINT") or os.getenv("MSI_ENDPOINT"):
            _credential = DefaultAzureCredential(
                exclude_cli_credential=True,
                exclude_shared_token_cache_credential=True,
                exclude_visual_studio_code_credential=True,
            )
            log.info("Using managed identity credential for RAG service identity")
        else:
            raise RuntimeError(
                "No supported Azure credential configuration found. "
                "Set AZURE_TENANT_ID with L4_RAG_SERVICE_CLIENT_ID/L4_RAG_SERVICE_CLIENT_SECRET "
                "for local runs, or configure managed identity in Azure Web App."
            )
    return _credential


def _get_aoai_client() -> Any:
    global _aoai_client
    if _aoai_client is None:
        aoai_endpoint = (os.getenv("L4_RAG_LLM_ENDPOINT") or os.getenv("L4_AOAI_ENDPOINT") or "").strip()
        if not aoai_endpoint:
            raise RuntimeError("Missing required environment variable: L4_RAG_LLM_ENDPOINT or L4_AOAI_ENDPOINT")
        token_provider = get_bearer_token_provider(
            _get_credential(), "https://cognitiveservices.azure.com/.default"
        )
        _aoai_client = AzureOpenAI(
            azure_endpoint=aoai_endpoint,
            azure_ad_token_provider=token_provider,
            api_version="2025-01-01-preview",
        )
    return _aoai_client


def _llm_target_endpoint(model_deployment: str) -> str:
    aoai_endpoint = (os.getenv("L4_RAG_LLM_ENDPOINT") or os.getenv("L4_AOAI_ENDPOINT") or "").strip()
    if not aoai_endpoint:
        raise RuntimeError("Missing required environment variable: L4_RAG_LLM_ENDPOINT or L4_AOAI_ENDPOINT")
    return (
        f"{aoai_endpoint.rstrip('/')}/openai/deployments/"
        f"{model_deployment}/chat/completions"
    )


def _rag_model_name() -> str:
    return (os.getenv("L4_RAG_MODEL_NAME") or "").strip() or "gpt-5.4-mini"


def _configure_telemetry() -> None:
    global _telemetry_configured
    if _telemetry_configured:
        return

    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
    if not connection_string:
        log.warning(
            "APPLICATIONINSIGHTS_CONNECTION_STRING not set; Azure Monitor request telemetry is disabled"
        )
        return

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        from opentelemetry.sdk.resources import Resource
    except ImportError:
        log.warning(
            "Azure Monitor OpenTelemetry packages unavailable; continuing without request telemetry",
            exc_info=True,
        )
        return

    try:
        configure_azure_monitor(
            connection_string=connection_string,
            credential=_get_credential(),
            resource=Resource.create({"service.name": SERVICE_NAME}),
            logger_name=__name__,
            enable_live_metrics=False,
            instrumentation_options={
                "fastapi": {"enabled": True},
                "requests": {"enabled": True},
                "urllib": {"enabled": True},
                "urllib3": {"enabled": True},
                "azure_sdk": {"enabled": True},
            },
        )
    except Exception:
        log.warning(
            "Azure Monitor request telemetry initialization failed; continuing without "
            "experimental request tracing while preserving the main RAG flow and LLM evidence logging",
            exc_info=True,
        )
        return

    _telemetry_configured = True
    log.info("Azure Monitor telemetry configured for service %s", SERVICE_NAME)


def _get_ui_proxy_target_url() -> str:
    base_url = os.getenv("L4_RAG_SERVICE_URL", "").strip()
    if not base_url:
        raise RuntimeError("Missing required environment variable: L4_RAG_SERVICE_URL")
    return base_url.rstrip("/") + "/responses"


def _proxy_ui_request(input_text: str) -> tuple[int, bytes, str]:
    body = json.dumps({"input": input_text}).encode("utf-8")
    request = urllib_request.Request(
        _get_ui_proxy_target_url(),
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib_request.urlopen(request, timeout=120) as response:
            content_type = response.headers.get("Content-Type", "application/json")
            return response.status, response.read(), content_type
    except urllib_error.HTTPError as exc:
        content_type = exc.headers.get("Content-Type", "application/json")
        return exc.code, exc.read(), content_type


_configure_telemetry()


@asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    _build_index()
    yield


app = fastapi.FastAPI(title="AIGovernTrustworthyRAGApp", lifespan=lifespan)


class QueryRequest(BaseModel):
    input: str


class Citation(BaseModel):
    source: str
    chunk_id: int
    page_number: int | None = None
    excerpt: str


class QueryResponse(BaseModel):
    output: list[dict[str, Any]]
    citations: list[Citation]
    archive_id: str | None = None


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "chunks_loaded": len(_chunks)})


@app.post("/responses", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    if not req.input.strip():
        raise HTTPException(status_code=400, detail="input must not be empty")

    model_deployment = _require_env("L4_RAG_MODEL_DEPLOYMENT")
    context_chunks = _retrieve(req.input)
    context_text = "\n\n".join(
        (
            f"[{chunk.source} chunk {chunk.chunk_id}"
            f"{f', page {chunk.page_number}' if chunk.page_number is not None else ''}]\n"
            f"{chunk.text}"
        )
        for chunk in context_chunks
    )
    if not context_text:
        context_text = "No relevant context excerpts were retrieved from the knowledge base."

    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Context:\n{context_text}\n\nQuestion: {req.input}",
        },
    ]
    llm_input_payload: dict[str, Any] = {
        "model_name": _rag_model_name(),
        "deployment": model_deployment,
        "messages": messages,
        "target_type": "rag_service",
        "target_id": RAG_TARGET_ID,
    }
    target_endpoint = _llm_target_endpoint(model_deployment)

    credential = _get_credential()
    aoai_client = _get_aoai_client()

    try:
        completion = aoai_client.chat.completions.create(
            model=model_deployment,
            messages=messages,
            max_completion_tokens=1024,
            temperature=0.0,
        )
        answer = completion.choices[0].message.content or ""
        response_id = completion.id
        llm_output_payload: dict[str, Any] = {
            "answer": answer,
            "response_id": response_id,
        }
        citations = [
            Citation(
                source=chunk.source,
                chunk_id=chunk.chunk_id,
                page_number=chunk.page_number,
                excerpt=chunk.text[:300],
            )
            for chunk in context_chunks
        ]

        ev = log_llm_call(
            service_name=SERVICE_NAME,
            target_type="rag_service",
            source_type="rag_service",
            target_id=RAG_TARGET_ID,
            target_endpoint=target_endpoint,
            llm_input=llm_input_payload,
            llm_output=llm_output_payload,
            credential=credential,
            model_name=_rag_model_name(),
            response_id=response_id,
            citations_count=len(citations),
            extra_attributes={
                "rag_app_name": RAG_APP_NAME,
                "retrieval_mode": RETRIEVAL_MODE,
                "rag_app_url": RAG_APP_URL or None,
            },
        )
        archive_id = ev.invocation.archive_id

        return QueryResponse(
            output=[{"type": "message", "role": "assistant", "content": answer}],
            citations=citations,
            archive_id=archive_id,
        )

    except Exception as exc:
        log.exception("RAG request failed")
        try:
            log_llm_call(
                service_name=SERVICE_NAME,
                target_type="rag_service",
                source_type="rag_service",
                target_id=RAG_TARGET_ID,
                target_endpoint=target_endpoint,
                llm_input=llm_input_payload,
                error={"type": type(exc).__name__, "message": str(exc)},
                credential=credential,
                model_name=_rag_model_name(),
                extra_attributes={
                    "rag_app_name": RAG_APP_NAME,
                    "retrieval_mode": RETRIEVAL_MODE,
                    "rag_app_url": RAG_APP_URL or None,
                },
            )
        except Exception as evidence_exc:
            raise HTTPException(
                status_code=502,
                detail=(
                    f"RAG request failed with {type(exc).__name__}: {exc}; "
                    f"evidence logging also failed with {type(evidence_exc).__name__}: {evidence_exc}"
                ),
            ) from evidence_exc
        raise HTTPException(status_code=502, detail=f"{type(exc).__name__}: {exc}") from exc


@app.post("/ui/responses")
def ui_query(req: QueryRequest) -> Response:
    try:
        status_code, payload, content_type = _proxy_ui_request(req.input)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UI proxy failed: {type(exc).__name__}: {exc}") from exc
    return Response(content=payload, status_code=status_code, media_type=content_type.split(";", 1)[0])


_CHAT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>AI Governance RAG — Chat</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#0f1117;color:#e2e8f0;height:100vh;display:flex;flex-direction:column}
header{background:#1a1f2e;border-bottom:1px solid #2d3748;padding:14px 24px;display:flex;align-items:center;gap:10px}
header h1{font-size:18px;color:#63b3ed;font-weight:700}
header span{font-size:12px;color:#718096}
#chat{flex:1;overflow-y:auto;padding:24px;display:flex;flex-direction:column;gap:16px}
.msg{max-width:780px;width:100%}
.msg.user{align-self:flex-end}
.msg.assistant{align-self:flex-start}
.bubble{border-radius:12px;padding:14px 18px;font-size:14px;line-height:1.7;white-space:pre-wrap;word-break:break-word}
.msg.user .bubble{background:#2b6cb0;color:#fff;border-bottom-right-radius:4px}
.msg.assistant .bubble{background:#1a2035;border:1px solid #2d3748;border-bottom-left-radius:4px}
.citations{margin-top:10px;display:flex;flex-wrap:wrap;gap:6px}
.cit{background:#0d1117;border:1px solid #2d3748;border-radius:6px;padding:4px 10px;font-size:11px;color:#90cdf4;font-family:monospace}
.arc{font-size:10px;color:#4a5568;margin-top:6px;font-family:monospace}
footer{background:#1a1f2e;border-top:1px solid #2d3748;padding:14px 24px;display:flex;gap:10px}
textarea{flex:1;background:#0d1117;border:1px solid #4a5568;color:#e2e8f0;padding:10px 14px;border-radius:8px;font-size:14px;resize:none;outline:none;height:56px;font-family:inherit}
textarea:focus{border-color:#63b3ed}
button{background:#2b6cb0;color:#fff;border:none;padding:0 22px;border-radius:8px;font-size:14px;cursor:pointer;font-weight:600;transition:background .15s}
button:hover{background:#3182ce}
button:disabled{background:#2d3748;color:#718096;cursor:not-allowed}
.thinking{color:#718096;font-style:italic;font-size:13px}
</style>
</head>
<body>
<header>
  <h1>🤖 AI Governance RAG</h1>
  <span>Knowledge: NIST AI RMF · EU AI Act · OWASP LLM Top 10 · Singapore Model AI Governance</span>
</header>
<div id="chat"></div>
<footer>
  <textarea id="inp" placeholder="Ask about AI Governance standards…" onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();send()}"></textarea>
  <button id="btn" onclick="send()">Send</button>
</footer>
<script>
const chat=document.getElementById('chat');
const inp=document.getElementById('inp');
const btn=document.getElementById('btn');
function addMsg(role,content,citations,archive_id){
  const d=document.createElement('div');
  d.className='msg '+role;
  let inner=`<div class="bubble">${escHtml(content)}</div>`;
  if(citations&&citations.length){
    const cits=citations.map(c=>`<span class="cit">${escHtml(c.source)} p.${c.page_number||'?'}</span>`).join('');
    inner+=`<div class="citations">${cits}</div>`;
  }
  if(archive_id) inner+=`<div class="arc">archive_id: ${escHtml(archive_id)}</div>`;
  d.innerHTML=inner;
  chat.appendChild(d);
  chat.scrollTop=chat.scrollHeight;
  return d;
}
function escHtml(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
async function send(){
  const q=inp.value.trim();
  if(!q)return;
  inp.value='';btn.disabled=true;
  addMsg('user',q);
  const thinking=document.createElement('div');
  thinking.className='msg assistant';
  thinking.innerHTML='<div class="bubble thinking">Thinking…</div>';
  chat.appendChild(thinking);
  chat.scrollTop=chat.scrollHeight;
  try{
    const r=await fetch('/ui/responses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({input:q})});
    const d=await r.json();
    chat.removeChild(thinking);
    if(r.ok){
      const content=d.output&&d.output[0]?d.output[0].content:'(no response)';
      addMsg('assistant',content,d.citations,d.archive_id);
    }else{
      addMsg('assistant','❌ Error: '+(d.detail||r.status));
    }
  }catch(e){
    chat.removeChild(thinking);
    addMsg('assistant','❌ Network error: '+e.message);
  }
  btn.disabled=false;inp.focus();
}
</script>
</body>
</html>"""


@app.get("/")
def chat_ui():
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=_CHAT_HTML)
