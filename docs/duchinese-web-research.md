# DuChinese Web App: read-only technical survey

Status: 2026-08-04

This document records a read-only inspection of resources that the current DuChinese web application delivers through ordinary public and entitled-account use. It is intended to guide a personal, unofficial client.

No authentication controls, paywall, DRM, CAPTCHA, or other access restrictions were bypassed. No state-changing request was sent. No DuChinese text, credentials, session material, or downloaded assets are stored in this repository.

## Executive summary

The web reader is a server-rendered Ruby-on-Rails-style application enhanced by a Vite-built Vue 3 single-page interface. It uses Pinia for client state and Axios for HTTP requests. The application exposes conventional same-origin REST routes rather than an observed GraphQL endpoint.

The most useful discovery is that a readable lesson is not reconstructed from HTML or OCR. Its page metadata contains a `crd_url`, and that URL returns ordinary JSON containing already segmented words, simplified and traditional Hanzi, Pinyin, contextual meanings, grammar references, sentence boundaries, sentence translations, and syllable timing data. Lesson audio is a separate MP3 URL. This is almost exactly the neutral input model needed by an e-ink reader.

Public list responses mark inaccessible lessons as locked, and the Vue reader deliberately does not fetch `crd_url` when `lesson.locked` is true. Entitled-account verification confirmed that accessible premium lessons use the same reader-data shape as public lessons.

## Verified from live responses

### Hosts and delivery

- Main application and same-origin REST routes: `https://duchinese.net`
- Static application bundles, lesson data, audio, and images: `https://static.duchinese.net`
- The checked `.crd` response was delivered through CloudFront from Amazon S3 and advertised `ETag`, `Last-Modified`, and byte-range support.
- The main site identifies an nginx front end. Responses expose Rails-characteristic details such as an encrypted `_reader-server_session` cookie, Rails route helpers, authenticity tokens, `X-Request-Id`, and `X-Runtime`.

Sources inspected:

- <https://duchinese.net/lessons>
- <https://duchinese.net/lessons/248-how-much-is-this>
- <https://duchinese.net/accounts/sign_in>
- Public Vite modules under <https://static.duchinese.net/vite/assets/>

### Frontend stack

- Vite production bundles with content-hashed names
- Vue 3 and Vue Router
- Pinia stores named `user`, `lessons`, and `readingScreen`
- Axios for requests
- Rails-generated JavaScript route helpers
- Cookie-backed reader preferences through `js-cookie`
- Bootstrap UI components
- Sentry and New Relic instrumentation

No source maps were available at the conventional `<bundle>.js.map` URLs for the representative bundles checked; all returned `404`.

### Public REST routes

The following routes are present in the normally delivered route-helper bundle. Only GET requests to public/list resources were exercised.

Read-oriented routes:

| Route | Observed purpose |
| --- | --- |
| `GET /lessons/top.json` | Homepage/library sections and categories |
| `GET /lessons/latest.json` | Paginated newest lessons |
| `GET /lessons/free.json` | Free lessons |
| `GET /lessons/search.json?q=...` | Paginated search |
| `GET /lessons/:friendly_id` | Server-rendered lesson metadata and reader boot data |
| `GET /lessons/:friendly_id/navigation.json` | Previous/next navigation; inferred from route name |
| `GET /lessons/courses/:id` | Course metadata/page |
| `GET /lessons/saved.json` | Saved lesson list; login-dependent |
| `GET /lessons/studied.json` | Studied lesson list; login-dependent |
| `GET /lessons/:friendly_id/ratings.json` | Rating/comment data |
| `GET /flashcards/list.json` | Saved words |
| `GET /flashcards/status.json` | Review counts |
| `GET /flashcards/chart_data.json` | Saved-word history |
| `GET /flashcards/dict/:text.json` | Dictionary lookup |
| `GET /flashcards/definition/:id.json` | Definition lookup |
| `GET /grammar` and `/grammar/:slug` | Grammar index/detail |

State-changing routes also exist for saving/studying lessons, flashcards, review answers, ratings, and feedback. They were identified only from code and were not called. A first client should remain read-only until the retrieval model is stable.

No GraphQL URL, GraphQL client, or GraphQL operation was found in the inspected HTML and representative Vite modules.

### Library and lesson metadata

`GET /lessons/top.json` returned an object with:

