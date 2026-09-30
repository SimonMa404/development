from __future__ import annotations

from typing import Dict

DYNAMIC_WORLD_CLASS_COLORS: Dict[str, str] = {
    "water": "#1f77b4",
    "trees": "#2ca02c",
    "grass": "#7bc043",
    "flooded_vegetation": "#5e4fa2",
    "crops": "#d4a373",
    "shrub_and_scrub": "#8d99ae",
    "built": "#d62728",
    "bare": "#c7c7c7",
    "snow_and_ice": "#f1f5f9",
    "clouds": "#7f7f7f",
}

DYNAMIC_WORLD_CLASS_ORDER = [
    "water",
    "trees",
    "grass",
    "flooded_vegetation",
    "crops",
    "shrub_and_scrub",
    "built",
    "bare",
    "snow_and_ice",
    "clouds",
]


def dynamic_world_percent_palette(class_name: str) -> str:
    return DYNAMIC_WORLD_CLASS_COLORS.get(class_name, "#808080")
