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

## Relative summer LST time-series convention

For dashboard time-series mode (Planegg), store yearly outputs under:

- `rasters/derived/planegg/relative_summer_lst/`

Recommended files:

- Yearly rasters (one per summer): `lst_relative_summer_anomaly_<year>.tif`
- Optional summary CSV used by the API endpoint `/api/layers/time-series/lst-relative-summer`:
	- `rasters/derived/planegg/relative_summer_lst/yearly_summary.csv`

Expected CSV columns (header names):

- `year` (required)
- `layer_id` (optional, catalog layer id for that year)
- `mean_anomaly_degC` (optional, chart value in °C)
- `mean_lst_degC` (optional)
- `n_scenes` (optional, kept scenes after valid-fraction filtering)
