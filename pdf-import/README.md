# Local PDF preparation

Laptop-side Python subproject for preparing original PDF pages with tappable
Chinese text for the reMarkable reader. This package does not run on the tablet
and does not need a DuChinese account.

## Current status

Implemented: local PaddleOCR, preparation of character geometry, a single-pass
LLM annotation command, strict correction/alignment validation, the five-page
benchmark/viewer, and assembly of one annotated page for the existing reader.

Implemented additionally: batch processing of a rendered page range and a local
offline preview. Still missing: semantic layout analysis for arbitrary textbook
layouts for complex layouts. The tablet PDF reader now supports page-range navigation. Preparation
currently selects Chinese-containing OCR regions in Paddle's reading order,
recording omitted regions. Explicit region selection is available. The LLM
receives fixed line IDs and text parts separated at large horizontal gaps to interpret sentences and exercises. Character coordinates stay local.
`score` and `viewer` remain specific to the five-page benchmark.

## Agreed pipeline

PDF rendering → PaddleOCR with positions → text/layout preparation → **one LLM
pass per text batch** → deterministic validation → offline reader package.

The LLM pass produces word segmentation, contextual pinyin and meanings,
and sentence translations. It may automatically replace individual visually
similar Chinese characters when the context makes the correction unambiguous
(for example, 自已 → 自己). Character count and source positions must remain
unchanged. Store original text and each replacement separately. Ambiguous text
stays unchanged; do not rewrite sentences, add missing words, or answer exercise
blanks. Meanings and pinyin use the corrected text.

There is **no additional agentic correction loop or mandatory visual review**.
Technical validation checks offsets, permitted replacements, token coverage,
sentence references and box bounds. Failed validation must be reported rather
than silently producing a mismatched package. Semantic correctness of pinyin,
glosses and translations still depends on the model; deterministic checks
verify structure and source alignment, not meaning.

## Structure

```text
pdf-import/
  pyproject.toml                 installable package and optional OCR dependencies
  requirements-ocr-lock.txt      tested Python 3.12 OCR environment snapshot
  run                           source-checkout CLI
  check                         synthetic alignment/scoring checks
  src/duchinese_pdf/
    __main__.py                 CLI, lazy loading of optional dependencies
    ocr.py                      untouched Paddle output and run metadata
    prepare.py                  Paddle geometry and canonical source offsets
    annotate.py                 one DeepSeek/OpenAI call or offline replay
    line_contract.py            tested Flash line-ID prompt and local offsets
    batch.py                    page-range OCR and Flash processing
    preview.py                  offline browser preview
    annotation_schema.py        strict output and character-confusion policy
    prompts/annotate.txt         single-pass annotation instructions
    assemble.py                 validated page data and reader assets
    score.py                    Chinese CER and diagnostic overlays
    viewer.py                   offline benchmark viewer
    templates/comparison.html   viewer template
  checks/                       synthetic checks without private book content
```

The device UI remains in [`../packaging/pdf-test/`](../packaging/pdf-test/).
Its popup and translation bar are shared with DuChinese through
[`../packaging/shared/`](../packaging/shared/). Device build/deploy scripts stay
in `../scripts/`. The old Python script names there forward to this package;
there is one implementation of each operation.

## Use from a checkout

Run the following from the repository root. Inputs and outputs are relative to
the current directory, not to this package.

```sh
pdf-import/run --help
pdf-import/run assemble --help
pdf-import/check
```

Use `PDF_IMPORT_PYTHON=/path/to/python` to choose an interpreter. For the existing
local OCR environment:

```sh
PDF_IMPORT_PYTHON=build/ocr-benchmark/venv/bin/python pdf-import/run ocr \
  build/ocr-benchmark/page-{22,23,24,25,26}.png \
  --models build/ocr-benchmark/models --output build/ocr-benchmark/paddle
```

See [the benchmark report](../docs/ocr-benchmark.md) for memory limits, exact
settings, model hashes and measured results. No OCR run is triggered by setup.

