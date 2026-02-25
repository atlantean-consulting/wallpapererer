#!/usr/bin/env python3
"""
Build a date catalog for downloaded Bing wallpapers.

The archive page for each month (bingwallpaper.anerg.com/archive/us/YYYYMM)
lists images in reverse-chronological order: position 1 is the most recent
day of the month, position N is day 1.  This script fetches those pages and
writes date ↔ image_id mappings to a CSV.

Output CSV columns:
  date       – YYYY-MM-DD (the calendar date the image was Bing's wallpaper)
  yyyymm     – YYYYMM (month key matching scraper filenames)
  image_id   – image identifier used in URLs and local filenames
  filename   – YYYYMM_ImageID.jpg (the local filename pattern)

Usage:
  python build_date_catalog.py                       # current + previous month
  python build_date_catalog.py --start 202501        # from Jan 2025 onward
  python build_date_catalog.py --start 202601 --end 202602
  python build_date_catalog.py --output my_dates.csv
"""

import argparse
import csv
import re
import sys
import time
from datetime import datetime, date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://bingwallpaper.anerg.com"
DEFAULT_OUTPUT = Path("./image_dates.csv")

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


def get_with_retry(session: requests.Session, url: str) -> requests.Response | None:
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"  [warn] {url} → {exc}")
    return None


def get_image_ids(session: requests.Session, yyyymm: str) -> list[str]:
    """Return image IDs in page order (position 1 first = most recent day)."""
    url = f"{BASE_URL}/archive/us/{yyyymm}"
    resp = get_with_retry(session, url)
    if not resp:
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    seen = set()
    ids = []
    for a in soup.find_all("a", href=re.compile(r"^/detail/us/")):
        img_id = a["href"].rsplit("/", 1)[-1]
        if img_id and img_id not in seen:
            seen.add(img_id)
            ids.append(img_id)
    return ids


def assign_dates(yyyymm: str, image_ids: list[str]) -> list[dict]:
    """
    Map image_ids (in reverse-chron page order) to calendar dates.

    The archive page lists position 1 = most recent day, position N = day 1.
    So day = total_images - position + 1.
    """
    year = int(yyyymm[:4])
    month = int(yyyymm[4:6])
    n = len(image_ids)
    rows = []
    for position, image_id in enumerate(image_ids, 1):
        day = n - position + 1
        d = date(year, month, day)
        rows.append({
            "date": d.isoformat(),
            "yyyymm": yyyymm,
            "image_id": image_id,
            "filename": f"{yyyymm}_{image_id}.jpg",
        })
    return rows


def load_existing(csv_path: Path) -> dict[str, dict]:
    """Return existing rows keyed by (yyyymm, image_id)."""
    if not csv_path.exists():
        return {}
    existing = {}
    with csv_path.open(newline="") as f:
        for row in csv.DictReader(f):
            key = (row["yyyymm"], row["image_id"])
            existing[key] = row
    return existing


def write_csv(csv_path: Path, rows: list[dict]) -> None:
    rows_sorted = sorted(rows, key=lambda r: r["date"])
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "yyyymm", "image_id", "filename"])
        writer.writeheader()
        writer.writerows(rows_sorted)


def main():
    now = datetime.now()
    this_month = now.strftime("%Y%m")
    prev_month_dt = datetime(now.year, now.month, 1)
    if prev_month_dt.month == 1:
        prev_month_dt = prev_month_dt.replace(year=prev_month_dt.year - 1, month=12)
    else:
        prev_month_dt = prev_month_dt.replace(month=prev_month_dt.month - 1)
    prev_month = prev_month_dt.strftime("%Y%m")

    parser = argparse.ArgumentParser(
        description="Build a date ↔ image_id catalog from the Bing wallpaper archive."
    )
    parser.add_argument(
        "--start", default=prev_month,
        help=f"First month to catalog, YYYYMM (default: {prev_month})",
    )
    parser.add_argument(
        "--end", default=this_month,
        help=f"Last month to catalog, YYYYMM (default: {this_month})",
    )
    parser.add_argument(
        "--output", default=str(DEFAULT_OUTPUT),
        help=f"Output CSV path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--delay", type=float, default=1.0,
        help="Seconds between requests (default: 1.0)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-fetch months even if already in the CSV",
    )
    args = parser.parse_args()

    csv_path = Path(args.output)
    months = generate_months(args.start, args.end)

    existing = load_existing(csv_path)
    all_rows = {k: v for k, v in existing.items()}  # start with what we have

    session = requests.Session()

    for yyyymm in months:
        # Check if we already have a complete entry for this month
        month_keys = [k for k in all_rows if k[0] == yyyymm]
        if month_keys and not args.force:
            # For past months (fully in the past), skip. For current month,
            # always re-fetch since new images are added daily.
            now_ym = datetime.now().strftime("%Y%m")
            if yyyymm < now_ym:
                print(f"{yyyymm}  {len(month_keys)} entries already in CSV — skipping")
                continue

        print(f"{yyyymm}  fetching archive page…", end=" ", flush=True)
        image_ids = get_image_ids(session, yyyymm)
        time.sleep(args.delay)

        if not image_ids:
            print("no images found")
            continue

        print(f"{len(image_ids)} images")
        new_rows = assign_dates(yyyymm, image_ids)

        # Remove stale entries for this month and replace with fresh data
        for k in list(all_rows.keys()):
            if k[0] == yyyymm:
                del all_rows[k]
        for row in new_rows:
            all_rows[(row["yyyymm"], row["image_id"])] = row

    write_csv(csv_path, list(all_rows.values()))
    print(f"\nWrote {len(all_rows)} entries to {csv_path}")


if __name__ == "__main__":
    sys.exit(main())
