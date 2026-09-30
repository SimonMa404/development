from __future__ import annotations

from src.config import get_city_config
from src.era5_client import fetch_era5_daily
from src.gee_client import export_image, get_dynamic_world_mode, get_lst_mean, get_ndvi_annual, initialize_earth_engine


def main() -> None:
    city_name = "munich"
    city = get_city_config(city_name)
    initialize_earth_engine()

    roi = (
        __import__("ee").Geometry.Point([city.center_lon, city.center_lat]).buffer(city.buffer_km * 1000)
    )

    ndvi = get_ndvi_annual(city_name, 2024)
    export_image(ndvi, f"{city_name}_ndvi_2024", roi.geometry().bounds().getInfo(), scale=10)

    lst = get_lst_mean(city_name, 2023, 2024)
    export_image(lst, f"{city_name}_lst_mean_2023_2024", roi.geometry().bounds().getInfo(), scale=100)

    dw = get_dynamic_world_mode(city_name, 2024, 2024)
    export_image(dw, f"{city_name}_dynamic_world_mode_2024", roi.geometry().bounds().getInfo(), scale=10)

    fetch_era5_daily(city_name)
    print(f"Munich data fetch pipeline completed for {city_name}.")


if __name__ == "__main__":
    main()
