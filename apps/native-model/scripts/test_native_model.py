"""
test_native_model.py — 直连 Azure OpenAI 原生模型 deployment，验证推理端点可调用。

不经过 APIM，直接调用 AOAI Chat Completions API（Entra token 认证）。
用于步骤 3 验证（实施顺序步骤 3.6）。

运行方式：
    python3 apps/native-model/scripts/test_native_model.py
    python3 apps/native-model/scripts/test_native_model.py "What is AI governance?"

前置条件：
    - L4_FOUNDRY_NATIVE_MODEL_DEPLOYMENT 已填入 .env.local.L4
    - L4_AOAI_ENDPOINT 已填入 .env.local.L4
    - RAG SPN（L4_RAG_SERVICE_CLIENT_ID）持有 Cognitive Services OpenAI Contributor
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

_ENV_FILE = Path(__file__).resolve().parents[3] / ".env.local.L4"
_API_VERSION = "2025-01-01-preview"
_TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"

_DEFAULT_PROMPTS = [
    "What is AI governance and why does it matter?",
    "Name three key principles of trustworthy AI.",
    "What does NIST AI RMF stand for?",
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


def chat(endpoint: str, deployment: str, token_fn, prompt: str) -> dict:
    url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version={_API_VERSION}"
    headers = {
        "Authorization": f"Bearer {token_fn()}",
        "Content-Type": "application/json",
    }
    body = {
        "messages": [{"role": "user", "content": prompt}],
        "max_completion_tokens": 200,
    }
    r = requests.post(url, headers=headers, json=body, timeout=30)
    r.raise_for_status()
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    model = data.get("model", "?")
    usage = data.get("usage", {})
    return {"content": content, "model": model, "usage": usage}


def main() -> None:
    aoai_endpoint = _require("L4_AOAI_ENDPOINT")
    deployment = _require("L4_FOUNDRY_NATIVE_MODEL_DEPLOYMENT")
    tenant_id = _require("AZURE_TENANT_ID")
    client_id = _require("L4_RAG_SERVICE_CLIENT_ID")
    client_secret = _require("L4_RAG_SERVICE_CLIENT_SECRET")

    prompts = sys.argv[1:] if len(sys.argv) > 1 else _DEFAULT_PROMPTS

    credential = ClientSecretCredential(tenant_id, client_id, client_secret)
    token_fn = lambda: credential.get_token(_TOKEN_SCOPE).token  # noqa: E731

    print(f"[INFO] AOAI endpoint : {aoai_endpoint}")
    print(f"[INFO] Deployment    : {deployment}")
    print(f"[INFO] Prompts       : {len(prompts)}\n")

    all_passed = True
    for i, prompt in enumerate(prompts, 1):
        print(f"{'='*60}")
        print(f"P{i}: {prompt}")
        print(f"{'='*60}")
        try:
            result = chat(aoai_endpoint, deployment, token_fn, prompt)
        except requests.HTTPError as exc:
            print(f"[FAIL] HTTP {exc.response.status_code}: {exc.response.text[:200]}")
            all_passed = False
            continue
        except requests.RequestException as exc:
            print(f"[FAIL] Request error: {exc}")
            all_passed = False
            continue

        content = result["content"]
        print(f"\nModel  : {result['model']}")
        print(f"Tokens : prompt={result['usage'].get('prompt_tokens','?')} "
              f"completion={result['usage'].get('completion_tokens','?')}")
        print(f"\nAnswer ({len(content)} chars):")
        print(content[:400])
        if len(content) > 400:
            print("  ... (truncated)")

        if content.strip():
            print("[PASS] Response received ✓")
        else:
            print("[FAIL] Empty response")
            all_passed = False
        print()

    print(f"{'='*60}")
    if all_passed:
        print("[RESULT] ALL PROMPTS PASSED — Native model endpoint is callable ✅")
    else:
        print("[RESULT] SOME PROMPTS FAILED — review warnings above")
        sys.exit(1)


if __name__ == "__main__":
    main()
