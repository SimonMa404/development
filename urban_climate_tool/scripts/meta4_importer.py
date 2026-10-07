from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

META_NS = {"m": "urn:ietf:params:xml:ns:metalink"}


Meta4Entry = dict[str, object]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_meta4(meta4_path: Path) -> list[Meta4Entry]:
    root = ET.fromstring(meta4_path.read_bytes())
    entries: list[Meta4Entry] = []

    for file_elem in root.findall(".//m:file", META_NS):
        name = file_elem.get("name")
        if not name:
            continue
        size_elem = file_elem.find("m:size", META_NS)
        hash_elem = file_elem.find("m:hash[@type='sha-256']", META_NS)
        url_elems = file_elem.findall("m:url", META_NS)

        if size_elem is None or hash_elem is None or not hash_elem.text:
            continue

        urls = [u.text.strip() for u in url_elems if u.text and u.text.strip()]
        if not urls:
            continue

        entries.append(
            {
                "name": name,
                "size": int(size_elem.text),
                "sha256": hash_elem.text.strip().lower(),
                "urls": urls,
            }
        )

    return entries


def filter_entries_by_extension(entries: list[Meta4Entry], accepted_extensions: tuple[str, ...]) -> list[Meta4Entry]:
    return [entry for entry in entries if str(entry["name"]).lower().endswith(accepted_extensions)]


def validate_download(path: Path, expected_size: int, expected_sha256: str) -> bool:
    if not path.exists():
        return False
    if path.stat().st_size != expected_size:
        return False
    return file_sha256(path) == expected_sha256


def download_entry(entry: Meta4Entry, dest_dir: Path, force: bool = False, timeout: int = 120) -> Path:
    name = str(entry["name"])
    expected_size = int(entry["size"])
    expected_sha256 = str(entry["sha256"])
    urls = list(entry["urls"])  # type: ignore[arg-type]

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name

    if dest.exists() and not force and validate_download(dest, expected_size, expected_sha256):
        print(f"[skip] {name} already valid")
        return dest

    for url in urls:
        print(f"[download] {name} <- {url}")
        try:
            with requests.get(url, stream=True, timeout=timeout) as response:
                response.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                with tmp.open("wb") as fh:
                    for chunk in response.iter_content(chunk_size=1 << 20):
                        if chunk:
                            fh.write(chunk)
                tmp.rename(dest)
            if validate_download(dest, expected_size, expected_sha256):
                print(f"  -> ok ({dest.stat().st_size / 1e6:.1f} MB)")
                return dest
            print(f"  !! validation failed for {name} from {url}", file=sys.stderr)
        except requests.RequestException as exc:
            print(f"  !! failed {url}: {exc}", file=sys.stderr)

    raise RuntimeError(f"Failed to download valid file for {name}")


def download_entries(entries: list[Meta4Entry], dest_dir: Path, force: bool = False, timeout: int = 120) -> list[Path]:
    downloaded: list[Path] = []
    for entry in entries:
        downloaded.append(download_entry(entry, dest_dir=dest_dir, force=force, timeout=timeout))
    return downloaded
