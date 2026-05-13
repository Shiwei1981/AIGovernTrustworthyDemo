"""Error types for shared observability."""


class ObservabilityError(Exception):
    """Base class for package errors."""


class ConfigurationError(ObservabilityError):
    """Raised when required configuration is missing or invalid."""


class ValidationError(ObservabilityError):
    """Raised when evidence input does not satisfy contract requirements."""


class SerializationError(ObservabilityError):
    """Raised when a payload cannot be serialized into stable JSON."""


class BlobWriteError(ObservabilityError):
    """Raised when evidence archive blobs cannot be written to Blob Storage."""


class TelemetryEmitError(ObservabilityError):
    """Raised when the thin evidence event cannot be emitted to App Insights."""