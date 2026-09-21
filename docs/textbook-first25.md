# First 25 original PDF pages — Flash import, 2026-09-16

Processed original PDF pages 1–25 of the local textbook, including covers and
front matter. This is not printed lesson pages 1–25. Raw scans were rendered at
240 dpi and processed with the previously tested PP-OCRv5 CPU configuration.
DeepSeek Flash used Thinking and a 48,000-completion-token cap, with a maximum
of two simultaneous requests. No model-assisted repair loop or manual OCR edits.

## Outcome

- 25 original page rasters retained and hash-verified.
- 20 pages annotated and passed the full schema, correction, coverage, gap and
  geometry validator; 1,146 annotation tokens with their original rectangles.
- Five pages (3, 6, 7, 10, 11) had no Chinese detected and remain image-only.
- Two permitted 已 → 己 corrections, on PDF pages 22 and 25, with original text,
  positions and reasons retained in the corresponding correction audit.
- 20 successful provider responses: 19,408 input and 169,477 completion tokens,
  including reasoning. Three earlier requests have no returned usage, so billing
  for those attempts is unknown.

Page 15 had a connection reset. A host restart interrupted the ongoing requests
for pages 21 and 24, while page 25 had not yet started. The three unreturned
requests were explicitly repeated once with unchanged prompts, preserving their
first attempt directories. No received model answer was repaired or retried.
`manifest-before-resume.json` and recovery logs preserve the interrupted state.

Technical validation is not a guarantee of semantic correctness. Spot-checks of
normal questions and dialogues on pages 19, 20, 23 and 24 were sensible; the
exercise-blank limitations discussed in the benchmark remain accepted. Not every
word/translation on the 25 pages received manual linguistic review.

## Local artifacts

The complete private run is retained at `tests/textbook-first25/`, with the
working copy in `build/textbook-first25/`:

- `preview.html`: offline browser reader with page switching, tappable original
  text regions, contextual pinyin/gloss popups and sentence translations.
- `manifest.json`, `summary.json`: page index, processing status and totals.
- `images/page-NNN.png`: untouched rendered PDF pages.
- `ocr/`: raw OCR, per-page timings and image hashes.
- `pages/NNN/book.json`: assembled per-page reader data.
- `pages/NNN/annotation*/`: exact requests, raw responses, run metadata and
  validated character/annotation/correction files.

Open `preview.html` beside its image directory; it needs no web server or key.
These files contain private textbook content and remain gitignored. The range was subsequently deployed to the reMarkable on 2026-09-17 with
bottom previous/next navigation in the existing PDF Reader Test app.

## Integration checks

Flash is now the annotation CLI default with the tested line-ID contract.
The previous OpenAI path remains explicitly selectable. Credentials can be read
from an environment variable or an explicitly selected `--key-file`; the local
DeepSeek file lives outside the repo with permissions 0600.

40 automated checks pass. The saved real 48k Flash response also passes through
the production integration in offline replay with zero API calls, and its
request exactly matches the benchmark request. All 25 image hashes and all 20
published annotation sets were revalidated after completion. Browser checks
verified all 25 page entries, raster loading, word/pinyin/sentence popups,
page switching and image-only pages; screenshots were inspected on the cover
and dialogue page 23.

## Tablet deployment — 2026-09-17

The builder now accepts the batch directory and packages all 25 original images
and validated per-page data. `PdfPage.qml` switches pages with bottom navigation,
clears the selected word and pan/zoom on switching, and keeps the shared word
popup and sentence translation bar. Image-only pages remain fully navigable.
Single-page packages remain supported.

`python3 scripts/check-pdf-collection.py build/pdf-test-app` passed: 25 image
loads, actual lookup taps on all 20 annotated pages, empty pages, next/previous
buttons, boundaries and selection reset. The rendered dialogue page was inspected.
The 43MB resource bundle was transferred using the existing checksum/backup/
restart installer. Device hashes matched, xochitl restarted from PID 971 to
1252 and remained active. Activated package: `a5b1046c9194cfbe`, UI build
`4c48ca23af85`. Open **PDF Reader Test** in AppLoad; no Reload step is necessary.

## Content framing fix — 2026-09-17

The original scans after the cover are 3968×2806 pixels, with actual book
content alternating between the left and right halves. Fitting the entire
scan made the page small and off-center. The collection packager now computes
a display-only content rectangle per page from raster ink plus all OCR regions
(including English and pinyin) and annotation boxes, with a small safety margin.
Illustrations are included through raster detection. Blank pages retain their
full view. Original images and linguistic data are unchanged.

`page_view.py` uses only Pillow; it does not invoke OCR or an LLM again. The
reader's existing shared rendering/hit-test transform consumes the new `view`.
All 25 crops were visually inspected together; all annotation rectangles were
checked inside their view; real QML taps still pass on all 20 annotated pages.
43 Python checks pass, including blank/full-bleed, asymmetric margins, and
preserving illustrations plus faint OCR-protected regions. The packaged
`ui/page-views.json` records every chosen rectangle for inspection.

The framing fix was installed as package `47a005984910b18d`, UI build
`da477d38e0e5`; xochitl restarted from PID 1252 to 1395. Remote package
checksums matched after activation.
