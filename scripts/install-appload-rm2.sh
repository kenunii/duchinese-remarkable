#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
device=root@10.11.99.1
device_set=false
with_session=false
with_mobile_session=false
for argument in "$@"; do
    case "$argument" in
        --with-session) with_session=true ;;
        --with-mobile-session) with_mobile_session=true ;;
        -*) echo "Unknown option: $argument" >&2; exit 2 ;;
        *)
            if $device_set; then
                echo "Usage: $0 [device] [--with-session] [--with-mobile-session]" >&2
                exit 2
            fi
            device=$argument
            device_set=true
            ;;
    esac
done
remote_dir=/home/root/xovi/exthome/appload/duchinese
session_file=${DUCHINESE_SESSION_FILE:-$HOME/.config/duchinese-remarkable/session.json}
mobile_session_file=${DUCHINESE_MOBILE_SESSION_FILE:-$HOME/.config/duchinese-remarkable/mobile-session.json}

"$project_root/scripts/build-appload-native.sh"

ssh "$device" "mkdir -p '$remote_dir/backend'"
scp "$project_root/build/appload-native/manifest.json" "$device:$remote_dir/manifest.json.new"
scp "$project_root/build/appload-native/icon.png" "$device:$remote_dir/icon.png.new"
scp "$project_root/build/appload-native/resources.rcc" "$device:$remote_dir/resources.rcc.new"
scp "$project_root/build/appload-native/backend/entry" "$device:$remote_dir/backend/entry.new"
ssh "$device" "chmod 755 '$remote_dir/backend/entry.new' && \
    mv '$remote_dir/manifest.json.new' '$remote_dir/manifest.json' && \
    mv '$remote_dir/icon.png.new' '$remote_dir/icon.png' && \
    mv '$remote_dir/resources.rcc.new' '$remote_dir/resources.rcc' && \
    mv '$remote_dir/backend/entry.new' '$remote_dir/backend/entry'"
if $with_session && [[ -f "$session_file" ]]; then
    ssh "$device" "mkdir -p /home/root/.config/duchinese-remarkable && chmod 700 /home/root/.config/duchinese-remarkable"
    scp "$session_file" "$device:/home/root/.config/duchinese-remarkable/session.json"
    ssh "$device" "chmod 600 /home/root/.config/duchinese-remarkable/session.json"
elif $with_session; then
    echo "Session requested but not found: $session_file" >&2
    exit 1
fi
if $with_mobile_session && [[ -f "$mobile_session_file" ]]; then
    ssh "$device" "mkdir -p /home/root/.config/duchinese-remarkable && chmod 700 /home/root/.config/duchinese-remarkable"
    scp "$mobile_session_file" "$device:/home/root/.config/duchinese-remarkable/mobile-session.json"
    ssh "$device" "chmod 600 /home/root/.config/duchinese-remarkable/mobile-session.json"
elif $with_mobile_session; then
    echo "Mobile session requested but not found: $mobile_session_file" >&2
    exit 1
fi
ssh "$device" '
backend_pid=$(ps w | awk '\''/backend\/entry \/tmp\/duchinese-remarkable\.sock/ && !/awk/ { print $1; exit }'\'')
if [ -n "$backend_pid" ]; then
    kill "$backend_pid"
fi
if [ "$(systemctl is-active xochitl.service)" != active ]; then
    echo "xochitl is not active after deployment" >&2
    exit 1
fi
'

echo "Installed DuChinese for AppLoad on $device; open it once to load the new version"
