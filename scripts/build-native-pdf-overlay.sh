#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source_dir="$project_root/packaging/native-pdf-overlay"
output_dir="$project_root/build/native-pdf-overlay"
if [[ $# -lt 3 || $# -ne $((3 * ($# / 3))) ]]; then
    echo "Usage: $0 PREPARED_COLLECTION SOURCE_PDF TABLET_DOCUMENT_UUID [PREPARED_COLLECTION SOURCE_PDF TABLET_DOCUMENT_UUID ...]" >&2
    exit 2
fi
rcc_bin=${RCC_BIN:-/usr/lib/qt6/rcc}

mkdir -p "$output_dir"
python3 "$project_root/scripts/build-native-pdf-overlay.py" "$output_dir" "$@"
cp "$source_dir/LookupOverlay.qml" "$output_dir/LookupOverlay.qml"
cp "$source_dir/SentencePopup.qml" "$output_dir/SentencePopup.qml"
cp "$project_root/packaging/shared/WordPopup.qml" "$output_dir/WordPopup.qml"
cp "$project_root/assets/fonts/NotoSansSC.ttf" "$output_dir/NotoSansSC.ttf"
python3 - "$source_dir/document-overlay.qmd.in" "$output_dir/document-overlay.qmd" "$output_dir/LookupData.js" <<'PY'
import json
from pathlib import Path
import re
import sys
template, output, lookup_data = map(Path, sys.argv[1:])
match = re.search(r'^var documents = (.*);$', lookup_data.read_text(), re.MULTILINE)
if not match:
    raise SystemExit('Generated lookup data is missing its document map')
document_ids = list(json.loads(match.group(1)))
output.write_text(template.read_text().replace('@PDF_DOCUMENT_IDS@', json.dumps(document_ids)))
PY
cat > "$output_dir/application.qrc" <<'QRC'
<RCC><qresource prefix="/duchinese-pdf-overlay">
<file>LookupOverlay.qml</file>
<file>SentencePopup.qml</file>
<file>LookupData.js</file>
<file>WordPopup.qml</file>
<file>NotoSansSC.ttf</file>
</qresource></RCC>
QRC
"$rcc_bin" --binary -o "$output_dir/duchinese-pdf-overlay.rcc" "$output_dir/application.qrc"
echo "Built native PDF overlay in $output_dir"
