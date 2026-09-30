# Urban Adaptation Tool

A script-first urban climate adaptation analysis project for Munich, designed so it can be replicated for other cities.

## Goals

- Evaluate urban climate hazards using Google Earth Engine data
- Incorporate ERA5 climate time series and extreme rainfall signals
- Map vulnerability using exposed population and critical infrastructure
- Visualize hazard, land-cover, and vegetation layers in a Streamlit map app
- Track adaptation effectiveness over time using the same processing pipeline

## Project structure

- `scripts/`: standalone Python scripts for data collection and processing
- `src/`: reusable project modules for config, raster utilities, and climate logic
- `app/`: Streamlit app for map-based exploration
- `data/raw/`: raw downloads from GEE and ERA5
- `data/processed/`: processed GeoTIFF layers and summary tables

## Recommended workflow

1. Configure the city in `src/config.py`
2. Run the GEE data pipeline: `python scripts/01_fetch_gee.py`
3. Run the ERA5 pipeline: `python scripts/02_fetch_era5.py`
4. Process rasters into per-class and summary layers: `python scripts/03_process_rasters.py`
5. Start the app: `streamlit run app/app.py`

## Munich defaults

The default study area is Munich, Germany, centered around:

- latitude: 48.137154
- longitude: 11.576124
- radius: 15 km

The project is intentionally structured so another city can be added by changing the config entry instead of rewriting the analysis logic.
