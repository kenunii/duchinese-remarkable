# DeepSeek annotation experiment — 2026-09-16

This is a small live comparison for the local PDF importer, not a general model
ranking. Requests use the production compact text/offset/gap prompt and the
production annotation validator. No rejected response was repaired and counted
as a success. The production provider remains unchanged.

## Models and pricing

The live `/models` endpoint exposed `deepseek-flash` and `deepseek-v4-pro`.
Responses returned those same IDs. The current official pricing table identifies
these as V4.1 Flash and V4 Pro 0813 respectively; V4.1 Pro was not offered.

The September 10 announcement said Pro would route to Flash after September 14.
The freshly retrieved pricing page instead explicitly says the V4 Pro service
continues with its original billing. We use the current table and record both
requested and returned IDs, but those IDs cannot independently prove which
weights served a request. See [current pricing](https://api-docs.deepseek.com/quick_start/pricing/)
and the [earlier announcement](https://www.deepseek.com/en/news/deepseek-v4-1-flash/).

Off-peak USD per million tokens:

| API model | Cached input | Uncached input | Output |
| --- | ---: | ---: | ---: |
| deepseek-flash | 0.003 | 0.15 | 0.60 |
| deepseek-v4-pro | 0.022 | 0.66 | 1.98 |

Peak rates are twice these. Peak windows are weekdays 01:00–04:00 and
06:00–10:00 UTC. The calls here started off-peak. Reported costs are estimates
from returned token usage and the published rate card, not a billing export.
Cached input and all completion tokens, including reasoning, are included.

## Protocol

Ten calls: three cases on both models without Thinking, then the two difficult
cases on both models with Thinking. The latter are separate experiments, not
an automatic repair loop. Two concurrent requests maximum, no automatic retries,
14,000 completion tokens per request, 240-second HTTP timeout. Thinking effort
is the provider default, not explicitly tuned. Temperature 0 is sent; its
behavior in Thinking mode is provider-controlled.

DeepSeek [JSON mode](https://api-docs.deepseek.com/guides/json_mode/) ensures JSON,
not our exact schema. The schema and an illustrative example are included in
the system prompt, and local validation enforces the contract. This differs from
OpenAI's server-side strict schema mode. No OpenAI model was called in this test.

Cases:

- **Challenge:** seven synthetic sentences, including one intentional 自已 typo,
  legitimate 已经 and 巳时, contextual readings of 教/行/得/乐, negation, and
  three versus thirteen. The correction must target original offset 4.
- **PDF 26:** dense prose and percentages, 477 prepared characters including
  punctuation and digits; no OCR correction required.
- **PDF 25:** questions, exercise blanks and prose, 321 prepared characters;
  one expected 自已 → 自己 correction at original offset 123.

Private source and raw results are in ignored `build/deepseek-benchmark/`, with
Thinking runs in its `thinking/` subdirectory. Credentials were read in memory
from the existing remote credential file documented by the user's other project;
no key was printed or written into this repository. Reproduction is documented
in [experiments/README.md](../pdf-import/experiments/README.md).

## Qualitative inspection

Both non-thinking models produced broadly sensible translations and the expected
polyphonic readings on the challenge. However, both returned an invalid
correction record: Pro used offset 3 instead of 4; Flash gave a no-op 自 → 自
record while silently changing 已 to 己 in the words. Both were rejected.

On PDF 25 without Thinking, both again gave wrong correction offsets (Flash
119, Pro 121, expected 123). Flash additionally inserted eight literal `[blank]`
markers into the source-word text, totaling 56 extra characters, despite the
instruction to use placeholders only in translations. Pro preserved the source
word text, but split the exercise into fragments and repeated/invented context
in their translations. The exercise translations were not ready for use.

On PDF 26 both passed all technical checks. Flash retained the percentage claims
in its translations. Pro omitted the entire 35.7%-of-residents/income claim from
the translation of the segment that contains it. This is a concrete example of
semantic failure that a source-alignment validator does not detect. Some Flash
word glosses were awkward (for example its explanation of 都 in the comparison).
Neither output is certified publication-quality.

Thinking made both challenge correction records valid, preserved 已经 and 巳时,
and produced appropriate contextual readings of 银行/行长/行不行, 得 and 音乐/快乐.
Flash used 5,515 reasoning tokens and Pro 4,962 on that short challenge. This is
substantial overhead for a simple annotation task, even though the dollar cost
is small.

The experiment exposes a weakness in our current contract: models must count
absolute character offsets for corrections, even though normal word offsets are
computed locally. A promising next change is to derive correction positions by
comparing the original and annotated text locally, enforcing equal length and
the visual-confusion allowlist, while retaining the model's correction reasons.
This was NOT applied to these outputs or used to reclassify failed runs.

## Measured results

| Model | Thinking | Case | Seconds | Input tokens | Completion tokens (reasoning included) | Valid | Estimated USD |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: |
| deepseek-flash | disabled | challenge | 5.4 | 1067 | 1369 | no | 0.000981 |
| deepseek-v4-pro | disabled | challenge | 18.2 | 1064 | 2615 | no | 0.005880 |
| deepseek-flash | disabled | page26 | 17.9 | 1383 | 5732 | yes | 0.003534 |
| deepseek-v4-pro | disabled | page26 | 48.5 | 1380 | 7934 | yes | 0.016620 |
| deepseek-flash | disabled | page25 | 19.4 | 1372 | 3815 | no | 0.002382 |
| deepseek-v4-pro | disabled | page25 | 35.7 | 1369 | 5440 | no | 0.011103 |
| deepseek-flash | enabled | challenge | 30.1 | 1092 | 6977 | yes | 0.004350 |
| deepseek-v4-pro | enabled | challenge | 77.4 | 1143 | 7027 | yes | 0.014668 |
| deepseek-flash | enabled | page25 | 62.1 | 1397 | 14000 | no | 0.008497 |
| deepseek-v4-pro | enabled | page25 | 151.0 | 1448 | 14000 | no | 0.028676 |

Total estimated off-peak cost: **$0.096690** for ten requests. Four of ten responses passed the full technical validator. This pass rate describes these selected cases/settings only, not general model accuracy.

Both Thinking runs on PDF 25 exhausted all 14,000 completion tokens in reasoning and produced no final annotation. These are token-budget failures, not graded translations. A larger budget or smaller batches could change the result, but neither was tested.

On the same dense page without Thinking, Flash cost about $0.00353 and took 17.9 s; Pro cost about $0.01662 and took 48.5 s. Flash was about 4.7 times cheaper and 2.7 times faster in that pair, while retaining a claim that Pro omitted.

Recommendation: Flash is the better candidate to continue evaluating for this pipeline. Pro did not demonstrate a quality advantage worth its extra cost in this small sample. Neither configuration is ready for unattended textbook conversion with the current correction-offset contract. Fix local offset derivation and exercise handling before scaling; no agentic repair loop is required for that design change.

All requests and raw answers were preserved unchanged. No credentials are included. A copy of the experiment is retained under ignored `tests/deepseek-benchmark/` so deleting build artifacts does not lose the evidence.

Follow-up: [five Luna calls on the same prompts](luna-benchmark.md).

Follow-up: [retest with line IDs and clearer blank instructions](line-benchmark.md).
