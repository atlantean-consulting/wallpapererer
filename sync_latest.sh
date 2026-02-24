#!/usr/bin/env bash
# Daily sync: download new Bing wallpapers, embed metadata, move to high/,
# then apply today's wallpaper of the day.
#
# Usage:
#   ./sync_latest.sh              # sync and apply wallpaper
#   ./sync_latest.sh --no-apply   # sync only, don't change the desktop
set -euo pipefail

APPLY=true
for arg in "$@"; do
    [[ "$arg" == "--no-apply" ]] && APPLY=false
done

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Cover both current and previous month so the 1st-of-month run catches
# any images that dropped on the last day of the previous month.
THIS_MONTH=$(date +%Y%m)
PREV_MONTH=$(date -d "$(date +%Y-%m-01) -1 month" +%Y%m)
TODAY_DAY=$(date +%-d)

echo "[$(date '+%F %T')] Starting wallpaper sync (${PREV_MONTH}–${THIS_MONTH})"

# If we have fewer images for this month than today's day number, the month was
# marked "done" before today's image existed.  Evict it from the state so the
# scraper re-checks the archive page and picks up any new images.
MONTH_COUNT=$(find ./bing_wallpapers/high/ -name "${THIS_MONTH}*" -printf '.' 2>/dev/null | wc -m)
if [ "$MONTH_COUNT" -lt "$TODAY_DAY" ]; then
    echo "[$(date '+%F %T')] ${MONTH_COUNT} image(s) for ${THIS_MONTH}, expected ~${TODAY_DAY} — re-queueing month"
    if [ -f scrape_state.json ]; then
        python3 -c "
import json
path = 'scrape_state.json'
s = json.load(open(path))
s['done_months'] = [m for m in s.get('done_months', []) if m != '${THIS_MONTH}']
json.dump(s, open(path, 'w'), indent=2)
"
    fi
fi

python3 scrape_bing.py --start "$PREV_MONTH" --end "$THIS_MONTH"
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
    python3 set_wallpaper.py
fi

echo "[$(date '+%F %T')] Done"
