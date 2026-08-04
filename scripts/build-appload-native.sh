#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source_dir="$project_root/packaging/appload-native"
output_dir="$project_root/build/appload-native"
rcc_bin=${RCC_BIN:-$(command -v rcc || true)}

if [[ -z "$rcc_bin" ]]; then
    echo "rcc was not found; set RCC_BIN to the Qt resource compiler" >&2
    exit 1
fi

mkdir -p "$output_dir"
cp "$source_dir/manifest.json" "$output_dir/manifest.json"
"$rcc_bin" --binary -o "$output_dir/resources.rcc" "$source_dir/application.qrc"

echo "Built native AppLoad package in $output_dir"
