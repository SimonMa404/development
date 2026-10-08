from __future__ import annotations

from pathlib import Path
from typing import Any
from functools import lru_cache

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio import features as rasterio_features
from rasterio.mask import mask as rasterio_mask
from shapely.geometry import box, shape
from shapely.ops import unary_union

from app.core.config import settings
from app.core.errors import LayerUnavailableError
from app.repositories.local_raster import LocalRasterRepository
from app.repositories.local_vector import LocalVectorRepository
from app.services.catalog_service import CatalogService

_EMPTY_STATS: dict[str, float | int] = {
    "count": 0,
    "minimum": 0.0,
    "maximum": 0.0,
    "mean": 0.0,
    "median": 0.0,
    "stddev": 0.0,
}

_DEFAULT_LST_BINS: list[dict[str, float | str | None]] = [
    {"label": "Cool (< 22°C)", "minimum_c": None, "maximum_c": 22.0},
    {"label": "Mild (22–26°C)", "minimum_c": 22.0, "maximum_c": 26.0},
    {"label": "Warm (26–30°C)", "minimum_c": 26.0, "maximum_c": 30.0},
    {"label": "Hot (≥ 30°C)", "minimum_c": 30.0, "maximum_c": None},
]

_DEFAULT_NDVI_BINS: list[dict[str, float | str | None]] = [
    {"label": "No vegetation", "minimum_c": None, "maximum_c": 0.0},
    {"label": "Low vegetation", "minimum_c": 0.0, "maximum_c": 0.2},
    {"label": "Moderate vegetation", "minimum_c": 0.2, "maximum_c": 0.4},
    {"label": "Dense vegetation", "minimum_c": 0.4, "maximum_c": 0.6},
    {"label": "Very dense vegetation", "minimum_c": 0.6, "maximum_c": None},
]


def _compute_histogram(valid: np.ndarray, value_type: str | None) -> dict[str, Any] | None:
    if valid.size == 0:
        return None
    if value_type == "categorical":
        # Bin edges centered on integer class indices so each class gets its own bar.
        lo = int(valid.min())
        hi = int(valid.max())
        bins = np.arange(lo, hi + 2) - 0.5
        counts, bin_edges = np.histogram(valid, bins=bins)
    else:
        counts, bin_edges = np.histogram(valid, bins=20)
    return {"bin_edges": [float(edge) for edge in bin_edges], "counts": [int(count) for count in counts]}


def _compute_class_breakdown(
    valid: np.ndarray, labels: list[str] | None, palette: list[str] | None
) -> list[dict[str, Any]] | None:
    if valid.size == 0 or not labels or not palette:
        return None
    total = valid.size
    breakdown: list[dict[str, Any]] = []
    for class_index, label in enumerate(labels):
        count = int(np.count_nonzero(valid == class_index))
        if count == 0:
            continue
        color = palette[class_index] if class_index < len(palette) else "#64748b"
        breakdown.append(
            {
                "class_index": class_index,
                "label": label,
                "color": color,
                "count": count,
                "percentage": round(100 * count / total, 2),
            }
        )
    breakdown.sort(key=lambda item: item["count"], reverse=True)
    return breakdown


def _compute_stats(
    masked_array: np.ma.MaskedArray,
    value_type: str | None = None,
    labels: list[str] | None = None,
    palette: list[str] | None = None,
) -> dict[str, Any]:
    valid = masked_array.compressed()
    valid = valid[np.isfinite(valid)]
    if valid.size == 0:
        return dict(_EMPTY_STATS)
    return {
        "count": int(valid.size),
        "minimum": float(valid.min()),
        "maximum": float(valid.max()),
        "mean": float(valid.mean()),
        "median": float(np.median(valid)),
        "stddev": float(valid.std(ddof=0)),
        "histogram": _compute_histogram(valid, value_type),
        "class_breakdown": _compute_class_breakdown(valid, labels, palette) if value_type == "categorical" else None,
    }