```text
sections[]
  section_id
  section_name
  display
  item_type
  items[]
  more_url
more_categories[]
```

Individual items are either lessons or course-like entries. Observed lesson metadata fields include:

```text
id
title
level
synopsis
note
release_at
release_at_formatted
updated_at
free
locked
path
canonical_url
audio_url
crd_url
thumb_image_url
medium_image_url
large_image_url
author
has_course
course
course_group
course_path
course_position
course_title
course_type
```

Course objects include:

```text
id
title
description
group
type
levels[]
lesson_count
placeholder_count
release_at
path
lessons_url
lessons_canonical_path
document_ids
documents
medium_image_url
large_image_url
is_new
```

Pagination responses such as `latest.json` and `search.json` use:

```text
lessons[]
next_page_url
```

### Reader data (`.crd`)

For an unlocked public lesson, the server-rendered page sets a `window.lesson` object containing `crd_url`. The Vue reader performs an Axios GET against that URL. Although its HTTP content type is `application/x-mscardfile`, the body inspected was plain JSON.

Top-level shape:

```text
{
  version: integer,
  synopsis: string,
  words: array,
  sentence_indices: integer array,
  sentence_translations: string array,
  syllable_times: number array
}
```

Observed compact word fields and their expanded meaning in the delivered JavaScript:

| Wire field | Meaning |
| --- | --- |
| `hanzi` | Simplified text for this token |
| `tc_hanzi` | Traditional text for this token |
| `pinyin` | Space-separated syllables; absent for symbols |
| `meaning` | Contextual word meaning |
| `hsk` | HSK level |
| `g` | Grammar-point identifier |
| `gh` | Grammar highlight hidden flag; supported by parser but not present in the checked sample |
| `l` | Simplified lemma override; supported by parser |
| `lt` | Traditional lemma override; supported by parser |
| `k` | Lemma Pinyin override; supported by parser |
| `d` | Dictionary identifier; supported by parser |
| `o` | Highlight offset; supported by parser |

The client-side `LessonData` class:

- assigns each token an ordinal ID;
- treats a missing `pinyin` as a symbol;
- derives syllable count from Pinyin;
- maps `syllable_times` to non-symbol word playback positions;
- adds start/end sentinels around `sentence_indices`;
- retains `sentence_translations` alongside those boundaries.

This makes tap lookup straightforward on reMarkable: layout the existing tokens, retain their rectangles, then map touch coordinates back to a token. No Chinese tokenizer is required for DuChinese material.

### Audio and visual assets

- Lesson narration is exposed through `lesson.audio_url` and, in the checked public lesson, was an MP3 on `static.duchinese.net`.
- Word-to-audio synchronization uses the `.crd` `syllable_times` array.
- Lesson and course covers are static JPEG URLs at paths shaped like `/documents/<id>/<hash>.jpg` and `/courses/<id>/<hash>.jpg`.
- Assets use hashed filenames or version query strings, suitable for immutable/local caching keyed by the full URL or response ETag.

### Authentication and session behavior

The official sign-in page uses a standard HTML form:

```text
POST /accounts/sign_in
account[email]
account[password]
authenticity_token
```

Verified response/session properties:

- Cookie name: `_reader-server_session`
- Flags: `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`
- Rails-style CSRF token is emitted as `<meta name="csrf-token">`.
- The frontend explicitly supplies `X-CSRF-Token` for at least one JSON POST operation.
- The authenticated UI state is initialized from `data-*` attributes on `#vue-root`, including `signedIn`, `subscribed`, `userGroup`, and email when present.
- Saved/studied IDs and flashcard data may be injected into page globals for hydration.

Because the session cookie is `HttpOnly`, browser JavaScript cannot read it. A native client should not ask users to copy credentials or scrape the password form. Safe designs include a local browser-assisted login flow that captures the final cookie in its own cookie jar or an explicit local session import. Ordinary authenticated navigation can rotate the cookie, so the client must persist replacements atomically.

### Offline and caching behavior

No application service worker, Cache Storage usage, IndexedDB usage, `localStorage`, or `sessionStorage` usage was found in the inspected public HTML and representative Vite modules.

The checked implementation instead appears to rely on:

- normal browser HTTP caching for hashed Vite assets;
- HTTP caching/ETags for `.crd`, MP3, and images;
- transient Pinia state;
- browser history state for page restoration;
- ordinary cookies for preferences such as Pinyin display, character set, font sizes, grammar highlights, filters, and playback settings.

