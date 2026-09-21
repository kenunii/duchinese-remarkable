#!/usr/bin/env bash
set -euo pipefail
project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
book_dir=${1:?Usage: build-pdf-test.sh PREPARED_BOOK_DIR}
book_dir=$(realpath "$book_dir")
output_dir="$project_root/build/pdf-test-app"
mkdir -p "$output_dir/ui"
cp "$project_root/packaging/pdf-test/manifest.json" "$output_dir/manifest.json"
cp "$project_root/packaging/appload-native/icon.png" "$output_dir/icon.png"
cp "$project_root/packaging/pdf-test/ui/"*.qml "$output_dir/ui/"
cp "$project_root/packaging/shared/"*.qml "$output_dir/ui/"
# Remove only generated page rasters from the previous build.
rm -f "$output_dir/ui/"page*.png
if [[ -f "$book_dir/manifest.json" ]]; then
    python3 "$project_root/scripts/prepare-pdf-collection.py" "$book_dir" "$output_dir/ui"
else
    cp "$book_dir/Book.js" "$book_dir/page.png" "$output_dir/ui/"
fi
cp "$project_root/assets/fonts/NotoSansSC.ttf" "$output_dir/ui/"
build_id=$(cat "$output_dir/ui/"*.qml "$output_dir/ui/Book.js" "$output_dir/ui/"page*.png | sha256sum | cut -c1-12)
printf '.pragma library\nvar id = "%s";\n' "$build_id" > "$output_dir/ui/BuildInfo.js"
cat > "$output_dir/application.qrc" <<'QRC'
<RCC><qresource prefix="/pdf-test">
<file alias="Main.qml">ui/Main.qml</file>
<file alias="PdfPage.qml">ui/PdfPage.qml</file>
<file alias="WordPopup.qml">ui/WordPopup.qml</file>
<file alias="SentenceTranslationBar.qml">ui/SentenceTranslationBar.qml</file>
<file alias="Book.js">ui/Book.js</file>
<file alias="BuildInfo.js">ui/BuildInfo.js</file>
<file alias="NotoSansSC.ttf">ui/NotoSansSC.ttf</file>
</qresource></RCC>
QRC
rcc_bin=${RCC_BIN:-/usr/lib/qt6/rcc}
python3 - "$output_dir" <<'PYQRC'
import sys
from pathlib import Path
root=Path(sys.argv[1]);p=root/'application.qrc';text=p.read_text()
entries=''.join(f'<file alias="{image.name}">ui/{image.name}</file>\n' for image in sorted((root/'ui').glob('page*.png')))
p.write_text(text.replace('</qresource>',entries+'</qresource>'))
PYQRC
"$rcc_bin" --binary -o "$output_dir/resources.rcc" "$output_dir/application.qrc"
echo "Built $output_dir"