class StatisticsService:
    def __init__(self, catalog_service: CatalogService | None = None):
        self.catalog_service = catalog_service or CatalogService()
        self.repository = LocalRasterRepository(settings.data_root_path)
        self.vector_repository = LocalVectorRepository(settings.data_root_path)

    def tree_statistics(self, geometry: dict[str, Any], layer_id: str = "trees-3d-planegg") -> dict[str, Any]:
        layer = self.catalog_service.get_by_id(layer_id)
        if layer.layer_type != "vector":
            raise LayerUnavailableError(f"Layer '{layer_id}' is not a vector layer.")

        layer_path = settings.data_root_path / layer.relative_path
        if not layer_path.exists():
            raise LayerUnavailableError(f"Tree layer file not found: {layer.relative_path}")

        selected_geom_4326 = shape(geometry)
        selected_geom_25832 = gpd.GeoSeries([selected_geom_4326], crs="EPSG:4326").to_crs(epsg=25832).iloc[0]
        area_hectares = float(selected_geom_25832.area / 10000) if not selected_geom_25832.is_empty else 0.0

        query_bounds_4326 = list(selected_geom_4326.bounds)
        stats_relative_path = layer.relative_path
        sibling_parquet = Path(layer.relative_path).with_suffix(".parquet")
        if (settings.data_root_path / sibling_parquet).exists():
            stats_relative_path = sibling_parquet.as_posix()

        trees_gdf = self.vector_repository.read_frame(stats_relative_path, bbox=query_bounds_4326)
        if trees_gdf.empty:
            return {
                "layer_id": layer_id,
                "title": layer.title,
                "tree_count": 0,
                "area_hectares": area_hectares,
                "tree_density_per_hectare": 0.0 if area_hectares > 0 else None,
                "mean_height": None,
                "median_height": None,
                "maximum_height": None,
                "minimum_height": None,
                "mean_ground_elevation": None,
            }

        if trees_gdf.crs is None:
            trees_gdf = trees_gdf.set_crs("EPSG:4326")

        trees_25832 = trees_gdf.to_crs(epsg=25832) if trees_gdf.crs != "EPSG:25832" else trees_gdf.copy()
        minx, miny, maxx, maxy = selected_geom_25832.bounds
        candidates = trees_25832.cx[minx:maxx, miny:maxy].copy()

        if candidates.empty:
            return {
                "layer_id": layer_id,
                "title": layer.title,
                "tree_count": 0,
                "area_hectares": area_hectares,
                "tree_density_per_hectare": 0.0 if area_hectares > 0 else None,
                "mean_height": None,
                "median_height": None,
                "maximum_height": None,
                "minimum_height": None,
                "mean_ground_elevation": None,
            }

        centroid_mask = candidates.geometry.centroid.apply(selected_geom_25832.covers)
        selected = candidates.loc[centroid_mask].copy()

        heights = _numeric_series(selected, "height")
        base_heights = _numeric_series(selected, "base_height")
        valid_heights = heights.dropna()
        valid_base_heights = base_heights.dropna()
        tree_count = int(len(selected))

        return {
            "layer_id": layer_id,
            "title": layer.title,
            "tree_count": tree_count,
            "area_hectares": area_hectares,
            "tree_density_per_hectare": float(tree_count / area_hectares) if area_hectares > 0 else None,
            "mean_height": float(valid_heights.mean()) if not valid_heights.empty else None,
            "median_height": float(valid_heights.median()) if not valid_heights.empty else None,
            "maximum_height": float(valid_heights.max()) if not valid_heights.empty else None,
            "minimum_height": float(valid_heights.min()) if not valid_heights.empty else None,
            "mean_ground_elevation": float(valid_base_heights.mean()) if not valid_base_heights.empty else None,
        }

    def area_statistics(self, geometry: dict[str, Any], layer_ids: list[str]) -> list[dict[str, Any]]:
        """Compute per-layer statistics for a user-drawn polygon plus a
        whole-layer baseline for comparison.
        """
        results: list[dict[str, Any]] = []

        selected_geometry = shape(geometry)

        for layer_id in layer_ids:
            layer = self.catalog_service.get_by_id(layer_id)
            if layer.layer_type != "raster":
                raise LayerUnavailableError(
                    f"Layer '{layer_id}' is not a raster layer; area statistics currently supports raster layers only."
                )

            path = self.repository.raster_path(layer.relative_path)

            labels = layer.legend.labels if layer.legend else None
            palette = layer.legend.palette if layer.legend else None

            with rasterio.open(path) as dataset:
                nodata = layer.nodata if layer.nodata is not None else dataset.nodata

                full_band = dataset.read(1, masked=True)
                if nodata is not None:
                    full_band = np.ma.masked_equal(full_band.filled(nodata), nodata)
                baseline_stats = _compute_stats(full_band, layer.value_type, labels, palette)

                raster_bounds = box(*dataset.bounds)
                if selected_geometry.contains(raster_bounds):
                    selected_stats = baseline_stats
                else:
                    try:
                        out_image, _ = rasterio_mask(dataset, [geometry], crop=True, nodata=nodata, filled=True)
                    except ValueError:
                        # Geometry does not overlap the raster extent.
                        selected_stats = dict(_EMPTY_STATS)
                    else:
                        band = out_image[0]
                        if nodata is not None:
                            selected_masked = np.ma.masked_equal(band, nodata)
                        else:
                            selected_masked = np.ma.masked_invalid(band)
                        selected_stats = _compute_stats(selected_masked, layer.value_type, labels, palette)

            results.append(
                {
                    "layer_id": layer_id,
                    "title": layer.title,
                    "units": layer.units,
                    "value_type": layer.value_type,
                    "legend": layer.legend.model_dump() if layer.legend else None,
                    "value_range": layer.value_range.model_dump() if layer.value_range else None,
                    "selected": selected_stats,
                    "baseline": baseline_stats,
                }
            )

        return results

    def building_context_statistics(
        self,
        geometry: dict[str, Any],
        layer_ids: list[str],
        buildings_layer_id: str,
        buffer_meters: float = 15.0,
    ) -> list[dict[str, Any]]:
        if buffer_meters <= 0:
            raise LayerUnavailableError("buffer_meters must be > 0")

        buildings_layer = self.catalog_service.get_by_id(buildings_layer_id)
        if buildings_layer.layer_type != "vector":
            raise LayerUnavailableError(f"Layer '{buildings_layer_id}' is not a vector layer.")

        buildings_path = settings.data_root_path / buildings_layer.relative_path
        if not buildings_path.exists():
            raise LayerUnavailableError(f"Buildings layer file not found: {buildings_layer.relative_path}")

        building_geom = shape(geometry)
        selected_gdf = gpd.GeoSeries([building_geom], crs="EPSG:4326").to_crs(epsg=25832)
        selected_buffer = selected_gdf.buffer(buffer_meters).to_crs(epsg=4326).iloc[0]

        all_buildings_union_geom = self._buffered_buildings_union_geometry(str(buildings_path), float(buffer_meters))

        results: list[dict[str, Any]] = []
        for layer_id in layer_ids:
            layer = self.catalog_service.get_by_id(layer_id)
            if layer.layer_type != "raster":
                raise LayerUnavailableError(
                    f"Layer '{layer_id}' is not a raster layer; building context statistics supports raster layers only."
                )

            path = self.repository.raster_path(layer.relative_path)
            labels = layer.legend.labels if layer.legend else None
            palette = layer.legend.palette if layer.legend else None

            with rasterio.open(path) as dataset:
                nodata = layer.nodata if layer.nodata is not None else dataset.nodata

                # Selected building + surrounding neighborhood buffer.
                try:
                    selected_out, _ = rasterio_mask(
                        dataset,
                        [selected_buffer.__geo_interface__],
                        crop=True,
                        nodata=nodata,
                        filled=True,
                    )
                    selected_band = selected_out[0]
                    if nodata is not None:
                        selected_masked = np.ma.masked_equal(selected_band, nodata)
                    else:
                        selected_masked = np.ma.masked_invalid(selected_band)
                    selected_stats = _compute_stats(selected_masked, layer.value_type, labels, palette)
                except ValueError:
                    selected_stats = dict(_EMPTY_STATS)

                # Average context around all buildings in the ROI.
                try:
                    avg_out, _ = rasterio_mask(
                        dataset,
                        [all_buildings_union_geom],
                        crop=True,
                        nodata=nodata,
                        filled=True,
                    )
                    avg_band = avg_out[0]
                    if nodata is not None:
                        avg_masked = np.ma.masked_equal(avg_band, nodata)
                    else:
                        avg_masked = np.ma.masked_invalid(avg_band)
                    average_building_stats = _compute_stats(avg_masked, layer.value_type, labels, palette)
                except ValueError:
                    average_building_stats = dict(_EMPTY_STATS)

            results.append(
                {
                    "layer_id": layer_id,
                    "title": layer.title,
                    "units": layer.units,
                    "value_type": layer.value_type,
                    "legend": layer.legend.model_dump() if layer.legend else None,
                    "value_range": layer.value_range.model_dump() if layer.value_range else None,
                    "selected": selected_stats,
                    "average_building": average_building_stats,
                }
            )

        return results

    def buildings_overview_statistics(
        self,
        layer_ids: list[str],
        buildings_layer_id: str,
    ) -> list[dict[str, Any]]:
        buildings_layer = self.catalog_service.get_by_id(buildings_layer_id)
        if buildings_layer.layer_type != "vector":
            raise LayerUnavailableError(f"Layer '{buildings_layer_id}' is not a vector layer.")

        buildings_path = settings.data_root_path / buildings_layer.relative_path
        if not buildings_path.exists():
            raise LayerUnavailableError(f"Buildings layer file not found: {buildings_layer.relative_path}")

        buildings_union = self._buildings_union_geometry(str(buildings_path))

        results: list[dict[str, Any]] = []
        for layer_id in layer_ids:
            layer = self.catalog_service.get_by_id(layer_id)
            if layer.layer_type != "raster":
                raise LayerUnavailableError(
                    f"Layer '{layer_id}' is not a raster layer; buildings overview supports raster layers only."
                )

            path = self.repository.raster_path(layer.relative_path)
            labels = layer.legend.labels if layer.legend else None
            palette = layer.legend.palette if layer.legend else None

            with rasterio.open(path) as dataset:
                nodata = layer.nodata if layer.nodata is not None else dataset.nodata
                try:
                    out, _ = rasterio_mask(dataset, [buildings_union], crop=True, nodata=nodata, filled=True)
                except ValueError:
                    building_stats = dict(_EMPTY_STATS)
                else:
                    band = out[0]
                    if nodata is not None:
                        masked = np.ma.masked_equal(band, nodata)
                    else:
                        masked = np.ma.masked_invalid(band)
                    building_stats = _compute_stats(masked, layer.value_type, labels, palette)

            results.append(
                {
                    "layer_id": layer_id,
                    "title": layer.title,
                    "units": layer.units,
                    "value_type": layer.value_type,
                    "legend": layer.legend.model_dump() if layer.legend else None,
                    "value_range": layer.value_range.model_dump() if layer.value_range else None,
                    "buildings": building_stats,
                }
            )

        return results

    def heat_vulnerability(
        self,
        geometry: dict[str, Any],
        census_layer_id: str = "census-2022-100m-planegg",
        lst_layer_id: str | None = "lst-planegg",
        ndvi_layer_id: str | None = None,
    ) -> dict[str, Any]:
        census_layer = self.catalog_service.get_by_id(census_layer_id)
        if census_layer.layer_type != "vector":
            raise LayerUnavailableError(f"Layer '{census_layer_id}' is not a vector layer.")

        census_path = settings.data_root_path / census_layer.relative_path
        if not census_path.exists():
            raise LayerUnavailableError(f"Census layer file not found: {census_layer.relative_path}")

        selected_geom_4326 = shape(geometry)
        selected_geom_3035 = gpd.GeoSeries([selected_geom_4326], crs="EPSG:4326").to_crs(epsg=3035).iloc[0]
        census_gdf = gpd.read_file(census_path)
        if census_gdf.empty:
            return {
                "census_layer_id": census_layer_id,
                "lst_layer_id": lst_layer_id,
                "ndvi_layer_id": ndvi_layer_id,
                "summary": {
                    "census_cells": 0,
                    "total_population": None,
                    "elderly_population": None,
                    "elderly_share": None,
                    "children_population": None,
                    "children_share": None,
                    "missing_elderly_population": None,
                    "missing_children_population": None,
                },
                "lst_exposure_bins": None,
                "ndvi_exposure_bins": None,
            }

        if census_gdf.crs is None:
            census_gdf = census_gdf.set_crs("EPSG:4326")

        census_3035 = census_gdf.to_crs(epsg=3035)
        minx, miny, maxx, maxy = selected_geom_3035.bounds
        candidates = census_3035.cx[minx:maxx, miny:maxy].copy()
        if candidates.empty:
            return {
                "census_layer_id": census_layer_id,
                "lst_layer_id": lst_layer_id,
                "ndvi_layer_id": ndvi_layer_id,
                "summary": {
                    "census_cells": 0,
                    "total_population": None,
                    "elderly_population": None,
                    "elderly_share": None,
                    "children_population": None,
                    "children_share": None,
                    "missing_elderly_population": None,
                    "missing_children_population": None,
                },
                "lst_exposure_bins": None,
                "ndvi_exposure_bins": None,
            }

        centroid_mask = candidates.geometry.centroid.apply(selected_geom_3035.covers)
        selected = candidates.loc[centroid_mask].copy()

        selected_4326 = selected.to_crs(epsg=4326)
        population = _numeric_series(selected_4326, "population")
        elderly_share = _normalize_share_series(_numeric_series(selected_4326, "elderly_share"))
        children_share = _normalize_share_series(_numeric_series(selected_4326, "children_share"))

        elderly_count = population * elderly_share
        children_count = population * children_share

        total_population = _sum_nullable(population)
        elderly_population = _sum_nullable(elderly_count)
        children_population = _sum_nullable(children_count)

        elderly_share_total = None
        if total_population and elderly_population is not None:
            elderly_share_total = elderly_population / total_population

        children_share_total = None
        if total_population and children_population is not None:
            children_share_total = children_population / total_population

        missing_elderly_population = _sum_nullable(population[elderly_share.isna()])
        missing_children_population = _sum_nullable(population[children_share.isna()])

        lst_exposures: list[dict[str, Any]] | None = None
        if lst_layer_id:
            lst_layer = self.catalog_service.get_by_id(lst_layer_id)
            if lst_layer.layer_type != "raster":
                raise LayerUnavailableError(f"Layer '{lst_layer_id}' is not a raster layer.")
            lst_path = self.repository.raster_path(lst_layer.relative_path)
            lst_exposures = _sample_population_exposure(
                selected_4326=selected_4326,
                raster_path=lst_path,
                nodata_override=lst_layer.nodata,
                bins=_DEFAULT_LST_BINS,
                population=population,
                elderly_count=elderly_count,
                children_count=children_count,
            )

        ndvi_exposures: list[dict[str, Any]] | None = None
        if ndvi_layer_id:
            ndvi_layer = self.catalog_service.get_by_id(ndvi_layer_id)
            if ndvi_layer.layer_type != "raster":
                raise LayerUnavailableError(f"Layer '{ndvi_layer_id}' is not a raster layer.")
            ndvi_path = self.repository.raster_path(ndvi_layer.relative_path)
            ndvi_exposures = _sample_population_exposure(
                selected_4326=selected_4326,
                raster_path=ndvi_path,
                nodata_override=ndvi_layer.nodata,
                bins=_DEFAULT_NDVI_BINS,
                population=population,
                elderly_count=elderly_count,
                children_count=children_count,
            )

        return {
            "census_layer_id": census_layer_id,
            "lst_layer_id": lst_layer_id,
            "ndvi_layer_id": ndvi_layer_id,
            "summary": {
                "census_cells": int(len(selected_4326)),
                "total_population": total_population,
                "elderly_population": elderly_population,
                "elderly_share": elderly_share_total,
                "children_population": children_population,
                "children_share": children_share_total,
                "missing_elderly_population": missing_elderly_population,
                "missing_children_population": missing_children_population,
            },
            "lst_exposure_bins": lst_exposures,
            "ndvi_exposure_bins": ndvi_exposures,
        }

    def land_use_composition(
        self,
        geometry: dict[str, Any],
        layer_id: str = "nutzung-planegg",
        category_field: str = "nutzart",
    ) -> dict[str, Any]:
        layer = self.catalog_service.get_by_id(layer_id)
        if layer.layer_type != "vector":
            raise LayerUnavailableError(f"Layer '{layer_id}' is not a vector layer.")

        layer_path = settings.data_root_path / layer.relative_path
        if not layer_path.exists():
            raise LayerUnavailableError(f"Layer file not found: {layer.relative_path}")

        selected_geom_4326 = shape(geometry)
        if selected_geom_4326.is_empty:
            raise LayerUnavailableError("Selected geometry is empty.")

        selected_geom_25832 = gpd.GeoSeries([selected_geom_4326], crs="EPSG:4326").to_crs(epsg=25832).iloc[0]
        selected_area_m2 = float(selected_geom_25832.area)

        if selected_area_m2 <= 0:
            raise LayerUnavailableError("Selected geometry has zero area.")

        features = self.vector_repository.read_frame(layer.relative_path, bbox=list(selected_geom_4326.bounds))
        if features.empty:
            return {
                "layer_id": layer_id,
                "title": layer.title,
                "category_field": category_field,
                "summary": {
                    "selected_area_m2": selected_area_m2,
                    "selected_area_hectares": selected_area_m2 / 10000.0,
                    "covered_area_m2": 0.0,
                    "covered_area_hectares": 0.0,
                    "covered_share_pct": 0.0,
                    "uncovered_area_m2": selected_area_m2,
                    "uncovered_area_hectares": selected_area_m2 / 10000.0,
                },
                "classes": [],
            }

        if features.crs is None:
            features = features.set_crs("EPSG:4326")

        features_25832 = features.to_crs(epsg=25832) if str(features.crs) != "EPSG:25832" else features.copy()
        candidates = features_25832.loc[features_25832.geometry.intersects(selected_geom_25832)].copy()

        if candidates.empty:
            return {
                "layer_id": layer_id,
                "title": layer.title,
                "category_field": category_field,
                "summary": {
                    "selected_area_m2": selected_area_m2,
                    "selected_area_hectares": selected_area_m2 / 10000.0,
                    "covered_area_m2": 0.0,
                    "covered_area_hectares": 0.0,
                    "covered_share_pct": 0.0,
                    "uncovered_area_m2": selected_area_m2,
                    "uncovered_area_hectares": selected_area_m2 / 10000.0,
                },
                "classes": [],
            }

        candidates["_intersection_area_m2"] = candidates.geometry.intersection(selected_geom_25832).area
        intersections = candidates.loc[candidates["_intersection_area_m2"] > 0].copy()

        if intersections.empty:
            return {
                "layer_id": layer_id,
                "title": layer.title,
                "category_field": category_field,
                "summary": {
                    "selected_area_m2": selected_area_m2,
                    "selected_area_hectares": selected_area_m2 / 10000.0,
                    "covered_area_m2": 0.0,
                    "covered_area_hectares": 0.0,
                    "covered_share_pct": 0.0,
                    "uncovered_area_m2": selected_area_m2,
                    "uncovered_area_hectares": selected_area_m2 / 10000.0,
                },
                "classes": [],
            }

        if category_field not in intersections.columns:
            intersections[category_field] = "Unknown"

        intersections[category_field] = (
            intersections[category_field]
            .fillna("Unknown")
            .astype(str)
            .str.strip()
            .replace({"": "Unknown"})
        )

        grouped = (
            intersections.groupby(category_field, dropna=False)
            .agg(feature_count=(category_field, "size"), area_m2=("_intersection_area_m2", "sum"))
            .reset_index()
            .sort_values("area_m2", ascending=False)
        )

        covered_area_m2 = float(grouped["area_m2"].sum())
        uncovered_area_m2 = max(0.0, selected_area_m2 - covered_area_m2)

        classes: list[dict[str, Any]] = []
        for _, row in grouped.iterrows():
            area_m2 = float(row["area_m2"])
            classes.append(
                {
                    "category": str(row[category_field]),
                    "feature_count": int(row["feature_count"]),
                    "area_m2": area_m2,
                    "area_hectares": area_m2 / 10000.0,
                    "share_of_selected_pct": (100.0 * area_m2 / selected_area_m2) if selected_area_m2 > 0 else 0.0,
                    "share_of_covered_pct": (100.0 * area_m2 / covered_area_m2) if covered_area_m2 > 0 else 0.0,
                }
            )

        return {
            "layer_id": layer_id,
            "title": layer.title,
            "category_field": category_field,
            "summary": {
                "selected_area_m2": selected_area_m2,
                "selected_area_hectares": selected_area_m2 / 10000.0,
                "covered_area_m2": covered_area_m2,
                "covered_area_hectares": covered_area_m2 / 10000.0,
                "covered_share_pct": (100.0 * covered_area_m2 / selected_area_m2) if selected_area_m2 > 0 else 0.0,
                "uncovered_area_m2": uncovered_area_m2,
                "uncovered_area_hectares": uncovered_area_m2 / 10000.0,
            },
            "classes": classes,
        }

    def change_detection(self, from_layer_id: str, to_layer_id: str) -> dict[str, Any]:
        from_layer = self.catalog_service.get_by_id(from_layer_id)
        to_layer = self.catalog_service.get_by_id(to_layer_id)

        from_path = settings.data_root_path / from_layer.relative_path
        to_path = settings.data_root_path / to_layer.relative_path
        if not from_path.exists() or not to_path.exists():
            raise LayerUnavailableError("One or both rasters unavailable")

        with rasterio.open(from_path) as from_src, rasterio.open(to_path) as to_src:
            from_data = from_src.read(1)
            to_data = to_src.read(1)

            if from_data.shape != to_data.shape:
                raise ValueError("Rasters have mismatched dimensions")

            from_nodata = from_src.nodata
            to_nodata = to_src.nodata
            from_valid = from_data != from_nodata if from_nodata is not None else np.ones(from_data.shape, dtype=bool)
            to_valid = to_data != to_nodata if to_nodata is not None else np.ones(to_data.shape, dtype=bool)
            both_valid = from_valid & to_valid

            from_flat = from_data[both_valid].astype(int)
            to_flat = to_data[both_valid].astype(int)
            changed_mask = both_valid & (from_data != to_data)

            transitions: dict[tuple[int, int], int] = {}
            for from_class, to_class in zip(from_flat, to_flat):
                key = (int(from_class), int(to_class))
                transitions[key] = transitions.get(key, 0) + 1

            from_year = from_layer.temporal_year or (
                int(from_layer.acquisition_date[:4]) if from_layer.acquisition_date and len(from_layer.acquisition_date) >= 4 else 0
            )
            to_year = to_layer.temporal_year or (
                int(to_layer.acquisition_date[:4]) if to_layer.acquisition_date and len(to_layer.acquisition_date) >= 4 else 0
            )

            legend = from_layer.legend
            if legend is None:
                labels = []
                palette = []
            elif isinstance(legend, dict):
                labels = legend.get("labels", []) or []
                palette = legend.get("palette", []) or []
            else:
                labels = list(getattr(legend, "labels", []) or [])
                palette = list(getattr(legend, "palette", []) or [])

            pixel_area_hectares = 0.01  # Dynamic World 10m pixels
            valid_pixel_count = int(both_valid.sum())
            total_area_hectares = valid_pixel_count * pixel_area_hectares

            transition_rows: list[dict[str, Any]] = []
            transition_share_by_pair: dict[tuple[int, int], float] = {}
            changed_pixel_count = 0
            for (from_index, to_index), pixel_count in sorted(transitions.items()):
                if from_index == to_index:
                    continue

                changed_pixel_count += pixel_count
                area_hectares = pixel_count * pixel_area_hectares
                share_pct = (area_hectares / total_area_hectares * 100.0) if total_area_hectares > 0 else 0.0
                if share_pct >= 1.0:
                    confidence_level = "high"
                    confidence_color = "#ef4444"
                elif share_pct >= 0.25:
                    confidence_level = "medium"
                    confidence_color = "#f97316"
                else:
                    confidence_level = "low"
                    confidence_color = "#facc15"

                transition_share_by_pair[(from_index, to_index)] = share_pct
                transition_rows.append(
                    {
                        "from_class_index": from_index,
                        "from_class_label": labels[from_index] if from_index < len(labels) else f"Class {from_index}",
                        "from_class_color": palette[from_index] if from_index < len(palette) else "#94a3b8",
                        "to_class_index": to_index,
                        "to_class_label": labels[to_index] if to_index < len(labels) else f"Class {to_index}",
                        "to_class_color": palette[to_index] if to_index < len(palette) else "#94a3b8",
                        "pixel_count": pixel_count,
                        "area_hectares": area_hectares,
                        "share_pct": share_pct,
                        "confidence_level": confidence_level,
                        "confidence_color": confidence_color,
                    }
                )

            transition_rows.sort(key=lambda row: row["area_hectares"], reverse=True)

            changed_areas_geojson: dict[str, Any] | None = None
            if np.any(changed_mask):
                confidence_mask = np.zeros(from_data.shape, dtype=np.uint8)
                for (from_index, to_index), share_pct in transition_share_by_pair.items():
                    class_mask = both_valid & (from_data == from_index) & (to_data == to_index)
                    if share_pct >= 1.0:
                        confidence_mask[class_mask] = 3
                    elif share_pct >= 0.25:
                        confidence_mask[class_mask] = 2
                    else:
                        confidence_mask[class_mask] = 1

                features = []
                for geom, value in rasterio_features.shapes(
                    confidence_mask,
                    mask=confidence_mask > 0,
                    transform=from_src.transform,
                ):
                    confidence_value = int(value)
                    if confidence_value == 3:
                        confidence_level = "high"
                        confidence_color = "#ef4444"
                    elif confidence_value == 2:
                        confidence_level = "medium"
                        confidence_color = "#f97316"
                    else:
                        confidence_level = "low"
                        confidence_color = "#facc15"

                    features.append(
                        {
                            "type": "Feature",
                            "properties": {
                                "confidence_level": confidence_level,
                                "confidence_color": confidence_color,
                            },
                            "geometry": geom,
                        }
                    )

                if features:
                    changed_areas_geojson = {"type": "FeatureCollection", "features": features}

            changed_area_hectares = changed_pixel_count * pixel_area_hectares
            changed_share_pct = (changed_pixel_count / valid_pixel_count * 100.0) if valid_pixel_count > 0 else 0.0
            low_share = sum(row["share_pct"] for row in transition_rows if row["confidence_level"] == "low")
            medium_share = sum(row["share_pct"] for row in transition_rows if row["confidence_level"] == "medium")
            high_share = sum(row["share_pct"] for row in transition_rows if row["confidence_level"] == "high")

            return {
                "from_layer_id": from_layer_id,
                "to_layer_id": to_layer_id,
                "from_year": from_year,
                "to_year": to_year,
                "title": f"LULC Change {from_year} → {to_year}",
                "total_area_hectares": total_area_hectares,
                "changed_area_hectares": changed_area_hectares,
                "changed_share_pct": changed_share_pct,
                "uncertainty_share_pct": low_share,
                "certainty_by_level_pct": {
                    "high": high_share,
                    "medium": medium_share,
                    "low": low_share,
                },
                "changed_areas_geojson": changed_areas_geojson,
                "transitions": transition_rows,
            }

    @staticmethod
    @lru_cache(maxsize=8)
    def _buffered_buildings_union_geometry(buildings_path: str, buffer_meters: float) -> dict[str, Any]:
        buildings_gdf = gpd.read_file(buildings_path).to_crs(epsg=25832)
        buffered = buildings_gdf.geometry.buffer(buffer_meters)
        unioned = buffered.union_all() if hasattr(buffered, "union_all") else buffered.unary_union
        unioned_4326 = gpd.GeoSeries([unioned], crs="EPSG:25832").to_crs(epsg=4326).iloc[0]
        return unioned_4326.__geo_interface__

    @staticmethod
    @lru_cache(maxsize=8)
    def _buildings_union_geometry(buildings_path: str) -> dict[str, Any]:
        buildings_gdf = gpd.read_file(buildings_path).to_crs(epsg=4326)
        geom_series = buildings_gdf.geometry
        unioned = geom_series.union_all() if hasattr(geom_series, "union_all") else geom_series.unary_union
        return unioned.__geo_interface__

