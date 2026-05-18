"""Shared Trace Chain backend helpers for Tier 1 and Tier 2 consumer apps."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any

from azure.core.credentials import TokenCredential
from azure.storage.blob import BlobServiceClient


def query_trace_chain(
    *,
    trace_id: str,
    credential: TokenCredential,
    preferred_source_type: str = "tier1_consumer",
    logger: Any | None = None,
) -> dict[str, Any]:
    """Query App Insights evidence and Blob archive payloads for one trace."""
    safe_id = "".join(c for c in trace_id if c in "0123456789abcdefABCDEF")
    if not safe_id:
        raise ValueError("Invalid trace_id")

    query = (
        "union requests, dependencies, traces "
        "| where timestamp > ago(7d) "
        f"| where * has '{safe_id}' "
        "| project timestamp, itemType, id, operation_Id, operation_ParentId, "
        "cloud_RoleName, name, message, resultCode, success, duration, customDimensions "
        "| order by timestamp asc | limit 80"
    )
    rows = _query_app_insights(query, credential, logger)

    evidence_rows: list[dict[str, Any]] = []
    requests_list: list[dict[str, Any]] = []
    deps_list: list[dict[str, Any]] = []

    for row in rows:
        if len(row) < 12:
            continue
        ts, item_type, rid, _op_id, parent_id, role, name, message, result_code, success, duration, custom_dims = row
        if item_type == "trace" and message == "AIGovernTrustworthyLLMEvidence":
            try:
                dims = json.loads(custom_dims) if isinstance(custom_dims, str) else (custom_dims or {})
                ref = dims.get("aigov.payload.ref", "")
                evidence_entry = {"timestamp": ts}
                evidence_entry.update(dims)
                evidence_rows.append({
                    "timestamp": ts,
                    "evidence": evidence_entry,
                    "archive_prefix": ref.rstrip("/") if ref else "",
                })
            except Exception as exc:
                _warn(logger, "Failed to parse evidence row: %s", exc)
        elif item_type == "request":
            requests_list.append({
                "timestamp": ts,
                "id": rid,
                "parent_id": parent_id,
                "role": role or "",
                "name": name or "",
                "result_code": result_code or "",
                "success": bool(success),
                "duration_ms": round(float(duration or 0), 1),
            })
        elif item_type == "dependency":
            deps_list.append({
                "timestamp": ts,
                "id": rid,
                "parent_id": parent_id,
                "role": role or "",
                "name": name or "",
                "result_code": result_code or "",
                "success": bool(success),
                "duration_ms": round(float(duration or 0), 1),
            })

    evidence = (
        next(
            (entry["evidence"] for entry in evidence_rows if entry["evidence"].get("aigov.source.type") == preferred_source_type),
            None,
        )
        or (evidence_rows[0]["evidence"] if evidence_rows else {})
    )
    primary_archive_prefix = (
        next(
            (entry["archive_prefix"] for entry in evidence_rows if entry["evidence"].get("aigov.source.type") == preferred_source_type),
            "",
        )
        or (evidence_rows[0]["archive_prefix"] if evidence_rows else "")
    )

    primary_blob = _load_blob_archive(primary_archive_prefix, credential, logger)
    blob_archives = []
    for entry in evidence_rows:
        archive = _load_blob_archive(entry["archive_prefix"], credential, logger)
        blob_archives.append({
            "timestamp": entry["timestamp"],
            "service_name": entry["evidence"].get("service.name", ""),
            "source_type": entry["evidence"].get("aigov.source.type", ""),
            "target_type": entry["evidence"].get("aigov.target.type", ""),
            "target_id": entry["evidence"].get("aigov.target.id", ""),
            "archive_id": entry["evidence"].get("aigov.archive.id", ""),
            "payload_ref": entry["evidence"].get("aigov.payload.ref", ""),
            **archive,
        })

    return {
        "trace_id": safe_id,
        "evidence": evidence,
        "evidences": [entry["evidence"] for entry in evidence_rows],
        "blob_metadata": primary_blob["blob_metadata"],
        "blob_input": primary_blob["blob_input"],
        "blob_output": primary_blob["blob_output"],
        "blob_archives": blob_archives,
        "requests": requests_list,
        "dependencies": deps_list,
    }


def _query_app_insights(query: str, credential: TokenCredential, logger: Any | None) -> list[list[Any]]:
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
    if not connection_string:
        raise RuntimeError("Missing required environment variable: APPLICATIONINSIGHTS_CONNECTION_STRING")
    app_id = _connection_string_parts(connection_string).get("ApplicationId", "").strip()
    if not app_id:
        raise RuntimeError("APPLICATIONINSIGHTS_CONNECTION_STRING is missing ApplicationId")

    token = credential.get_token("https://api.applicationinsights.io/.default").token
    url = f"https://api.applicationinsights.io/v1/apps/{app_id}/query?query={urllib.parse.quote(query)}"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read())
    except Exception as exc:
        _warn(logger, "App Insights trace query failed: %s", exc)
        return []

    tables = payload.get("tables") or []
    if not tables:
        return []
    rows = tables[0].get("rows")
    return rows if isinstance(rows, list) else []


def _load_blob_archive(archive_prefix: str, credential: TokenCredential, logger: Any | None) -> dict[str, Any]:
    blob_metadata: dict[str, Any] = {}
    blob_input = None
    blob_output = None
    if not archive_prefix:
        return {
            "blob_metadata": blob_metadata,
            "blob_input": blob_input,
            "blob_output": blob_output,
        }

    container_client = _blob_container_client(credential)
    for suffix in ("metadata.json", "input.json", "output.json"):
        blob_path = f"{archive_prefix}/{suffix}"
        try:
            payload = container_client.get_blob_client(blob_path).download_blob().readall()
            content = json.loads(payload)
            if suffix == "metadata.json":
                blob_metadata = content
            elif suffix == "input.json":
                blob_input = content
            else:
                blob_output = content
        except Exception as exc:
            _warn(logger, "Failed to load blob archive payload %s: %s", blob_path, exc)
    return {
        "blob_metadata": blob_metadata,
        "blob_input": blob_input,
        "blob_output": blob_output,
    }


def _blob_container_client(credential: TokenCredential) -> Any:
    account_name = os.getenv("L4_OBSERVABILITY_BLOB_STORAGE_ACCOUNT_NAME", "").strip()
    container_name = os.getenv("L4_OBSERVABILITY_BLOB_CONTAINER", "").strip()
    if not account_name:
        raise RuntimeError("Missing required environment variable: L4_OBSERVABILITY_BLOB_STORAGE_ACCOUNT_NAME")
    if not container_name:
        raise RuntimeError("Missing required environment variable: L4_OBSERVABILITY_BLOB_CONTAINER")
    service_client = BlobServiceClient(
        account_url=f"https://{account_name}.blob.core.windows.net",
        credential=credential,
    )
    return service_client.get_container_client(container_name)


def _connection_string_parts(connection_string: str) -> dict[str, str]:
    return {
        name.strip(): value.strip()
        for segment in connection_string.split(";")
        if "=" in segment
        for name, value in [segment.split("=", 1)]
    }


def _warn(logger: Any | None, message: str, *args: Any) -> None:
    if logger is not None:
        logger.warning(message, *args)
