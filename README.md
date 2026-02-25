# Wallpapererer

Micro$lop's Bing Search is only useful for pornography, but Bing Wallpaper is a real treat. Too bad it's a Bill Gates product!

"But Paul, using the inscrutable power of AI, we can build *our OWN Bing Wallpaper*, with *blackjack* and ~*hookers*~ *sex workers*!"

And that's exactly what I've done! **Wallpapererer** is a collection of Python and shell scripts that emulate the behavior of the Bing Wallpaper™ App (A Micro$lop Joint), by fetching, organizing, and applying them for the Linux Mint Cinnamon desktop. It supports single-monitor and multi-monitor setups, automated daily sync via systemd, and EXIF metadata embedding, so you can pretend to respect copyright.

## Installation

```bash
pip install -r requirements.txt
```

Dependencies: Pillow, requests, beautifulsoup4, piexif.

## Scripts

### `scrape_bing.py` — Download the Bing wallpaper archive

Bulk-downloads the Bing Wallpaper archive from bingwallpaper.anerg.com (2009–present), organized into monthly batches.

```bash
# Download newest images first (recommended — old ones are low-res)
python scrape_bing.py --reverse

# Download a specific range
python scrape_bing.py --start 202001 --end 202601 --reverse

# Key flags
#   --reverse        newest-first
#   --start YYYYMM   first month (default: 200906)
#   --end   YYYYMM   last month  (default: current month)
#   --output DIR     destination directory (default: ./bing_wallpapers)
#   --delay SECS     pause between requests (default: 1.0)
#   --reset          ignore saved progress state
```

Progress is saved to `scrape_state.json`; runs are resumable.

### `scrape_metadata.py` — Embed EXIF metadata into downloaded images

Fetches image titles, descriptions, and photographer credits from the detail pages and embeds them losslessly into the JPEGs via piexif.

```bash
python scrape_metadata.py

# Key flags
#   --input DIR   wallpaper directory (default: ./bing_wallpapers)
#   --delay SECS  pause between requests (default: 1.0)
#   --dry-run     preview without modifying files
#   --force       re-process files that already have EXIF data
#   --reset       ignore saved progress state
```

Embedded fields: `ImageDescription`, `Artist`, `Copyright`, `XPTitle` (image ID), `XPComment` (full caption), `DateTimeOriginal`.

### `sort_by_resolution.py` — Organize by resolution tier

Moves wallpapers into `high/`, `medium/`, and `low/` subfolders:

- `high/` — ≥ 3840 px wide (4K)
- `medium/` — ≥ 1920 px wide (1080p / 2K)
- `low/` — < 1920 px wide

```bash
python sort_by_resolution.py
python sort_by_resolution.py --dry-run   # preview only
```

The full set, as of late February 2026 *e.v.*, weighs about 16.5 GB. Email me if you want a `.torrent`, so we don't all hammer the server.

### `build_date_catalog.py` — Map image IDs to calendar dates

Fetches each month's archive page and writes a `date ↔ image_id` mapping to `image_dates.csv`. The archive lists images in reverse-chronological order (most recent day first), so positions are converted to dates using `day = total_images − position + 1`.

```bash
# Refresh the catalog for the current and previous month (default)
python build_date_catalog.py

# Catalog a specific range
python build_date_catalog.py --start 202501 --end 202602

# Key flags
#   --start YYYYMM   first month (default: previous month)
#   --end   YYYYMM   last month  (default: current month)
#   --output FILE    CSV path (default: ./image_dates.csv)
#   --force          re-fetch months already in the CSV
```

Past months are skipped on re-runs (already complete); the current month is always re-fetched since a new image is added each day. Output columns: `date`, `yyyymm`, `image_id`, `filename`.

### `prepare_sync.py` — Surgical scrape-state management

Reads `image_dates.csv`, checks which image files are actually present on disk, and updates `scrape_state.json` accordingly — marking present images as done and un-marking only the genuinely missing ones. Exits 0 if everything is already present (no scraping needed), or 1 if any images are missing.

The current calendar month is never written into `done_months`, so the scraper always re-checks it tomorrow for the next day's image. Past months where all images are present are marked done so the scraper skips them entirely.

```bash
# Check the default window (previous + current month)
python prepare_sync.py

# Key flags
#   --start YYYYMM      first month to check (default: previous month)
#   --end   YYYYMM      last month to check  (default: current month)
#   --wallpaper-dir DIR directory to search  (default: ./bing_wallpapers)
#   --catalog FILE      CSV to read          (default: ./image_dates.csv)
```

This is called automatically by the sync scripts; you rarely need to invoke it directly.


### `set_wallpaper.py` — Apply a single wallpaper (single-monitor)

