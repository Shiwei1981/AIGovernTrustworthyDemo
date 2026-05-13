"""
test_query.py — 调用 Foundry Agent（RAG），验证问答与 citation 返回。

Agent 由 ai.azure.com Portal 创建，存储在 Foundry 命名空间（非 AOAI Assistants），
必须通过 Foundry Agent REST API（token scope: https://ml.azure.com）访问。

运行方式：
    cd apps/rag-service
    .venv/bin/python scripts/test_query.py
    .venv/bin/python scripts/test_query.py "What is NIST AI RMF?"

前置条件：
    - L4_RAG_AGENT_ID 已填入 .env.local.L4
    - L4_FOUNDRY_AGENT_BASE_URL 已填入 .env.local.L4
    - RAG SPN 对 Foundry Project 有读权限（Cognitive Services OpenAI Contributor）
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests

_ENV_FILE = Path(__file__).resolve().parents[3] / ".env.local.L4"
_API_VERSION = "2024-05-01-preview"
_TOKEN_SCOPE = "https://ml.azure.com/.default"

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


def _require(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        print(f"[ERROR] Missing required env var: {name}", file=sys.stderr)
        sys.exit(1)
    return value


class FoundryAgentClient:
    """Minimal REST client for Foundry Agent (Assistants-compatible API)."""

    def __init__(self, base_url: str, token_fn):
        self.base = base_url.rstrip("/")
        self._token_fn = token_fn

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token_fn()}",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self.base}/{path.lstrip('/')}?api-version={_API_VERSION}"

    def create_thread(self) -> str:
        r = requests.post(self._url("threads"), headers=self._headers(), json={})
        r.raise_for_status()
        return r.json()["id"]

    def add_message(self, thread_id: str, content: str) -> None:
        r = requests.post(
            self._url(f"threads/{thread_id}/messages"),
            headers=self._headers(),
            json={"role": "user", "content": content},
        )
        r.raise_for_status()

    def create_run(self, thread_id: str, assistant_id: str) -> str:
        r = requests.post(
            self._url(f"threads/{thread_id}/runs"),
            headers=self._headers(),
            json={"assistant_id": assistant_id},
        )
        r.raise_for_status()
        return r.json()["id"]

    def get_run(self, thread_id: str, run_id: str) -> dict:
        r = requests.get(
            self._url(f"threads/{thread_id}/runs/{run_id}"),
            headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()

    def list_messages(self, thread_id: str) -> list:
        r = requests.get(
            self._url(f"threads/{thread_id}/messages"),
            headers=self._headers(),
        )
        r.raise_for_status()
        return r.json().get("data", [])


def ask(client: FoundryAgentClient, agent_id: str, question: str) -> dict:
    """Send one question to the agent and return answer + citations."""
    thread_id = client.create_thread()
    client.add_message(thread_id, question)
    run_id = client.create_run(thread_id, agent_id)

    for _ in range(60):
        time.sleep(5)
        run = client.get_run(thread_id, run_id)
        if run["status"] in ("completed", "failed", "cancelled", "expired"):
            break

    if run["status"] != "completed":
        return {"status": run["status"], "answer": None, "citations": []}

    messages = client.list_messages(thread_id)
    for msg in messages:
        if msg["role"] == "assistant":
            for block in msg.get("content", []):
                if block.get("type") == "text":
                    text_val = block["text"]["value"]
                    annotations = block["text"].get("annotations", [])
                    citations = [
                        {
                            "file_id": ann.get("file_citation", {}).get("file_id", ""),
                            "text": ann.get("text", "")[:80],
                        }
                        for ann in annotations
                        if ann.get("type") == "file_citation"
                    ]
                    return {
                        "status": "completed",
                        "answer": text_val,
                        "citations": citations,
                    }
    return {"status": "completed", "answer": "(no assistant message)", "citations": []}


def main() -> None:
    agent_id = _require("L4_RAG_AGENT_ID")
    base_url = _require("L4_FOUNDRY_AGENT_BASE_URL")
    tenant_id = _require("AZURE_TENANT_ID")
    client_id = _require("L4_RAG_SERVICE_CLIENT_ID")
    client_secret = _require("L4_RAG_SERVICE_CLIENT_SECRET")

    questions = sys.argv[1:] if len(sys.argv) > 1 else _DEFAULT_QUESTIONS

    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
    )
    client = FoundryAgentClient(
        base_url=base_url,
        token_fn=lambda: credential.get_token(_TOKEN_SCOPE).token,
    )

    print(f"[INFO] Foundry Agent Base : {base_url}")
    print(f"[INFO] Agent ID           : {agent_id}")
    print(f"[INFO] Questions          : {len(questions)}\n")

    all_passed = True
    for i, q in enumerate(questions, 1):
        print(f"{'='*60}")
        print(f"Q{i}: {q}")
        print(f"{'='*60}")
        try:
            result = ask(client, agent_id, q)
        except requests.HTTPError as exc:
            print(f"[FAIL] HTTP error: {exc}")
            all_passed = False
            continue

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
