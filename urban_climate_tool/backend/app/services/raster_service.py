from __future__ import annotations

from typing import Any

import numpy as np
import rasterio
import requests
from rasterio.io import MemoryFile
from rio_tiler.errors import TileOutsideBounds
from rio_tiler.io import Reader

from app.core.config import settings
from app.core.errors import LayerUnavailableError
from app.repositories.local_raster import LocalRasterRepository
from app.services.catalog_service import CatalogService

ColorMap = dict[int, tuple[int, int, int, int]]
GLOBAL_TERRAIN_30M_TEMPLATE = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def _build_continuous_colormap(palette: list[str]) -> ColorMap:
    """Interpolate a hex palette into a 256-entry RGBA colormap for rescaled (0-255) data."""
    colors = [_hex_to_rgb(color) for color in palette]
    steps = len(colors)
    colormap: ColorMap = {}
    for i in range(256):
        position = i / 255 * (steps - 1)
        index = int(position)
        fraction = position - index
        if index >= steps - 1:
            r, g, b = colors[-1]
        else:
            r0, g0, b0 = colors[index]
            r1, g1, b1 = colors[index + 1]
            r = round(r0 + (r1 - r0) * fraction)
            g = round(g0 + (g1 - g0) * fraction)
            b = round(b0 + (b1 - b0) * fraction)
        colormap[i] = (r, g, b, 255)
    return colormap


def _build_categorical_colormap(palette: list[str]) -> ColorMap:
    """Map each discrete class index directly to its palette color."""
    return {index: (*_hex_to_rgb(color), 255) for index, color in enumerate(palette)}


class RasterService:
    def __init__(self, catalog_service: CatalogService | None = None):
        self.catalog_service = catalog_service or CatalogService()
        self.repository = LocalRasterRepository(settings.data_root_path)

    def get_layer_metadata(self, layer_id: str) -> dict[str, Any]:
        layer = self.catalog_service.get_by_id(layer_id)
        path = self.repository.raster_path(layer.relative_path)
        with Reader(path) as reader:
            info = reader.info()
            return {
                "layer_id": layer_id,
                "bounds": list(info.get("bounds", [])),
                "crs": info.get("crs"),
                "dtype": info.get("dtype"),
                "nodata": info.get("nodata"),
                "width": info.get("width"),
                "height": info.get("height"),
            }

    def get_tile(self, layer_id: str, z: int, x: int, y: int) -> tuple[bytes, str]:
        layer = self.catalog_service.get_by_id(layer_id)
        if layer.layer_type != "raster":
            raise LayerUnavailableError(f"Layer '{layer_id}' is not a raster layer.")

        path = self.repository.raster_path(layer.relative_path)
        palette = layer.legend.palette if layer.legend else ["#000000", "#ffffff"]
        is_categorical = layer.value_type == "categorical"

        try:
            with Reader(path) as reader:
                image = reader.tile(x, y, z)
        except TileOutsideBounds as exc:
            raise LayerUnavailableError(f"Requested tile is outside raster bounds for layer '{layer_id}'.") from exc

        if is_categorical:
            colormap = _build_categorical_colormap(palette)
            png_bytes = image.render(img_format="PNG", colormap=colormap)
        else:
            vmin = layer.value_range.minimum if layer.value_range else 0
            vmax = layer.value_range.maximum if layer.value_range else 1
            image.rescale(in_range=((vmin, vmax),))
            colormap = _build_continuous_colormap(palette)
            png_bytes = image.render(img_format="PNG", colormap=colormap)

        return png_bytes, "image/png"

    def terrain_available(self) -> bool:
        dem_path = self.repository.raster_path("rasters/processed/planegg/dem_1m.tif")
        return dem_path.exists()

    def get_terrain_tile(self, z: int, x: int, y: int) -> tuple[bytes, str]:
        dem_path = self.repository.raster_path("rasters/processed/planegg/dem_1m.tif")
        fallback_rgb = self._fetch_fallback_terrain_tile(z, x, y)

        if not dem_path.exists():
            if fallback_rgb is None:
                raise LayerUnavailableError("DEM raster is missing and fallback terrain tile is unavailable.")
            return self._encode_rgb_png(fallback_rgb), "image/png"

        try:
            with Reader(dem_path) as reader:
                image = reader.tile(x, y, z, tilesize=256)
        except TileOutsideBounds:
            if fallback_rgb is None:
                raise LayerUnavailableError("Requested terrain tile is outside DEM bounds and fallback is unavailable.")
            return self._encode_rgb_png(fallback_rgb), "image/png"

        dem = image.data[0].astype(np.float64)
        valid_mask = np.isfinite(dem) & (dem > -1000.0) & (dem != 0.0)
        if image.mask is not None:
            valid_mask &= image.mask > 0
        if fallback_rgb is None and np.any(valid_mask):
            local_fill = float(np.median(dem[valid_mask]))
            dem = np.where(valid_mask, dem, local_fill)
        else:
            dem = np.where(valid_mask, dem, 0.0)
        dem = np.nan_to_num(dem, nan=0.0)

        encoded = np.clip(dem + 32768.0, 0.0, 65535.0)
        r = np.floor(encoded / 256.0).astype(np.uint8)
        g = np.floor(encoded % 256.0).astype(np.uint8)
        b = np.floor((encoded - np.floor(encoded)) * 256.0).astype(np.uint8)
        rgb = np.stack([r, g, b], axis=0)

        if fallback_rgb is not None and not np.all(valid_mask):
            fallback_copy = fallback_rgb.copy()
            fallback_copy[:, valid_mask] = rgb[:, valid_mask]
            rgb = fallback_copy

        return self._encode_rgb_png(rgb), "image/png"

    def _fetch_fallback_terrain_tile(self, z: int, x: int, y: int) -> np.ndarray | None:
        url = GLOBAL_TERRAIN_30M_TEMPLATE.format(z=z, x=x, y=y)
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            with MemoryFile(response.content) as mem:
                with mem.open() as src:
                    data = src.read()
                    if data.shape[0] >= 3:
                        return data[:3].astype(np.uint8)
        except requests.RequestException:
            return None
        except Exception:
            return None
        return None

    def _encode_rgb_png(self, rgb: np.ndarray) -> bytes:
        with MemoryFile() as memfile:
            with memfile.open(driver="PNG", width=256, height=256, count=3, dtype="uint8") as dst:
                dst.write(rgb)
            return memfile.read()

    def sample_point(self, layer_id: str, lon: float, lat: float) -> dict[str, Any]:
        layer = self.catalog_service.get_by_id(layer_id)
        if layer.layer_type != "raster":
            raise LayerUnavailableError(f"Layer '{layer_id}' is not a raster layer.")

        path = self.repository.raster_path(layer.relative_path)
        nodata = layer.nodata if layer.nodata is not None else -9999

        try:
            with Reader(path) as reader:
                value = reader.point(lon, lat)
                sampled = value.data[0] if hasattr(value, "data") else value[0]
        except Exception:
            sampled = nodata

        valid = sampled is not None and sampled != nodata
        return {
            "layer_id": layer_id,
            "longitude": lon,
            "latitude": lat,
            "sampled_value": float(sampled) if isinstance(sampled, (float, int, np.integer, np.floating)) else None,
            "units": layer.units,
            "valid": bool(valid),
            "nodata": bool(not valid),
        }

