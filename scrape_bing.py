#!/usr/bin/env python3
"""
Bing Wallpaper Archive Scraper
Scrapes wallpapers from https://bingwallpaper.anerg.com/ (archive going back to 2009).

Strategy:
  1. Iterate over monthly archive pages (/archive/us/YYYYMM)
  2. Extract image IDs from /detail/us/{ImageID} links
  3. Try direct CDN download first (img.nanxiongnandi.com/{YYYYMM}/{ImageID}.jpg)
  4. Fall back to fetching the detail page for a signed 4K imgproxy URL

Usage:
  python scrape_bing.py                        # download everything
  python scrape_bing.py --start 202501         # from Jan 2025 onward
  python scrape_bing.py --start 202001 --end 202012  # specific range
  python scrape_bing.py --output ~/wallpapers  # custom output dir
  python scrape_bing.py --delay 2.0            # slower, more polite
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://bingwallpaper.anerg.com"
CDN_BASE = "https://img.nanxiongnandi.com"
DEFAULT_OUTPUT = Path("./bing_wallpapers")
STATE_FILE = Path("./scrape_state.json")

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


# ---------------------------------------------------------------------------
# Month generation
# ---------------------------------------------------------------------------

def generate_months(start: str, end: str) -> list[str]:
    """Return list of YYYYMM strings between start and end (inclusive)."""
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
# Scraping logic
# ---------------------------------------------------------------------------

def get_image_ids(session: requests.Session, yyyymm: str) -> list[str]:
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


def try_direct_cdn(session: requests.Session, yyyymm: str, image_id: str,
                   dest: Path) -> bool:
    url = f"{CDN_BASE}/{yyyymm}/{image_id}.jpg"
    resp = get_with_retry(session, url, stream=True, timeout=120)
    if not resp:
        return False
    # Sanity-check: must look like a JPEG (>50 KB)
    content = b""
    for chunk in resp.iter_content(65536):
        content += chunk
    if len(content) < 50_000 or not content.startswith(b"\xff\xd8"):
        return False
    dest.write_bytes(content)
    return True


def get_4k_url_from_detail(session: requests.Session, image_id: str) -> str | None:
    url = f"{BASE_URL}/detail/us/{image_id}"
    resp = get_with_retry(session, url)
    if not resp:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    # Prefer highest resolution: 4K > 2K > 1920
    for width in ("w:3840", "w:2560", "w:1920"):
        for a in soup.find_all("a", href=re.compile(re.escape(width))):
            return a["href"]
    return None


def download_url(session: requests.Session, url: str, dest: Path) -> bool:
    resp = get_with_retry(session, url, stream=True, timeout=180)
    if not resp:
        return False
    content = b""
    for chunk in resp.iter_content(65536):
        content += chunk
    if len(content) < 50_000:
        return False
    dest.write_bytes(content)
    return True


# ---------------------------------------------------------------------------
# State persistence (so we can resume interrupted runs)
# ---------------------------------------------------------------------------

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"done_months": [], "done_images": [], "failed_images": []}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Download Bing Wallpaper archive from bingwallpaper.anerg.com"
    )
    parser.add_argument(
        "--output", default=str(DEFAULT_OUTPUT),
        help="Directory to save wallpapers (default: ./bing_wallpapers)",
    )
    parser.add_argument(
        "--start", default="200906",
        help="First month to scrape, YYYYMM (default: 200906)",
    )
    parser.add_argument(
        "--end", default=datetime.now().strftime("%Y%m"),
        help="Last month to scrape, YYYYMM (default: current month)",
    )
    parser.add_argument(
        "--delay", type=float, default=1.0,
        help="Seconds to wait between requests (default: 1.0)",
    )
    parser.add_argument(
        "--direct-only", action="store_true",
        help="Only attempt direct CDN download; skip detail-page fallback",
    )
    parser.add_argument(
        "--cdn-first", action="store_true",
        help="Try direct CDN before detail page (faster but lower JPEG quality)",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Ignore saved state and re-check everything",
    )
    parser.add_argument(
        "--reverse", action="store_true",
        help="Process months newest-first (good for grabbing recent 4K images first)",
    )
    args = parser.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    state = {} if args.reset else load_state()
    done_months  = set(state.get("done_months",  []))
    done_images  = set(state.get("done_images",  []))
    failed_images = set(state.get("failed_images", []))

    months = generate_months(args.start, args.end)
    if args.reverse:
        months = list(reversed(months))
    print(f"Planning to scrape {len(months)} months ({args.start}–{args.end})")
    print(f"Output: {out_dir.resolve()}\n")

    session = requests.Session()
    n_dl = n_skip = n_fail = 0

    for mi, yyyymm in enumerate(months, 1):
        prefix = f"[{mi:>3}/{len(months)}] {yyyymm}"

        if yyyymm in done_months:
            print(f"{prefix}  already complete")
            continue

        image_ids = get_image_ids(session, yyyymm)
        time.sleep(args.delay)

        if not image_ids:
            print(f"{prefix}  no images found (month may not exist yet)")
            done_months.add(yyyymm)
            save_state({"done_months": sorted(done_months),
                        "done_images": sorted(done_images),
                        "failed_images": sorted(failed_images)})
            continue

        print(f"{prefix}  {len(image_ids)} images")

        for ii, img_id in enumerate(image_ids, 1):
            key = f"{yyyymm}/{img_id}"
            dest = out_dir / f"{yyyymm}_{img_id}.jpg"
            tag  = f"  [{ii:>2}/{len(image_ids)}] {img_id}"

            # Already on disk?
            if dest.exists() and dest.stat().st_size > 50_000:
                print(f"{tag}  skip (on disk)")
                n_skip += 1
                done_images.add(key)
                continue

            if key in done_images:
                print(f"{tag}  skip (state)")
                n_skip += 1
                continue

            if args.cdn_first or args.direct_only:
                # 1a) CDN-first path (fast, lower quality)
                ok = try_direct_cdn(session, yyyymm, img_id, dest)
                time.sleep(args.delay)
                if not ok and not args.direct_only:
                    dl_url = get_4k_url_from_detail(session, img_id)
                    time.sleep(args.delay)
                    if dl_url:
                        ok = download_url(session, dl_url, dest)
                        time.sleep(args.delay)
            else:
                # 1b) Detail-page first (higher quality via imgproxy q:100)
                dl_url = get_4k_url_from_detail(session, img_id)
                time.sleep(args.delay)
                if dl_url:
                    ok = download_url(session, dl_url, dest)
                    time.sleep(args.delay)
                else:
                    ok = try_direct_cdn(session, yyyymm, img_id, dest)
                    time.sleep(args.delay)

            if ok:
                kb = dest.stat().st_size // 1024
                print(f"{tag}  {kb} KB")
                n_dl += 1
                done_images.add(key)
            else:
                print(f"{tag}  FAILED")
                n_fail += 1
                failed_images.add(key)
                if dest.exists():
                    dest.unlink()

        done_months.add(yyyymm)
        save_state({"done_months": sorted(done_months),
                    "done_images": sorted(done_images),
                    "failed_images": sorted(failed_images)})

    print(f"\nFinished.  Downloaded: {n_dl}  Skipped: {n_skip}  Failed: {n_fail}")
    if failed_images:
        print(f"Failed entries written to {STATE_FILE} under 'failed_images'.")

    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
