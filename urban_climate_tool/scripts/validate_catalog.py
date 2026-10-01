#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import yaml

from app.core.config import settings
from app.services.catalog_service import CatalogService


def main() -> int:
    try:
        catalog = CatalogService(settings.layer_catalog_path)
        print(f"Catalog loaded successfully: {settings.catalog_path}")
        print(f"Registered layers: {len(catalog.get_all())}")
        print(f"Available layers: {len(catalog.get_available_layers())}")
        return 0
    except Exception as exc:  # pragma: no cover - CLI error reporting
        print(f"Catalog validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
