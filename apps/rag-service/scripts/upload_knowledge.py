"""
upload_knowledge.py — 上传 knowledge-base/ 下所有 PDF 到 Azure OpenAI vector store，
并将 vector store 绑定到 RAG Assistant。

使用 AzureOpenAI 客户端 + Entra 令牌（RAG Service SPN）。
使用 AIGovernTrustworthyAOAI（AIGovernTrustworthyRG）。

运行方式：
    cd apps/rag-service
    .venv/bin/python scripts/upload_knowledge.py

前置条件：
    - create_agent.py 已运行，L4_RAG_AGENT_ID 已填入 .env.local.L4
    - knowledge-base/ 目录下有 PDF 文件
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

_ENV_FILE = Path(__file__).resolve().parents[3] / ".env.local.L4"
_KB_DIR = Path(__file__).resolve().parents[1] / "knowledge-base"

_AOAI_ENDPOINT = "https://aigoverntrustworthyaoai.openai.azure.com/"
_AOAI_API_VERSION = "2025-01-01-preview"


def _load_env(path: Path) -> None:
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


_load_env(_ENV_FILE)

from azure.identity import ClientSecretCredential  # noqa: E402
from openai import AzureOpenAI  # noqa: E402


def _require(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        print(f"[ERROR] Missing required env var: {name}", file=sys.stderr)
        sys.exit(1)
    return value


def main() -> None:
    agent_id = _require("L4_RAG_AGENT_ID")
    tenant_id = _require("AZURE_TENANT_ID")
    client_id = _require("L4_RAG_SERVICE_CLIENT_ID")
    client_secret = _require("L4_RAG_SERVICE_CLIENT_SECRET")

    pdf_files = sorted(_KB_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"[ERROR] No PDF files found in {_KB_DIR}", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Knowledge base directory : {_KB_DIR}")
    print(f"[INFO] PDF files found          : {len(pdf_files)}")
    for f in pdf_files:
        print(f"       - {f.name}  ({f.stat().st_size / 1024 / 1024:.1f} MB)")

    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
    )
    openai_client = AzureOpenAI(
        azure_endpoint=_AOAI_ENDPOINT,
        api_version=_AOAI_API_VERSION,
        azure_ad_token_provider=lambda: credential.get_token(
            "https://cognitiveservices.azure.com/.default"
        ).token,
    )

    # Upload each PDF and collect file IDs
    print("\n[INFO] Uploading files to Azure OpenAI...")
    file_ids: list[str] = []
    for pdf_path in pdf_files:
        print(f"       Uploading {pdf_path.name}...", end=" ", flush=True)
        with open(pdf_path, "rb") as fh:
            uploaded = openai_client.files.create(file=fh, purpose="assistants")
        print(f"-> {uploaded.id}")
        file_ids.append(uploaded.id)

    # Create a vector store with all files
    print(f"\n[INFO] Creating vector store with {len(file_ids)} file(s)...")
    vector_store = openai_client.vector_stores.create(
        name="AIGovernTrustworthyDemoRAGVectorStore",
        file_ids=file_ids,
    )
    print(f"[OK]   Vector store created : {vector_store.id}")
    print(f"       Status               : {vector_store.status}")

    # Poll until processing completes
    if vector_store.file_counts.in_progress > 0:
        print("[INFO] Files still processing. Polling for completion (up to 5 min)...")
        for _ in range(30):
            time.sleep(10)
            vector_store = openai_client.vector_stores.retrieve(vector_store.id)
            in_prog = vector_store.file_counts.in_progress
            print(f"       status={vector_store.status} in_progress={in_prog}", flush=True)
            if in_prog == 0:
                break
        else:
            print("[WARN] Timed out waiting for vector store. Check Foundry Portal.")

    print(f"\n[INFO] Final status    : {vector_store.status}")
    print(f"       Files completed : {vector_store.file_counts.completed}")
    print(f"       Files failed    : {vector_store.file_counts.failed}")

    # Bind the vector store to the agent
    print(f"\n[INFO] Binding vector store to agent {agent_id}...")
    openai_client.beta.assistants.update(
        assistant_id=agent_id,
        tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
    )
    print(f"[OK]   Vector store {vector_store.id} bound to agent {agent_id}.")
    print(f"\n[ACTION] Optionally add to .env.local.L4:")
    print(f"         L4_RAG_VECTOR_STORE_ID={vector_store.id}")


if __name__ == "__main__":
    main()
