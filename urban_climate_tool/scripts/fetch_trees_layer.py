#!/usr/bin/env python3
"""
Process individual trees from Bayern geopackage and create GeoJSON layer.
Source: https://geodaten.bayern.de/opengeodata/OpenDataDetail.html?pn=einzelbaeume

Attributes:
- ID: Tree identifier
- dgmhoehe: Absolute height of tree (from DGM - Digital Elevation Model)
- baumhoehe: Height of tree above ground
"""

import sqlite3
import json
from pathlib import Path
import logging
import struct
from math import radians, cos, sin, asin, sqrt

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    Returns distance in meters
    """
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    
    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371000 # Radius of earth in meters
    return c * r

def load_planegg_boundary():
    """Load Planegg boundary and get bounding box in EPSG:25832."""
    boundary_path = Path(__file__).parent.parent / "storage" / "vectors" / "processed" / "planegg" / "boundary.geojson"
    
    if not boundary_path.exists():
        logger.warning(f"Boundary file not found: {boundary_path}")
        return None, None
    
    with open(boundary_path) as f:
        boundary_geojson = json.load(f)
    
    # Get approximate bounding box from coordinates
    # Planegg is roughly at: lat 48.09-48.12, lon 11.38-11.47
    # In EPSG:25832 (UTM 32): roughly 670000-675000 E, 5335000-5340000 N
    # These are approximate based on the GeoJSON coordinates
    
    return boundary_geojson, {
        "min_x": 670000,
        "max_x": 676000,
        "min_y": 5333000,
        "max_y": 5340000
    }

def parse_wkb_point(wkb_bytes):
    """Parse WKB binary format to extract X, Y coordinates."""
    # WKB format: endianness (1 byte) + geometry type (4 bytes) + X (8 bytes) + Y (8 bytes)
    if len(wkb_bytes) < 21:
        return None
    
    endianness = wkb_bytes[0]
    endian_char = '<' if endianness == 1 else '>'
    
    try:
        x, y = struct.unpack(f'{endian_char}dd', wkb_bytes[5:21])
        return (x, y)
    except struct.error:
        return None

def read_trees_from_geopackage(gpkg_path, bbox=None):
    """Read tree data from geopackage and convert to GeoJSON features.
    
    Args:
        gpkg_path: Path to geopackage file
        bbox: Optional bounding box dict with min_x, max_x, min_y, max_y to filter trees
    
    Returns:
        List of GeoJSON features
    """
    conn = sqlite3.connect(gpkg_path)
    cursor = conn.cursor()
    
    # Get all tree tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_trees';")
    tree_tables = [t[0] for t in cursor.fetchall()]
    
    logger.info(f"Found {len(tree_tables)} tree tables")
    
    features = []
    total_count = 0
    filtered_count = 0
    
    for table_name in sorted(tree_tables):
        # Get tree data from table
        cursor.execute(f"""
            SELECT fid, geom, ID, dgmhoehe, baumhoehe
            FROM [{table_name}]
        """)
        
        rows = cursor.fetchall()
        table_filtered = 0
        
        for fid, geom_wkb, tree_id, dgmhoehe, baumhoehe in rows:
            # Parse WKB geometry
            coords = parse_wkb_point(geom_wkb)
            if coords is None:
                continue
            
            x, y = coords
            total_count += 1
            
            # Filter by bounding box if provided
            if bbox:
                if not (bbox["min_x"] <= x <= bbox["max_x"] and 
                        bbox["min_y"] <= y <= bbox["max_y"]):
                    continue
            
            table_filtered += 1
            
            # Create GeoJSON feature
            # Use baumhoehe as height for 3D extrusion
            # Use dgmhoehe as base_height (elevation)
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [x, y]
                },
                "properties": {
                    "id": int(tree_id),
                    "height": float(baumhoehe),  # Tree height for 3D extrusion
                    "base_height": float(dgmhoehe),  # Ground elevation
                    "dgmhoehe": float(dgmhoehe),  # Preserve original name
                    "baumhoehe": float(baumhoehe),  # Preserve original name
                    "tile": table_name
                }
            }
            
            features.append(feature)
            filtered_count += 1
        
        if table_filtered > 0:
            logger.info(f"  {table_name}: {table_filtered} trees")
    
    conn.close()
    
    logger.info(f"Total trees processed: {total_count}")
    logger.info(f"Trees in bbox: {filtered_count}")
    
    return features

def filter_trees_in_boundary(features, boundary_path):
    """Filter trees to only those within the Planegg boundary."""
    if not boundary_path.exists():
        logger.warning(f"Boundary file not found: {boundary_path}")
        return features
    
    try:
        import geopandas as gpd
        from shapely.geometry import Point
    except ImportError:
        logger.warning("geopandas not available, skipping boundary filtering")
        return features
    
    # Load boundary
    boundary_gdf = gpd.read_file(boundary_path)
    
    # Reproject if needed (boundary should be in EPSG:25832)
    if boundary_gdf.crs.to_epsg() != 25832:
        boundary_gdf = boundary_gdf.to_crs(25832)
    
    boundary = boundary_gdf.geometry.unary_union
    
    # Filter features
    filtered_features = []
    for feature in features:
        coords = feature["geometry"]["coordinates"]
        point = Point(coords[0], coords[1])
        
        if point.within(boundary):
            filtered_features.append(feature)
    
    logger.info(f"Filtered to {len(filtered_features)} trees within Planegg boundary")
    
    return filtered_features

def save_geojson(features, output_path):
    """Save features to GeoJSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    with open(output_path, 'w') as f:
        json.dump(geojson, f, indent=2)
    
    logger.info(f"Saved {len(features)} trees to {output_path}")

def main():
    project_root = Path(__file__).parent.parent
    gpkg_path = project_root / "data" / "124028_baeume.gpkg"
    output_path = project_root / "storage" / "vectors" / "processed" / "planegg" / "trees.geojson"
    
    logger.info(f"Reading geopackage: {gpkg_path}")
    
    if not gpkg_path.exists():
        logger.error(f"Geopackage not found: {gpkg_path}")
        return
    
    # Load boundary
    boundary_geojson, bbox = load_planegg_boundary()
    
    # Read trees with bounding box filter
    features = read_trees_from_geopackage(gpkg_path, bbox=bbox)
    
    # Save to GeoJSON
    save_geojson(features, output_path)
    
    logger.info("Done!")

if __name__ == "__main__":
    main()
