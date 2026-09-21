#!/usr/bin/env bash
set -euo pipefail
project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
"$project_root/scripts/deploy-appload.sh" "$project_root/build/pdf-test-app" "${1:-rm2}" duchinese-pdf-test
