# Shade Modelling - Quick Start Guide

## Prerequisites

✓ DEM exists: `storage/rasters/processed/planegg/dem_1m.tif`
✓ Buildings exist: `storage/vectors/processed/planegg/buildings_3d.geojson`
✓ Trees exist: `storage/vectors/processed/planegg/trees.geojson`
✓ `pvlib` installed in backend Python environment

## Generate Shade Rasters

### Option A: Quick Start (Dry Run)
```bash
python scripts/generate_shade_rasters.py --date 2023-07-21
```
This will:
- Display planned raster generation steps
- **Not** write outputs (dry run)
- Exit cleanly

### Option B: Full Generation + Catalog Registration
```bash
python scripts/generate_shade_rasters.py --date 2023-07-21 --register
```
This will:
- Build DSM from DEM + buildings + trees
- Compute shade for 10:00-18:00 hourly on 2023-07-21
- Write 5 rasters to `storage/rasters/derived/planegg/shade/`:
  - `sun_hours_2023-07-21.tif`
  - `shade_hours_2023-07-21.tif`
  - `shade_fraction_2023-07-21.tif`
  - `dsm_1m.tif`
  - `tree_canopy_1m.tif`
- Register first 3 in `catalog/layers.yaml` with metadata and styling
- Takes ~5-10 minutes (machine-dependent)

### Option C: Custom Parameters
```bash
python scripts/generate_shade_rasters.py \
  --date 2023-07-21 \
  --timezone Europe/Berlin \
  --times "06:00,09:00,12:00,15:00,18:00,21:00" \
  --tree-transmissivity 0.15 \
  --register
```

**Common Parameters**:
- `--date`: Target date (YYYY-MM-DD). Examples: 2023-07-21 (hot day), 2023-12-21 (winter)
- `--timezone`: Timezone for sun calculations. Default: `Europe/Berlin`
- `--times`: Comma-separated times (HH:MM). Default: `10:00,11:00,...,18:00` (9 hours)
- `--tree-transmissivity`: Light penetration (0-1). Default: 0.2 (20% through, 80% blocked)

## View in Frontend

1. **Restart backend** (if already running):
   ```bash
   docker compose restart backend
   ```
   Or if running locally:
   ```bash
   # Stop current instance and restart
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Open frontend** at `http://localhost:3000`

3. **Expand "Shade & Solar"** group in the left layer panel

4. **Toggle layers**:
   - `Daily Sun Hours 2023-07-21`: Sunlit hours (yellow = full sun, red = full shade)
   - `Daily Shade Hours 2023-07-21`: Shaded hours (inverse coloring)
   - `Shade Fraction 2023-07-21`: Percentage shaded (0-100%)

5. **Interact**:
   - Click on any pixel to sample sun/shade hours at that location
   - Draw a polygon and fetch area statistics (mean, min, max shade hours)
   - Adjust opacity to blend with other layers

## Understanding Outputs

### Sun Hours
- **Range**: 0-9 hours (if simulating 10:00-18:00 = 9 timesteps)
- **Color**: Yellow (full sun) → Red (full shade)
- **Interpretation**: "This pixel receives direct sunlight for 7 out of 9 hours"
- **Use case**: Identify permanently shaded areas, good for microclimate planning

### Shade Hours
- **Range**: 0-9 hours
- **Color**: Red (full shade) → Yellow (full sun)
- **Interpretation**: "This pixel is in shade for 2 out of 9 hours"
- **Use case**: Where shade is most valuable (cooling, green space)

### Shade Fraction
- **Range**: 0-100%
- **Color**: Yellow (0% shaded) → Red (100% shaded)
- **Interpretation**: "This pixel is shaded for 22% of the simulation period"
- **Use case**: Direct comparison with heat vulnerability or LST layers

### DSM (Digital Surface Model)
- **Values**: Elevation in meters (stored as floating-point GeoTIFF)
- **Use**: Debugging, checking if buildings/trees were incorporated correctly
- **Note**: Not directly visualized in UI (technical layer for reference)

### Tree Canopy Layer
- **Values**: Canopy height in meters
- **Use**: Separate visualization of tree obstruction (for transparency analysis)
- **Note**: Not registered in catalog by default (technical debugging layer)

## Model Parameters & Assumptions

### Transmissivity
- Default: **20%** of direct sunlight passes through tree crowns
- Realistic range: 10-40% depending on species and season
- Fully opaque (0%): extreme case; trees modelled as solid blocks
- Fully transparent (100%): no shade effect; trees invisible

**Examples**:
- Dense deciduous (summer, full leaf): ~15-20%
- Sparse coniferous: ~30-50%
- Very dense urban forest: ~5-10%

### Simulation Times
- Default: **10:00-18:00 hourly** (covers peak heat period)
- Can extend to **06:00-21:00** for full daylight
- Can use fewer times for faster computation (e.g., 12:00 only for single-point shade)

### Reference Date
- Default: **2023-07-21** (summer solstice ≈ hottest day, longest day)
- Alternative: **2023-12-21** (winter solstice, shortest day, low sun angle)
- Use summer for heat adaptation planning; winter for light availability

## Troubleshooting

### "pvlib is required for shade modelling"
```bash
pip install pvlib
```

### "Rasters did not generate" or "Output directory not created"
Check file permissions:
```bash
ls -la storage/rasters/derived/planegg/
# Should show existing directories with write permission
```

### "Layer doesn't appear in UI after registration"
1. Verify file exists:
   ```bash
   ls -lh storage/rasters/derived/planegg/shade/sun_hours_*.tif
   ```
2. Restart backend:
   ```bash
   docker compose restart backend
   ```
3. Clear browser cache (Ctrl+Shift+R or Cmd+Shift+R)
4. Check catalog entry:
   ```bash
   grep -A5 "shade-sun-hours" catalog/layers.yaml
   ```

### "Shade values look wrong" (all 0s or all 9s)
- Check DSM was built correctly: Does `dsm_1m.tif` have non-zero values?
- Check buildings and trees were included:
  ```bash
  python -c "
  import rasterio
  with rasterio.open('storage/rasters/derived/planegg/shade/dsm_1m.tif') as src:
      data = src.read(1)
      print(f'Min: {data.min()}, Max: {data.max()}, Mean: {data.mean():.1f}')
  "
  ```
- If DSM values are constant, inputs may not have been properly rasterized

### Script runs but produces tiny output files (<1 MB)
- Likely issue: DSM was empty or all masked
- Debug: Check if buildings/trees GeoJSON files are valid and in correct CRS (EPSG:25832)

## Next Steps

1. **Generate for other dates**: Run with `--date 2023-12-21` (winter) for comparison
2. **Test transmissivity**: Re-run with `--tree-transmissivity 0.1` to see effect of denser canopy
3. **Integrate with analysis**: Overlay shade layers with heat vulnerability or LST to find shade-deficient heat-exposed areas
4. **Plan interventions**: Identify locations needing tree planting or shade structures

## Documentation

Full documentation in:
- `README.md` - Architecture and modelling approach
- `SHADE_IMPLEMENTATION.md` - Technical implementation details
- `backend/app/services/shade_service.py` - Code documentation (docstrings)
- `scripts/generate_shade_rasters.py` - CLI and registration logic

## Support

For issues or questions:
1. Check the `SHADE_IMPLEMENTATION.md` for technical details
2. Review modelling limitations in `README.md`
3. Inspect script logs for error messages
4. Verify input data integrity (DEM, buildings, trees)

---

**Last Updated**: 8 Oktober 2026  
**Status**: Ready for use and testing
