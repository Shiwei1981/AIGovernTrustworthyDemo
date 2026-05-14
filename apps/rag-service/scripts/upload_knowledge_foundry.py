#!/usr/bin/env python3
"""Upload AI Governance PDFs to Foundry vector store and update .env.local.L4.

Usage:
    python scripts/upload_knowledge_foundry.py

Prerequisites:
    - L4_RAG_FOUNDRY_ACCOUNT_ENDPOINT in environment (or .env.local.L4 loaded)
    - PDF files present in apps/rag-service/knowledge-base/
    - AzureCliCredential with Azure AI Developer role on the Foundry Account

The script:
  1. Reads all PDFs from knowledge-base/.
  2. Uploads each to Foundry files (purpose=assistants).
  3. Creates (or reuses) a vector store named after the project.
  4. Adds all uploaded files to the vector store and waits for processing.
  5. Prints the vector store ID to stdout so it can be set in .env.local.L4.
"""

from __future__ import annotations

import io
import os
import sys
import time
from pathlib import Path

from azure.identity import AzureCliCredential, get_bearer_token_provider
from openai import AzureOpenAI

REPO_ROOT = Path(__file__).resolve().parents[3]
KNOWLEDGE_BASE_DIR = REPO_ROOT / "apps" / "rag-service" / "knowledge-base"
VECTOR_STORE_NAME = "AIGovernTrustworthyDemoRAGVectorStore"

# Load env from .env.local.L4 if not already set
_env_file = REPO_ROOT / ".env.local.L4"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip().strip('"'))


def build_client() -> AzureOpenAI:
    account_endpoint = os.environ.get(
        "L4_RAG_FOUNDRY_ACCOUNT_ENDPOINT",
        os.environ.get("FOUNDRY_ACCOUNT_ENDPOINT", ""),
    )
    if not account_endpoint:
        sys.exit(
            "ERROR: L4_RAG_FOUNDRY_ACCOUNT_ENDPOINT not set. "
            "Load .env.local.L4 or export the variable."
        )
    cred = AzureCliCredential()
    tp = get_bearer_token_provider(cred, "https://cognitiveservices.azure.com/.default")
    return AzureOpenAI(
        azure_endpoint=account_endpoint,
        api_version="2025-04-01-preview",
        azure_ad_token_provider=tp,
    )


def find_pdfs() -> list[Path]:
    if not KNOWLEDGE_BASE_DIR.exists():
        sys.exit(f"ERROR: knowledge-base directory not found: {KNOWLEDGE_BASE_DIR}")
    pdfs = sorted(KNOWLEDGE_BASE_DIR.glob("*.pdf"))
    if not pdfs:
        sys.exit(
            f"ERROR: No PDF files found in {KNOWLEDGE_BASE_DIR}. "
            "Place AI Governance PDFs there before running this script."
        )
    return pdfs


def upload_files(client: AzureOpenAI, pdfs: list[Path]) -> list[str]:
    print(f"Uploading {len(pdfs)} PDF(s)...")
    file_ids: list[str] = []
    for pdf in pdfs:
        print(f"  Uploading: {pdf.name}")
        with pdf.open("rb") as fh:
            result = client.files.create(
                file=(pdf.name, fh, "application/pdf"),
                purpose="assistants",
            )
        file_ids.append(result.id)
        print(f"    → {result.id}")
    return file_ids


def get_or_create_vector_store(client: AzureOpenAI) -> str:
    for vs in client.vector_stores.list():
        if vs.name == VECTOR_STORE_NAME:
            print(f"Reusing existing vector store: {vs.id} ({vs.name})")
            return vs.id
    vs = client.vector_stores.create(name=VECTOR_STORE_NAME)
    print(f"Created vector store: {vs.id} ({vs.name})")
    return vs.id


def add_files_to_vector_store(
    client: AzureOpenAI, vs_id: str, file_ids: list[str]
) -> None:
    print(f"Adding {len(file_ids)} file(s) to vector store {vs_id}...")
    for fid in file_ids:
        client.vector_stores.files.create(vector_store_id=vs_id, file_id=fid)

    # Wait until all files finish processing
    print("Waiting for vector store processing...")
    for attempt in range(60):
        vs = client.vector_stores.retrieve(vs_id)
        fc = vs.file_counts
        pending = getattr(fc, "in_progress", 0)
        failed = getattr(fc, "failed", 0)
        completed = getattr(fc, "completed", 0)
        total = getattr(fc, "total", len(file_ids))
        print(
            f"  [{attempt+1:02d}] completed={completed} in_progress={pending} "
            f"failed={failed} total={total}",
            end="\r",
        )
        if pending == 0:
            print()
            if failed:
                print(f"WARNING: {failed} file(s) failed to process.")
            break
        time.sleep(5)
    else:
        print("\nWARNING: Timed out waiting for vector store processing.")


def main() -> None:
    client = build_client()
    pdfs = find_pdfs()
    file_ids = upload_files(client, pdfs)
    vs_id = get_or_create_vector_store(client)
    add_files_to_vector_store(client, vs_id, file_ids)

    print()
    print("=" * 60)
    print(f"Vector Store ID: {vs_id}")
    print()
    print("Update .env.local.L4:")
    print(f"  L4_RAG_VECTOR_STORE_ID={vs_id}")
    print("=" * 60)


if __name__ == "__main__":
    main()
