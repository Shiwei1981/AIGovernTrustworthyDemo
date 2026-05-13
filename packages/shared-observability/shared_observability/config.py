"""Configuration loading for shared observability."""

from __future__ import annotations

from dataclasses import dataclass
from os import getenv

from .errors import ConfigurationError


@dataclass(slots=True)
class BlobSettings:
    account_name: str
    container: str
    prefix: str


@dataclass(slots=True)
class TelemetrySettings:
    connection_string: str


@dataclass(slots=True)
class ObservabilitySettings:
    package_name: str
    blob: BlobSettings
    telemetry: TelemetrySettings


def _require_env(name: str) -> str:
    value = getenv(name)
    if value is None or not value.strip():
        raise ConfigurationError(f"Missing required environment variable: {name}")
    return value.strip()


def load_settings_from_env() -> ObservabilitySettings:
    """Load and validate the minimum settings needed by the package."""

    return ObservabilitySettings(
        package_name=_require_env("L4_OBSERVABILITY_PACKAGE_NAME"),
        blob=BlobSettings(
            account_name=_require_env("L4_OBSERVABILITY_BLOB_STORAGE_ACCOUNT_NAME"),
            container=_require_env("L4_OBSERVABILITY_BLOB_CONTAINER"),
            prefix=_require_env("L4_OBSERVABILITY_BLOB_PREFIX"),
        ),
        telemetry=TelemetrySettings(
            connection_string=_require_env("APPLICATIONINSIGHTS_CONNECTION_STRING"),
        ),
    )