#!/usr/bin/env python3
"""
Convert tree data for Planegg into a mixed-geometry GeoJSON.

For each tree inside the Planegg boundary this script writes:
- one Point feature for clean 2D rendering,
- one small Polygon for the trunk,
- one larger Polygon for the canopy.
"""

import json
from pathlib import Path

import fiona
import geopandas as gpd
import pandas as pd

def main():
    gpkg_path = Path('/app/data/124028_baeume.gpkg')
    output_path = Path('/app/storage/vectors/processed/planegg/trees.geojson')
    boundary_path = Path('/app/storage/vectors/processed/planegg/boundary.geojson')
    
    print(f"Reading geopackage: {gpkg_path}")
    
    # Read boundary for clipping
    gdf_boundary = gpd.read_file(boundary_path)
    if gdf_boundary.crs != 'EPSG:4326':
        gdf_boundary = gdf_boundary.to_crs('EPSG:4326')

    boundary_utm = gdf_boundary.to_crs('EPSG:25832')

    # Auto-discover all tree layers. A previously omitted layer caused a visible gap.
    tile_layers = [layer for layer in fiona.listlayers(str(gpkg_path)) if layer.endswith('_trees')]
    tile_layers.sort()
    
    all_features = []
    total_loaded = 0
    total_raw = 0
    
    for layer_name in tile_layers:
        try:
            gdf = gpd.read_file(str(gpkg_path), layer=layer_name)
            print(f"Processing {layer_name}... {len(gdf)} features")
            total_raw += len(gdf)

            if gdf.crs != 'EPSG:25832':
                gdf = gdf.to_crs('EPSG:25832')

            gdf['geometry'] = gdf.geometry.centroid
            gdf = gpd.clip(gdf, boundary_utm)
            if gdf.empty:
                continue

            print(f"  After clipping to boundary: {len(gdf)} features")

            tree_heights = [
                float(value) if pd.notna(value) else 12.0
                for value in gdf.get('baumhoehe', pd.Series([12.0] * len(gdf), index=gdf.index))
            ]
            trunk_radii = [max(0.28, min(0.55, height * 0.015)) for height in tree_heights]
            canopy_radii = [max(1.6, min(4.8, height * 0.16)) for height in tree_heights]

            centroids_wgs84 = gpd.GeoSeries(gdf.geometry, crs='EPSG:25832').to_crs('EPSG:4326')
            trunks_wgs84 = gpd.GeoSeries(
                [geom.buffer(radius, resolution=6) for geom, radius in zip(gdf.geometry, trunk_radii)],
                crs='EPSG:25832',
            ).to_crs('EPSG:4326')
            canopies_wgs84 = gpd.GeoSeries(
                [geom.buffer(radius, resolution=8) for geom, radius in zip(gdf.geometry, canopy_radii)],
                crs='EPSG:25832',
            ).to_crs('EPSG:4326')

            for pos, (idx, row) in enumerate(gdf.iterrows()):
                tree_height = tree_heights[pos]
                base_height = float(row['dgmhoehe']) if 'dgmhoehe' in row and pd.notna(row['dgmhoehe']) else 0.0

                trunk_height = max(1.8, min(4.2, tree_height * 0.24))
                canopy_base = max(1.2, trunk_height * 0.7)

                centroid_wgs84 = centroids_wgs84.iloc[pos]
                trunk_wgs84 = trunks_wgs84.iloc[pos]
                canopy_wgs84 = canopies_wgs84.iloc[pos]

                tree_id = f"{layer_name}:{int(row.get('ID', idx)) if pd.notna(row.get('ID')) else idx}"

                properties = {
                    "id": tree_id,
                    "tile": layer_name,
                    "height": tree_height,
                    "base_height": base_height,
                    "trunk_height": trunk_height,
                    "canopy_base": canopy_base,
                }

                for col in row.index:
                    if col != 'geometry' and col not in properties and col != 'ID':
                        val = row[col]
                        if pd.notna(val):
                            try:
                                properties[col] = float(val) if isinstance(val, (int, float)) else str(val)
                            except Exception:
                                pass

                point_feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [float(centroid_wgs84.x), float(centroid_wgs84.y)],
                    },
                    "properties": {
                        **properties,
                        "tree_part": "point",
                    },
                }

                trunk_feature = {
                    "type": "Feature",
                    "geometry": trunk_wgs84.__geo_interface__,
                    "properties": {
                        **properties,
                        "tree_part": "trunk",
                    },
                }

                canopy_feature = {
                    "type": "Feature",
                    "geometry": canopy_wgs84.__geo_interface__,
                    "properties": {
                        **properties,
                        "tree_part": "canopy",
                    },
                }

                all_features.extend([point_feature, trunk_feature, canopy_feature])
            
            total_loaded += len(gdf)

        except Exception as e:
            print(f"  Warning - could not load {layer_name}: {e}")

    print(f"\nTotal features after clipping: {len(all_features)}")
    print(f"Total loaded from all layers: {total_loaded}")
    print(f"Total raw features scanned: {total_raw}")
    print(f"Writing to {output_path}...")

    geojson = {
        "type": "FeatureCollection",
        "features": all_features
    }

    with open(output_path, 'w') as f:
        json.dump(geojson, f)

    file_size = output_path.stat().st_size / 1024 / 1024
    print(f"Done! File size: {file_size:.1f} MB")
    print(f"Feature count: {len(all_features)}")

if __name__ == "__main__":
    main()
