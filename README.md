# Wallpapererer

Microslop's Bing Search is only useful for pornography, but Bing Wallpaper is a real treat. Too bad it's a Bill Gates product!

"But Paul, using the inscrutable power of AI, we can build *our OWN Bing Wallpaper*, with *blackjack* and ~*hookers*~ *sex workers*!"

And that's exactly what I've done! **Wallpapererer** is a collection of Python and shell scripts for fetching, organizing, and applying Bing archive wallpapers on the Linux Mint Cinnamon desktop. It supports single-monitor and multi-monitor setups, automated daily sync via systemd, and EXIF metadata embedding, so you can pretend to respect copyright.

## Monitor Configuration

The multi-monitor compositor `wallpaper_combiner.py` is configured for my home desktop, which is a triple-wide setup (spared no expense), laid out like so:

- Left screen: 1920×1080
- Center screen: 3440×1440 (ultrawide)
- Right screen: 1920×1080

Screens are aligned at the top edge.

The geometry can be easily adjusted by mucking about in the file. You're a smart cookie; I'm sure you'll figure it out.

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

The full set, as of late February 2026 *e.v.* weighs about 16.5 GB. Email me if you want the `.torrent`.

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

### `wallpaper_combiner.py` — Low-level multi-monitor compositor

Stitches images into a single wide canvas. Used internally by `set_combined_wallpaper.py` but can also be called directly.

```bash
# Two images: one for center, one for both sides
./wallpaper_combiner.py -o output.png --center main.jpg --sides side.jpg

# Three images: one per monitor
./wallpaper_combiner.py -o output.png --left left.jpg --center center.jpg --right right.jpg
```

### `fix_wallpaper_resolution.sh` — Fix post-suspend resolution degradation

Fixes a Cinnamon bug where the wallpaper renders at degraded resolution after resuming from suspend. Toggles `picture-options` from `zoom` → `spanned` with a brief pause to force a full redraw.

```bash
./fix_wallpaper_resolution.sh
```

### `sync_latest.sh` — Daily sync (single-monitor)

Orchestrates the full daily update pipeline:

1. Download the current and previous month's images (re-checks current month if today's image is missing)
2. Embed EXIF metadata into any new files
3. Move new files into `bing_wallpapers/high/`
4. Apply today's wallpaper via `set_wallpaper.py`

```bash
./sync_latest.sh
./sync_latest.sh --no-apply   # sync only, skip wallpaper step
```

### `sync_latest_multi.sh` — Daily sync (multi-monitor)

Identical to `sync_latest.sh` but calls `set_combined_wallpaper.py` at the end instead of `set_wallpaper.py`. Use this on a multi-monitor setup.

```bash
./sync_latest_multi.sh
./sync_latest_multi.sh --no-apply
```

## Automation

A systemd user timer runs the daily sync automatically, with `Persistent=true` to catch up if the machine was off at the scheduled time. These files are in the `systemd` directory here, but you'll want to move them to `~/.config/systemd/user/`. 

**Unit files:**
- `~/.config/systemd/user/wallpapererer-sync.service`
- `~/.config/systemd/user/wallpapererer-sync.timer`

**One-time setup:**
```bash
systemctl --user daemon-reload
systemctl --user enable --now wallpapererer-sync.timer
```

**Check status:**
```bash
systemctl --user list-timers wallpapererer-sync.timer
journalctl --user -u wallpapererer-sync.service
```

Logs also append to `sync.log` in the project directory.

Enjoy that sweet, sweet visual eye candy!

-- Paul