## Install in a separate environment

The tested OCR interpreter is **Python 3.12**. PaddlePaddle **3.2.2** is pinned
because 3.3.1 failed in the measured CPU configuration. Heavy OCR dependencies
are optional; assembling a page only needs Pillow. Scoring also needs lxml.

```sh
python3.12 -m venv pdf-import/.venv
pdf-import/.venv/bin/pip install -e './pdf-import[ocr,benchmark]'
pdf-import/.venv/bin/duchinese-pdf --help
```

For the exact recorded OCR dependency versions, install
`pdf-import/requirements-ocr-lock.txt` first, then the editable package above.
That snapshot covers OCR; lxml is added by the `benchmark` extra. Poppler is an
external dependency for PDF rendering; Tesseract and its Chinese model are only
needed for the comparison baseline. Qt tools and PySide6 belong to device
packaging/UI checks, not this Python package.


## OCR → LLM → prepared reader page

The default is **DeepSeek Flash with Thinking enabled, a 48,000-completion-token
limit and a 900-second HTTP timeout**, using the tested line-ID contract.
Batch processing sends up to 16 page requests concurrently by default; use
`--annotation-workers N` to tune concurrency without changing Thinking mode.
Pages enter the annotation queue as their OCR finishes, so parallel requests
cannot make the sequential OCR stage finish sooner.
Configure `DEEPSEEK_API_KEY` in the environment, or pass
`--key-file /path/to/private/deepseek-key` to `annotate` or `batch`.
The locally copied credential file is private (mode 0600) and outside the repo. Credentials never go into command
arguments or saved requests. One request per page, no automatic repair loop.
DeepSeek JSON mode is followed by strict local schema, correction and alignment
checks; it does not enforce the schema server-side.

The existing OpenAI Responses path remains available through `--provider openai
--model MODEL` and `OPENAI_API_KEY`. That compatibility path retains its earlier
prompt/schema. `--model` / `PDF_IMPORT_MODEL` and `--provider` /
`PDF_IMPORT_PROVIDER` override selection. No extra LLM SDK is needed.

### Google Vision OCR trial

The direct image trial sends rendered page images to Cloud Vision's
`DOCUMENT_TEXT_DETECTION` endpoint and saves its symbol boxes in the existing
`prepare` input shape. It needs a Google Cloud project with billing, the Cloud
Vision API enabled, and an API key restricted to that API. It does not need
Cloud Storage or the `gcloud` CLI. Save the key outside Git in a mode-0600 file;
the script sends it in an HTTP header and never writes it to the output.

```sh
PYTHONPATH=pdf-import/src python3 -m duchinese_pdf.google_vision \
  build/new-textbook-20260930/images/page-{026,040,046}.png \
  --output build/google-vision-trial --key-file /path/to/private/vision-key
```

The output stays under the ignored `build/` directory. Each page contains the
raw provider response and a converted `page-NNN_res.json` file that can be
passed to `prepare`. Inspect OCR text and character geometry before using it
for a full book. Page images and recognized text are sent to Google for this
trial; the PDF file itself is not uploaded by this command.

After a successful OCR quality check, the same command accepts a full page
glob and `--workers 32`. The Google output must be complete before annotation.
`batch-existing` reads those finished OCR files, sends DeepSeek Flash requests
with Thinking enabled in parallel, and writes per-page results and a manifest.
It reuses finished pages after an interruption and never silently resends an
attempt that might already have reached DeepSeek.

```sh
PYTHONPATH=pdf-import/src python3 -m duchinese_pdf batch-existing \
  /path/to/compressed.pdf /path/to/rendered/images \
  /path/to/google-vision-output /path/to/new-collection \
  --first 47 --last 210 --workers 128 \
  --title 'Chinese textbook' --key-file /path/to/private/deepseek-key
```

