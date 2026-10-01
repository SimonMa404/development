from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class Repository(ABC):
    """Abstract repository interface for geospatial datasets."""

    @abstractmethod
    def resolve_path(self, relative_path: str) -> Path:
        """Return the absolute path for a registered dataset and ensure it is inside DATA_ROOT."""

    @abstractmethod
    def exists(self, relative_path: str) -> bool:
        """Check whether a dataset is present."""

    @abstractmethod
    def read_bytes(self, relative_path: str) -> bytes:
        """Read file bytes for a dataset."""


class LocalRepository(Repository):
    def __init__(self, data_root: str | Path):
        self.data_root = Path(data_root).expanduser().resolve()

    def resolve_path(self, relative_path: str) -> Path:
        candidate = (self.data_root / relative_path).resolve()
        if self.data_root not in candidate.parents and candidate != self.data_root:
            raise ValueError(f"Path escapes DATA_ROOT: {relative_path}")
        return candidate

    def exists(self, relative_path: str) -> bool:
        try:
            return self.resolve_path(relative_path).exists()
        except ValueError:
            return False

    def read_bytes(self, relative_path: str) -> bytes:
        path = self.resolve_path(relative_path)
        return path.read_bytes()
