# Shade Modelling - Performance & Timing Guide

## Expected Runtimes

### Phase 1: Digital Surface Model (DSM) Generation
**ONE-TIME build (reusable for all shade calculations)**

```
┌─────────────────────────────────────────┐
│ CHECKPOINT 1: Load DEM         ~0.2s    │
│ CHECKPOINT 2: Add 5047 buildings ~30-40s│  ◄─── Shows progress bar
│ CHECKPOINT 3: Add 387K trees   ~90-120s │  ◄─── Shows progress bar
│ CHECKPOINT 4: Write rasters    ~20-30s  │
├─────────────────────────────────────────┤
│ TOTAL DSM BUILD:              ~3-4 min  │
└─────────────────────────────────────────┘
```

**Output:**
- `storage/rasters/derived/planegg/dsm_1m.tif` (~200 MB)
- `storage/rasters/derived/planegg/tree_canopy_1m.tif` (~200 MB)

### Phase 2: Shade Computation (reuses DSM)
**Fast! Can run multiple times with different dates/times**

```
┌────────────────────────────────────────┐
│ CHECKPOINT 1: Load DSM          ~0.5s  │
│ CHECKPOINT 2: Load tree canopy  ~0.5s  │
│ CHECKPOINT 3: Ray-cast 9 times ~60-90s │  ◄─── Shows progress
│ CHECKPOINT 4: Write outputs     ~10s   │
├────────────────────────────────────────┤
│ TOTAL SHADE RUN:               ~2 min  │
└────────────────────────────────────────┘
```

**Output:**
- `storage/rasters/derived/planegg/shade/sun_hours_2023-07-21.tif`
- `storage/rasters/derived/planegg/shade/shade_hours_2023-07-21.tif`
- `storage/rasters/derived/planegg/shade/shade_fraction_2023-07-21.tif`

---

## Workflow

### Quick Test (5-10 minutes)
```bash
# Build DSM once
python scripts/generate_dsm_only.py

# Test with 3 timestamps (30 sec)
python scripts/test_shade_quick.py

# Verify files exist and look correct
```

### Full Production Run (5-6 minutes)
```bash
# Build DSM (if not already done)
python scripts/generate_dsm_only.py

# Generate full shade rasters (9 timestamps) + register
python scripts/generate_shade_rasters_phase2.py --date 2023-07-21 --register

# Restart backend to pick up new catalog
docker compose restart backend
```

### Fast Reruns (2 minutes each)
```bash
# Different date with existing DSM
python scripts/generate_shade_rasters_phase2.py --date 2023-06-21 --register

# Different times (3 key times instead of 9)
python scripts/generate_shade_rasters_phase2.py --date 2023-07-21 --times 08:00,12:00,18:00 --register
```

---

## Progress Indicators

During execution, you'll see real-time output like:

```
[CHECKPOINT 1] Loading DEM...
  ✓ DEM loaded: 6838x5546 (0.17s)

[CHECKPOINT 2] Adding buildings...
  Loading buildings...
  Loaded 5047 buildings
  Reprojecting...
  Rasterizing 5047 buildings...
    Buildings |███████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░| 35.2% (1776/5047)
```

Progress bars update in real-time. Times shown:
- **Low% at start** = still loading/setting up
- **Mid% (~50%)** = halfway through rasterization
- **Near 100%** = finishing up

---

## Performance Tips

### Speed Up Further

1. **Fewer timestamps** (if ~3 are enough):
   ```bash
   python scripts/generate_shade_rasters_phase2.py \
     --date 2023-07-21 \
     --times 08:00,12:00,18:00 \
     --register
   ```
   **Saves ~60s per run**

2. **Different tree transmissivity** (e.g., 50% light):
   ```bash
   python scripts/generate_shade_rasters_phase2.py \
     --date 2023-07-21 \
     --tree-transmissivity 0.5 \
     --register
   ```
   **No additional time cost**

3. **Batch multiple dates**:
   ```bash
   for date in 2023-06-21 2023-07-21 2023-08-21; do
     python scripts/generate_shade_rasters_phase2.py --date $date --register
   done
   ```
   **DSM is built once, then reused 3x**

### Troubleshooting Slow Runs

| Issue | Cause | Solution |
|-------|-------|----------|
| Stuck at "Rasterizing N buildings" | Looping through each geometry | Normal, shows progress bar |
| No progress bar visible | Buffered output | Run with `-u` flag: `python -u script.py` |
| Taking >10 min | DSM too large or IO bottleneck | Check available disk space, close other apps |
| Out of memory | 6838×5546 raster too large | Reduce DEM resolution (expert mode) |

---

## Next Steps

1. **Generate DSM** (one-time)
2. **Run quick test** to verify
3. **Generate full shade rasters** with registration
4. **View in frontend** at `Shade & Solar` layer group
5. **Iterate** with different dates/parameters as needed

---

## File Structure

```
storage/rasters/derived/planegg/
├── dsm_1m.tif                    ← Phase 1 output (reusable)
├── tree_canopy_1m.tif            ← Phase 1 output (for transmissivity)
└── shade/
    ├── sun_hours_2023-07-21.tif  ← Phase 2 outputs (per date)
    ├── shade_hours_2023-07-21.tif
    └── shade_fraction_2023-07-21.tif
```

All GeoTIFFs are georeferenced (EPSG:25832) and ready for visualization.
