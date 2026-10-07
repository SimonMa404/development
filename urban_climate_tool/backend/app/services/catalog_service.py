from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.core.config import settings
from app.core.errors import DataValidationError, LayerNotFoundError, LayerUnavailableError
from app.schemas.catalog import LayerCatalog, LayerCatalogEntry


class CatalogService:
    def __init__(self, catalog_path: str | Path | None = None):
        self.catalog_path = Path(catalog_path) if catalog_path else settings.catalog_path
        if not self.catalog_path.is_absolute():
            self.catalog_path = (settings.catalog_path.parent / self.catalog_path).resolve()
        self.catalog = self.load_catalog()

    def load_catalog(self) -> LayerCatalog:
        if not self.catalog_path.exists():
            raise FileNotFoundError(f"Catalog file does not exist: {self.catalog_path}")

        with self.catalog_path.open("r", encoding="utf-8") as file:
            payload = yaml.safe_load(file) or {}

        if "layers" not in payload:
            raise DataValidationError("Catalog must contain a top-level 'layers' list.")

        catalog = LayerCatalog.model_validate(payload)
        self.validate_registered_files(catalog)
        return catalog

    def validate_registered_files(self, catalog: LayerCatalog) -> None:
        root = settings.data_root_path.resolve()
        for layer in catalog.layers:
            path = (root / layer.relative_path).resolve()
            if not str(path).startswith(str(root)):
                raise DataValidationError(f"Layer '{layer.id}' resolves outside DATA_ROOT.")
            if layer.layer_type == "raster" and layer.data_format.lower() not in {"geotiff", "tif", "tiff"}:
                raise DataValidationError(f"Raster layer '{layer.id}' has unsupported data format '{layer.data_format}'.")
            if layer.layer_type == "vector" and layer.data_format.lower() not in {"geojson", "gpkg", "shapefile", "shp", "parquet", "geoparquet"}:
                raise DataValidationError(f"Vector layer '{layer.id}' has unsupported data format '{layer.data_format}'.")
            if layer.legend is None and layer.layer_type in {"raster", "vector"}:
                raise DataValidationError(f"Layer '{layer.id}' is missing legend metadata.")
            if layer.style is None and layer.layer_type in {"raster", "vector"}:
                raise DataValidationError(f"Layer '{layer.id}' is missing style metadata.")

    def get_all(self) -> list[LayerCatalogEntry]:
        return list(self.catalog.layers)

    def get_by_id(self, layer_id: str) -> LayerCatalogEntry:
        for layer in self.catalog.layers:
            if layer.id == layer_id:
                return layer
        raise LayerNotFoundError(f"Unknown layer: {layer_id}")

    def list_frontend_layers(self) -> list[dict[str, Any]]:
        layers: list[dict[str, Any]] = []
        for layer in self.catalog.layers:
            path = (settings.data_root_path / layer.relative_path).resolve()
            available = path.exists()
            layers.append(
                {
                    "id": layer.id,
                    "title": layer.title,
                    "short_title": layer.short_title,
                    "description": layer.description,
                    "layer_type": layer.layer_type,
                    "thematic_group": layer.thematic_group,
                    "storage_backend": layer.storage_backend,
                    "data_format": layer.data_format,
                    "relative_path": layer.relative_path,
                    "source": layer.source,
                    "attribution": layer.attribution,
                    "units": layer.units,
                    "value_type": layer.value_type,
                    "native_crs": layer.native_crs,
                    "bounds": layer.bounds,
                    "acquisition_date": layer.acquisition_date,
                    "spatial_resolution": layer.spatial_resolution,
                    "nodata": layer.nodata,
                    "value_range": layer.value_range.model_dump() if layer.value_range else None,
                    "default_visible": layer.default_visible,
                    "default_opacity": layer.default_opacity,
                    "default_order": layer.default_order,
                    "min_zoom": layer.min_zoom,
                    "max_zoom": layer.max_zoom,
                    "inspectable": layer.inspectable,
                    "selectable": layer.selectable,
                    "style": layer.style.model_dump() if layer.style else None,
                    "legend": layer.legend.model_dump() if layer.legend else None,
                    "analysis_capabilities": layer.analysis_capabilities,
                    "tags": layer.tags,
                    "is_demo": layer.is_demo,
                    "available": available,
                }
            )
        return layers

    def get_available_layers(self) -> list[LayerCatalogEntry]:
        available: list[LayerCatalogEntry] = []
        for layer in self.catalog.layers:
            if (settings.data_root_path / layer.relative_path).resolve().exists():
                available.append(layer)
        return available
