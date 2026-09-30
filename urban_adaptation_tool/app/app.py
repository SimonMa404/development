from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pathlib import Path

import folium
import rasterio
import streamlit as st
from streamlit_folium import st_folium

from src.config import get_city_config, get_project_root

PROJECT_ROOT = get_project_root()
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "rasters"


@st.cache_data
def list_layer_files() -> list[Path]:
    files = []
    for path in PROCESSED_DIR.rglob("*.tif"):
        if path.is_file():
            files.append(path)
    return sorted(files)


@st.cache_data
def get_raster_bounds(path: str):
    with rasterio.open(path) as src:
        return {
            "west": src.bounds.left,
            "south": src.bounds.bottom,
            "east": src.bounds.right,
            "north": src.bounds.top,
            "crs": src.crs.to_string() if src.crs else "EPSG:4326",
        }


@st.cache_data
def get_layer_summary() -> list[str]:
    return [path.name for path in list_layer_files()]


def build_map(selected_layers: list[Path], opacity: float) -> folium.Map:
    city = get_city_config("munich")
    m = folium.Map(
        location=[city.center_lat, city.center_lon],
        zoom_start=11,
        tiles="CartoDB positron",
        control_scale=True,
    )

    if not selected_layers:
        folium.Marker(
            [city.center_lat, city.center_lon],
            popup=f"{city.name.title()} center",
        ).add_to(m)
        return m

    for layer_path in selected_layers:
        bounds = get_raster_bounds(str(layer_path))
        layer_name = layer_path.name
        image_layer = folium.raster_layers.ImageOverlay(
            image=str(layer_path),
            bounds=[[bounds["south"], bounds["west"]], [bounds["north"], bounds["east"]]],
            opacity=opacity,
            colormap=lambda x: (x, x, x, 1),
            name=layer_name,
        )
        image_layer.add_to(m)

    folium.LayerControl().add_to(m)
    return m


def app() -> None:
    st.title("Urban Adaptation Tool")
    st.caption("Munich climate hazard and vulnerability viewer using GEE and ERA5-derived raster layers")

    layer_files = list_layer_files()
    if not layer_files:
        st.warning("No GeoTIFF layers were found. Run the data collection scripts first.")
        return

    layer_names = [p.name for p in layer_files]
    selected = st.multiselect(
        "Select raster layers to show on the map",
        options=layer_names,
        default=layer_names[:3] if len(layer_names) >= 3 else layer_names,
    )

    opacity = st.slider("Layer opacity", min_value=0.1, max_value=1.0, value=0.7, step=0.05)

    selected_paths = [p for p in layer_files if p.name in selected]
    map_obj = build_map(selected_paths, opacity)
    st_folium(map_obj, width=1100, height=700, returned_objects=[])

    st.subheader("Notes")
    st.write(
        "This app is designed for urban heat stress, NDVI vegetation, Dynamic World land-cover classes, and other processed climate risk layers. "
        "Each TIFF is rendered as an overlay on the map and can be toggled in the layer control."
    )


if __name__ == "__main__":
    app()
