#!/usr/bin/env python3
"""
Apply today's specific Bing wallpaper on a multi-monitor setup.

Looks up today's date in image_dates.csv to find the image Bing featured
today and places it on the center monitor.  A second image (date-seeded by
default, or random with --random) is chosen from the collection for the side
monitors.  The two are composited via wallpaper_combiner.py and applied with
picture-options: spanned.

Usage:
  python set_today_combined.py
  python set_today_combined.py --random     # random image for the sides
  python set_today_combined.py --dry-run
"""

import argparse
import csv
import random
import subprocess
import sys
from datetime import date
from pathlib import Path

try:
    import piexif
    HAS_PIEXIF = True
except ImportError:
    HAS_PIEXIF = False

from wallpaper_combiner import create_two_image_wallpaper

DEFAULT_CATALOG = Path("./image_dates.csv")
DEFAULT_INPUT   = Path("./bing_wallpapers/high")
DEFAULT_OUTPUT  = Path("./combined_wallpaper.png")


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


def print_image_info(label: str, path: Path):
    info = read_exif_info(path)
    print(f"{label}: {path.name}")
    if info.get("caption"):
        print(f"  Caption: {info['caption']}")
    elif info.get("description"):
        print(f"           {info['description']}")
    if info.get("artist"):
        print(f"  Artist:  {info['artist']}")


def lookup_today(catalog_path: Path) -> str | None:
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
    subprocess.run(
        ["gsettings", "set", "org.cinnamon.desktop.background", "picture-options", "spanned"],
        check=True,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Apply today's Bing wallpaper of the day on a multi-monitor setup"
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
        "--output", default=str(DEFAULT_OUTPUT),
        help=f"Output path for combined image (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--random", dest="truly_random", action="store_true",
        help="Pick a new random image for the sides each run (default: date-seeded)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show which images would be picked without compositing or applying",
    )
    args = parser.parse_args()

    catalog_path = Path(args.catalog)
    input_dir    = Path(args.input)

    # Center: today's specific image
    filename = lookup_today(catalog_path)
    if not filename:
        print(f"Error: no catalog entry for today ({date.today().isoformat()})")
        print(f"       Run build_date_catalog.py first, or check {args.catalog}")
        return 1

    center_img = input_dir / filename
    if not center_img.exists():
        print(f"Error: today's image not on disk: {center_img}")
        return 1

    # Sides: pick from the full collection, excluding today's image
    all_files = sorted(
        f for f in input_dir.iterdir()
        if f.is_file() and f.suffix.lower() == ".jpg" and f.name != filename
    )
    if not all_files:
        print(f"Error: no other wallpapers found in {input_dir} for the sides")
        return 1

    if args.truly_random:
        sides_img = random.choice(all_files)
    else:
        seed = int(date.today().strftime("%Y%m%d"))
        sides_img = random.Random(seed).choice(all_files)

    print_image_info("Center", center_img)
    print()
    print_image_info("Sides ", sides_img)

    if args.dry_run:
        print("\n(dry run — not composited or applied)")
        return 0

    output = Path(args.output)
    print(f"\nCompositing → {output}")
    canvas = create_two_image_wallpaper(center_img, sides_img, "center")
    canvas.save(output, quality=95)
    print(f"Saved ({canvas.size[0]}x{canvas.size[1]})")

    apply_wallpaper(output)
    print("Applied (spanned).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
