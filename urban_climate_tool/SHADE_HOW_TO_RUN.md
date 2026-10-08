# How to Run Shade Generation

## Terminal Setup

### Option 1: Use VS Code Terminal (Easiest)
1. Open VS Code
2. Press `Ctrl+`` (backtick) to open integrated terminal
3. Terminal should already be in the project folder
4. You'll see commands run with progress bars in real-time

### Option 2: Use System Terminal
```bash
cd "/Users/simonmarggraf/Library/CloudStorage/OneDrive-Persönlich/Desktop/9_Coding Projects/development/urban_climate_tool"
```

---

## Step-by-Step Workflow

### STEP 1: Activate Python Environment
```bash
source .venv/bin/activate
```

You'll see your terminal change to show `(.venv)` at the start, like:
```
(.venv) $ 
```

### STEP 2: Build DSM (ONE-TIME - ~4 minutes)

```bash
python scripts/generate_dsm_only.py
```

**You'll see:**
```
[CHECKPOINT 1] Loading DEM...
  ✓ DEM loaded: 6838x5546 (0.17s)

[CHECKPOINT 2] Adding buildings...
  Loaded 5047 buildings
  Reprojecting...
  Rasterizing 5047 buildings...
    Buildings |████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░| 32.5% (1641/5047)
```

The progress bar will update in real-time. Let it run to completion (~3-4 min).

**✓ When done, you'll see:**
```
[COMPLETE] DSM building took 234.45s total
  - DEM: 0.17s | Buildings: 45.23s | Trees: 156.34s | Writing: 32.71s

Output files:
  - storage/rasters/derived/planegg/dsm_1m.tif
  - storage/rasters/derived/planegg/tree_canopy_1m.tif
```

---

### STEP 3: Quick Test (OPTIONAL - 30 seconds)

Verify everything works before full run:

```bash
python scripts/test_shade_quick.py
```

**You'll see:**
```
[CHECKPOINT 1] Loading DSM...
  ✓ DSM loaded: 6838x5546

[CHECKPOINT 2] Loading tree canopy...
  ✓ Tree canopy loaded (17.3m max height)

[CHECKPOINT 3] Ray-casting for 3 timestamps...
  Timestamps |███████████████████████████████████████| 100.0% (3/3)

[COMPLETE] Shade computation took 28.34s total
```

**Output files created:**
- `storage/rasters/derived/planegg/shade/sun_hours_2023-07-21.tif`
- `storage/rasters/derived/planegg/shade/shade_hours_2023-07-21.tif`
- `storage/rasters/derived/planegg/shade/shade_fraction_2023-07-21.tif`

---

### STEP 4: Full Production Run (~2 minutes)

Generate shade with all 9 timestamps and register in catalog:

```bash
python scripts/generate_shade_rasters_phase2.py --date 2023-07-21 --register
```

**You'll see:**
```
[CHECKPOINT 1] Loading DSM...
  ✓ DSM loaded: 6838x5546

[CHECKPOINT 3] Ray-casting for 9 timestamps...
  Timestamps |████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░| 44.4% (4/9)
  
[CHECKPOINT 4] Writing output rasters...
    ✓ sun_hours_2023-07-21.tif
    ✓ shade_hours_2023-07-21.tif
    ✓ shade_fraction_2023-07-21.tif

Registering shade layers in catalog...
  ✓ Registered 3 new layers in catalog
```

---

### STEP 5: View in Frontend

Restart backend to load new layers:

```bash
docker compose restart backend
```

Then open frontend and look for **"Shade & Solar"** layer group:
- You'll see 3 new layers
- Click on them to view on the map
- Click pixels to sample sun/shade hours

---

## Complete Command Sequence

Copy & paste this to run everything in order:

```bash
cd "/Users/simonmarggraf/Library/CloudStorage/OneDrive-Persönlich/Desktop/9_Coding Projects/development/urban_climate_tool"
source .venv/bin/activate

echo "=== PHASE 1: Building DSM (4 min) ==="
python scripts/generate_dsm_only.py

echo ""
echo "=== PHASE 2: Testing (30 sec) ==="
python scripts/test_shade_quick.py

echo ""
echo "=== PHASE 3: Full production run (2 min) ==="
python scripts/generate_shade_rasters_phase2.py --date 2023-07-21 --register

echo ""
echo "=== Restarting backend ==="
docker compose restart backend

echo ""
echo "✓ Done! Check frontend at http://localhost:3000"
```

---

## What to Do If Stuck

### "Command not found: python"
```bash
# Use full path to venv python
.venv/bin/python scripts/generate_dsm_only.py
```

### "No module named 'app'"
```bash
# Make sure you're in the project root
pwd  # Should show: .../urban_climate_tool

# And venv is activated
which python  # Should show: .../urban_climate_tool/.venv/bin/python
```

### Progress bar not updating
```bash
# Run with unbuffered output
python -u scripts/generate_dsm_only.py
```

### Accidentally closed terminal mid-run
```bash
# Check if still running
ps aux | grep generate_dsm

# If running, let it finish (don't interrupt)
# If stuck, kill and restart
pkill -f generate_dsm
```

### Want to stop a running process
Press: `Ctrl+C`

---

## Different Scenarios

### Generate for different date
```bash
python scripts/generate_shade_rasters_phase2.py --date 2023-06-21 --register
python scripts/generate_shade_rasters_phase2.py --date 2023-08-21 --register
```

### Fast run with only 3 timestamps
```bash
python scripts/generate_shade_rasters_phase2.py \
  --date 2023-07-21 \
  --times 08:00,12:00,18:00 \
  --register
```

### Without registering to catalog
```bash
python scripts/generate_shade_rasters_phase2.py --date 2023-07-21
# (outputs written but not added to layer list)
```

### Change tree transmissivity (e.g., 50% light through)
```bash
python scripts/generate_shade_rasters_phase2.py \
  --date 2023-07-21 \
  --tree-transmissivity 0.5 \
  --register
```

---

## Typical Run Times

| Stage | Time | Can Skip? |
|-------|------|-----------|
| DSM Build | 3-4 min | ❌ No (one-time) |
| Quick Test | 30 sec | ✅ Yes (optional) |
| Full Shade | 2 min | ❌ No (required) |
| Docker restart | 10 sec | ✅ Yes (if eager) |
| **TOTAL FIRST TIME** | ~6 min | |
| **RERUNS** | ~2 min | (DSM reused) |

---

## Monitoring Progress

### In VS Code Terminal
- Progress bars appear **in real-time**
- Each checkpoint logs status
- Errors appear immediately

### In External Terminal
```bash
# Monitor progress in separate tab
tail -f dsm_progress.log
```

### Check output files
```bash
# See generated files
ls -lh storage/rasters/derived/planegg/

# Check file sizes
du -h storage/rasters/derived/planegg/*
```

---

## Next: View Results

Once complete, restart the application:

```bash
docker compose restart backend
```

Then:
1. Open http://localhost:3000 in browser
2. Left sidebar → expand "Shade & Solar" group
3. Select layer to view on map
4. Click pixels to see sun/shade hours

See [SHADE_PERFORMANCE.md](SHADE_PERFORMANCE.md) for detailed timing info.