```sh
# Keep the existing raw OCR intact; prepare a separate annotation input.
pdf-import/run prepare \
  build/ocr-benchmark/paddle/page-26/page-26_res.json \
  build/ocr-benchmark/page-26.png build/local-pdf/page-26.json

# Optional: inspect the exact prompt/schema without a key or any network call.
pdf-import/run annotate build/local-pdf/page-26.json \
  build/local-pdf/page-26-preview --dry-run

# One Flash request. Text and gap hints go to the API; character boxes,
# original PDF and page raster stay local.
pdf-import/run annotate build/local-pdf/page-26.json \
  build/local-pdf/page-26-annotation

pdf-import/run assemble build/ocr-benchmark/page-26.png \
  build/local-pdf/page-26-annotation/result/characters.json \
  build/local-pdf/page-26-annotation/result/annotations.json \
  build/local-pdf/page-26-book --page 26 --printed-page 8 \
  --title 'Contemporary Chinese 4'
```

Each annotation run requires a new directory and saves:

- `source.json`: untouched prepared text, source geometry and provenance.
- `request.json`: exact prompt, model and output schema, without credentials.
- `response.json`: raw API response bound to the source/request hash.
- `run.json`: status, model, request count and returned token usage.
- `result/characters.json`, `annotations.json`, `corrections.json`: validated
  output only, with original/corrected text and reasons for every substitution.

The current correction allowlist is `己已巳`, `未末`, `土士`, `日曰`, `乌鸟`,
`千干`, `天夭`, `人入`. Only a single-character substitution within a group is
accepted, with the original offset derived locally and a recorded reason. The prompt additionally
requires unambiguous context. That contextual judgment cannot be proven by the
validator. Tokens must cover the entire corrected text in order. Chinese tokens
need pinyin and a contextual meaning; each sentence needs a translation.

Preparation removes whitespace with an explicit normalization record, checks
that Paddle's tokens match the recognized text, and keeps the original OCR
file hash. Multi-letter/number tokens share their original OCR rectangle; no
new per-letter coordinates are invented. Empty/non-Chinese regions are recorded
as omitted by default. `prepare --lines 0 1 2` overrides selection using original
zero-based OCR region IDs. It does not reorder them or fix complex layouts.

There is one request per page, with a current limit of 2,000 prepared characters.
For larger inputs select smaller regions explicitly. `--max-output-tokens` and
`--timeout` are configurable. Refusals, truncation, malformed output and alignment
errors fail the run; they do not trigger another LLM call. HTTP/network errors
also have no automatic retry. A timeout may occur after the provider accepted
work, so inspect the failed run before choosing to submit again.

A saved response can be validated again without a key or network access:

```sh
pdf-import/run annotate build/local-pdf/page-26.json \
  build/local-pdf/page-26-replay \
  --response build/local-pdf/page-26-annotation/response.json
```

Replays require the same source, prompt/schema, model and token limit. Responses
from the previous verbose coordinate-based prompt cannot be replayed against
the compact prompt; their original run files remain intact. A response
from a different request is rejected. Failed validation retains the raw response
but publishes no `result/` directory. Dry runs publish no annotation result.

The provider integration is tested with synthetic transport/replay/truncation
checks and the preserved real 48k Flash response. Live model comparisons and
limitations are documented in [the 48k report](../docs/line-benchmark-48k.md).
Exercise translations can be awkward; source fidelity remains strict.

## Process a page range

Render the desired original PDF pages at 240 dpi using Poppler, then run OCR
and Flash concurrently (one OCR process, maximum two Flash calls). The batch
command expects `images/page-NNN.png` with three-digit PDF page numbers.

```sh
mkdir -p build/textbook-first25/images
pdftoppm -f 1 -l 25 -r 240 -png tests/compressed-textbook4.pdf \
  build/textbook-first25/images/page
pdf-import/run batch tests/compressed-textbook4.pdf build/textbook-first25 \
  --last 25 --ocr-python build/ocr-benchmark/venv/bin/python \
  --models build/ocr-benchmark/models --title 'Contemporary Chinese 4'
pdf-import/run preview build/textbook-first25
```

