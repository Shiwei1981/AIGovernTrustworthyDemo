from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests
from azure.identity import ClientSecretCredential

_ENV_FILE = Path(__file__).resolve().parents[3] / ".env.local.L4"
_API_VERSION = "2025-01-01-preview"
_TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"
_MAX_ATTEMPTS = 20
_RETRY_DELAY_SECONDS = 15


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        if value and value not in ("<to-be-created>", "<to-be-deployed>", "<to-be-configured>"):
            os.environ.setdefault(key.strip(), value)


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"[ERROR] Missing required env var: {name}", file=sys.stderr)
        sys.exit(1)
    return value


def _is_deployment_creating(response: requests.Response) -> bool:
    if response.status_code != 400:
        return False
    try:
        payload = response.json()
    except ValueError:
        return False
    error = payload.get("error") or {}
    code = str(error.get("code", "")).strip()
    message = str(error.get("message", "")).strip()
    return code == "DeploymentCreating" or "DeploymentCreating" in message


def main() -> None:
    _load_env(_ENV_FILE)
    deployment = _require("L4_FOUNDRY_FINETUNE_MODEL_DEPLOYMENT")
    full_endpoint = os.environ.get("L4_FOUNDRY_FINETUNE_MODEL_ENDPOINT", "").strip()
    if full_endpoint:
        url = full_endpoint
    else:
        endpoint = _require("L4_AOAI_ENDPOINT")
        url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version={_API_VERSION}"
    tenant_id = _require("AZURE_TENANT_ID")
    client_id = _require("L4_RAG_SERVICE_CLIENT_ID")
    client_secret = _require("L4_RAG_SERVICE_CLIENT_SECRET")
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Summarize why traceability matters in AI governance."

    credential = ClientSecretCredential(tenant_id, client_id, client_secret)
    token = credential.get_token(_TOKEN_SCOPE).token
    response = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "messages": [{"role": "user", "content": prompt}],
                "max_completion_tokens": 300,
            },
            timeout=60,
        )
        if response.ok:
            break
        if attempt < _MAX_ATTEMPTS and _is_deployment_creating(response):
            print(
                f"[INFO] Deployment still warming up (attempt {attempt}/{_MAX_ATTEMPTS}); retrying...",
                file=sys.stderr,
            )
            time.sleep(_RETRY_DELAY_SECONDS)
            continue
        response.raise_for_status()

    if response is None:
        raise RuntimeError("Fine-tuned deployment request did not execute")

    payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    print(content)
    if not content.strip():
        raise RuntimeError("Fine-tuned deployment returned an empty response")


if __name__ == "__main__":
    main()
