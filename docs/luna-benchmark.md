# Luna versus DeepSeek annotation experiment — 2026-09-16

Five live calls to `gpt-5.6-luna`, which was also the returned model ID. These
replay the exact stored system/user messages and source from the
[DeepSeek experiment](deepseek-benchmark.md); message equality was checked for
all five requests. Same Chat Completions JSON mode, schema in prompt, production
local validator, 14,000 completion-token cap including reasoning, no retries or
repairs, maximum two concurrent requests. This does not test OpenAI strict
Structured Outputs or the production Responses endpoint.

Luna used reasoning `none` on all three cases, then `medium` on challenge and
page25. Temperature 0 for `none`, omitted for `medium`; DeepSeek Thinking used
its provider default effort. Reasoning settings and tokenizers are not identical
across providers. Each cell is one trial, so timings and pass fractions are
observations, not statistically reliable model rankings.

## Measured comparison

Costs are USD from returned usage and current standard tariffs, including
reasoning and cache writes. DeepSeek costs use the earlier off-peak runs.

| Case / reasoning | Luna valid / seconds / USD | Flash valid / seconds / USD | Pro valid / seconds / USD |
| --- | --- | --- | --- |
| Challenge / off | yes / 16.6 / 0.001905 | no / 5.4 / 0.000981 | no / 18.2 / 0.005880 |
| PDF 26 / off | no / 49.7 / 0.006222 | yes / 17.9 / 0.003534 | yes / 48.5 / 0.016620 |
| PDF 25 / off | no / 35.5 / 0.004776 | no / 19.4 / 0.002382 | no / 35.7 / 0.011103 |
| Challenge / on | no / 23.4 / 0.003226 | yes / 30.1 / 0.004350 | yes / 77.4 / 0.014668 |
| PDF 25 / on | no / 43.4 / 0.006330 | no / 62.1 / 0.008497 | no / 151.0 / 0.028676 |

Luna: **1/5 technically valid, $0.022459 total**. Flash: 2/5, $0.019744.
Pro: 2/5, $0.076947. Passing validates structure and source alignment, not
translation accuracy. Every rejected answer remains rejected in these results.

Luna token counts (input / completion / reasoning subset):

- Challenge none: 1,044 / 1,370 / 0.
- PDF 26 none: 1,379 / 4,898 / 0.
- PDF 25 none: 1,349 / 3,699 / 0.
- Challenge medium: 1,044 / 2,471 / 1,072.
- PDF 25 medium: 1,349 / 4,994 / 1,481.

All Luna responses finished normally; none hit the token cap. All reported
standard service tier and zero cache-read tokens; input details itemized cache
writes (1,041, 1,376, 1,346, 1,041, 1,346 tokens respectively).
The script was updated to account for those itemized writes after the run;
result/summary cost metadata was recalculated without making additional calls.
Raw provider responses and answers are unchanged.

## What the answers actually did

**Challenge, no reasoning:** Luna corrected 自已 → 自己 at the right offset 4.
It retained legitimate 已经 and 巳时 and gave appropriate contextual readings
for 教, 银行, 行长, 行不行, 得, 音乐 and 快乐. Counts and negation were preserved.
Both DeepSeek models failed the correction record on this case without Thinking.

**Challenge, medium:** Luna returned the same intended text correction but
reported offset 3 instead of 4, causing rejection. Extra reasoning did not
improve this trial. Both DeepSeek Thinking runs passed this case.

**PDF 26, no reasoning:** Luna preserved the source-word text exactly and
translated the 35.7% income claim omitted by Pro. However, it emitted a bogus
correction record `力 → 努` at offset 0, outside the permitted confusion groups.
Its own reason said the fragment should be preserved, and the actual word text
remained 力. The validator correctly rejected this internally inconsistent
answer. It also translated survey nonresponse 没有选择 as “had no choice,”
which misrepresents the context, and grouped several complete sentences into
large segments, making sentence-level translation less convenient.

**PDF 25, no reasoning:** Luna included the right correction at offset 123 but
also an invalid no-op 自 → 自 at 122. It inserted nine literal `[blank]`
markers into source-word text, which must remain aligned to the PDF. Some
English exercise text was awkward, including a literal “squid” rendering of a
fragment of the firing idiom. These issues extend beyond counting offsets.

**PDF 25, medium:** Luna returned an answer within budget, whereas both
DeepSeek Thinking runs used all 14,000 tokens without a final annotation.
But Luna reported correction offset 122 instead of 123, omitted the source
clause 刘天明在学校工作, and inserted an extra 的. This is still unusable for
our aligned PDF layer. The omissions are in both word coverage and translation.

## Conclusion and evidence

This sample gives no reason to prefer Luna over Flash for the current contract.
Luna did better on the small no-reasoning challenge and spent far fewer reasoning
tokens, but it failed both real pages. On the dense page it was about 1.8 times
as expensive and 2.8 times as slow as Flash. Neither is ready for unattended
whole-book conversion. Local derivation of correction positions remains useful,
but source omissions, insertions and contradictory correction records must
still be rejected; fixing offsets alone would not fix these Luna outputs.

No production model or prompt was changed. Reproduction script:
`pdf-import/experiments/luna_benchmark.py`. Requests, sources, raw responses,
answers, validation results and text differences are retained in ignored
`build/luna-benchmark/` and copied to `tests/luna-benchmark/`. Credentials were
read into memory through the existing remote credential location, never logged
or stored in the repository.

Pricing reference: [OpenAI API pricing](https://developers.openai.com/api/docs/pricing),
standard short-context Luna rates per million tokens: input $0.20, cache read
$0.02, cache write $0.25, output $1.20. These are usage-based estimates, not a
billing export. Model and effort support:
[Luna model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-luna).

Follow-up: [retest with line IDs and clearer blank instructions](line-benchmark.md).
