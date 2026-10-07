#!/usr/bin/env python3
"""
Convert geopackage tree points to small polygon squares for 3D visualization.
Each tree point becomes a 2x2 meter square (adjustable via TREE_SIZE_M).
"""

import json
import geopandas as gpd
from shapely.geometry import box
import sys

# Tree size in meters - defines the base polygon size
TREE_SIZE_M = 2.0

# Tiles to process (adjust as needed)
TILES = ['5330_trees', '5331_trees', '5332_trees']

# Input/output paths
GEOPACKAGE = '/app/data/124028_baeume.gpkg'
OUTPUT_GEOJSON = '/app/storage/vectors/processed/planegg/trees.geojson'

def point_to_square_polygon(lon, lat, size_degrees=0.00002):
    """Convert a point to a small square polygon in degrees (~2m at equator)."""
    half = size_degrees
    return box(lon - half, lat - half, lon + half, lat + half)

def process_trees():
    """Load trees from geopackage tiles and convert to polygons."""
    all_features = []
    total_trees = 0
    
    for tile_name in TILES:
        print(f"Processing {tile_name}...", file=sys.stderr)
        try:
            # Read from geopackage
            gdf = gpd.read_file(GEOPACKAGE, layer=tile_name)
            print(f"  Loaded {len(gdf)} trees from {tile_name}", file=sys.stderr)
            
            # Convert to WGS84 if needed
            if gdf.crs != 'EPSG:4326':
                gdf = gdf.to_crs('EPSG:4326')
            
            # Create polygon geometry from points
            def make_polygon(geom):
                if geom.is_empty:
                    return geom
                # Create 2m x 2m square centered on point (approximately 0.00002 degrees)
                return point_to_square_polygon(geom.x, geom.y)
            
            gdf['geometry'] = gdf.geometry.apply(make_polygon)
            
            # Extract features
            for idx, row in gdf.iterrows():
                geom_json = json.loads(json.dumps(json.loads(gpd.GeoSeries([row.geometry]).to_json())['features'][0]['geometry']))
                feature = {
                    'type': 'Feature',
                    'geometry': geom_json,
                    'properties': {
                        'id': int(row.get('ID', idx)) if 'ID' in row else idx,
                        'height': float(row.get('baumhoehe', 10)),
                        'base_height': float(row.get('dgmhoehe', 0)),
                        'tile': tile_name,
                    }
                }
                all_features.append(feature)
                total_trees += 1
                
        except Exception as e:
            print(f"  Error processing {tile_name}: {e}", file=sys.stderr)
            continue
    
    # Create FeatureCollection
    feature_collection = {
        'type': 'FeatureCollection',
        'features': all_features
    }
    
    # Write to GeoJSON
    with open(OUTPUT_GEOJSON, 'w') as f:
        json.dump(feature_collection, f)
    
    print(f"\nProcessed {total_trees} trees total", file=sys.stderr)
    print(f"Written to {OUTPUT_GEOJSON}", file=sys.stderr)
    print(f"File size: {len(json.dumps(feature_collection)) / 1024 / 1024:.1f} MB", file=sys.stderr)

if __name__ == '__main__':
    process_trees()