Picks an image from `bing_wallpapers/high/` and applies it via `gsettings`. Prints the EXIF caption and photographer credit after applying.

Uses date-based seeding by default (stable all day, rotates at midnight).

```bash
python set_wallpaper.py
python set_wallpaper.py --random          # fresh pick every run
python set_wallpaper.py --month 202602    # restrict to one month
python set_wallpaper.py --dry-run         # show selection without applying
```

### `set_combined_wallpaper.py` — Apply a composited wallpaper (multi-monitor)

Picks two images, composites them via `wallpaper_combiner.py` (one image on the center ultrawide, one on both side monitors), and applies the result with `picture-options: spanned`.

```bash
python set_combined_wallpaper.py
python set_combined_wallpaper.py --random
python set_combined_wallpaper.py --month 202602
python set_combined_wallpaper.py --dry-run      # show selection only, no compositing
```

### `sync_latest.sh` — Daily sync (single-monitor)

Orchestrates the full daily update pipeline:

1. Refresh `image_dates.csv` for the current and previous month (`build_date_catalog.py`)
2. Check which catalog images are missing from disk (`prepare_sync.py`); if none, skip straight to step 4
3. Download only the missing images (`scrape_bing.py`)
4. Embed EXIF metadata into any new files (`scrape_metadata.py`)
5. Move new files into `bing_wallpapers/high/`
6. Apply today's wallpaper via `set_today.py`

```bash
./sync_latest.sh
./sync_latest.sh --no-apply   # sync only, skip wallpaper step
./sync_latest.sh --random     # apply a date-seeded pick from the archive instead of today's image
```

### `sync_latest_multi.sh` — Daily sync (multi-monitor)

Same pipeline as `sync_latest.sh` but calls `set_today_combined.py` at the end instead of `set_today.py`. Use this on a multi-monitor setup.

```bash
./sync_latest_multi.sh
./sync_latest_multi.sh --no-apply
./sync_latest_multi.sh --random
```

### `set_today.py` — Apply today's actual Bing image (single-monitor)

Looks up today's date in `image_dates.csv` and applies that specific image — the one Bing actually featured today. Used by `sync_latest.sh` as the default wallpaper step.

```bash
python set_today.py
python set_today.py --dry-run
```

### `set_today_combined.py` — Apply today's actual Bing image (multi-monitor)

Same idea as `set_today.py` but for a triple-monitor setup: today's image goes on the center ultrawide, and a date-seeded pick from the archive fills the side monitors. Used by `sync_latest_multi.sh` as the default wallpaper step.

```bash
python set_today_combined.py
python set_today_combined.py --random    # random image for the sides
python set_today_combined.py --dry-run
```

### `wallpaper_combiner.py` — Low-level multi-monitor compositor

The multi-monitor compositor `wallpaper_combiner.py` is configured for my home desktop, which is a triple-wide setup (spared no expense), laid out like so:

- Left screen: 1920×1080
- Center screen: 3440×1440 (ultrawide)
- Right screen: 1920×1080

Screens are aligned at the top edge.

The geometry can be easily adjusted by mucking about in the file. You're a smart cookie; I'm sure you'll figure it out.

The script itself stitches images into a single wide canvas. Used internally by `set_combined_wallpaper.py` but can also be called directly.

```bash
# Two images: one for center, one for both sides
./wallpaper_combiner.py -o output.png --center main.jpg --sides side.jpg

# Three images: one per monitor
./wallpaper_combiner.py -o output.png --left left.jpg --center center.jpg --right right.jpg
```

### `fix_wallpaper_resolution.sh` — Fix post-suspend resolution degradation

Fixes an annoying Cinnamon bug where the wallpaper renders at degraded resolution after resuming from suspend. Toggles `picture-options` from `zoom` → `spanned` with a brief pause to force a full redraw. Once I figure out how to fix this permanently, I'll let y'all know, thus rendering this script redundant.

```bash
./fix_wallpaper_resolution.sh
```

## Automation

A systemd user timer runs the daily sync automatically, with `Persistent=true` to catch up if the machine was off at the scheduled time.

**One-time setup:**
```bash
./install_systemd.sh
```

This fills in the project directory in the service template, copies both unit files to `~/.config/systemd/user/`, reloads the daemon, and enables the timer. It prints the expanded service file before activating so you can confirm everything looks right.

If you're on a multi-monitor setup, edit `systemd/wallpapererer-sync.service` to call `sync_latest_multi.sh` instead of `sync_latest.sh` before running the install script.

**Check status:**
```bash
systemctl --user list-timers wallpapererer-sync.timer
journalctl --user -u wallpapererer-sync.service
```

Logs also append to `sync.log` in the project directory.

Enjoy that sweet, sweet visual eye candy!

-- Paul
