"""
test_e2e_via_apim.py — 真实流量端到端测试（经 APIM gateway → Foundry Agent）

测试内容：
  客户端不携带任何 Authorization header，直接调用 APIM gateway URL。
  APIM inbound policy 负责注入 MSI token 后转发给 Foundry Agent。
  验证：APIM token 注入 → Foundry Agent 执行 → 返回回答 + citations。

网络前提：
  APIM 是 Internal VNet 模式（私网 IP 10.1.2.4）。
  本机 /etc/hosts 已添加：10.1.2.4  aigoverntrustworthydemoapim.azure-api.net

运行方式：
    cd apps/rag-service
    .venv/bin/python scripts/test_e2e_via_apim.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests

_ENV_FILE = Path(__file__).resolve().parents[3] / ".env.local.L4"
_API_VERSION = "2024-05-01-preview"
_TEST_QUESTION = "What are the four core functions of the NIST AI Risk Management Framework?"
_AGENT_ID = "asst_sFQ8LdzWZsExbdIYc8z2MkjV"


def _load_env(path: Path) -> None:
    if not path.exists():
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


def main() -> None:
    gateway = os.environ.get("L4_APIM_GATEWAY_URL", "https://aigoverntrustworthydemoapim.azure-api.net")
    base = f"{gateway.rstrip('/')}/rag"

    # 客户端不携带 Authorization — 由 APIM MSI policy 注入
    headers = {"Content-Type": "application/json"}

    print("=" * 60)
    print("End-to-End APIM Gateway Test")
    print(f"  Gateway : {gateway}")
    print(f"  Path    : /rag  (→ Foundry Agent {_AGENT_ID})")
    print(f"  Auth    : NONE from client (APIM MSI token injection)")
    print("=" * 60)
    print()

    def url(path):
        return f"{base}/{path.lstrip('/')}?api-version={_API_VERSION}"

    # Step 1: Create thread
    print("[1/5] POST /rag/threads ...")
    r = requests.post(url("threads"), headers=headers, json={})
    print(f"      HTTP {r.status_code}")
    if r.status_code != 200:
        print(f"[FAIL] {r.text[:200]}")
        sys.exit(1)
    thread_id = r.json()["id"]
    print(f"      thread_id = {thread_id}")

    # Step 2: Add message
    print(f"\n[2/5] POST /rag/threads/{thread_id[:16]}…/messages ...")
    r = requests.post(url(f"threads/{thread_id}/messages"), headers=headers,
                      json={"role": "user", "content": _TEST_QUESTION})
    print(f"      HTTP {r.status_code}")
    if r.status_code != 200:
        print(f"[FAIL] {r.text[:200]}")
        sys.exit(1)

    # Step 3: Create run
    print(f"\n[3/5] POST /rag/threads/{thread_id[:16]}…/runs ...")
    r = requests.post(url(f"threads/{thread_id}/runs"), headers=headers,
                      json={"assistant_id": _AGENT_ID})
    print(f"      HTTP {r.status_code}")
    if r.status_code != 200:
        print(f"[FAIL] {r.text[:200]}")
        sys.exit(1)
    run_id = r.json()["id"]
    print(f"      run_id = {run_id}")

    # Step 4: Poll run status
    print(f"\n[4/5] Polling run status ...")
    status = "queued"
    for i in range(60):
        time.sleep(5)
        r = requests.get(url(f"threads/{thread_id}/runs/{run_id}"), headers=headers)
        if r.status_code != 200:
            print(f"[FAIL] Poll HTTP {r.status_code}: {r.text[:100]}")
            sys.exit(1)
        status = r.json()["status"]
        print(f"      [{i*5+5:3d}s] status = {status}")
        if status in ("completed", "failed", "cancelled", "expired"):
            break

    if status != "completed":
        print(f"[FAIL] Run ended with status: {status}")
        sys.exit(1)

    # Step 5: List messages
    print(f"\n[5/5] GET /rag/threads/{thread_id[:16]}…/messages ...")
    r = requests.get(url(f"threads/{thread_id}/messages"), headers=headers)
    print(f"      HTTP {r.status_code}")
    if r.status_code != 200:
        print(f"[FAIL] {r.text[:200]}")
        sys.exit(1)

    answer = None
    citations = []
    for msg in r.json().get("data", []):
        if msg["role"] == "assistant":
            for block in msg.get("content", []):
                if block.get("type") == "text":
                    answer = block["text"]["value"]
                    citations = [a for a in block["text"].get("annotations", [])
                                 if a.get("type") == "file_citation"]
                    break
        if answer:
            break

    print()
    print("=" * 60)
    print("RESULT")
    print("=" * 60)
    if answer:
        print(f"  Answer ({len(answer)} chars): {answer[:300]}...")
        print(f"  Citations : {len(citations)}")
        for c in citations[:3]:
            print(f"    - {c.get('text','')}")
        print()
        if citations:
            print("[RESULT] ✅ PASS — 真实流量经 APIM gateway → Foundry Agent，回答+citations 均正常")
        else:
            print("[RESULT] ⚠️  回答正常但无 citations")
    else:
        print("[RESULT] ✗ FAIL — 未收到 assistant 消息")
        sys.exit(1)


if __name__ == "__main__":
    main()
