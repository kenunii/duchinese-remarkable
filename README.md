# DuChinese for reMarkable

An unofficial, personal-use DuChinese client for reMarkable tablets.

## Goal

Make it possible to read DuChinese stories on a reMarkable using an existing,
paid DuChinese account while preserving the learning interactions that make the
content useful:

- browse the user's DuChinese library
- read stories in a distraction-free, E Ink-friendly interface
- tap a word to reveal its pinyin and meaning
- tap a sentence to reveal its translation
- optionally show or hide pinyin globally
- cache entitled stories for offline reading
- preserve reading progress and saved vocabulary where practical

This is intended to be an independent client, not a redistribution of
DuChinese content.

## Product idea

The project has two deliberately separate parts:

1. **DuChinese adapter**
   - authenticate using the user's own account
   - access the same data made available to that user by the DuChinese web app
   - map stories, chapters, sentences, tokens, pinyin, translations, and
     progress into a stable internal format

2. **reMarkable reader**
   - render the internal story format for E Ink
   - map touch coordinates to words and sentences
   - show lightweight lookup overlays
   - manage navigation, offline storage, and reading progress

Keeping the boundary between these components means changes to DuChinese's web
application should only require changes to the adapter, not to the tablet UI.

```text
DuChinese web app / API
          |
          v
  DuChinese adapter
          |
          v
 stable local story model
          |
          v
   reMarkable reader
```

## Initial MVP

- sign in without storing a plaintext password
- list available stories from the user's account
- download and locally cache one story
- render Chinese text as paginated content
- tap a token to show hanzi, pinyin, and meaning
- tap a sentence to show its translation
- navigate between pages and remember the current position
- work offline after a story has been cached

The UI can initially be developed against synthetic fixtures while the web
adapter is investigated independently.

## Internal story model

The reader should consume a provider-neutral representation similar to:

```json
{
  "storyId": "example-story",
  "title": "Example title",
  "level": "intermediate",
  "sentences": [
    {
      "hanzi": "我今天坐地铁去上班。",
      "translation": "Today I took the subway to work.",
      "tokens": [
        {
          "hanzi": "地铁",
          "pinyin": "dìtiě",
          "meaning": "subway"
        }
      ]
    }
  ]
}
```

The exact model will be refined after inspecting the data exposed by the web
application.

## Constraints

- Users must authenticate with their own legitimate DuChinese account.
- The client must not bypass subscriptions, DRM, paywalls, or other access
  controls.
- DuChinese stories and proprietary assets must not be committed to this
  repository or redistributed.
- Session tokens and cached content are private local data and must be stored
  with restrictive permissions.
- Public test fixtures must be synthetic or otherwise freely licensed.
- The integration is unofficial and may break when DuChinese changes its web
  application or APIs.
- DuChinese is a trademark of its respective owner; this project is not
  affiliated with or endorsed by DuChinese.

## Open decisions

- target reMarkable model and CPU architecture
- native Qt/QML app versus a community launcher/runtime integration
- whether progress synchronization should initially be read-only or
  bidirectional
- local cache format and encryption expectations
- installation and update mechanism for the tablet application

## Status

The DuChinese web application and the reMarkable 2 rendering stack have been
investigated. A synthetic Qt Quick reader probe now builds and runs on an rM2
using reMarkable's official E Ink backend. No credentials or proprietary
DuChinese content are included.

## Reader development

The first native reader probe lives in `apps/reader`. It targets the official
rM2 SDK matching software 3.27 and uses the device-provided `epaper` Qt platform
and scenegraph backends.

Build it with:

```sh
scripts/build-rm2.sh
```

For a manual device test, copy the binary, Noto Sans SC font, and runner to a
directory under `/home/root`, then run the runner as root. It temporarily stops
`xochitl` and always starts it again when the reader exits.

The current probe exits automatically after three minutes and contains only
synthetic Chinese example text.

The working in-UI integration lives in `packaging/appload-native`. It is a
native AppLoad frontend rendered inside `xochitl`, so it does not compete with
the reMarkable UI for the physical E Ink framebuffer. Build its resource bundle
with:

```sh
scripts/build-appload-native.sh
```

Set `RCC_BIN` if the Qt resource compiler is not available on `PATH`. Copy the
generated `manifest.json` and `resources.rcc` from `build/appload-native` into a
dedicated directory below AppLoad's application root.
