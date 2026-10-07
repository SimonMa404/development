# Urban Climate Tool

## Quick setup (run commands)

### Option A: Docker (recommended)

```bash
docker compose up --build -d
```

Offline startup (after first online build):

```bash
docker compose up -d --no-build
```

App URLs:
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`

### Option B: Local development

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend (new terminal):

```bash
cd frontend
npm install
npm run dev
```

A geospatial decision-support web application for climate adaptation managers in German cities and municipalities.

## Architecture

The solution is structured into a Python FastAPI backend and a Next.js frontend. Geospatial data access, validation, metadata management, and analysis remain on the backend. The frontend consumes catalogue-driven metadata and renders layers generically, with no hardcoded dataset IDs.

Core principles:
- The backend owns geospatial data access, metadata, processing and analysis.
- The frontend renders layers and manages user interaction.
- Raster data is served as XYZ tiles and not converted to GeoJSON.
- Vector data is exposed through a generic API and can later evolve into vector tiles or PostGIS-backed services.
- Dataset registration is configuration-driven via `catalog/layers.yaml`.
- Runtime data remains outside Git under `storage/`.
- All file access is constrained to registered dataset paths within `DATA_ROOT`.

## Why runtime data is excluded from Git

This repository tracks the application configuration, source code, catalogue metadata and scripts only. Raster and vector data files are versioned outside Git because they are large, generated, and often sensitive or environment-specific. The project is designed so that the application can be cloned and run without any local or remote geospatial runtime data, then populated incrementally with local or production datasets.

## Storage layout

Runtime data lives under `storage/` and is created automatically when the backend or helper scripts run:

- `storage/rasters/source/` – source GeoTIFFs or other raster uploads
- `storage/rasters/processed/` – processed raster layers ready for serving
- `storage/rasters/derived/` – model results, summaries, derived products
- `storage/vectors/source/` – original vector files or uploads
- `storage/vectors/processed/` – prepared vector datasets
- `storage/uploads/` – user-uploaded content
- `storage/cache/` – caches for tiles or other derived artifacts
- `storage/temporary/` – temporary files

The repository only tracks `storage/.gitkeep` and `storage/README.md`.

## Layer catalogue

The tracked source of dataset metadata is `catalog/layers.yaml`. This catalog is the canonical registry of supported geodata layers. Actual data files remain on disk under `storage/` and are referenced via relative paths.

### Catalogue validation

The backend validates the catalog on startup. It verifies:
- duplicate IDs
- required fields
- safe path resolution within `DATA_ROOT`
- existence of registered files
- file-format compatibility with layer type
- valid legend/style metadata

## Generating the placeholder raster

Run:

```bash
cd scripts
python create_placeholder_heatmap.py
```

This creates a deterministic placeholder heat GeoTIFF at:

`storage/rasters/processed/placeholder_heat.tif`

The generated raster uses EPSG:25832, has nodata, includes a valid affine transform, and is suitable for serving as tiled raster data.

Use `--force` to overwrite the existing raster if needed:

```bash
python scripts/create_placeholder_heatmap.py --force
```

## Running the backend

Create a virtual environment and install dependencies:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

Start the API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Running the frontend

```bash
cd frontend
npm install
npm run dev
```

The app runs on `http://localhost:3000` and calls the backend at `http://localhost:8000`.

## Running through Docker

From the project root:

```bash
docker compose up --build
```

This mounts `./storage` into the backend container so runtime data is persisted locally without being committed.

## Running Docker offline

You can run the stack without internet access if images are already built locally.

One-time preparation while online:

```bash
docker compose build
```

Then start offline:

```bash
docker compose up -d --no-build
```

Notes:
- Do not use `--build` when offline.
- Avoid pruning local images if you want to keep offline capability.

## Adding a real GeoTIFF

A concrete workflow:

1. Copy the file into `storage/rasters/source/`.
2. Validate its CRS, nodata and metadata.
3. Convert it to a processed Cloud Optimized GeoTIFF under `storage/rasters/processed/`.
4. Add a matching layer entry to `catalog/layers.yaml`.
5. Run the catalogue validator.
6. Restart or reload the backend.
7. Confirm that the layer appears automatically in the frontend.

## Importing 1m DEM from .meta4

