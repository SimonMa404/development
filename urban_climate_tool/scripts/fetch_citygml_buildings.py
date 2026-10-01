"""Download Bavaria LoD2 CityGML building tiles covering Planegg and extract
building footprints + heights into a single GeoJSON for 3D visualization.

Usage:
    python scripts/fetch_citygml_buildings.py [--force]
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import geopandas as gpd
import requests
from lxml import etree
from pyproj import Transformer
from shapely.geometry import Polygon, mapping
from shapely.geometry.polygon import orient

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "citygml" / "raw"
BOUNDARY_PATH = REPO_ROOT / "storage" / "vectors" / "processed" / "planegg" / "boundary_buffered.geojson"
OUTPUT_PATH = REPO_ROOT / "storage" / "vectors" / "processed" / "planegg" / "buildings_3d.geojson"

# BKG/Bayern LoD2 CityGML tiles (2km grid) covering Planegg + surroundings.
TILES = [
    {
        "name": "678_5328.gml",
        "size": 61100723,
        "sha256": "e3c1053d80640f5c3e4d59c2ea2e9ce131ec5d69955d749f6f9a1f787e469271",
        "urls": [
            "https://download1.bayernwolke.de/a/lod2/citygml/678_5328.gml",
            "https://download2.bayernwolke.de/a/lod2/citygml/678_5328.gml",
        ],
    },
    {
        "name": "678_5326.gml",
        "size": 19199358,
        "sha256": "05419f67c43527461bb8406f3f0cc84e00c80a4d6b4a75193e7e4b0d3f584fc1",
        "urls": [
            "https://download1.bayernwolke.de/a/lod2/citygml/678_5326.gml",
            "https://download2.bayernwolke.de/a/lod2/citygml/678_5326.gml",
        ],
    },
    {
        "name": "678_5332.gml",
        "size": 8578558,
        "sha256": "0de6d9cf5aa63d4db346ec666c4d8c76a7dd2ead6e08e9e8e17ba9804a5e94fe",
        "urls": [
            "https://download1.bayernwolke.de/a/lod2/citygml/678_5332.gml",
            "https://download2.bayernwolke.de/a/lod2/citygml/678_5332.gml",
        ],
    },
    {
        "name": "680_5330.gml",
        "size": 74033833,
        "sha256": "0b965f08a0be3e16b59b262783b81e1056f16c0e9e547cc9a93ae0d5f7f7baca",
        "urls": [
            "https://download1.bayernwolke.de/a/lod2/citygml/680_5330.gml",
            "https://download2.bayernwolke.de/a/lod2/citygml/680_5330.gml",
        ],
    },
    {
        "name": "682_5332.gml",
        "size": 26825461,
        "sha256": "9db468a11a0ae90a30bb3748f36f63ec4f769a32d70a9989c3b56738f74dac89",
        "urls": [
            "https://download1.bayernwolke.de/a/lod2/citygml/682_5332.gml",
            "https://download2.bayernwolke.de/a/lod2/citygml/682_5332.gml",
        ],
    },
    {
        "name": "678_5330.gml",
        "size": 35912850,
        "sha256": "e7b136714055e751084da05a2c2e6edbb8688ce0049fc53844c0c848c44e0822",
        "urls": [
            "https://download1.bayernwolke.de/a/lod2/citygml/678_5330.gml",
            "https://download2.bayernwolke.de/a/lod2/citygml/678_5330.gml",
        ],
    },
    {
        "name": "682_5328.gml",
        "size": 44408656,
        "sha256": "0956abf3cbc089c8ebea91c7b4f93db38990967237e65969401e981d027e66d9",
        "urls": [
            "https://download1.bayernwolke.de/a/lod2/citygml/682_5328.gml",
            "https://download2.bayernwolke.de/a/lod2/citygml/682_5328.gml",
        ],
    },
    {
        "name": "676_5330.gml",
        "size": 2797183,
        "sha256": "84253e15dd92fc75d3839fa45a0758ebb8e781235ed6c5e5568e57596099a33f",
        "urls": [
            "https://download1.bayernwolke.de/a/lod2/citygml/676_5330.gml",
            "https://download2.bayernwolke.de/a/lod2/citygml/676_5330.gml",
        ],
    },
    {
        "name": "680_5328.gml",
        "size": 5677612,
        "sha256": "7c3348ebae299dc7fc557f38affe5fe2817fad151f8e6f4b69bdbffdc5e4db7c",
        "urls": [
            "https://download1.bayernwolke.de/a/lod2/citygml/680_5328.gml",
            "https://download2.bayernwolke.de/a/lod2/citygml/680_5328.gml",
        ],
    },
    {
        "name": "682_5330.gml",
        "size": 29607101,
        "sha256": "902ddc678904dd0eb8570a210115210f5c13a4ee322eaee19bceddcb370319cf",
        "urls": [
            "https://download1.bayernwolke.de/a/lod2/citygml/682_5330.gml",
            "https://download2.bayernwolke.de/a/lod2/citygml/682_5330.gml",
        ],
    },
    {
        "name": "676_5332.gml",
        "size": 82113763,
        "sha256": "0b385eea3ef44dd1a7df18a75313312356f769255406b38a55835450c2d154c0",
        "urls": [
            "https://download1.bayernwolke.de/a/lod2/citygml/676_5332.gml",
            "https://download2.bayernwolke.de/a/lod2/citygml/676_5332.gml",
        ],
    },
    {
        "name": "680_5326.gml",
        "size": 56101,
        "sha256": "9a90a016326904ccc7a15cb2c1b0a1ca1361a5068176115403703260cc724e59",
        "urls": [
            "https://download1.bayernwolke.de/a/lod2/citygml/680_5326.gml",
            "https://download2.bayernwolke.de/a/lod2/citygml/680_5326.gml",
        ],
    },
]

NS = {
    "gml": "http://www.opengis.net/gml",
    "bldg": "http://www.opengis.net/citygml/building/1.0",
}

BUILDING_TAGS = {
    "{http://www.opengis.net/citygml/building/1.0}Building",
    "{http://www.opengis.net/citygml/building/2.0}Building",
    "{http://www.opengis.net/citygml/building/1.0}BuildingPart",
    "{http://www.opengis.net/citygml/building/2.0}BuildingPart",
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _find_children_by_local_name(elem, *names: str):
    return [child for child in elem if _local(child.tag) in names]


def _find_descendants_by_local_name(elem, *names: str):
    return [d for d in elem.iter() if _local(d.tag) in names]


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_tile(path: Path, expected_size: int, expected_sha256: str) -> bool:
    if not path.exists():
        return False
    size_ok = path.stat().st_size == expected_size
    if not size_ok:
        return False
    return _file_sha256(path) == expected_sha256


def download_tiles(force: bool = False, strict: bool = True) -> list[Path]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    failures: list[str] = []

    for tile in TILES:
        name = tile["name"]
        expected_size = tile["size"]
        expected_sha256 = tile["sha256"]
        urls: list[str] = tile["urls"]
        dest = RAW_DIR / name

        if dest.exists() and not force and _validate_tile(dest, expected_size, expected_sha256):
            print(f"[skip] {name} already downloaded ({dest.stat().st_size / 1e6:.1f} MB)")
            paths.append(dest)
            continue

        print(f"[download] {name}")
        success = False
        for url in urls:
            print(f"  trying {url}")
            try:
                with requests.get(url, stream=True, timeout=120) as response:
                    response.raise_for_status()
                    tmp = dest.with_suffix(".part")
                    with open(tmp, "wb") as fh:
                        for chunk in response.iter_content(chunk_size=1 << 20):
                            fh.write(chunk)
                    tmp.rename(dest)
                if _validate_tile(dest, expected_size, expected_sha256):
                    print(f"  -> OK ({dest.stat().st_size / 1e6:.1f} MB, sha256 verified)")
                    paths.append(dest)
                    success = True
                    break
                print(f"  !! checksum/size mismatch for {name} from {url}", file=sys.stderr)
            except requests.RequestException as exc:
                print(f"  !! failed from {url}: {exc}", file=sys.stderr)

        if not success:
            failures.append(name)

    if failures and strict:
        raise SystemExit(f"Failed to download/validate required tiles: {', '.join(failures)}")

    if failures:
        print(f"WARNING: missing/invalid tiles: {', '.join(failures)}", file=sys.stderr)

    # Validate any skipped existing files for strict completeness.
    if strict:
        for tile in TILES:
            path = RAW_DIR / tile["name"]
            if not _validate_tile(path, tile["size"], tile["sha256"]):
                raise SystemExit(f"Tile failed validation: {tile['name']}")

    return paths


def _parse_poslist(text: str) -> list[tuple[float, float, float]]:
    vals = [float(v) for v in text.split()]
    return [(vals[i], vals[i + 1], vals[i + 2]) for i in range(0, len(vals), 3)]


def _extract_ring(surface_elem) -> list[tuple[float, float, float]] | None:
    poslists = _find_descendants_by_local_name(surface_elem, "posList")
    for poslist in poslists:
        if poslist.text:
            return _parse_poslist(poslist.text)
    positions = _find_descendants_by_local_name(surface_elem, "pos")
    if positions:
        coords = []
        for pos in positions:
            if not pos.text:
                continue
            vals = [float(v) for v in pos.text.split()]
            coords.append(tuple(vals[:3]))
        if coords:
            return coords
    return None


def _extract_ground_footprint(building_elem) -> list[tuple[float, float, float]] | None:
    for bounded in _find_children_by_local_name(building_elem, "boundedBy"):
        ground_candidates = _find_children_by_local_name(bounded, "GroundSurface")
        for ground in ground_candidates:
            ring = _extract_ring(ground)
            if ring and len(ring) >= 4:
                return ring
    # Fallback: some buildings only define a RoofSurface + WallSurfaces; use the
    # lowest wall ring as an approximate footprint.
    for bounded in _find_children_by_local_name(building_elem, "boundedBy"):
        wall_candidates = _find_children_by_local_name(bounded, "WallSurface")
        for wall in wall_candidates:
            ring = _extract_ring(wall)
            if ring and len(ring) >= 4:
                return ring
    return None


def _extract_height(building_elem, footprint_z: list[float]) -> float:
    height_elems = _find_children_by_local_name(building_elem, "measuredHeight")
    for height_elem in height_elems:
        if height_elem.text:
            try:
                value = float(height_elem.text)
                if value > 0:
                    return value
            except ValueError:
                pass

    # Fallback: derive height from the overall Z range of the building's surfaces.
    all_z: list[float] = list(footprint_z)
    for bounded in _find_children_by_local_name(building_elem, "boundedBy"):
        ring = _extract_ring(bounded)
        if ring:
            all_z.extend(z for _, _, z in ring)
    if len(all_z) >= 2:
        height = max(all_z) - min(all_z)
        if height > 0:
            return round(height, 1)
    return 6.0  # sensible default for a small residential building


def _extract_building_metadata(building_elem) -> dict[str, str | float | None]:
    creation_date = None
    creation_candidates = _find_children_by_local_name(building_elem, "creationDate")
    if creation_candidates and creation_candidates[0].text:
        creation_date = creation_candidates[0].text.strip()

    attributes: dict[str, str] = {}
    for string_attr in _find_descendants_by_local_name(building_elem, "stringAttribute"):
        name = string_attr.attrib.get("name")
        if not name:
            continue
        values = _find_children_by_local_name(string_attr, "value")
        if values and values[0].text:
            attributes[name] = values[0].text.strip()

    return {
        "creation_date": creation_date,
        "method": attributes.get("Methode"),
        "municipality_code": attributes.get("Gemeindeschluessel"),
        "roof_height": attributes.get("HoeheDach"),
        "ground_height": attributes.get("HoeheGrund"),
    }


def parse_tile(path: Path, boundary_25832) -> list[dict]:
    features: list[dict] = []
    context = etree.iterparse(str(path), events=("end",), tag=tuple(BUILDING_TAGS))
    count = 0
    kept = 0
    for _, elem in context:
        count += 1
        ring = _extract_ground_footprint(elem)
        if ring:
            xy = [(x, y) for x, y, _ in ring]
            if xy[0] != xy[-1]:
                xy.append(xy[0])
            try:
                polygon = Polygon(xy)
                if not polygon.is_valid:
                    polygon = polygon.buffer(0)
                if polygon.is_empty or polygon.area <= 0:
                    raise ValueError("empty polygon")
            except Exception:
                polygon = None

            if polygon is not None and polygon.intersects(boundary_25832):
                height = _extract_height(elem, [z for _, _, z in ring])
                building_id = elem.get("{http://www.opengis.net/gml}id", f"b{count}")
                metadata = _extract_building_metadata(elem)
                features.append(
                    {
                        "id": building_id,
                        "height": height,
                        "geometry": polygon,
                        "source_tile": path.name,
                        **metadata,
                    }
                )
                kept += 1

        # Free memory: clear this element and unlink from its ancestors.
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]

    print(f"  parsed {count} building elements, kept {kept} within Planegg ROI")
    return features


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Re-download tiles even if already present")
    parser.add_argument("--skip-download", action="store_true", help="Parse already-downloaded tiles only")
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Allow processing if some tiles are missing/invalid (default: fail if not complete)",
    )
    args = parser.parse_args()

    if not BOUNDARY_PATH.exists():
        raise SystemExit(f"Boundary file not found: {BOUNDARY_PATH}. Run extract_planegg_boundary.py first.")

    boundary_gdf = gpd.read_file(BOUNDARY_PATH).to_crs(epsg=25832)
    boundary_25832 = boundary_gdf.union_all() if hasattr(boundary_gdf, "union_all") else boundary_gdf.unary_union

    strict = not args.allow_partial

    if args.skip_download:
        tile_paths: list[Path] = []
        missing: list[str] = []
        for tile in TILES:
            tile_path = RAW_DIR / tile["name"]
            if _validate_tile(tile_path, tile["size"], tile["sha256"]):
                tile_paths.append(tile_path)
            else:
                missing.append(tile["name"])
        if missing and strict:
            raise SystemExit(f"Missing/invalid tiles (strict mode): {', '.join(missing)}")
        if missing:
            print(f"WARNING: Missing/invalid tiles: {', '.join(missing)}", file=sys.stderr)
    else:
        tile_paths = download_tiles(force=args.force, strict=strict)

    if not tile_paths:
        raise SystemExit("No CityGML tiles available to parse.")

    all_features: list[dict] = []
    for path in tile_paths:
        print(f"[parse] {path.name}")
        all_features.extend(parse_tile(path, boundary_25832))

    print(f"Total buildings within Planegg ROI: {len(all_features)}")

    transformer = Transformer.from_crs("EPSG:25832", "EPSG:4326", always_xy=True)

    geojson_features = []
    for feature in all_features:
        polygon_4326 = orient(
            Polygon([transformer.transform(x, y) for x, y in feature["geometry"].exterior.coords]),
            sign=1.0,
        )
        geojson_features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": feature["id"],
                    "height": feature["height"],
                    "min_height": 0,
                    "source_tile": feature.get("source_tile"),
                    "creation_date": feature.get("creation_date"),
                    "method": feature.get("method"),
                    "municipality_code": feature.get("municipality_code"),
                    "roof_height": feature.get("roof_height"),
                    "ground_height": feature.get("ground_height"),
                },
                "geometry": mapping(polygon_4326),
            }
        )

    geojson = {"type": "FeatureCollection", "features": geojson_features}

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    import json

    with open(OUTPUT_PATH, "w") as fh:
        json.dump(geojson, fh)

    print(f"Wrote {len(geojson_features)} buildings to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
