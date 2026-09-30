from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
import matplotlib.cm as cm
import matplotlib.colors as mcolors

from src.config import get_project_root, get_city_config

PROJECT_ROOT = get_project_root()
RASTER_DIR = PROJECT_ROOT / "data" / "processed" / "rasters" / "munich"
ASSETS_DIR = PROJECT_ROOT / "app" / "assets" / "overlays" / "munich"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def tif_to_png(tif_path: Path, out_png: Path, nodata=None):
    with rasterio.open(tif_path) as src:
        arr = src.read(1).astype('float32')
        bounds = src.bounds
        profile = src.profile

    if nodata is None:
        nodata = profile.get('nodata', None)

    if nodata is not None:
        arr = np.where(arr == nodata, np.nan, arr)

    # Normalize values
    valid = np.isfinite(arr)
    if valid.any():
        vmin = float(np.nanpercentile(arr, 2))
        vmax = float(np.nanpercentile(arr, 98))
        norm = (arr - vmin) / (vmax - vmin)
        norm = np.clip(norm, 0.0, 1.0)
    else:
        norm = np.zeros_like(arr)

    # Choose color mapping based on filename
    name = tif_path.stem.lower()
    rgba = np.zeros((norm.shape[0], norm.shape[1], 4), dtype=np.uint8)

    def apply_colormap(norm_arr, cmap_name='viridis'):
        cmap = cm.get_cmap(cmap_name)
        mapped = cmap(norm_arr)  # RGBA floats 0-1
        mapped = (mapped * 255).astype(np.uint8)
        return mapped  # shape (h,w,4)

    if 'ndvi' in name:
        # vivid green ramp: map norm to green channel strongly
        r = (50 * (1 - norm)).astype(np.uint8)
        g = (120 + (norm * 135)).astype(np.uint8)
        b = (30 * (1 - norm)).astype(np.uint8)
        rgba[:, :, 0] = r
        rgba[:, :, 1] = g
        rgba[:, :, 2] = b
        rgba[:, :, 3] = (valid * 230).astype(np.uint8)
    elif 'lst' in name or 'temperature' in name:
        # simple heatmap: blue->yellow->red approximation
        r = (55 + (norm * 200)).astype(np.uint8)
        g = (20 + (1 - (norm - 0.5)**2) * 180).astype(np.uint8)
        b = (200 * (1 - norm)).astype(np.uint8)
        rgba[:, :, 0] = r
        rgba[:, :, 1] = g
        rgba[:, :, 2] = b
        rgba[:, :, 3] = (valid * 220).astype(np.uint8)
    elif 'dynamic_world' in name or any(k in name for k in ['water','trees','grass','built','bare']):
        # For dynamic world class masks, pick solid colors
        class_colors = {
            'water': (0, 114, 189),
            'trees': (34, 139, 34),
            'grass': (124, 252, 0),
            'built': (220, 53, 69),
            'bare': (210, 180, 140),
            'bareland': (210, 180, 140),
            'snow': (240, 240, 240),
        }
        chosen = None
        for k in class_colors:
            if k in name:
                chosen = class_colors[k]
                break
        if chosen is None:
            # fallback to solid gray
            rgba[:, :, 0] = (norm * 200).astype(np.uint8)
            rgba[:, :, 1] = (norm * 200).astype(np.uint8)
            rgba[:, :, 2] = (norm * 200).astype(np.uint8)
            rgba[:, :, 3] = (valid * 200).astype(np.uint8)
        else:
            # colorize: where valid, show solid color scaled by presence
            r, g, b = chosen
            mask = np.isfinite(arr)
            rgba[mask, 0] = r
            rgba[mask, 1] = g
            rgba[mask, 2] = b
            rgba[mask, 3] = 220
    else:
        # default grayscale
        gray = (norm * 255).astype(np.uint8)
        rgba[:, :, 0] = gray
        rgba[:, :, 1] = gray
        rgba[:, :, 2] = gray
        rgba[:, :, 3] = (valid * 255).astype(np.uint8)

    img = Image.fromarray(rgba, mode='RGBA')
    img.save(out_png)

    return bounds


def build_overlays():
    overlays = {}
    for tif in sorted(RASTER_DIR.glob("*.tif")):
        out_png = ASSETS_DIR / (tif.stem + ".png")
        bounds = tif_to_png(tif, out_png)
        overlays[out_png.name] = {
            "png": str(Path("assets") / "overlays" / "munich" / out_png.name),
            "bounds": [[bounds.bottom, bounds.left], [bounds.top, bounds.right]],
        }
    meta_path = ASSETS_DIR.parent / "munich_overlays.json"
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(overlays, fh, indent=2)
    print(f"Wrote {len(overlays)} overlays to {ASSETS_DIR} and metadata to {meta_path}")


if __name__ == "__main__":
    build_overlays()
