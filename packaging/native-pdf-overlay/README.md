# Native PDF lookup test

This Xovi QML patch adds passive finger-tap lookup to reMarkable's normal document
view. Each tablet document UUID is supplied at build time, and its source PDF must
match the prepared collection by SHA-256. The overlay appears only on validated
pages in those collections. Other documents keep their normal view. Find IDs by
on-device PDF hash with `python3 scripts/find-remarkable-pdf-ids.py SOURCE_PDF`;
this also finds a reimported copy with a new document ID.

Lookup uses the native page's visible rectangle and the PDF CropBox to map short
finger taps to reviewed OCR word boxes. A passive Qt TapHandler observes taps
without taking the exclusive grab; native drag, pinch, and stylus input remain
with xochitl. The popup, word outline, and Chinese font are packaged separately
from the PDF and its native ink data.
Holding a finger on an annotated word shows the translation of its sentence and
outlines the sentence's text lines.

Build the resource bundle with:

```sh
bash scripts/build-native-pdf-overlay.sh \
  PREPARED_COLLECTION SOURCE_PDF TABLET_DOCUMENT_UUID \
  [PREPARED_COLLECTION SOURCE_PDF TABLET_DOCUMENT_UUID ...]
```

The bundle is written to `build/native-pdf-overlay/`. The readable QMD patch is
generated from `packaging/native-pdf-overlay/document-overlay.qmd.in`. It targets
the reMarkable 3.27.3.0 document view. The generated bundle and document-specific
lookup data stay under ignored `build/`.
