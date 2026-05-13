"""
create_agent.py — 创建 RAG Governance Service 的 Azure OpenAI Assistant with File Search。

使用 AzureOpenAI 客户端 + Entra 令牌（RAG Service SPN），直接调用 Azure OpenAI Assistants API。
使用 AIGovernTrustworthyAOAI（AIGovernTrustworthyRG）。

运行方式：
    cd apps/rag-service
    .venv/bin/python scripts/create_agent.py

成功后将输出 Agent ID，需手动填入 .env.local.L4 的 L4_RAG_AGENT_ID。

前置条件：
    - L4_FOUNDRY_NATIVE_MODEL_DEPLOYMENT 已填入
    - L4_RAG_SERVICE_CLIENT_ID / L4_RAG_SERVICE_CLIENT_SECRET / AZURE_TENANT_ID 已填入
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ENV_FILE = Path(__file__).resolve().parents[3] / ".env.local.L4"

_AOAI_ENDPOINT = "https://AIGovernTrustworthyAOAI.openai.azure.com/"
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
    model = _require("L4_FOUNDRY_NATIVE_MODEL_DEPLOYMENT")
    tenant_id = _require("AZURE_TENANT_ID")
    client_id = _require("L4_RAG_SERVICE_CLIENT_ID")
    client_secret = _require("L4_RAG_SERVICE_CLIENT_SECRET")

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

    print(f"[INFO] Azure OpenAI endpoint : {_AOAI_ENDPOINT}")
    print(f"[INFO] Model deployment      : {model}")
    print("[INFO] Creating Assistant with File Search tool...")

    agent = openai_client.beta.assistants.create(
        model=model,
        name="AIGovernTrustworthyDemoRAGAgent",
        instructions=(
            "You are an expert on AI governance standards and regulations. "
            "Answer questions strictly based on the provided knowledge base documents. "
            "Always cite the source document for every claim. "
            "If the answer is not found in the knowledge base, say so clearly."
        ),
        tools=[{"type": "file_search"}],
    )

    print(f"\n[OK] Assistant created successfully.")
    print(f"     Agent ID   : {agent.id}")
    print(f"     Agent name : {agent.name}")
    print(f"\n[ACTION] Add the following line to .env.local.L4:")
    print(f"         L4_RAG_AGENT_ID={agent.id}")


if __name__ == "__main__":
    main()
