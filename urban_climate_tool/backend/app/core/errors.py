from __future__ import annotations

class DataValidationError(ValueError):
    """Raised when a registered dataset is invalid."""


class LayerNotFoundError(KeyError):
    """Raised when a dataset ID is not registered."""


class LayerUnavailableError(RuntimeError):
    """Raised when a layer file is missing or unusable."""


class InvalidLayerTypeError(TypeError):
    """Raised when a dataset does not match the expected type."""


class StoragePathError(ValueError):
    """Raised when a path escapes DATA_ROOT."""
