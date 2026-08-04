#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source_dir="$project_root/packaging/appload-native"
output_dir="$project_root/build/appload-native"
rcc_bin=${RCC_BIN:-}

if [[ -z "$rcc_bin" ]]; then
    for candidate in "$(command -v rcc 2>/dev/null || true)" \
        "$(command -v rcc6 2>/dev/null || true)" \
        /usr/lib/qt6/rcc; do
        if [[ -n "$candidate" && -x "$candidate" ]]; then
            rcc_bin=$candidate
            break
        fi
    done
fi

if [[ -z "$rcc_bin" ]]; then
    echo "Qt 6 rcc was not found; install Qt 6 or set RCC_BIN explicitly" >&2
    exit 1
fi

mkdir -p "$output_dir"
cp "$source_dir/manifest.json" "$output_dir/manifest.json"
"$rcc_bin" --binary -o "$output_dir/resources.rcc" "$source_dir/application.qrc"

echo "Built native AppLoad package in $output_dir"
