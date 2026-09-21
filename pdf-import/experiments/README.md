# Live DeepSeek annotation benchmark

`deepseek_benchmark.py` runs a bounded comparison using the same compact source
and annotation contract as the importer. It uses DeepSeek Chat Completions JSON
mode with the schema in the prompt, then the production semantic-structure and
geometry validator. JSON mode is not strict server-side schema enforcement.

From the repository root:

```sh
# DEEPSEEK_API_KEY is read from the environment; never included in artifacts.
python3 pdf-import/experiments/deepseek_benchmark.py --work build/deepseek-benchmark
python3 pdf-import/experiments/deepseek_benchmark.py --thinking enabled \
  --cases challenge page25 --work build/deepseek-benchmark/thinking
```

The script also accepts `--key-file PATH` for an explicitly selected local
credential file. Credentials are read into memory only and are not printed or
written to request/response files. The test requires the existing prepared
page-25/page-26 inputs in `build/llm-step-check/`.

The first command makes six annotation requests (three cases, two models); the
second makes four requests (two cases, two models). Each case is independent,
with no repair call or automatic retry. Concurrency is limited to two requests.
There is a 14,000-completion-token cap and 240-second timeout per request.
Thinking uses the provider default effort; only enabled/disabled is specified.

All raw textbook-bearing input/output stays under ignored `build/`. The source
of the synthetic challenge is included in the script. Returned model IDs, token
usage including cache hits and reasoning tokens, wall time, finish reason,
validation failures and successes are recorded. Cost estimates use published
September 16, 2026 tariffs, not an account billing export; refresh them before
reusing the benchmark on another date. Peak and off-peak estimates are separate.

This is a provider experiment, not a switch of the production importer from
OpenAI to DeepSeek. See [the measured report](../../docs/deepseek-benchmark.md).

## Luna comparison

`luna_benchmark.py` replays the exact stored messages and source from the Flash
baseline against `gpt-5.6-luna`, using the same Chat Completions JSON mode and
local validator. It makes five calls: challenge/page26/page25 with reasoning
`none`, then challenge/page25 with `medium`. The 14,000-token budget includes
reasoning. Temperature is zero for `none` and omitted for `medium`. Standard
service tier, no retries or repairs, maximum two concurrent requests. Each run
requires a new output directory.

```sh
# OPENAI_API_KEY from the environment, or pass --key-file PATH.
python3 pdf-import/experiments/luna_benchmark.py
```

The default baseline is the ignored `tests/deepseek-benchmark/` evidence copy.
Outputs go to `build/luna-benchmark/`. Full usage is retained. Pricing estimates
use September 16, 2026 standard rates; a separate upper bound accounts for cache
writes if the usage response does not itemize them. See the
[Luna comparison](../../docs/luna-benchmark.md).

## Line-ID follow-up

`line_contract.py` defines an experimental replacement contract: fixed line IDs,
corrected text per line, reasons only for changed lines, no model-generated
numeric offsets. Input `parts` represent text separated by large horizontal
layout gaps. A concrete blank example distinguishes immutable Chinese text from
English placeholders. Full-page sentence/word annotations remain separate so
OCR line wraps do not force sentence boundaries.

`compile_lines` requires exactly the original line IDs/order/lengths, derives
allowed substitutions locally and feeds the existing word-coverage, gap and
geometry validator. It never repairs or drops bad model output. Regression
checks are included in `pdf-import/check`.

```sh
python3 pdf-import/experiments/line_benchmark.py
```

This makes 15 calls (the same five case/settings pairs for each of the three
models), with the original 14,000-token limit and two concurrent requests.
Credentials come from OPENAI_API_KEY / DEEPSEEK_API_KEY. Baseline sources are read from
`tests/deepseek-benchmark/`; a fresh `build/line-benchmark/` directory is required.
No production default is changed. See [the follow-up report](../../docs/line-benchmark.md).

To repeat only the two DeepSeek Thinking exercise cases with a larger budget:

```sh
python3 pdf-import/experiments/line_benchmark.py \
  --work build/line-benchmark-48k \
  --models deepseek-flash deepseek-v4-pro \
  --max-tokens 48000 --timeout 900 --thinking-page25-only
```

The 900-second HTTP timeout allows the larger generation to finish; it is not a
change in reasoning effort. Requests otherwise match the 14k line-contract run.
This command makes exactly two calls, without retries or answer repair.
