# Real Data Fetching Guide

This project uses two real data sources:
1. **Google Earth Engine** – Sentinel-2 NDVI, Landsat LST, Dynamic World LULC
2. **Copernicus ERA5** – Daily temperature & precipitation

## Prerequisites

### 1. Google Earth Engine Setup

```bash
# Install Earth Engine client
pip install earthengine-api geemap

# Authenticate
earthengine authenticate
```

This opens a browser where you log in with your Google account (Earth Engine is free). Your credentials are saved locally.

### 2. Copernicus Climate Data Store Setup

```bash
# Install CDS client
pip install cdsapi

# Register at: https://cds.climate.copernicus.eu/
# Copy your credentials to ~/.cdsapirc:
# url: https://cds.climate.copernicus.eu/api/v2
# key: YOUR_UID:YOUR_API_KEY
```

## Fetch Real Data

### Step 1: Fetch GEE Data

```bash
cd urban_adaptation_tool
python scripts/01_fetch_gee_real_data.py
```

**What happens:**
- Queries Sentinel-2 for NDVI (2024)
- Queries Landsat 8/9 for surface temperature (2023-2024)
- Queries Dynamic World for LULC classification (2023)
- Starts export jobs to your Google Drive

**⏱️ Note:** Exports run async. Check your Google Drive or Earth Engine dashboard for progress (typically 5-30 minutes).

**Download step:**
Once complete, download the TIFFs from Google Drive to:
```
data/processed/rasters/munich/
```

### Step 2: Convert TIFFs to Overlays

After GEE exports are complete and downloaded:

```bash
python scripts/06_prepare_overlays.py
```

This converts GeoTIFFs → PNG overlays with proper color scales (NDVI green, LST heatmap, DW classes solid colors).

### Step 3: Fetch ERA5 Climate Data

```bash
python scripts/02_fetch_era5_real_data.py
```

**What happens:**
- Fetches daily 2m temperature and precipitation for 2019-2024
- Computes spatial mean over Munich bounding box
- Saves to `data/processed/summary/munich_era5_daily_summary.csv`

**⏱️ Duration:** ~10-30 minutes (depending on CDS server load)

## Run the App

```bash
python app/app_dash.py
```

Now the app displays:
- **Real satellite layers:** Sentinel-2 NDVI, Landsat LST, Dynamic World classifications
- **Real climate plots:** ERA5 temperature and precipitation time series (2019-2024)

## Troubleshooting

### "Earth Engine not initialized"
→ Run `earthengine authenticate` and try again.

### CDS timeout
→ ERA5 data requests can be large. If timeout, fetch year-by-year:
```python
# In scripts/02_fetch_era5_real_data.py, modify the loop to fetch 1 year at a time
```

### GEE exports stuck
→ Check status in Earth Engine Code Editor or dashboard. May require manual approval for large exports.

### Missing TIFFs
→ Ensure you downloaded from Google Drive to `data/processed/rasters/munich/` before running step 2.

## Customizing for Other Cities

Edit `src/config.py` and add a new city:

```python
ZURICH_CONFIG = CityConfig(
    name="zurich",
    center_lon=8.545594,
    center_lat=47.368650,
    buffer_km=15,
    ...
)
```

Then fetch data with `get_city_config("zurich")` in the scripts above.
