# Line-ID annotation follow-up — 2026-09-16

This repeats the [DeepSeek](deepseek-benchmark.md) and [Luna](luna-benchmark.md)
experiments with a revised input/output contract, rather than relaxing validation
or repairing failed responses. Same three source cases, three exact model IDs,
five settings per model, one call per cell, 14,000 completion tokens including
reasoning, two concurrent requests, no retries. JSON mode for all providers.
Luna uses none/medium; DeepSeek uses disabled/enabled with its default effort.

## Contract changes

Input supplies fixed line IDs with `parts`: text chunks separated by detected
large horizontal gaps. Their concatenation is the source text; gaps are not
characters. This replaces numeric gap offsets that models had to interpret.
Output contains every line ID in original order with corrected text and a reason
only if changed. Code derives correction positions by comparing equal-length
strings, permitting only the original visual-confusion allowlist.

Sentence translations and words remain a separate full-page sequence so words
and sentences can span OCR line wraps. Chinese text fields are explicitly
separated from English translations. A worked exercise-blank example forbids
inserting `[blank]` in the Chinese source, while allowing it in English.

The validator rejects missing/reordered/duplicate line IDs, length changes,
unapproved substitutions, inconsistent correction reasons, missing/extra word
characters, words spanning detected gaps, and invalid geometry. It feeds the
existing production validator after deriving offsets; it does not repair outputs.
Five new regression checks passed alongside the existing 27 checks.

This changes several prompt/format details together, so it cannot isolate the
causal effect of line IDs versus the blank example or wording. Each cell is one
sample; before/after differences are suggestive, not statistical success rates.
A technical pass does not guarantee accurate translations or good sentence
boundaries. This remains an experiment; no production default was switched.

## Evidence and reproduction

Run `python3 pdf-import/experiments/line_benchmark.py` from the repository root.
The baseline source files come from ignored `tests/deepseek-benchmark/`.
`line_contract.py` implements the experimental contract; `inspect_line_benchmark.py`
produces source/word differences without modifying answers. Prompts, source,
raw provider responses, answers and validation results are stored under ignored
`build/line-benchmark/` and retained in `tests/line-benchmark/` after completion.
Message digests allow confirming all providers received the same prompt per case.
Credentials stay in memory and are not included in artifacts.