To enable terrain-based 3D mode, build a clipped DEM for Planegg:

```bash
python scripts/fetch_dem_from_meta4.py --meta4 "09184138 (1).meta4"
```

This script:
- parses the MetaLink file,
- downloads and SHA-256 validates DEM GeoTIFF tiles,
- mosaics tiles,
- clips to the buffered Planegg ROI,
- writes `storage/rasters/processed/planegg/dem_1m.tif`.

Once this file exists, the frontend enables the `3D Terrain` switch automatically.

## Importing DOM and RGB 20cm rasters from .meta4

For additional high-resolution rasters, use the new reusable importer:

```bash
python scripts/import_raster_from_meta4.py \
	--meta4 "data/09184138 (4).meta4" \
	--raw-subdir dom_20cm \
	--output storage/rasters/processed/planegg/dom_20cm.tif

python scripts/import_raster_from_meta4.py \
	--meta4 "data/09184138_RGB20cm.meta4" \
	--raw-subdir rgb_20cm \
	--output storage/rasters/processed/planegg/rgb_20cm.tif
```

Convenience wrappers are also available:

```bash
python scripts/fetch_dom_from_meta4.py --meta4 "data/09184138 (4).meta4"
python scripts/fetch_rgb_from_meta4.py --meta4 "data/09184138_RGB20cm.meta4"
```

UI behavior after import:
- `3D Terrain` now supports a model selector (`DEM` / `DOM`).
- In `DOM` mode, buildings and trees are shown as 2D overlays (no 3D extrusions).
- The RGB 20cm orthophoto layer is available in the layer list and intentionally hidden from the legend.

## Adding a real vector dataset

1. Place the source vector file in `storage/vectors/source/`.
2. Validate CRS and attributes.
3. Perform any simplification or filtering required.
4. Write the processed output into `storage/vectors/processed/`.
5. Add an entry to `catalog/layers.yaml` with `layer_type: vector`.
6. Restart the backend and confirm the generic vector endpoint is available.

## Importing German Census 2022 (100m) for vulnerability analysis

This project supports ROI-filtered 100m Census 2022 indicators from the
preprocessed `z22data` repository:

- Source repository: https://github.com/JsLth/z22data
- Source directory: `z22_data_100m/`
- Required files:
	- `population_0.parquet`
	- `age_from_65_0.parquet`
	- `age_under_18_0.parquet`

Run:

```bash
python scripts/fetch_census_2022_100m.py
```

What the script does:

1. Downloads the required parquet files to `storage/vectors/source/census_2022_100m/`.
2. Loads the ROI from `storage/vectors/processed/planegg/boundary_buffered.geojson`.
3. Reprojects ROI to EPSG:3035 and applies bbox-prefiltered reads on parquet data.
4. Selects complete 100m cells by centroid-in-ROI (no clipping of cell values).
5. Writes processed outputs:
	 - `storage/vectors/processed/planegg/census_2022_100m.geojson`
	 - `storage/vectors/processed/planegg/census_2022_100m.parquet`

The resulting layer is registered as `census-2022-100m-planegg` in the catalog.
Missing or disclosure-controlled Census values remain null and are never coerced to zero.

## Area analysis additions

The area analysis now includes:

- total population in selected area,
- elderly population (65+) and share,
- children population (<18) and share,
- LST-over-population exposure bins (pie-chart ready output).

Endpoint:

- `POST /api/analysis/heat-vulnerability`

This endpoint combines Census 100m cells with LST sampling at census-cell centroids,
and aggregates population-weighted exposure classes.

## Validating the catalogue

From the repository root:

```bash
python scripts/validate_catalog.py
```

The validation script checks catalogue integrity and emits clear errors when entries are invalid.

## Future storage abstraction

The repository and service interfaces are designed so local storage can later be replaced by S3-compatible object storage or cloud-backed data services without changing the API contract. This is implemented through repository abstractions and a configuration-driven dataset catalog.

## Planned future additions

- PostGIS-backed vector and analysis layers
- STAC catalog integration
- Authentication and role-based access control
- Background processing and asynchronous tasks
- More advanced climate-analysis workflows and report generation

## License

This project is for internal municipal climate adaptation workflows and is designed to be extendable for local government use.
