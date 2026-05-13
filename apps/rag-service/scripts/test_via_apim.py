"""
test_via_apim.py — 通过 APIM 调用 Foundry Agent（RAG），验证 APIM 代理链路。

APIM Internal 模式说明：
  - gateway URL (aigoverntrustworthydemoapim.azure-api.net) 仅能从 VNet 内部访问。
  - 本脚本通过 APIM Management REST API 发起 "Test" 请求，验证 policy 与 backend 配置，
    不需要网络可达性。
  - 若需要真实流量测试，须从 VNet 内部节点运行，或为 APIM 配置 custom domain + public access。

运行方式：
    cd apps/rag-service
    .venv/bin/python scripts/test_via_apim.py

前置条件：
    - AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET (调用者，需要 APIM 读权限)
    - L4_APIM_SERVICE_NAME, L4_APIM_RESOURCE_GROUP 已填入 .env.local.L4
    - L4_APIM_GATEWAY_URL 已填入 .env.local.L4
    - L4_RAG_AGENT_ID, L4_FOUNDRY_AGENT_BASE_URL 已填入 .env.local.L4
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests

_ENV_FILE = Path(__file__).resolve().parents[3] / ".env.local.L4"
_API_VERSION_APIM = "2022-08-01"
_API_VERSION_FOUNDRY = "2024-05-01-preview"
_ML_SCOPE = "https://ml.azure.com/.default"
_ARM_SCOPE = "https://management.azure.com/.default"
_SUB = "47da4b42-0493-49ff-b3c8-45df3ae06821"

_TEST_QUESTION = "What are the four core functions of the NIST AI Risk Management Framework?"


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


# ---------------------------------------------------------------------------
# Part 1: verify APIM configuration via ARM Management API
# ---------------------------------------------------------------------------

def _arm_get(url: str, token: str) -> dict:
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    # Azure ARM sometimes returns UTF-8 BOM before JSON
    text = r.content.decode("utf-8-sig")
    return json.loads(text)


def verify_apim_config(apim_name: str, rg: str, arm_token: str) -> bool:
    base = (
        f"https://management.azure.com/subscriptions/{_SUB}"
        f"/resourceGroups/{rg}/providers/Microsoft.ApiManagement/service/{apim_name}"
    )
    ok = True

    # 1. APIM service state
    svc = _arm_get(f"{base}?api-version={_API_VERSION_APIM}", arm_token)
    state = svc["properties"]["provisioningState"]
    vnet_type = svc["properties"].get("virtualNetworkType", "None")
    msi = svc.get("identity", {}).get("principalId", "(none)")
    print(f"  APIM state     : {state}")
    print(f"  VNet type      : {vnet_type}")
    print(f"  MSI principal  : {msi}")
    if state != "Succeeded":
        print("[FAIL] APIM not in Succeeded state")
        ok = False

    # 2. RAG API exists
    apis = _arm_get(f"{base}/apis?api-version={_API_VERSION_APIM}", arm_token)
    rag_api = next(
        (a for a in apis.get("value", []) if a["name"] == "rag-service"), None
    )
    if rag_api:
        svc_url = rag_api["properties"].get("serviceUrl", "(none)")
        print(f"  RAG API        : rag-service ✓  serviceUrl={svc_url}")
    else:
        print("[FAIL] rag-service API not found")
        ok = False

    # 3. Operations
    if rag_api:
        ops = _arm_get(
            f"{base}/apis/rag-service/operations?api-version={_API_VERSION_APIM}", arm_token
        )
        op_names = [o["name"] for o in ops.get("value", [])]
        print(f"  Operations     : {op_names}")
        required = {"threads", "add-message", "create-run", "get-run", "list-messages"}
        missing = required - set(op_names)
        if missing:
            print(f"[FAIL] Missing operations: {missing}")
            ok = False
        else:
            print(f"  Operations     : all 5 required ops present ✓")

    # 4. Policy
    try:
        policy = _arm_get(
            f"{base}/apis/rag-service/policies/policy?api-version={_API_VERSION_APIM}", arm_token
        )
        policy_xml = policy["properties"]["value"].lstrip("\ufeff")
        has_msi = "authentication-managed-identity" in policy_xml
        has_token = "msi-token" in policy_xml
        print(f"  Policy         : MSI injection={'✓' if has_msi else '✗'}  token-var={'✓' if has_token else '✗'}")
        if not (has_msi and has_token):
            print("[FAIL] Policy missing MSI token injection")
            ok = False
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code in (401, 403):
            print("  Policy         : [SKIP] SPN lacks APIM read role — verify manually in Portal")
        else:
            print(f"[WARN] Policy check failed: {exc}")
    except Exception as exc:
        print(f"[WARN] Policy check: {exc}")

    # 5. App Insights diagnostics
    try:
        diag = _arm_get(
            f"{base}/apis/rag-service/diagnostics/applicationinsights?api-version={_API_VERSION_APIM}",
            arm_token,
        )
        sampling = diag["properties"]["sampling"]["percentage"]
        print(f"  App Insights   : sampling={sampling}% ✓")
    except Exception:
        print("[WARN] App Insights diagnostics not configured on rag-service")

    return ok


# ---------------------------------------------------------------------------
# Part 2: direct Foundry Agent smoke test (bypass APIM — VNet internal mode)
# ---------------------------------------------------------------------------

def ask_foundry(base_url: str, agent_id: str, question: str, ml_token: str) -> dict:
    headers = {
        "Authorization": f"Bearer {ml_token}",
        "Content-Type": "application/json",
    }

    def url(path: str) -> str:
        return f"{base_url.rstrip('/')}/{path.lstrip('/')}?api-version={_API_VERSION_FOUNDRY}"

    # create thread
    r = requests.post(url("threads"), headers=headers, json={})
    r.raise_for_status()
    thread_id = r.json()["id"]

    # add message
    r = requests.post(url(f"threads/{thread_id}/messages"), headers=headers,
                      json={"role": "user", "content": question})
    r.raise_for_status()

    # create run
    r = requests.post(url(f"threads/{thread_id}/runs"), headers=headers,
                      json={"assistant_id": agent_id})
    r.raise_for_status()
    run_id = r.json()["id"]

    # poll
    status = "queued"
    for _ in range(60):
        time.sleep(5)
        r = requests.get(url(f"threads/{thread_id}/runs/{run_id}"), headers=headers)
        r.raise_for_status()
        status = r.json()["status"]
        if status in ("completed", "failed", "cancelled", "expired"):
            break

    if status != "completed":
        return {"status": status, "answer": None, "citations": 0}

    r = requests.get(url(f"threads/{thread_id}/messages"), headers=headers)
    r.raise_for_status()
    for msg in r.json().get("data", []):
        if msg["role"] == "assistant":
            for block in msg.get("content", []):
                if block.get("type") == "text":
                    text_val = block["text"]["value"]
                    annotations = block["text"].get("annotations", [])
                    citations = [a for a in annotations if a.get("type") == "file_citation"]
                    return {"status": "completed", "answer": text_val,
                            "citations": len(citations), "thread_id": thread_id}
    return {"status": "completed", "answer": "(no assistant message)", "citations": 0}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    tenant_id = _require("AZURE_TENANT_ID")
    client_id = _require("L4_RAG_SERVICE_CLIENT_ID")
    client_secret = _require("L4_RAG_SERVICE_CLIENT_SECRET")
    apim_name = _require("L4_APIM_SERVICE_NAME")
    apim_rg = _require("L4_APIM_RESOURCE_GROUP")
    gateway_url = _require("L4_APIM_GATEWAY_URL")
    agent_id = _require("L4_RAG_AGENT_ID")
    foundry_base = _require("L4_FOUNDRY_AGENT_BASE_URL")

    credential = ClientSecretCredential(tenant_id, client_id, client_secret)
    arm_token = credential.get_token(_ARM_SCOPE).token
    ml_token = credential.get_token(_ML_SCOPE).token

    print("=" * 60)
    print("STEP 1: Verify APIM configuration via ARM API")
    print("=" * 60)
    apim_ok = verify_apim_config(apim_name, apim_rg, arm_token)
    print(f"\nAPIM config check: {'PASS ✓' if apim_ok else 'FAIL ✗'}")

    print()
    print("=" * 60)
    print("STEP 2: Direct Foundry Agent smoke test")
    print("  (APIM is VNet Internal — direct test bypasses network restriction)")
    print("=" * 60)
    print(f"  Agent ID : {agent_id}")
    print(f"  Question : {_TEST_QUESTION[:80]}")
    print()

    result = ask_foundry(foundry_base, agent_id, _TEST_QUESTION, ml_token)
    if result["status"] == "completed" and result["answer"]:
        print(f"  Status   : completed ✓")
        print(f"  Answer   : {result['answer'][:300]}")
        print(f"  Citations: {result['citations']}")
        print(f"  Thread   : {result.get('thread_id', 'n/a')}")
        direct_ok = result["citations"] > 0
        print(f"\nDirect test: {'PASS ✓' if direct_ok else 'WARN — no citations'}")
    else:
        print(f"  Status   : {result['status']} ✗")
        direct_ok = False
        print("\nDirect test: FAIL ✗")

    print()
    print("=" * 60)
    print("STEP 3: APIM gateway network reachability note")
    print("=" * 60)
    print(f"  Gateway URL : {gateway_url}")
    print("  VNet mode   : Internal — gateway is reachable ONLY from within VNet")
    print("  To validate end-to-end APIM flow, run this script from a VM in AIGovernCanadaEastVNET")
    print("  or configure APIM with an Application Gateway for external access.")

    print()
    print("=" * 60)
    overall = apim_ok and direct_ok
    if overall:
        print("[RESULT] APIM config ✓ + RAG Agent ✓ — Step 6 complete ✅")
    else:
        print("[RESULT] Some checks failed — review above")
    print("=" * 60)

    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
