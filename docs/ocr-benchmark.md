# Textbook OCR benchmark

This experiment evaluates uncorrected OCR before automating the original-page
PDF reader. It does not generate translations, alter the existing reader, or
deploy anything to the tablet.

## Results (2026-09-16)

PP-OCRv5 is a strong candidate for the importer: its untouched Chinese output
has 2 edits across 1,209 reference characters (0.17% CER), versus Tesseract's
93 edits (7.69%). The two Paddle errors are both 己 recognized as 已. These are
sample results, not an accuracy guarantee for the book.

| PDF page | Layout | Reference characters | Paddle edits | Tesseract edits | Paddle seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| 22 | Vocabulary and exercises | 203 | 1 | 5 | 48.1 |
| 23 | Illustrated dialogue; dialogue scored | 140 | 0 | 29 | 26.6 |
| 24 | Dialogue and margin note | 188 | 0 | 30 | 36.3 |
| 25 | Questions, blanks and prose | 264 | 1 | 14 | 51.0 |
| 26 | Dense prose and margin note | 414 | 0 | 15 | 60.1 |
| **Total** | | **1,209** | **2** | **93** | **222.1** |

The evaluation-only spatial sort reduces Tesseract to 53 edits (4.38%); Paddle
stays at 2. This demonstrates that part of the baseline's error is reading
order, but sorting alone does not close the gap. Paddle took another 12.3 s to
initialize, excluding setup, PDF rendering and scoring. Tesseract took 33.8 s
for the same five images. A straight extrapolation of Paddle's OCR time is
about 2.1 hours for 172 similarly complex pages; this is not a measured book
runtime and excludes LLM annotation and review.

Visual inspection of enlarged character-box overlays on all five Paddle pages
shows substantially better character placement than the Tesseract overlays,
including around blanks and beside margin notes. Some boxes clip strokes or
slightly overlap neighbors. This is qualitative evidence of useful tap regions,
not a measured geometry accuracy score or a tablet tap test.

A line-confidence threshold below 0.95 flags 4 of 103 scored Chinese lines,
including only one of the two errors. The other error's line confidence is
0.962. Confidence alone cannot certify a page. These are line scores, not
character-specific confidence values.

The Chinese score does not imply clean whole-page text: printed pinyin on page
25 includes a badly garbled line; English notes are interleaved with Chinese
lines in raw reading order; blank fields split exercise text into fragments.
The page image preserves their visual appearance, but annotation preparation
must retain those distinctions and must not fill exercise answers.

### Smaller local model follow-up (2026-10-08)

PP-OCRv5 mobile detection and recognition were run on the same page-22 and
page-26 PNGs, with the server run's 240-dpi input, four CPU threads, 1536-pixel
detector limit, word boxes, and orientation/unwarping disabled. The downloaded
model initialization took 118.1 s once; inference took 17.3 s on page 22 and
12.3 s on page 26, compared with 48.1 s and 60.1 s for the earlier server run.
The two mobile pages had 8 and 4 Chinese edits respectively (12/617, 1.94%
CER), versus 1 and 0 server edits (1/617, 0.16% CER). The mobile output passed
the importer character-box validation on both pages. These two selected pages
show a useful speedup with lower text accuracy; they do not establish a
whole-book result or a controlled runtime comparison across different runs.

### Google Vision image OCR follow-up (2026-10-08)

Cloud Vision `DOCUMENT_TEXT_DETECTION` was tested on the same five reference
pages using rendered PNGs sent through `images:annotate`. Its symbol boxes pass
the importer's geometry checks. Vision's original paragraph order scrambled
some table and blank-fill layouts, so the adapter uses spatial rows when
Chinese paragraphs jump substantially upward on the page. With that ordering,
the five pages have 2, 0, 0, 3, and 0 Chinese edits respectively: 5/1,209
(0.41% CER). The pinned Paddle server run has 2/1,209 (0.17% CER).

The same Vision path processed all 210 PNGs of the new textbook in roughly
90 seconds with 32 concurrent requests and no request failures. All converted
pages passed the preparer's character-box checks. This measures OCR throughput
and syntax/geometry validation, not translation quality or whole-book OCR
accuracy; the reference pages belong to the earlier textbook sample.

### Agreed implementation after the benchmark

Use the pinned local Paddle configuration, prepare text/layout, then use one
LLM pass for word segmentation, contextual pinyin, meanings and sentence
translations. Allow unambiguous substitutions of individual visually similar
characters while preserving character count and coordinates. Keep raw OCR and
corrections separately. Ambiguous readings remain unchanged; never fill blanks
or rewrite sentences. Follow with deterministic schema/alignment validation.