def _sum_nullable(values: pd.Series) -> float | None:
    if values.empty:
        return None
    valid = values.dropna()
    if valid.empty:
        return None
    return float(valid.sum())


def _numeric_series(frame: gpd.GeoDataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _find_bin(value: float, bins: list[dict[str, float | str | None]]) -> int | None:
    for idx, item in enumerate(bins):
        minimum = item["minimum_c"]
        maximum = item["maximum_c"]
        lower_ok = True if minimum is None else value >= float(minimum)
        upper_ok = True if maximum is None else value < float(maximum)
        if lower_ok and upper_ok:
            return idx
    return None


def _normalize_share_series(values: pd.Series) -> pd.Series:
    out = values.copy()
    mask = out.notna() & (out > 1.0) & (out <= 100.0)
    out.loc[mask] = out.loc[mask] / 100.0
    return out


def _sample_population_exposure(
    selected_4326: gpd.GeoDataFrame,
    raster_path: Any,
    nodata_override: float | int | None,
    bins: list[dict[str, float | str | None]],
    population: pd.Series,
    elderly_count: pd.Series,
    children_count: pd.Series,
) -> list[dict[str, Any]]:
    exposures = [
        {
            "label": str(item["label"]),
            "minimum_c": item["minimum_c"],
            "maximum_c": item["maximum_c"],
            "population": None,
            "elderly_population": None,
            "children_population": None,
        }
        for item in bins
    ]

    if selected_4326.empty:
        return exposures

    with rasterio.open(raster_path) as dataset:
        nodata = nodata_override if nodata_override is not None else dataset.nodata
        points_native = selected_4326.to_crs(dataset.crs).geometry.centroid
        coords = [(point.x, point.y) for point in points_native]
        sampled_values = [value[0] for value in dataset.sample(coords)]

    for idx, raw_value in enumerate(sampled_values):
        if not np.isfinite(raw_value):
            continue
        if nodata is not None and float(raw_value) == float(nodata):
            continue

        pop = population.iloc[idx]
        elder = elderly_count.iloc[idx]
        child = children_count.iloc[idx]
        if pd.isna(pop):
            continue

        bin_index = _find_bin(float(raw_value), bins)
        if bin_index is None:
            continue

        current = exposures[bin_index]
        current["population"] = (current["population"] or 0.0) + float(pop)
        if not pd.isna(elder):
            current["elderly_population"] = (current["elderly_population"] or 0.0) + float(elder)
        if not pd.isna(child):
            current["children_population"] = (current["children_population"] or 0.0) + float(child)

    return exposures

