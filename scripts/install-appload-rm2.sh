#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
device=${1:-root@10.11.99.1}
remote_dir=/home/root/xovi/exthome/appload/duchinese
session_file=${DUCHINESE_SESSION_FILE:-$HOME/.config/duchinese-remarkable/session.json}

"$project_root/scripts/build-appload-native.sh"

ssh "$device" "mkdir -p '$remote_dir'"
scp "$project_root/build/appload-native/manifest.json" "$device:$remote_dir/manifest.json.new"
scp "$project_root/build/appload-native/resources.rcc" "$device:$remote_dir/resources.rcc.new"
ssh "$device" "mkdir -p '$remote_dir/backend'"
scp "$project_root/build/appload-native/backend/entry" "$device:$remote_dir/backend/entry.new"
ssh "$device" "chmod 755 '$remote_dir/backend/entry.new' && \
    mv '$remote_dir/manifest.json.new' '$remote_dir/manifest.json' && \
    mv '$remote_dir/resources.rcc.new' '$remote_dir/resources.rcc' && \
    mv '$remote_dir/backend/entry.new' '$remote_dir/backend/entry'"
if [[ -f "$session_file" ]]; then
    ssh "$device" "mkdir -p /home/root/.config/duchinese-remarkable && chmod 700 /home/root/.config/duchinese-remarkable"
    scp "$session_file" "$device:/home/root/.config/duchinese-remarkable/session.json"
    ssh "$device" "chmod 600 /home/root/.config/duchinese-remarkable/session.json"
else
    echo "No local DuChinese session found; install will start unauthenticated" >&2
fi
ssh "$device" 'systemctl restart xochitl'

echo "Installed DuChinese for AppLoad on $device"