Costs are estimated from returned usage, including cached input, cache writes
when itemized, and reasoning. Standard Luna pricing and DeepSeek off-peak/peak
rates were checked on the run date. These are not billing exports:
[OpenAI pricing](https://developers.openai.com/api/docs/pricing) and
[DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/).

## Inspection of the non-thinking outputs

All three models passed the synthetic challenge with the expected local
correction at offset 4. Legitimate 已经/巳时 were retained, contextual readings
of 教/行/得/乐 were appropriate, and negation and three-versus-thirteen were
preserved. Flash still uses some overly broad word chunks such as 很快乐.

All three also passed the technical checks on PDF 26, preserving every source
character and including all survey percentages in English. This fixes Pro's
previous omitted 35.7% claim and Luna's previous spurious correction record.
However, technical validity conceals important remaining quality problems:

- Flash splits segments at OCR wraps, sometimes inside words, and translates
  material from neighboring segments rather than just the selected source.
  The English for the Shanghai income/boss comparison is repeated across
  segments. This is a regression for the sentence-translation interaction,
  despite preserving all Chinese characters.
- Pro's translations cover the paragraphs, but its long paragraph-sized segments
  are less useful than individual sentences for the reader.
- Luna likewise groups paragraphs and still renders survey nonresponse
  没有选择 as “had no choice,” which is incorrect in this context.

All three failed PDF 25 without Thinking:

- Flash and Pro both describe 自已 → 自己 in the line correction reason but
  leave that line's text unchanged. Their word sequences use the corrected
  version, creating two contradictory representations. Pro's word sequence
  otherwise preserves the entire source. Flash additionally fills a blank
  with an invented 炒 in the source word sequence.
- Luna correctly changes the line text, but emits three malformed empty word
  objects, normalizes a full-width question mark to ASCII, and inserts an
  extra 的 in the word sequence. No raw output is repaired for scoring.

The earlier literal `[blank]` insertions into Chinese word text are absent in
these non-thinking trials. That is an improvement, but completing actual missing
words or dropping English blank markers is still a separate failure mode.

## Thinking outputs and interpretation

Flash's challenge response dropped a comma at source offset 56 and was rejected.
Pro and Luna passed the challenge with the expected correction and contextual
polyphonic readings. Flash again exhausted its completion budget on PDF 25
(13,999 reported completion tokens, all reasoning) without a final answer.

Luna medium passed every structural/coverage check on PDF 25, corrected offset
123 locally, and retained all source text. It used 753 reasoning tokens and
finished in 38.1 seconds. However, its exercise translations are **not ready for
the reader**: it split sentences at blank/line boundaries, repeated translations
of adjacent segments, translated parts of 炒鱿鱼 literally as “squid,” and
attached English content to a source segment consisting only of 家. Its final
page-edge segment invents an English blank instead of simply preserving the
incomplete sentence. The question section is substantially more coherent, with
appropriate contextual glosses for 自己, 当 and the complete 炒鱿鱼 idiom.

Thus higher technical pass counts do not imply that the sentence translation
feature is solved. Fixed line IDs remove offset arithmetic, but this particular
format duplicates corrected text in both `lines` and `sentences.words`, allowing
contradictions, and still invites OCR-line-based segmentation. A future contract
could use stable IDs for locally formed sentence/paragraph units and only one
source-bearing token sequence per unit, deriving corrections directly from it.
That is a proposed next experiment, not something silently applied to this run.

Pro Thinking also exhausted all 14,000 tokens on PDF 25 with no final answer.

## Measured results

| Model | Thinking | Case | Valid | Seconds | Input | Completion | Reasoning subset | Estimated USD |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| deepseek-flash | off | challenge | yes | 6.5 | 896 | 1547 | 0 | 0.001063 |
| deepseek-v4-pro | off | challenge | yes | 16.0 | 893 | 2204 | 0 | 0.004953 |
| gpt-5.6-luna | off | challenge | yes | 11.5 | 880 | 1461 | 0 | 0.001929 |
| deepseek-flash | off | page26 | yes | 19.7 | 1240 | 6303 | 0 | 0.003893 |
| deepseek-v4-pro | off | page26 | yes | 51.2 | 1237 | 8256 | 0 | 0.017163 |
| gpt-5.6-luna | off | page26 | yes | 36.8 | 1245 | 5570 | 0 | 0.006995 |
| deepseek-flash | off | page25 | no | 16.8 | 1220 | 5676 | 0 | 0.003513 |
| deepseek-v4-pro | off | page25 | no | 40.8 | 1217 | 6201 | 0 | 0.012673 |
| gpt-5.6-luna | off | page25 | no | 30.8 | 1206 | 4130 | 0 | 0.005257 |
| deepseek-flash | on | challenge | no | 38.1 | 921 | 8158 | 6605 | 0.005033 |
| deepseek-v4-pro | on | challenge | yes | 86.4 | 972 | 8676 | 6310 | 0.017820 |
| gpt-5.6-luna | on | challenge | yes | 17.2 | 880 | 1910 | 386 | 0.002468 |
| deepseek-flash | on | page25 | no | 63.4 | 1245 | 13999 | 13999 | 0.008511 |
| deepseek-v4-pro | on | page25 | no | 163.8 | 1296 | 14000 | 14000 | 0.028575 |
| gpt-5.6-luna | on | page25 | yes | 38.1 | 1206 | 4953 | 753 | 0.006245 |

All DeepSeek calls started off-peak. All 15 requested/returned model IDs match.
All source objects match the original benchmark; per-case messages are identical
across models and settings.

| Model | Prior technical passes | New technical passes | New run total USD |
| --- | ---: | ---: | ---: |
| deepseek-flash | 2/5 | 2/5 | 0.022012 |
| deepseek-v4-pro | 2/5 | 3/5 | 0.081185 |
| gpt-5.6-luna | 1/5 | 4/5 | 0.022895 |

Total estimated cost: **$0.126092** for 15 new calls.

Luna now has the highest technical pass count in this sample, but no model
has demonstrated reader-ready translations across both real pages. In particular,
Luna medium passes the exercise alignment checks while failing the qualitative
sentence-translation review. These results do not justify an automatic whole-book
run or a confident overall model ranking.

Follow-up: [48k-token retest](line-benchmark-48k.md) completed successfully for both DeepSeek models on the exercise page. Their earlier 14k outcomes were budget-limited.