The batch requires Linux user systemd for the tested 5GB OCR memory limit.
A new manifest is required; it never implicitly retries or overwrites a previous
run. It records the PDF/image hashes, original PDF page numbers and every outcome.
Pages without detected Chinese remain image-only. Failed annotations retain
source and raw responses, but do not publish clickable text. The original
rasters remain available for every page. Final per-page data is in
`pages/NNN/book.json`; `manifest.json` indexes the range. `preview.html` embeds
validated annotations and loads the neighboring original PNG files, so it works
without a server. To build and deploy the validated range with tablet page navigation:

```sh
scripts/build-pdf-test.sh tests/textbook-first25
python3 scripts/check-pdf-collection.py build/pdf-test-app
scripts/install-pdf-test-rm2.sh rm2
```

The device app is still named **PDF Reader Test** in AppLoad. The installer
backs up the previous package, verifies hashes and restarts xochitl to activate it.

## Prepare and validate the existing sample

```sh
pdf-import/run assemble \
  tests/pdf-page38/page.png tests/pdf-page38/characters.json \
  tests/pdf-page38/annotations.json build/pdf-test/book \
  --title 'Contemporary Chinese 4' --page 38 --printed-page 20 \
  --view 175 335 1610 1900
scripts/build-pdf-test.sh build/pdf-test/book
QT_QPA_PLATFORM=offscreen python3 scripts/check-pdf-page.py build/pdf-test-app
```

Assembly produces `book.json`, its QML counterpart `Book.js`, the original page
raster `page.png`, and an optional-to-inspect alignment overlay. All character
offsets are Unicode code-point offsets; rectangles use original raster pixels.
Words spanning multiple lines retain multiple rectangles. See the
[prototype notes](../docs/local-pdf-prototype.md) for provenance and deployment.

Private PDFs, OCR output and annotations remain under ignored `tests/` and
`build/`; they are not packaged as Python resources. Existing benchmark artifacts
and the isolated OCR environment stay at their current paths.

## Model evaluation

The [initial benchmark](../docs/deepseek-benchmark.md),
[line-ID follow-up](../docs/line-benchmark.md), and
[48k-token retest](../docs/line-benchmark-48k.md) preserve the experiments that led
to selecting Flash. Scripts in `experiments/` remain available for reproduction.

The [first 25-page run](../docs/textbook-first25.md) completed with 20 annotated
pages and five image-only pages; its artifacts include an offline preview.

## Tablet gestures and reading position

The PDF reader uses horizontal swipes: left advances, right goes back. There
are no bottom navigation buttons. Taps still open contextual word lookup;
short and primarily vertical gestures do not turn pages. The top sentence
translation bar is unchanged.

Each page change is written immediately to the reader's private INI file under
`~/.local/share/duchinese-pdf-reader/progress.ini`. Positions are keyed by the
full source PDF SHA-256 and store original PDF page numbers. Extending a range
from 25 to 50 pages or replacing the AppLoad package preserves the position.

Completed consecutive batches can be combined without repeating OCR/LLM work:

```sh
pdf-import/run merge build/textbook-first50 \
  tests/textbook-first25 tests/textbook-pages26-50
scripts/build-pdf-test.sh build/textbook-first50
python3 scripts/check-pdf-collection.py build/pdf-test-app 50
scripts/install-pdf-test-rm2.sh rm2
```

Batch validation remains strict: received answers that insert/delete source
characters are not published. `retry` is a separate, explicitly invoked fresh
attempt for selected rejected pages; it retains the first response and checks
that the source, prompt and request settings are unchanged. It neither sends
model feedback nor repairs returned text. It permits one recorded retry per page
and never reruns successful pages:

```sh
pdf-import/run retry build/textbook-pages26-50 --pages 30 \
  --key-file /path/to/private/deepseek-key
```
