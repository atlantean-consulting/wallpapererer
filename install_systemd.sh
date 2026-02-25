#!/usr/bin/env bash
# Install and enable the wallpapererer systemd user timer.
#
# Fills in the project directory in the service template, copies both unit
# files to ~/.config/systemd/user/, reloads the daemon, and enables the timer.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_DIR="$HOME/.config/systemd/user"
SERVICE_SRC="$DIR/systemd/wallpapererer-sync.service"
TIMER_SRC="$DIR/systemd/wallpapererer-sync.timer"
SERVICE_DEST="$UNIT_DIR/wallpapererer-sync.service"
TIMER_DEST="$UNIT_DIR/wallpapererer-sync.timer"

mkdir -p "$UNIT_DIR"

# Expand [CWD] placeholder with the actual project directory
sed "s|\[CWD\]|$DIR|g; s|\[EDIT THIS!!!\]|$DIR|g" "$SERVICE_SRC" > "$SERVICE_DEST"

cp "$TIMER_SRC" "$TIMER_DEST"

echo "Installed:"
echo "  $SERVICE_DEST"
echo "  $TIMER_DEST"
echo ""
cat "$SERVICE_DEST"
echo ""

systemctl --user daemon-reload
systemctl --user enable --now wallpapererer-sync.timer

echo ""
echo "Timer enabled. Next run:"
systemctl --user list-timers wallpapererer-sync.timer --no-pager
