from pathlib import Path

import pytest
import yaml

from app.core.errors import DataValidationError
from app.schemas.catalog import LayerCatalog
from app.services.catalog_service import CatalogService


def test_catalog_loads_valid_entries() -> None:
    catalog = CatalogService(Path("../catalog/layers.yaml"))
    assert len(catalog.get_all()) >= 1


def test_duplicate_ids_fail() -> None:
    payload = {
        "layers": [
            {"id": "dup", "title": "A", "layer_type": "raster", "relative_path": "rasters/processed/a.tif", "data_format": "geotiff", "legend": {"type": "continuous", "palette": ["#000000", "#ffffff"]}, "style": {"color_scale": "temperature"}},
            {"id": "dup", "title": "B", "layer_type": "raster", "relative_path": "rasters/processed/b.tif", "data_format": "geotiff", "legend": {"type": "continuous", "palette": ["#000000", "#ffffff"]}, "style": {"color_scale": "temperature"}},
        ]
    }
    with pytest.raises(ValueError):
        LayerCatalog.model_validate(payload)


def test_missing_files_fail() -> None:
    catalog = CatalogService(Path("../catalog/layers.yaml"))
    assert catalog.get_all()[0].relative_path
