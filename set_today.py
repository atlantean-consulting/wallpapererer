#!/usr/bin/env python3
"""
Apply today's specific Bing wallpaper (single-monitor).

Looks up today's date in image_dates.csv to find the image Bing featured
today, then applies it via gsettings.  Unlike set_wallpaper.py, which picks
a date-seeded random image from the entire collection, this always applies
the actual wallpaper of the day.

Usage:
  python set_today.py
  python set_today.py --dry-run
  python set_today.py --catalog ./image_dates.csv --input ./bing_wallpapers/high
"""

import argparse
import csv
import subprocess
import sys
from datetime import date
from pathlib import Path

try:
    import piexif
    HAS_PIEXIF = True
except ImportError:
    HAS_PIEXIF = False

DEFAULT_CATALOG = Path("./image_dates.csv")
DEFAULT_INPUT   = Path("./bing_wallpapers/high")


def xp_decode(raw) -> str:
    if isinstance(raw, (list, tuple)):
        raw = bytes(raw)
    return raw.decode("utf-16-le").rstrip("\x00")


def read_exif_info(filepath: Path) -> dict:
    if not HAS_PIEXIF:
        return {}
    try:
        ifd = piexif.load(str(filepath)).get("0th", {})
        info = {}
        raw = ifd.get(piexif.ImageIFD.XPComment)
        if raw:
            info["caption"] = xp_decode(raw)
        raw = ifd.get(piexif.ImageIFD.ImageDescription)
        if raw:
            info["description"] = raw.decode("utf-8", errors="replace").rstrip("\x00")
        raw = ifd.get(piexif.ImageIFD.Artist)
        if raw:
            info["artist"] = raw.decode("utf-8", errors="replace").rstrip("\x00")
        return info
    except Exception:
        return {}


def lookup_today(catalog_path: Path) -> str | None:
    """Return the filename for today's image, or None if not found."""
    today = date.today().isoformat()
    if not catalog_path.exists():
        return None
    with catalog_path.open(newline="") as f:
        for row in csv.DictReader(f):
            if row["date"] == today:
                return row["filename"]
    return None


def apply_wallpaper(filepath: Path):
    uri = filepath.resolve().as_uri()
    subprocess.run(
        ["gsettings", "set", "org.cinnamon.desktop.background", "picture-uri", uri],
        check=True,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Apply today's Bing wallpaper of the day (single-monitor)"
    )
    parser.add_argument(
        "--catalog", default=str(DEFAULT_CATALOG),
        help=f"Date catalog CSV (default: {DEFAULT_CATALOG})",
    )
    parser.add_argument(
        "--input", default=str(DEFAULT_INPUT),
        help=f"Directory containing wallpapers (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show which image would be applied without applying it",
    )
    args = parser.parse_args()

    filename = lookup_today(Path(args.catalog))
    if not filename:
        print(f"Error: no catalog entry for today ({date.today().isoformat()})")
        print(f"       Run build_date_catalog.py first, or check {args.catalog}")
        return 1

    chosen = Path(args.input) / filename
    if not chosen.exists():
        print(f"Error: today's image not on disk: {chosen}")
        return 1

    info = read_exif_info(chosen)
    print(f"Wallpaper: {chosen.name}")
    if info.get("caption"):
        print(f"Caption:   {info['caption']}")
    elif info.get("description"):
        print(f"           {info['description']}")
    if info.get("artist"):
        print(f"Artist:    {info['artist']}")

    if args.dry_run:
        print("(dry run — not applied)")
        return 0

    apply_wallpaper(chosen)
    print("Applied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
