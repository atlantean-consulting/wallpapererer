# Wallpapererer

Micro$lop's Bing Search is only useful for pornography, but Bing Wallpaper is a real treat. Too bad it's a Bill Gates product!

"But Paul, using the inscrutable power of AI, we can build *our OWN Bing Wallpaper*, with *blackjack* and ~*hookers*~ *sex workers*!"

And that's exactly what I've done! **Wallpapererer** is a collection of Python and shell scripts that emulate the behavior of the Bing Wallpaper™ App (A Micro$lop Joint), by fetching, organizing, and applying them for the Linux Mint Cinnamon desktop. It supports single-monitor and multi-monitor setups, automated daily sync via systemd, and EXIF metadata embedding, so you can pretend to respect copyright.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Download the archive (newest first — old ones are low-res)
python scrape_bing.py --reverse

# Embed EXIF metadata (titles, credits, etc.)
python scrape_metadata.py

# Sort into high/medium/low resolution folders
python sort_by_resolution.py

# Apply a wallpaper
python set_wallpaper.py                    # single monitor
python set_combined_wallpaper.py           # multi-monitor
```

## Daily Automation

Set up a systemd timer and forget about it:

```bash
# Single monitor
./install_systemd.sh

# Multi-monitor: edit systemd/wallpapererer-sync.service to call
# sync_latest_multi.sh instead of sync_latest.sh, then:
./install_systemd.sh
```

The timer syncs daily and catches up if the machine was off. Logs go to `sync.log`.

You can also run the sync manually:

```bash
./sync_latest.sh              # single monitor
./sync_latest_multi.sh        # multi-monitor
```

Both accept `--no-apply` (sync only) and `--random` (random wallpaper instead of today's).

## Script Reference

For detailed flags, usage examples, and internals, see **[MANUAL.md](MANUAL.md)**.

| Script | What it does |
|--------|-------------|
| `scrape_bing.py` | Bulk-download the Bing wallpaper archive (2009–present) |
| `scrape_metadata.py` | Embed EXIF metadata (titles, credits) into downloaded JPEGs |
| `sort_by_resolution.py` | Sort wallpapers into `high/`, `medium/`, `low/` folders |
| `build_date_catalog.py` | Map image IDs to calendar dates (`image_dates.csv`) |
| `prepare_sync.py` | Surgical scrape-state management for incremental syncs |
| `set_wallpaper.py` | Apply a wallpaper (single monitor) |
| `set_combined_wallpaper.py` | Composite and apply a wallpaper (multi-monitor) |
| `set_today.py` | Apply today's actual Bing image (single monitor) |
| `set_today_combined.py` | Apply today's actual Bing image (multi-monitor) |
| `wallpaper_combiner.py` | Low-level multi-monitor image compositor |
| `sync_latest.sh` | Full daily sync pipeline (single monitor) |
| `sync_latest_multi.sh` | Full daily sync pipeline (multi-monitor) |
| `fix_wallpaper_resolution.sh` | Fix post-suspend wallpaper resolution bug (Cinnamon) |
| `install_systemd.sh` | Install and enable the systemd timer |

The full set, as of late February 2026 *e.v.*, weighs about 16.5 GB. Email me if you want a `.torrent`, so we don't all hammer the server.

-- Paul