Therefore there is no evidence yet that the web app itself maintains a durable offline lesson library. This is a negative observation from the inspected bundles, not proof across every lazy-loaded feature.

## Remaining inferences from delivered bundles

- Saved and studied state is represented primarily as sets of lesson IDs hydrated into the user store.
- “Progress” on the web appears to mean studied/saved lesson state, course position/navigation, and flashcard review state. No per-character scroll position or precise audio position synchronization endpoint has been observed.
- Premium `.crd` and MP3 asset URLs may change or expire even when a currently returned URL works without an authentication header. A client must not assume that a URL can be shared or cached indefinitely.

## Entitled-account verification (2026-08-04)

Ordinary entitled-account behavior was observed interactively in the official
web application. The network capture remains local outside the repository;
only its structure and behavior are recorded here.

Verified findings:

- `GET /lessons/top.json` works with the Rails session cookie and returns the
  account's available library sections and categories.
- Lesson objects use the same metadata shape found during public research.
- An observed entitled premium lesson returned `free: false`, `locked: false`,
  and usable `crd_url`, `audio_url`, and image URLs.
- Premium `.crd` uses the same schema as public content, including token,
  sentence-boundary, translation, and syllable-timing data.
- `.crd` and MP3 requests to `static.duchinese.net` included neither the Rails
  cookie nor an Authorization header. These asset URLs must nevertheless only
  be consumed when returned normally for an entitled lesson; the client must
  never construct or probe them.
- Asset URLs included query strings and ETags. The complete returned URL and
  ETag should be treated as cache identity; query parameters must not be
  stripped by the client.
- Ordinary authenticated GET navigation returned a new
  `_reader-server_session` cookie. The client must apply and atomically persist
  session rotation after every response.
- Explicitly selecting "mark read" generated
  `POST /lessons/:id/studied`; selecting "read" again to undo it generated
  `DELETE /lessons/:id/studied`. These requests were user-triggered and were
  not caused automatically by opening or leaving a lesson. The client mirrors
  this boundary by synchronizing studied state only after an explicit action.

The authenticated `/lessons` page exposed `data-signed-in`, `data-subscribed`,
and user hydration state. It hydrated studied and saved ID sets but did not
embed the library itself; the library is obtained through the JSON routes.

## Open questions

1. Are premium `.crd`, audio, and image URLs signed or short-lived in any deployment?
2. Can an account require an external identity-provider flow rather than email/password?
3. Is there a read-only endpoint for current reading position, or only binary studied state?
4. Do `.crd` schema versions or optional token keys vary across levels and old/new content?
5. Are audio timings always per syllable, and how are pauses or multi-character readings represented?
6. Does the web client ever cache lesson bodies beyond the current in-memory reader state?

## Implementation boundary

Keep DuChinese transport separate from the reMarkable UI:

```text
DuChineseSession
  -> listLibrary(filters, cursor)
  -> getLessonMetadata(id)
  -> getReaderData(crdUrl)
  -> getAudio(audioUrl)

DuChinese mapper
  -> NeutralBook / Chapter / Sentence / Token model

reMarkable reader
  -> local cache
  -> pagination and token rectangles
  -> tap-to-Pinyin / contextual meaning
  -> sentence translation
  -> optional synchronized audio
```

Initial robustness rules:

- Honor `locked`; never probe or construct hidden asset URLs.
- Follow only URLs returned to the authenticated account by normal read requests.
- Validate MIME type and JSON schema before caching.
- Preserve unknown fields and record `.crd` version for forwards compatibility.
- Cache by canonical lesson ID plus `updated_at`, URL version, or ETag.
- Keep session state outside the repository with mode `0600`.
- Never log cookies, CSRF tokens, full response bodies, or proprietary lesson text.
- Use anonymous hand-authored fixtures in tests.
- Send progress or library-state writes only after an explicit user action, and
  keep unrelated rating and flashcard operations out of scope.

## Public product references

DuChinese publicly describes the web reader as supporting instant word translations, complete sentence translations, and synchronized human audio:

- <https://duchinese.net/blog/2018/01/22/45-announcing-du-chinese-for-the-web/>
- <https://duchinese.net/blog/2016/01/08/12-du-chinese-for-android-released/>
