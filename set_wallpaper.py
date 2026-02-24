#!/usr/bin/env python3
"""
Pick a wallpaper from the high-res catalog and apply it in Cinnamon.

By default uses a date-seeded random choice (stable all day, changes daily).
Use --random for a fresh pick each time.

Usage:
  python set_wallpaper.py                       # today's pick from high/
  python set_wallpaper.py --random              # new random each run
  python set_wallpaper.py --month 202602        # restrict to one month
  python set_wallpaper.py --input ~/wallpapers  # custom catalog directory
  python set_wallpaper.py --dry-run             # show pick without applying
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

DEFAULT_INPUT = Path("./bing_wallpapers/high")


def xp_decode(raw) -> str:
    """Decode Windows XP-style UTF-16LE EXIF value (bytes or tuple of ints)."""
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


def apply_wallpaper(filepath: Path):
    uri = filepath.resolve().as_uri()
    subprocess.run(
        ["gsettings", "set", "org.cinnamon.desktop.background", "picture-uri", uri],
        check=True,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Set a random Bing wallpaper from the high-res catalog"
    )
    parser.add_argument(
        "--input", default=str(DEFAULT_INPUT),
        help="Directory to pick from (default: ./bing_wallpapers/high)",
    )
    parser.add_argument(
        "--month", metavar="YYYYMM",
        help="Restrict to images from this month (e.g. 202602)",
    )
    parser.add_argument(
        "--random", dest="truly_random", action="store_true",
        help="Pick a new random image each run (default: date-seeded, stable all day)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show which image would be selected without applying it",
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

    if not files:
        qualifier = f" for month {args.month}" if args.month else ""
        print(f"No wallpapers found{qualifier} in {catalog}")
        return 1

    if args.truly_random:
        chosen = random.choice(files)
    else:
        seed = int(date.today().strftime("%Y%m%d"))
        chosen = random.Random(seed).choice(files)

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
