# Textbook pages 1–50

The reader combines the existing pages 1–25 with a new OCR/DeepSeek Flash batch
for PDF pages 26–50. Original PDF rasters remain unchanged; ink/OCR bounds define
the display crop, and tappable word regions use the original image coordinates.

## Reader behavior

Swipe left to advance and right to go back. The bottom navigation buttons have
been removed; tapping a word still opens the shared dictionary popup, and the
shared sentence translation bar remains at the top. Short or primarily vertical
gestures do not turn pages.

Page changes synchronously save the original PDF page number to
`~/.local/share/duchinese-pdf-reader/progress.ini`, keyed by the source PDF SHA-256.
The position survives AppLoad package replacement, reader restarts, and extending
the collection. An initial migration can carry over the old reader's last recorded page
change, only if no saved position already exists.

## Processing and validation

Flash uses the existing compact line-based request, Thinking enabled, and a
48,000-token output limit. Source alignment validation remains strict. Page 30's
first response inserted source characters and was rejected. Its explicit fresh
attempt uses the same input and request settings without correction feedback;
both attempts are retained for audit. The fresh attempt passed validation.

The completed collection contains 50 pages: 45 annotated pages and five
image-only front-matter pages, with 5,274 word tokens. The new batch is preserved
in `tests/textbook-pages26-50`; the original first batch remains in
`tests/textbook-first25`. No successful pages were regenerated.

The importer checks cover merging consecutive batches, rejecting mismatched
PDFs or image hashes, and retaining rejected responses during an explicit retry.
The reader check loads every page in actual QML, tests word lookup against the
display crop, exercises horizontal swipes and rejected vertical/short gestures,
and launches a fresh process to verify disk-persisted reading position.

Reproduction:

```sh
pdf-import/run merge build/textbook-first50 \
  tests/textbook-first25 tests/textbook-pages26-50
scripts/build-pdf-test.sh build/textbook-first50
python3 scripts/check-pdf-collection.py build/pdf-test-app 50
scripts/install-pdf-test-rm2.sh rm2
```

Validation passed: 46 importer checks and the 50-page QML integration check,
including reading position restoration in a fresh process.

Installed on `rm2`: package `35ca87b654cfab42`, UI build `eb14c04d7750`.
The installer verified all package hashes and restarted xochitl from PID 1395 to
1594. A subsequent remote check confirmed the service active, package hashes
correct, and the saved reading position preserved. Physical touch interaction
was not exercised remotely; gesture validation used the actual QML offscreen.
