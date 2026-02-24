#!/usr/bin/env bash
# Fix the post-suspend wallpaper resolution bug on multi-monitor Cinnamon setups.
# Toggles picture-options zoom → spanned to force a redraw at full resolution.
set -euo pipefail

gsettings set org.cinnamon.desktop.background picture-options zoom
sleep 2
gsettings set org.cinnamon.desktop.background picture-options spanned
