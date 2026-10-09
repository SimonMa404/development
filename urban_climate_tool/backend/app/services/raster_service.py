from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.io import MemoryFile
from rasterio.warp import transform_geom
from rio_tiler.errors import TileOutsideBounds
from rio_tiler.io import Reader

from app.core.config import settings
from app.core.errors import LayerUnavailableError
from app.repositories.local_raster import LocalRasterRepository
from app.services.catalog_service import CatalogService

ColorMap = dict[int, tuple[int, int, int, int]]


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
    TERRAIN_SOURCE_PATHS: dict[str, tuple[str, ...]] = {
        "dem": (
            "rasters/processed/planegg/dem_1m_terrain_cog.tif",
            "rasters/processed/planegg/dem_1m.tif",
        ),
        "dom": (
            "rasters/processed/planegg/dom_terrain_1m_cog.tif",
            "rasters/processed/planegg/dom_20cm.tif",
        ),
        "dsm": (
            "rasters/derived/planegg/dsm_1m.tif",
        ),
    }

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
        is_rgb = layer.value_type == "rgb" or (layer.style and layer.style.color_scale == "rgb")
        is_relative_summer_lst = layer.temporal_group == "relative_summer_lst"
        thematic_group = (layer.thematic_group or "").strip().lower()
        is_shade_overpass = layer.id.startswith(("shade-overpass-", "shade-ground-overpass-"))
        is_shade_layer = thematic_group in {"shade", "shade & solar"} or layer.id.startswith((
            "sun-hours-",
            "shade-hours-",
            "shade-fraction-",
            "shade-overpass-",
            "sun-hours-ground-",
            "shade-hours-ground-",
            "shade-fraction-ground-",
            "shade-ground-overpass-",
        ))
        is_dsm_overlay = layer.id == "dsm-planegg"

        try:
            with Reader(path) as reader:
                if is_rgb:
                    image = reader.tile(x, y, z, resampling_method="nearest")
                else:
                    interpolation = (layer.style.interpolation if layer.style else "") or ""
                    if is_relative_summer_lst:
                        image = reader.tile(x, y, z, resampling_method="nearest", nodata=None)
                    elif interpolation.lower() == "nearest" or is_shade_layer:
                        image = reader.tile(x, y, z, resampling_method="nearest")
                    else:
                        image = reader.tile(x, y, z)
        except TileOutsideBounds as exc:
            raise LayerUnavailableError(f"Requested tile is outside raster bounds for layer '{layer_id}'.") from exc

        if is_rgb:
            rgb = image.data
            if rgb.shape[0] >= 3:
                rgb = rgb[:3]
            elif rgb.shape[0] == 1:
                rgb = np.repeat(rgb, 3, axis=0)
            rgb = rgb.astype(np.float32)
            # Build AOI-valid mask from tile mask. This ensures strict clipping to real data.
            if image.mask is not None:
                mask = image.mask
                if mask.ndim == 3:
                    mask = mask[0]
                valid_mask = mask > 0
            else:
                valid_mask = np.isfinite(rgb[0])

            # Some RGB tiles expose full masks even outside AOI. Exclude probable nodata-black
            # pixels so outside areas remain transparent and do not skew stretch statistics.
            if layer.nodata == 0 or layer.temporal_group == "rgb_yearly":
                non_black = np.any(np.isfinite(rgb) & (rgb > 1e-6), axis=0)
                valid_mask = valid_mask & non_black

            # Enforce strict Planegg clipping for yearly Sentinel RGB layers.
            if "planegg" in layer.id and is_rgb:
                aoi_mask = self._planegg_aoi_mask_for_tile(image)
                if aoi_mask is not None:
                    valid_mask = valid_mask & aoi_mask

            # Use cached, layer-global RGB stretch bounds so colors remain stable across zoom levels.
            p_bounds = self._rgb_percentile_bounds(str(path), layer.nodata)
            out = np.zeros_like(rgb, dtype=np.uint8)
            for band_idx in range(min(3, rgb.shape[0])):
                band = rgb[band_idx]
                band_valid = band[valid_mask & np.isfinite(band)]
                if band_valid.size == 0:
                    continue

                p2, p98 = p_bounds[band_idx]
                if p98 <= p2:
                    p2 = float(np.percentile(band_valid, 2.0))
                    p98 = float(np.percentile(band_valid, 98.0))
                    if p98 <= p2:
                        p98 = p2 + 1.0

                scaled = (band - p2) / (p98 - p2)
                scaled = np.clip(scaled, 0.0, 1.0)

                band_u8 = np.clip(scaled * 255.0, 0, 255).astype(np.uint8)
                band_u8[~valid_mask] = 0
                out[band_idx] = band_u8

            alpha = np.where(valid_mask, 255, 0).astype(np.uint8)
            rgba = np.concatenate([out[:3], alpha[None, :, :]], axis=0)
            return self._encode_rgba_png(rgba), "image/png"

        if is_shade_overpass:
            # Hourly shade intensity layer:
            # - 0.0 (sunlit) => fully transparent
            # - 1.0 (full shade) => opaque black
            # - tree transmissivity values (e.g. 0.8 shade) => semi-transparent black
            values = np.nan_to_num(image.data[0].astype(np.float32), nan=0.0)
            values = np.clip(values, 0.0, 1.0)

            if image.mask is not None:
                base_mask = image.mask
                if base_mask.ndim == 3:
                    base_mask = base_mask[0]
                valid_mask = base_mask > 0
            else:
                valid_mask = np.isfinite(image.data[0])

            aoi_mask = self._planegg_aoi_mask_for_tile(image)
            if aoi_mask is not None:
                valid_mask = valid_mask & aoi_mask

            alpha = np.clip(values * 255.0, 0, 255).astype(np.uint8)
            alpha = np.where(valid_mask, alpha, 0).astype(np.uint8)

            rgb = np.zeros((3, alpha.shape[0], alpha.shape[1]), dtype=np.uint8)
            rgba = np.concatenate([rgb, alpha[None, :, :]], axis=0)
            return self._encode_rgba_png(rgba), "image/png"

        if is_categorical:
            colormap = _build_categorical_colormap(palette)
            png_bytes = image.render(img_format="PNG", colormap=colormap)
        else:
            aoi_mask: np.ndarray | None = None
            if is_relative_summer_lst or is_shade_layer or is_dsm_overlay:
                aoi_mask = self._planegg_aoi_mask_for_tile(image)

            vmin = layer.value_range.minimum if layer.value_range else 0
            vmax = layer.value_range.maximum if layer.value_range else 1
            image.rescale(in_range=((vmin, vmax),))
            colormap = _build_continuous_colormap(palette)

            if aoi_mask is None:
                png_bytes = image.render(img_format="PNG", colormap=colormap)
            else:
                values = np.nan_to_num(image.data[0], nan=0.0)
                values = np.clip(values, 0, 255).astype(np.uint8)

                if image.mask is not None:
                    base_mask = image.mask
                    if base_mask.ndim == 3:
                        base_mask = base_mask[0]
                    valid_mask = (base_mask > 0) & aoi_mask
                else:
                    valid_mask = np.isfinite(image.data[0]) & aoi_mask

                lut = np.zeros((256, 4), dtype=np.uint8)
                for idx in range(256):
                    lut[idx] = colormap[idx]

                rgba_hw = lut[values]
                rgba_hw[..., 3] = np.where(valid_mask, rgba_hw[..., 3], 0).astype(np.uint8)
                rgba = np.transpose(rgba_hw, (2, 0, 1))
                png_bytes = self._encode_rgba_png(rgba)

        return png_bytes, "image/png"

    def terrain_available(self, source: str = "dem") -> bool:
        source_paths = self.TERRAIN_SOURCE_PATHS.get(source)
        if source_paths is None:
            return False
        return any(self.repository.raster_path(candidate).exists() for candidate in source_paths)

    def terrain_sources_available(self) -> dict[str, bool]:
        return {source: self.terrain_available(source) for source in self.TERRAIN_SOURCE_PATHS}

    def terrain_statistics(self, source: str = "dem") -> dict[str, Any]:
        source_path = self._resolve_terrain_source_path(source)
        if source_path is None:
            raise LayerUnavailableError(f"Unsupported terrain source '{source}'.")

        path = self.repository.raster_path(source_path)
        if not path.exists():
            raise LayerUnavailableError(f"Terrain source '{source}' is unavailable.")

        return self._terrain_statistics_cached(str(path), source)

    @staticmethod
    @lru_cache(maxsize=16)
    def _terrain_statistics_cached(path_str: str, source: str) -> dict[str, Any]:
        path = Path(path_str)
        with rasterio.open(path) as dataset:
            band = dataset.read(1, masked=True).astype(np.float64)
            if dataset.nodata is not None:
                band = np.ma.masked_equal(band, dataset.nodata)

            values = band.compressed() if np.ma.isMaskedArray(band) else np.asarray(band).ravel()
            values = values[np.isfinite(values)]
            if values.size == 0:
                raise LayerUnavailableError(f"Terrain source '{source}' contains no valid data.")

            return {
                "source": source,
                "relative_path": path_str,
                "minimum": float(values.min()),
                "maximum": float(values.max()),
                "mean": float(values.mean()),
                "median": float(np.median(values)),
                "sample_count": int(values.size),
            }

    def get_terrain_tile(self, z: int, x: int, y: int, source: str = "dem") -> tuple[bytes, str]:
        tile_bytes = self._get_terrain_tile_cached(z, x, y, source)
        return tile_bytes, "image/png"

    @lru_cache(maxsize=8192)
    def _get_terrain_tile_cached(self, z: int, x: int, y: int, source: str = "dem") -> bytes:
        source_path = self._resolve_terrain_source_path(source)
        if source_path is None:
            raise LayerUnavailableError(f"Unsupported terrain source '{source}'.")

        dem_path = self.repository.raster_path(source_path)

        if not dem_path.exists():
            return self._flat_terrain_tile_png()

        try:
            with Reader(dem_path) as reader:
                image = reader.tile(x, y, z, tilesize=256)
        except TileOutsideBounds:
            return self._flat_terrain_tile_png()

        dem = image.data[0].astype(np.float64)
        valid_mask = np.isfinite(dem) & (dem > -1000.0) & (dem != 0.0)
        if image.mask is not None:
            valid_mask &= image.mask > 0

        if np.any(valid_mask):
            local_fill = float(np.median(dem[valid_mask]))
            dem = np.where(valid_mask, dem, local_fill)
        else:
            return self._flat_terrain_tile_png()
        dem = np.nan_to_num(dem, nan=0.0)

        encoded = np.clip(dem + 32768.0, 0.0, 65535.0)
        r = np.floor(encoded / 256.0).astype(np.uint8)
        g = np.floor(encoded % 256.0).astype(np.uint8)
        b = np.floor((encoded - np.floor(encoded)) * 256.0).astype(np.uint8)
        rgb = np.stack([r, g, b], axis=0)

        return self._encode_rgb_png(rgb)

    def _resolve_terrain_source_path(self, source: str) -> str | None:
        candidates = self.TERRAIN_SOURCE_PATHS.get(source)
        if candidates is None:
            return None
        for candidate in candidates:
            if self.repository.raster_path(candidate).exists():
                return candidate
        return candidates[-1]

    @staticmethod
    @lru_cache(maxsize=1)
    def _flat_terrain_tile_png() -> bytes:
        # Terrarium encoding for an approximate local baseline elevation.
        # Using ~540m avoids extreme cliffs when neighboring tiles have valid heights.
        baseline_elevation_m = 540.0
        encoded = np.clip(baseline_elevation_m + 32768.0, 0.0, 65535.0)
        r = int(np.floor(encoded / 256.0))
        g = int(np.floor(encoded % 256.0))
        b = int(np.floor((encoded - np.floor(encoded)) * 256.0))
        flat_rgb = np.zeros((3, 256, 256), dtype=np.uint8)
        flat_rgb[0, :, :] = r
        flat_rgb[1, :, :] = g
        flat_rgb[2, :, :] = b
        return RasterService._encode_rgb_png(flat_rgb)

    @staticmethod
    def _encode_rgb_png(rgb: np.ndarray) -> bytes:
        with MemoryFile() as memfile:
            with memfile.open(driver="PNG", width=256, height=256, count=3, dtype="uint8") as dst:
                dst.write(rgb)
            return memfile.read()

    @staticmethod
    def _encode_rgba_png(rgba: np.ndarray) -> bytes:
        with MemoryFile() as memfile:
            with memfile.open(driver="PNG", width=256, height=256, count=4, dtype="uint8") as dst:
                dst.write(rgba)
            return memfile.read()

    @staticmethod
    @lru_cache(maxsize=1)
    def _planegg_boundary_geom() -> dict[str, Any] | None:
        path = settings.data_root_path / "vectors/processed/planegg/boundary.geojson"
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        features = payload.get("features") if isinstance(payload, dict) else None
        if not isinstance(features, list) or not features:
            return None
        geom = features[0].get("geometry") if isinstance(features[0], dict) else None
        return geom if isinstance(geom, dict) else None

    def _planegg_aoi_mask_for_tile(self, image: Any) -> np.ndarray | None:
        geom = self._planegg_boundary_geom()
        if geom is None:
            return None
        transform = getattr(image, "transform", None)
        crs = getattr(image, "crs", None)
        if transform is None or crs is None:
            return None
        try:
            geom_proj = transform_geom("EPSG:4326", str(crs), geom)
            height = int(image.data.shape[1])
            width = int(image.data.shape[2])
            mask = rasterize(
                [(geom_proj, 1)],
                out_shape=(height, width),
                transform=transform,
                fill=0,
                all_touched=True,
                dtype=np.uint8,
            )
            return mask > 0
        except Exception:
            return None

    @staticmethod
    @lru_cache(maxsize=64)
    def _rgb_percentile_bounds(raster_path: str, nodata: float | int | None) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
        with rasterio.open(raster_path) as ds:
            h, w = ds.height, ds.width
            scale = max(h / 1024, w / 1024, 1)
            out_h = max(1, int(h / scale))
            out_w = max(1, int(w / scale))
            arr = ds.read(indexes=[1, 2, 3], out_shape=(3, out_h, out_w), resampling=Resampling.bilinear).astype(np.float32)

        bounds: list[tuple[float, float]] = []
        for band in arr:
            valid = np.isfinite(band)
            if nodata is not None:
                valid &= band != float(nodata)
            valid &= band > 0
            values = band[valid]
            if values.size < 16:
                values = band[np.isfinite(band)]
            if values.size == 0:
                bounds.append((0.0, 1.0))
                continue
            p2 = float(np.percentile(values, 2.0))
            p98 = float(np.percentile(values, 98.0))
            if p98 <= p2:
                p98 = p2 + 1.0
            bounds.append((p2, p98))

        while len(bounds) < 3:
            bounds.append(bounds[-1] if bounds else (0.0, 1.0))
        return bounds[0], bounds[1], bounds[2]

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

