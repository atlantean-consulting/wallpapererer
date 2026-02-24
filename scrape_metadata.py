#!/usr/bin/env python3
"""
Bing Wallpaper Metadata Scraper
Fetches image descriptions from bingwallpaper.anerg.com detail pages and embeds
them as EXIF metadata into already-downloaded JPEG files.

Uses piexif.insert() to splice EXIF data directly into the JPEG header — no
recompression, no quality loss.

Usage:
  python scrape_metadata.py                        # process all images
  python scrape_metadata.py --input ~/wallpapers   # custom directory
  python scrape_metadata.py --dry-run              # preview without modifying
  python scrape_metadata.py --force                # re-fetch even if EXIF present
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import piexif
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://bingwallpaper.anerg.com"
DEFAULT_INPUT = Path("./bing_wallpapers")
STATE_FILE = Path("./metadata_state.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": BASE_URL + "/",
}

MAX_RETRIES = 3

# Filename pattern: {YYYYMM}_{ImageID}.jpg
FILENAME_RE = re.compile(r"^(\d{6})_(.+)\.jpg$")


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def get_with_retry(session: requests.Session, url: str, **kwargs) -> requests.Response | None:
    kwargs.setdefault("timeout", 30)
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, headers=HEADERS, **kwargs)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"    [warn] {url} → {exc}")
    return None


# ---------------------------------------------------------------------------
# Caption fetching & parsing
# ---------------------------------------------------------------------------

def fetch_caption(session: requests.Session, image_id: str) -> str | None:
    """Fetch the caption text from the detail page for an image."""
    url = f"{BASE_URL}/detail/us/{image_id}"
    resp = get_with_retry(session, url)
    if not resp:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    div = soup.find("div", class_=re.compile(r"\bfw-bold\b.*\bpy-3\b|\bpy-3\b.*\bfw-bold\b"))
    if not div:
        # Fallback: try selecting with CSS-style matching
        for d in soup.find_all("div"):
            classes = d.get("class", [])
            if "fw-bold" in classes and "py-3" in classes:
                div = d
                break
    if not div:
        return None
    return div.get_text(strip=True) or None


def parse_caption(caption: str) -> dict:
    """Parse a caption string into structured components.

    Expected format:
        Description (© Photographer/Company)(Bing United States)

    Returns dict with keys: description, photographer, company, full_caption.
    """
    result = {
        "description": caption,
        "photographer": "",
        "company": "",
        "full_caption": caption,
    }

    # Strip the trailing (Bing United States) suffix
    cleaned = re.sub(r"\(Bing United States\)\s*$", "", caption).rstrip()

    # Split on the copyright marker
    parts = cleaned.split(" (© ", 1)
    if len(parts) == 2:
        result["description"] = parts[0].strip()
        credit = parts[1].rstrip(")")
        if "/" in credit:
            photographer, company = credit.split("/", 1)
            result["photographer"] = photographer.strip()
            result["company"] = company.strip()
        else:
            result["photographer"] = credit.strip()

    return result


# ---------------------------------------------------------------------------
# EXIF embedding
# ---------------------------------------------------------------------------

def build_exif(parsed: dict, image_id: str, yyyymm: str) -> bytes:
    """Build EXIF bytes from parsed caption data."""
    year = yyyymm[:4]
    month = yyyymm[4:6]

    # Start with empty EXIF
    exif_dict = {"0th": {}, "Exif": {}, "1st": {}, "GPS": {}}

    # 0th IFD fields
    exif_dict["0th"][piexif.ImageIFD.ImageDescription] = parsed["description"].encode("utf-8")

    if parsed["photographer"]:
        credit = parsed["photographer"]
        if parsed["company"]:
            credit += "/" + parsed["company"]
        exif_dict["0th"][piexif.ImageIFD.Artist] = credit.encode("utf-8")
        exif_dict["0th"][piexif.ImageIFD.Copyright] = f"© {credit} {year}".encode("utf-8")

    # XPTitle — image ID (UTF-16LE encoded for Windows compatibility)
    exif_dict["0th"][piexif.ImageIFD.XPTitle] = image_id.encode("utf-16le")

    # XPComment — full original caption
    exif_dict["0th"][piexif.ImageIFD.XPComment] = parsed["full_caption"].encode("utf-16le")

    # DateTimeOriginal — derived from filename month
    exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = f"{year}:{month}:01 00:00:00".encode("ascii")

    return piexif.dump(exif_dict)


def has_metadata(filepath: Path) -> bool:
    """Check if a JPEG already has an ImageDescription in its EXIF."""
    try:
        exif = piexif.load(str(filepath))
        desc = exif.get("0th", {}).get(piexif.ImageIFD.ImageDescription, b"")
        return bool(desc)
    except Exception:
        return False


def embed_exif(filepath: Path, exif_bytes: bytes) -> bool:
    """Insert EXIF bytes into JPEG file (lossless)."""
    try:
        piexif.insert(exif_bytes, str(filepath))
        return True
    except Exception as exc:
        print(f"    [warn] EXIF insert failed for {filepath.name}: {exc}")
        return False


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def load_state(state_file: Path) -> dict:
    if state_file.exists():
        return json.loads(state_file.read_text())
    return {"done": [], "failed": []}


def save_state(state_file: Path, state: dict) -> None:
    state_file.write_text(json.dumps(state, indent=2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Fetch Bing wallpaper metadata and embed into JPEG EXIF"
    )
    parser.add_argument(
        "--input", default=str(DEFAULT_INPUT),
        help="Directory containing wallpapers (default: ./bing_wallpapers)",
    )
    parser.add_argument(
        "--delay", type=float, default=1.0,
        help="Seconds to wait between requests (default: 1.0)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be fetched without modifying files",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Ignore saved state and re-check everything",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-fetch metadata even if EXIF is already present",
    )
    args = parser.parse_args()

    in_dir = Path(args.input)
    if not in_dir.is_dir():
        print(f"Error: {in_dir} is not a directory")
        return 1

    # Discover image files
    images = sorted(
        f for f in in_dir.glob("*.jpg")
        if FILENAME_RE.match(f.name)
    )
    if not images:
        print(f"No matching wallpaper files found in {in_dir}")
        return 0

    # Load state
    state = {} if args.reset else load_state(STATE_FILE)
    done = set(state.get("done", []))
    failed = set(state.get("failed", []))

    # Filter to images needing work
    to_process = []
    for filepath in images:
        key = filepath.name
        if key in done and not args.force:
            continue
        if not args.force and has_metadata(filepath):
            done.add(key)
            continue
        to_process.append(filepath)

    print(f"Found {len(images)} wallpapers, {len(to_process)} need metadata")
    if args.dry_run:
        for f in to_process:
            m = FILENAME_RE.match(f.name)
            print(f"  would fetch: {m.group(2)} ({m.group(1)})")
        return 0

    if not to_process:
        print("Nothing to do.")
        return 0

    session = requests.Session()
    n_ok = n_skip = n_fail = 0

    for i, filepath in enumerate(to_process, 1):
        m = FILENAME_RE.match(filepath.name)
        yyyymm = m.group(1)
        image_id = m.group(2)
        tag = f"[{i:>4}/{len(to_process)}] {image_id}"

        caption = fetch_caption(session, image_id)
        time.sleep(args.delay)

        if not caption:
            print(f"{tag}  no caption found")
            n_fail += 1
            failed.add(filepath.name)
            continue

        parsed = parse_caption(caption)
        exif_bytes = build_exif(parsed, image_id, yyyymm)

        if embed_exif(filepath, exif_bytes):
            desc_preview = parsed["description"][:60]
            if len(parsed["description"]) > 60:
                desc_preview += "..."
            print(f"{tag}  {desc_preview}")
            n_ok += 1
            done.add(filepath.name)
            failed.discard(filepath.name)
        else:
            n_fail += 1
            failed.add(filepath.name)

        # Save state periodically (every 50 images)
        if i % 50 == 0:
            save_state(STATE_FILE, {"done": sorted(done), "failed": sorted(failed)})

    save_state(STATE_FILE, {"done": sorted(done), "failed": sorted(failed)})
    print(f"\nFinished.  Updated: {n_ok}  Failed: {n_fail}")
    if failed:
        print(f"Failed entries written to {STATE_FILE} under 'failed'.")

    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
