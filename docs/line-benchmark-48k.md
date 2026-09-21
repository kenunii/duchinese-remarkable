# DeepSeek Thinking with 48k tokens — 2026-09-16

Two new live calls on PDF page 25, one each to `deepseek-flash` and
`deepseek-v4-pro`, with Thinking enabled and the same line-ID contract.
The saved API request objects were compared against the preceding 14k run:
**only `max_tokens` changed, from 14,000 to 48,000.** Input, system prompt,
JSON mode, temperature and Thinking setting were identical. No retries,
answer repair, or validation relaxation. One trial per model.

The local HTTP timeout was raised from 240 to 900 seconds to avoid censoring
longer generations. It does not change model behavior or reasoning effort.
The production importer configuration is unchanged.

Reproduction is in [experiments/README.md](../pdf-import/experiments/README.md).
Artifacts are under ignored `build/line-benchmark-48k/`, retained also in
`tests/line-benchmark-48k/`. The previous run is documented in
[the line-ID comparison](line-benchmark.md).

Costs are estimates from returned token usage, including all reasoning tokens,
and the [DeepSeek rate card](https://api-docs.deepseek.com/quick_start/pricing/)
checked on the run date. Peak/off-peak selection is recorded per request.

## Flash inspection

Flash completed normally and passed the unchanged validator: all line IDs,
source characters and word coverage are retained, with exactly the expected
已 → 己 correction at offset 123. No `[blank]` markers were inserted in Chinese.
It used 27,319 completion tokens, including 22,837 reasoning tokens, and took
111.1 seconds. This directly demonstrates that the prior 14k budget censored
this case; failure to finish at that budget was not evidence of inability.

Sentence grouping is much more coherent than Luna medium's earlier exercise
output: Flash keeps complete exercise sentences together and correctly joins
the final paragraph across OCR line wraps. Questions are translated sensibly;
the complete 炒鱿鱼 idiom has contextual pinyin and a firing/dismissal gloss.

Remaining semantic issues: several printed exercise blanks disappear in English
(e.g. before 同学, before 老板, and after 开一); the incomplete firing idiom is
rendered awkwardly as “[blank]ed the boss (squid),” and the salary comparison is
literal and unclear. Some glosses still include irrelevant dictionary senses
(e.g. “fire; stir-fry” for the contextual firing occurrence). Thus technically
valid does not mean all exercise translations are ready for the reader.

## Pro inspection and measured comparison

Pro also completed normally and passed every unchanged technical check, with
exactly the expected correction at offset 123 and no other source changes.
It used 28,669 completion tokens (22,590 reasoning) in 278.7 seconds.
It splits questions and their following “Why?” into individual sentences and
keeps the exercise sentences intact, avoiding the earlier wrap-based fragments.
Contextual firing glosses are more focused than Flash's, but exercise translations
still omit some blank markers, literally mistranslate the incomplete firing idiom
(“[blank] the boss as squid”), and render the salary comparison awkwardly.
There is no compelling overall semantic quality advantage in this one sample.

| Model | Budget | Finish | Technical validation | Completion tokens | Reasoning subset | Seconds | Estimated USD |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: |
| Flash | 14,000 | length; no final answer | incomplete | 13,999 | 13,999 | 63.4 | 0.008511 |
| Flash | 48,000 | stop | pass | 27,319 | 22,837 | 111.1 | 0.016428 |
| Pro | 14,000 | length; no final answer | incomplete | 14,000 | 14,000 | 163.8 | 0.028575 |
| Pro | 48,000 | stop | pass | 28,669 | 22,590 | 278.7 | 0.056803 |

Both new calls started off-peak and returned the requested model IDs. Total
estimated cost of these two calls: **$0.073231**. Cache hits were 1,024 input
tokens for Flash and 1,280 for Pro; full raw usage is retained in the artifacts.

**Conclusion:** raising the budget solved the completion failure for both models
on this page. Neither needed all 48k tokens. Both now preserve alignment and
produce better sentence boundaries, but the English for incomplete exercise
sentences still needs improvement. The former 14k failures should be described
as budget-limited outcomes, not evidence that the models cannot do the task.
This is one new sample per model; it does not establish a general success rate
or prove 48k is necessary. The observed outputs would fit below 32k, but a
32k request was not run and could produce a different generation.
