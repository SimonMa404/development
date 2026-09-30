from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class CityConfig:
    name: str
    country: str
    center_lon: float
    center_lat: float
    bbox: tuple[float, float, float, float]
    buffer_km: float = 15.0
    crs: str = "EPSG:4326"
    start_date: str = "2019-01-01"
    end_date: str = "2024-12-31"
    dynamic_world_classes: Dict[str, int] = field(
        default_factory=lambda: {
            "water": 0,
            "trees": 1,
            "grass": 2,
            "flooded_vegetation": 3,
            "crops": 4,
            "shrub_and_scrub": 5,
            "built": 6,
            "bare": 7,
            "snow_and_ice": 8,
            "clouds": 9,
        }
    )


MUNICH_CONFIG = CityConfig(
    name="munich",
    country="Germany",
    center_lon=11.576124,
    center_lat=48.137154,
    bbox=(11.18, 47.94, 11.97, 48.37),
    buffer_km=15.0,
    start_date="2019-01-01",
    end_date="2024-12-31",
)

CITY_CONFIGS = {"munich": MUNICH_CONFIG}


def get_city_config(city_name: str = "munich") -> CityConfig:
    city_key = city_name.lower().strip()
    if city_key not in CITY_CONFIGS:
        raise ValueError(f"Unsupported city: {city_name}. Available: {sorted(CITY_CONFIGS)}")
    return CITY_CONFIGS[city_key]


def get_project_root() -> Path:
    return PROJECT_ROOT
