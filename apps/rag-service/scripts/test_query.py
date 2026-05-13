"""
test_query.py — 直连 Azure OpenAI Assistant（RAG Agent），验证问答与 citation 返回。

不经过 APIM，直接调用 Azure OpenAI Assistants API（Entra token 认证）。
用于本地开发验证（实施顺序步骤 5）。

运行方式：
    cd apps/rag-service
    .venv/bin/python scripts/test_query.py
    .venv/bin/python scripts/test_query.py "What is NIST AI RMF?"

前置条件：
    - L4_RAG_AGENT_ID 已填入 .env.local.L4
    - Azure OpenAI endpoint 可访问（RAG SPN 持有 Cognitive Services OpenAI Contributor）
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

_ENV_FILE = Path(__file__).resolve().parents[3] / ".env.local.L4"
_AOAI_ENDPOINT = "https://AIGovernTrustworthyAOAI.openai.azure.com/"
_AOAI_API_VERSION = "2025-01-01-preview"

_DEFAULT_QUESTIONS = [
    "What are the four core functions of the NIST AI Risk Management Framework?",
    "What does the EU AI Act say about prohibited AI practices?",
    "What are the OWASP LLM Top 10 risks for 2025?",
]


def _load_env(path: Path) -> None:
    if not path.exists():
        print(f"[WARN] env file not found: {path}", file=sys.stderr)
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip().strip('"').strip("'")
        if v and v not in ("<to-be-created>", "<to-be-deployed>", "<to-be-configured>"):
            os.environ.setdefault(k.strip(), v)


_load_env(_ENV_FILE)

from azure.identity import ClientSecretCredential  # noqa: E402
from openai import AzureOpenAI  # noqa: E402


def _require(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        print(f"[ERROR] Missing required env var: {name}", file=sys.stderr)
        sys.exit(1)
    return value


def ask(client: AzureOpenAI, agent_id: str, question: str) -> dict:
    """Send one question to the agent and return answer + citations."""
    thread = client.beta.threads.create()
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=question,
    )
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=agent_id,
    )

    for _ in range(60):
        time.sleep(5)
        run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run.status in ("completed", "failed", "cancelled", "expired"):
            break

    if run.status != "completed":
        return {"status": run.status, "answer": None, "citations": []}

    messages = client.beta.threads.messages.list(thread_id=thread.id)
    for msg in messages.data:
        if msg.role == "assistant":
            for block in msg.content:
                if hasattr(block, "text"):
                    citations = [
                        {
                            "file_id": ann.file_citation.file_id,
                            "text": ann.text[:80] if ann.text else "",
                        }
                        for ann in block.text.annotations
                        if hasattr(ann, "file_citation")
                    ]
                    return {
                        "status": "completed",
                        "answer": block.text.value,
                        "citations": citations,
                    }
    return {"status": "completed", "answer": "(no assistant message)", "citations": []}


def main() -> None:
    agent_id = _require("L4_RAG_AGENT_ID")
    tenant_id = _require("AZURE_TENANT_ID")
    client_id = _require("L4_RAG_SERVICE_CLIENT_ID")
    client_secret = _require("L4_RAG_SERVICE_CLIENT_SECRET")

    questions = sys.argv[1:] if len(sys.argv) > 1 else _DEFAULT_QUESTIONS

    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
    )
    client = AzureOpenAI(
        azure_endpoint=_AOAI_ENDPOINT,
        api_version=_AOAI_API_VERSION,
        azure_ad_token_provider=lambda: credential.get_token(
            "https://cognitiveservices.azure.com/.default"
        ).token,
    )

    print(f"[INFO] Agent ID : {agent_id}")
    print(f"[INFO] Questions: {len(questions)}\n")

    all_passed = True
    for i, q in enumerate(questions, 1):
        print(f"{'='*60}")
        print(f"Q{i}: {q}")
        print(f"{'='*60}")
        result = ask(client, agent_id, q)

        if result["status"] != "completed":
            print(f"[FAIL] Run ended with status: {result['status']}")
            all_passed = False
            continue

        answer = result["answer"] or ""
        citations = result["citations"]
        print(f"\nAnswer ({len(answer)} chars):")
        print(answer[:600])
        if len(answer) > 600:
            print("  ... (truncated)")

        print(f"\nCitations: {len(citations)}")
        for c in citations[:5]:
            print(f"  file_id={c['file_id']}  text={c['text']!r}")

        if not citations:
            print("[WARN] No citations returned — source attribution will be 0% for this query")
            all_passed = False
        else:
            print("[PASS] Citations present ✓")
        print()

    print(f"{'='*60}")
    if all_passed:
        print("[RESULT] ALL QUERIES PASSED — RAG Agent is answering with citations ✅")
    else:
        print("[RESULT] SOME QUERIES FAILED — review warnings above")
        sys.exit(1)


if __name__ == "__main__":
    main()
