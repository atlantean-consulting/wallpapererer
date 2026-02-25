#!/usr/bin/env python3
"""
Prepare scrape_state.json for a targeted, surgical sync.

Reads image_dates.csv to know which images should exist for a given month
window, then checks the local wallpaper directory to see which are actually
present.  Updates scrape_state.json so that:

  - Images already on disk are marked in done_images (scraper will skip them)
  - Images missing from disk are removed from done_images and failed_images
    (scraper will download them)
  - Months where every known image is present are added to done_months
    (scraper skips the whole month)
  - The current calendar month is NEVER added to done_months (tomorrow has a
    new image)
  - Months with any missing image are removed from done_months so the scraper
    re-checks the archive page

This replaces the coarse "evict entire month" heuristic with per-image
precision, preventing unnecessary traffic.

Exit codes:
  0 — nothing to download
  1 — one or more images are missing (scraper should be run next)
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

STATE_FILE = Path("./scrape_state.json")
CATALOG_FILE = Path("./image_dates.csv")
DEFAULT_WALLPAPER_DIR = Path("./bing_wallpapers")
MIN_FILE_SIZE = 50_000  # bytes — anything smaller isn't a real image


def generate_months(start: str, end: str) -> list[str]:
    def parse(s):
        return datetime(int(s[:4]), int(s[4:6]), 1)

    cur = parse(start)
    stop = parse(end)
    months = []
    while cur <= stop:
        months.append(cur.strftime("%Y%m"))
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)
    return months


def load_catalog(csv_path: Path, months: set[str]) -> list[dict]:
    if not csv_path.exists():
        return []
    with csv_path.open(newline="") as f:
        return [row for row in csv.DictReader(f) if row["yyyymm"] in months]


def image_is_present(wallpaper_dir: Path, filename: str) -> bool:
    """Check high/ (permanent home) and root (freshly downloaded, not yet moved)."""
    for candidate in (wallpaper_dir / "high" / filename, wallpaper_dir / filename):
        if candidate.exists() and candidate.stat().st_size >= MIN_FILE_SIZE:
            return True
    return False


def main():
    now = datetime.now()
    this_month = now.strftime("%Y%m")
    prev_dt = datetime(now.year, now.month, 1)
    if prev_dt.month == 1:
        prev_dt = prev_dt.replace(year=prev_dt.year - 1, month=12)
    else:
        prev_dt = prev_dt.replace(month=prev_dt.month - 1)
    prev_month = prev_dt.strftime("%Y%m")

    parser = argparse.ArgumentParser(
        description="Surgically update scrape_state.json based on which catalog images are missing."
    )
    parser.add_argument("--start", default=prev_month,
                        help=f"First month to check (default: {prev_month})")
    parser.add_argument("--end", default=this_month,
                        help=f"Last month to check (default: {this_month})")
    parser.add_argument("--wallpaper-dir", default=str(DEFAULT_WALLPAPER_DIR),
                        help=f"Wallpaper directory (default: {DEFAULT_WALLPAPER_DIR})")
    parser.add_argument("--catalog", default=str(CATALOG_FILE),
                        help=f"Date catalog CSV (default: {CATALOG_FILE})")
    args = parser.parse_args()

    months_in_scope = set(generate_months(args.start, args.end))
    wallpaper_dir = Path(args.wallpaper_dir)

    catalog_rows = load_catalog(Path(args.catalog), months_in_scope)
    months_with_catalog = {r["yyyymm"] for r in catalog_rows}

    # Tally present vs missing per image
    present = []   # (yyyymm, image_id)
    missing = []   # (yyyymm, image_id)
    for row in catalog_rows:
        if image_is_present(wallpaper_dir, row["filename"]):
            present.append((row["yyyymm"], row["image_id"]))
        else:
            missing.append((row["yyyymm"], row["image_id"]))

    months_with_missing = {yyyymm for yyyymm, _ in missing}

    # Load scrape state (or start fresh)
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())
    else:
        state = {"done_months": [], "done_images": [], "failed_images": []}

    done_months   = set(state.get("done_months",   []))
    done_images   = set(state.get("done_images",   []))
    failed_images = set(state.get("failed_images", []))

    # Mark images we have as done
    for yyyymm, image_id in present:
        done_images.add(f"{yyyymm}/{image_id}")

    # Un-mark missing images so the scraper will fetch them
    for yyyymm, image_id in missing:
        key = f"{yyyymm}/{image_id}"
        done_images.discard(key)
        failed_images.discard(key)

    # Update done_months:
    #   - months with missing images → remove (scraper must re-visit)
    #   - months fully present AND not the current month → add
    #   - current month → never add (new image arrives tomorrow)
    for yyyymm in months_with_missing:
        done_months.discard(yyyymm)

    for yyyymm in months_with_catalog - months_with_missing:
        if yyyymm != this_month:
            done_months.add(yyyymm)

    # Current month must never be in done_months — a new image will arrive tomorrow
    done_months.discard(this_month)

    state["done_months"]   = sorted(done_months)
    state["done_images"]   = sorted(done_images)
    state["failed_images"] = sorted(failed_images)
    STATE_FILE.write_text(json.dumps(state, indent=2))

    # Report
    if missing:
        by_month: dict[str, list[str]] = {}
        for yyyymm, image_id in sorted(missing):
            by_month.setdefault(yyyymm, []).append(image_id)
        for yyyymm, ids in sorted(by_month.items()):
            print(f"[prepare_sync] {yyyymm}: {len(ids)} missing — {', '.join(ids)}")
        return 1  # signal to caller that the scraper should run
    else:
        count = len(present)
        print(f"[prepare_sync] All {count} catalog image(s) already present — skipping scraper")
        return 0


if __name__ == "__main__":
    sys.exit(main())
