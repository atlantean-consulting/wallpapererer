#!/usr/bin/env python3
"""
Sort wallpapers into resolution-based subfolders.

Tiers (by image width):
  high    >= 3840 px  (4K)
  medium  >= 1920 px  (1080p / 2K)
  low      < 1920 px  (older low-res images)

Only files directly in the target directory are moved; files already in a
subfolder are untouched, so the script is safe to re-run.

Usage:
  python sort_by_resolution.py                      # sort ./bing_wallpapers
  python sort_by_resolution.py --input ~/wallpapers # custom directory
  python sort_by_resolution.py --dry-run            # preview without moving
"""

import argparse
import sys
from pathlib import Path

from PIL import Image

DEFAULT_INPUT = Path("./bing_wallpapers")

TIERS = [
    ("high",   3840),
    ("medium", 1920),
    ("low",       0),
]


def classify(width: int) -> str:
    for name, threshold in TIERS:
        if width >= threshold:
            return name
    return "low"


def main():
    parser = argparse.ArgumentParser(
        description="Sort wallpapers into high / medium / low resolution subfolders"
    )
    parser.add_argument(
        "--input", default=str(DEFAULT_INPUT),
        help="Directory containing wallpapers (default: ./bing_wallpapers)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be moved without modifying anything",
    )
    args = parser.parse_args()

    in_dir = Path(args.input)
    if not in_dir.is_dir():
        print(f"Error: {in_dir} is not a directory")
        return 1

    # Only jpg files directly in in_dir (not in subfolders)
    files = sorted(f for f in in_dir.iterdir() if f.is_file() and f.suffix.lower() == ".jpg")
    if not files:
        print("Nothing to do.")
        return 0

    # Create destination dirs up front (unless dry-run)
    tier_names = [t[0] for t in TIERS]
    if not args.dry_run:
        for name in tier_names:
            (in_dir / name).mkdir(exist_ok=True)

    counts = {name: 0 for name in tier_names}
    errors = 0

    for filepath in files:
        try:
            with Image.open(filepath) as img:
                width, height = img.size
        except Exception as exc:
            print(f"  [warn] {filepath.name}: cannot read ({exc})")
            errors += 1
            continue

        tier = classify(width)
        dest = in_dir / tier / filepath.name

        if args.dry_run:
            print(f"  {filepath.name}  {width}×{height}  → {tier}/")
        else:
            filepath.rename(dest)

        counts[tier] += 1

    total = sum(counts.values())
    action = "would move" if args.dry_run else "moved"
    print(f"\n{action} {total} files  (errors: {errors})")
    for name in tier_names:
        if counts[name]:
            print(f"  {name:8s} {counts[name]}")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
