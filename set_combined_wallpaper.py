#!/usr/bin/env python3
"""
Pick two random wallpapers, combine them for a multi-monitor setup, and apply.

One image fills the center monitor; the other fills both side monitors.
By default uses date-seeded selection (stable all day, changes daily).

Usage:
  python set_combined_wallpaper.py                 # today's pick
  python set_combined_wallpaper.py --random        # new random each run
  python set_combined_wallpaper.py --month 202602  # restrict to one month
  python set_combined_wallpaper.py --dry-run       # show picks, no compositing or applying
"""

import argparse
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

DEFAULT_INPUT = Path("./bing_wallpapers/high")
DEFAULT_OUTPUT = Path("./combined_wallpaper.png")


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
        description="Combine two Bing wallpapers for a multi-monitor setup and apply"
    )
    parser.add_argument(
        "--input", default=str(DEFAULT_INPUT),
        help="Directory to pick from (default: ./bing_wallpapers/high)",
    )
    parser.add_argument(
        "--output", default=str(DEFAULT_OUTPUT),
        help="Output path for combined image (default: ./combined_wallpaper.png)",
    )
    parser.add_argument(
        "--month", metavar="YYYYMM",
        help="Restrict to images from this month (e.g. 202602)",
    )
    parser.add_argument(
        "--random", dest="truly_random", action="store_true",
        help="Pick new random images each run (default: date-seeded, stable all day)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show which images would be picked without compositing or applying",
    )
    args = parser.parse_args()

    catalog = Path(args.input)
    if not catalog.is_dir():
        print(f"Error: {catalog} is not a directory")
        return 1

    files = sorted(
        f for f in catalog.iterdir()
        if f.is_file() and f.suffix.lower() == ".jpg"
    )
    if args.month:
        files = [f for f in files if f.name.startswith(args.month)]

    if len(files) < 2:
        qualifier = f" for month {args.month}" if args.month else ""
        print(f"Need at least 2 wallpapers{qualifier} in {catalog} (found {len(files)})")
        return 1

    if args.truly_random:
        center_img, sides_img = random.sample(files, 2)
    else:
        seed = int(date.today().strftime("%Y%m%d"))
        center_img, sides_img = random.Random(seed).sample(files, 2)

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
