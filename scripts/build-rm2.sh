#!/bin/bash
set -euo pipefail

PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SDK_ROOT=${RM2_SDK_ROOT:?Set RM2_SDK_ROOT to the installed reMarkable SDK directory}

source "$SDK_ROOT/environment-setup-cortexa7hf-neon-remarkable-linux-gnueabi"
export LC_ALL=C.UTF-8

cmake \
    -S "$PROJECT_ROOT/apps/reader" \
    -B "$PROJECT_ROOT/build/rm2-reader" \
    -DCMAKE_BUILD_TYPE=Release
cmake --build "$PROJECT_ROOT/build/rm2-reader" --parallel
