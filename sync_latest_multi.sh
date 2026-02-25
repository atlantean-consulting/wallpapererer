#!/usr/bin/env bash
# Daily sync: download new Bing wallpapers, embed metadata, move to high/,
# then composite and apply a two-image multi-monitor wallpaper of the day.
#
# Usage:
#   ./sync_latest_multi.sh              # sync and apply combined wallpaper
#   ./sync_latest_multi.sh --no-apply   # sync only, don't change the desktop
set -euo pipefail

APPLY=true
RANDOM_PICK=false
for arg in "$@"; do
    [[ "$arg" == "--no-apply" ]] && APPLY=false
    [[ "$arg" == "--random"   ]] && RANDOM_PICK=true
done

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Cover both current and previous month so the 1st-of-month run catches
# any images that dropped on the last day of the previous month.
THIS_MONTH=$(date +%Y%m)
PREV_MONTH=$(date -d "$(date +%Y-%m-01) -1 month" +%Y%m)

echo "[$(date '+%F %T')] Starting wallpaper sync (${PREV_MONTH}–${THIS_MONTH})"

# Refresh the date catalog for the months we care about, then surgically update
# scrape_state.json so the scraper only downloads genuinely missing images.
python3 build_date_catalog.py --start "$PREV_MONTH" --end "$THIS_MONTH"
if python3 prepare_sync.py --start "$PREV_MONTH" --end "$THIS_MONTH"; then
    echo "[$(date '+%F %T')] All images already present — skipping scraper"
else
    python3 scrape_bing.py --start "$PREV_MONTH" --end "$THIS_MONTH"
fi
python3 scrape_metadata.py

# Move any newly downloaded root-level files to high/.
# (New Bing images are always 4K; sort_by_resolution.py would agree.)
shopt -s nullglob
new_files=(bing_wallpapers/*.jpg)
if (( ${#new_files[@]} > 0 )); then
    mv "${new_files[@]}" bing_wallpapers/high/
    echo "Moved ${#new_files[@]} new file(s) to high/"
else
    echo "No new files to move."
fi

if $APPLY; then
    if $RANDOM_PICK; then
        python3 set_combined_wallpaper.py
    else
        python3 set_today_combined.py
    fi
fi

echo "[$(date '+%F %T')] Done"
