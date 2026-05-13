"""Blob archive writer for LLM evidence payloads."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from azure.core.credentials import TokenCredential

from .errors import BlobWriteError


def write_evidence_archive(
    *,
    account_name: str,
    container: str,
    credential: "TokenCredential",
    input_path: str,
    output_path: str,
    metadata_path: str,
    input_bytes: bytes,
    output_bytes: bytes,
    metadata_bytes: bytes,
) -> None:
    """Upload input.json, output.json, metadata.json to Blob Storage.

    Uses Entra ID authentication via the supplied ``credential``; no storage
    account keys or SAS tokens are used.  Raises ``BlobWriteError`` on any
    failure (no retry — R-013).
    """
    try:
        from azure.storage.blob import BlobServiceClient
    except ImportError as exc:
        raise BlobWriteError(
            "azure-storage-blob is required: pip install azure-storage-blob"
        ) from exc

    try:
        svc = BlobServiceClient(
            account_url=f"https://{account_name}.blob.core.windows.net",
            credential=credential,
        )
        cc = svc.get_container_client(container)
        cc.get_blob_client(input_path).upload_blob(input_bytes, overwrite=True)
        cc.get_blob_client(output_path).upload_blob(output_bytes, overwrite=True)
        cc.get_blob_client(metadata_path).upload_blob(metadata_bytes, overwrite=True)
    except BlobWriteError:
        raise
    except Exception as exc:
        raise BlobWriteError(f"Failed to write evidence archive: {exc}") from exc
