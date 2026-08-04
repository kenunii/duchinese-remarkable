#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
device=${1:-root@10.11.99.1}
remote_dir=/home/root/xovi/exthome/appload/duchinese

"$project_root/scripts/build-appload-native.sh"

ssh "$device" "mkdir -p '$remote_dir'"
scp \
    "$project_root/build/appload-native/manifest.json" \
    "$project_root/build/appload-native/resources.rcc" \
    "$device:$remote_dir/"
ssh "$device" 'systemctl restart xochitl'

echo "Installed DuChinese for AppLoad on $device"
