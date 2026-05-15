from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pypdf
from azure.core.credentials import TokenCredential
from azure.identity import ClientSecretCredential, get_bearer_token_provider
from openai import AzureOpenAI

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = REPO_ROOT / ".env.local.L4"
KNOWLEDGE_BASE_DIR = REPO_ROOT / "apps" / "rag-service" / "knowledge-base"
DOCS_ARCHIVE_DIR = REPO_ROOT / "docs" / "finetune-qa-archive"
RAW_QA_PATH = DOCS_ARCHIVE_DIR / "aigoverntrustworthydemo-qa-raw.jsonl"
FINAL_JSONL_PATH = DOCS_ARCHIVE_DIR / "aigoverntrustworthydemo-qa-5000.jsonl"
AOAI_API_VERSION = "2025-01-01-preview"
AOAI_SCOPE = "https://cognitiveservices.azure.com/.default"


@dataclass(frozen=True, slots=True)
class SourcePage:
    source: str
    pdf_name: str
    page_number: int
    text: str


def load_env(path: Path = ENV_FILE) -> None:
    if not path.exists():
        print(f"[WARN] env file not found: {path}", file=sys.stderr)
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        if value and value not in ("<to-be-created>", "<to-be-deployed>", "<to-be-configured>"):
            os.environ.setdefault(key.strip(), value)


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def get_credential() -> TokenCredential:
    tenant_id = require_env("AZURE_TENANT_ID")
    client_id = (
        os.getenv("AZURE_CLIENT_ID")
        or os.getenv("L4_RAG_SERVICE_CLIENT_ID")
        or ""
    ).strip()
    client_secret = (
        os.getenv("AZURE_CLIENT_SECRET")
        or os.getenv("L4_RAG_SERVICE_CLIENT_SECRET")
        or ""
    ).strip()
    if not client_id or not client_secret:
        raise RuntimeError(
            "Missing Azure client identity. Set AZURE_CLIENT_ID/AZURE_CLIENT_SECRET "
            "or L4_RAG_SERVICE_CLIENT_ID/L4_RAG_SERVICE_CLIENT_SECRET."
        )
    return ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
    )


def get_aoai_client() -> AzureOpenAI:
    credential = get_credential()
    token_provider = get_bearer_token_provider(credential, AOAI_SCOPE)
    return AzureOpenAI(
        azure_endpoint=require_env("L4_AOAI_ENDPOINT"),
        azure_ad_token_provider=token_provider,
        api_version=AOAI_API_VERSION,
    )


def parse_pdf_pages() -> list[SourcePage]:
    pdf_paths = sorted(KNOWLEDGE_BASE_DIR.glob("*.pdf"))
    if not pdf_paths:
        raise RuntimeError(f"No PDF files found in knowledge base directory: {KNOWLEDGE_BASE_DIR}")

    pages: list[SourcePage] = []
    for pdf_path in pdf_paths:
        reader = pypdf.PdfReader(str(pdf_path))
        for page_number, page in enumerate(reader.pages, start=1):
            text = normalize_whitespace(page.extract_text() or "")
            if not text:
                continue
            pages.append(
                SourcePage(
                    source=pdf_path.stem,
                    pdf_name=pdf_path.name,
                    page_number=page_number,
                    text=text,
                )
            )
    if not pages:
        raise RuntimeError(f"No text could be extracted from PDF files in {KNOWLEDGE_BASE_DIR}")
    return pages


def ensure_archive_dir() -> Path:
    DOCS_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    return DOCS_ARCHIVE_DIR