No additional agentic correction loop or mandatory visual review is planned.
The benchmark supports this direction but does not establish whole-book
accuracy. The LLM command has since been implemented with deterministic validation and
offline tests; a live model quality test and the multi-page reader remain pending.
The tools and implementation contract now live in the
[PDF import subproject](../pdf-import/README.md).

## Method

The local input is `tests/compressed-textbook4.pdf`. Five consecutive PDF pages
22–26 (printed pages 4–8) cover a vocabulary table, illustrated dialogue,
dialogue with speaker labels and an English margin note, pinyin, exercises with
blanks, and dense prose with percentages. All are rendered at 240 dpi, with the
original blank margins retained. This is a small selected sample, not a random
estimate for all 172 PDF pages.

Independent Chinese transcriptions were prepared from the scans before reading
PaddleOCR output. A later visual audit fixed two extra characters in the page-26
reference; the original transcription and reason are preserved in the protocol.
References are used only by the scorer; the OCR runner never loads them.
Neither engine receives manual text or coordinate corrections.

The primary metric is Chinese-character Levenshtein edit distance divided by
reference length, using the engine's original reading order. It includes
recognition mistakes, omissions, spurious Chinese characters, and reading-order
errors. It excludes punctuation, digits, Latin script/pinyin, and blank lengths.
Page 23 scores only dialogue below 60% of page height; its illustration labels
and headings are excluded because bubble reading order is ambiguous.

A second, explicitly separate score sorts nearby line centers into rows and
then reads each row left to right. This helps diagnose speaker-label ordering;
it is not an improvement made to the raw OCR. Confidence values from different
engines are not directly comparable and are not calibrated probabilities.
Character-box overlays allow qualitative geometry review, separate from CER.

## Local artifacts and tools

Private scans, references and outputs stay in ignored directories:

- `tests/ocr-benchmark/protocol.json`: source/model/reference hashes and scope.
- `tests/ocr-benchmark/references/`: independent evaluation transcriptions.
- `tests/ocr-benchmark/requirements-lock.txt`: isolated Python environment.
- `build/ocr-benchmark/`: rendered pages, raw OCR, timings, logs and overlays.
- `build/ocr-benchmark/comparison.html`: offline interactive comparison.
- `tests/ocr-benchmark/results/`: preserved scans, raw output, scores and viewer
  independent of the disposable build environment.

Scripts:

```sh
# Render each selected PDF page; repeat with -f/-l 23 through 26.
pdftoppm -f 22 -l 22 -singlefile -r 240 -png \
  tests/compressed-textbook4.pdf build/ocr-benchmark/page-22

# Run inside the isolated Paddle environment, with CPU resource limits.
systemd-run --user --scope -p MemoryMax=5G -p MemorySwapMax=512M \
  env OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 \
  PDF_IMPORT_PYTHON=build/ocr-benchmark/venv/bin/python pdf-import/run ocr \
  build/ocr-benchmark/page-{22,23,24,25,26}.png \
  --models build/ocr-benchmark/models --output build/ocr-benchmark/paddle

pdf-import/run score \
  build/ocr-benchmark tests/ocr-benchmark/references
pdf-import/run viewer build/ocr-benchmark
pdf-import/check
```

The Tesseract baseline uses 5.5.2, `tessdata_best/chi_sim`, PSM 3,
`OMP_THREAD_LIMIT=2`, and `hocr_char_boxes=1`. The Paddle runner requests
PP-OCRv5 server detection and recognition models, character boxes, recognition
batch size 1, and a maximum detector input side of 1536 pixels. Document
rotation, unwarping and text-line orientation are disabled for these upright
scans. Engines therefore do not have identical runtime/thread configurations;
timings measure these local configurations, not a controlled speed ranking.

PaddlePaddle 3.3.1 failed with a oneDNN PIR attribute-conversion exception.
Disabling oneDNN caused excessive memory use; the initial high-resolution run
was stopped and subsequent attempts ran under a memory limit. Switching to the
legacy IR did not fix the exception. See the matching
[upstream report](https://github.com/PaddlePaddle/Paddle/issues/77340).
Pinning PaddlePaddle to **3.2.2** resolved the error. The completed run uses
PaddleOCR **3.7.0** and PaddleX **3.7.2**, with about 2.4 GB process RSS observed
during inference (not a measured peak). Five synthetic scorer checks passed,
including Tesseract header/caption retention and Paddle exported character-box
parsing.
