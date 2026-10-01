# Runtime Storage

This directory is reserved for runtime datasets and generated outputs.

Files in this folder are intentionally excluded from Git. Do not commit:
- GeoTIFFs
- COGs
- shapefiles
- GeoPackages
- uploads
- caches
- generated tiles
- derived model output
- local environment files

The directory structure is created automatically and is organized as follows:

- `rasters/source/`
- `rasters/processed/`
- `rasters/derived/`
- `vectors/source/`
- `vectors/processed/`
- `uploads/`
- `cache/`
- `temporary/`
