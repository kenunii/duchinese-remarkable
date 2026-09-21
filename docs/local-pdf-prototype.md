# Original-page PDF reading prototype

The separate **PDF Reader Test** AppLoad app shows the original PDF raster with
word hit regions, a pinyin/contextual-meaning popup, and an optional sentence
translation. The popup and tap-to-reveal sentence bar are shared QML components
used by both this app and the DuChinese reader (`packaging/shared/`). The PDF
opens fitted to its content with no extra header buttons. The internal full-page
and zoom coordinate transforms remain covered by the UI checks. It works offline without a DuChinese account or a
backend. This is a one-page, supervised prototype, not yet a general PDF importer.

## Sample prepared on 2026-09-16

Input: the user's local `tests/compressed-textbook4.pdf`, PDF page 38 (printed
page 20). The page contains a Chinese story and an English margin note. Only
the Chinese story has lookup annotations; the note remains visible in the scan.
The opening sentence continues from the previous page and is marked accordingly.

Reviewed inputs are preserved under ignored `tests/pdf-page38/`; working outputs
are under ignored `build/pdf-test/`: extracted PDF,
240 dpi page raster, raw Tesseract hOCR/TSV/text, reviewed transcription, explicit
OCR correction records, linguistic annotations, and alignment-review images.
The LLM annotations were authored in the Codex session after OCR and visual
review; no independent LLM API was called. They contain 230 annotated word
occurrences, 288 total tokens including punctuation, and 17 translated segments.

Tesseract 5.5.2 with `tessdata_best/chi_sim` supplied OCR text and line locations.
Several characters were wrong, and the English margin note contaminated two
lines. Raw hOCR character boxes were not reliable enough. For this sample the
transcript was corrected against the scan, line extents reviewed, and character
cells refined using vertical ink projections. Those cells were visually checked.
These supervised corrections are required inputs, not evidence that arbitrary
textbook pages can already be imported automatically.

The prototype annotations keep source character offsets, word-level pinyin and
short English meanings, sentence references and translations. Context-sensitive
entries include 教 (jiāo), grammar particles, 非要…不可, and 轻而易举. No source
text is silently rewritten by the package builder. Words split over lines keep
multiple hit rectangles, including 拼好 and 解决 in the sample.

## Build a reviewed page

Laptop processing is maintained in the [PDF import subproject](../pdf-import/README.md).
The old Python script paths remain compatibility entry points.

Dependencies: Python 3 + Pillow for assembly; Qt 6 `rcc` for packaging.
OCR additionally used Poppler, Tesseract, a Chinese language model, lxml and NumPy.
The local visual check uses PySide6.

```sh
pdf-import/run assemble \
  tests/pdf-page38/page.png \
  tests/pdf-page38/characters.json \
  tests/pdf-page38/annotations.json \
  build/pdf-test/book \
  --title 'Contemporary Chinese 4' --page 38 --printed-page 20 \
  --view 175 335 1610 1900
scripts/build-pdf-test.sh build/pdf-test/book
pdf-import/check
QT_QPA_PLATFORM=offscreen python3 scripts/check-pdf-page.py build/pdf-test-app
scripts/install-pdf-test-rm2.sh rm2
```

The UI check exercises all annotated regions with actual mouse events, validates
full-page and zoom coordinate mapping, and saves two rendered previews in the
build directory. It mounts resources below an isolated prefix like AppLoad does.
Both installers use `scripts/deploy-appload.sh`. It stages a complete package,
verifies SHA-256 sums before activation, keeps the previous package outside the
AppLoad scan directory, and restarts xochitl to clear registered resources and
cached QML. This closes open AppLoad windows but does not reboot the tablet.
A failed service activation restores the previous package. An identical package
already activated in the current xochitl process skips the restart. The PDF app
logs its content-derived build ID when opened. Open **PDF Reader Test** after
installation; refreshing AppLoad is no longer an activation step.

## Before scaling up

The agreed next implementation is local PaddleOCR, layout preparation, one LLM
annotation pass with narrowly permitted character substitutions, and deterministic
validation. Original OCR and corrections remain separate. No additional agentic
correction loop or mandatory visual review is planned. The single-pass LLM command is now implemented in `pdf-import/`; its live model
quality test and the full-book reader are still pending. See the subproject README. The
fixed sample's supervised geometry refinement is not the general importer.
