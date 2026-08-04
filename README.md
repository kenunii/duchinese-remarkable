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
investigated. A synthetic native AppLoad frontend now builds and runs inside the
standard reMarkable UI. No credentials or proprietary DuChinese content are
included.

The current UI is a synthetic interaction prototype. It demonstrates native
AppLoad integration, Chinese rendering, and tap-to-show pinyin and meaning; it
does not yet sign in to DuChinese or download stories.

## Quick setup on reMarkable 2

This is unofficial software which modifies the running reMarkable UI. Make sure
SSH access works and keep a recovery path before installing community software.
The tested combination is reMarkable 2 software 3.27.3, Xovi 0.3.3, and AppLoad
0.5.3. Other versions may need adjustments.

### Prerequisites

1. Install [Xovi](https://github.com/asivery/xovi) on the tablet.
2. Install AppLoad and its `qt-resource-rebuilder` dependency by following the
   [AppLoad documentation](https://github.com/asivery/rm-appload).
3. On the computer, install Git, OpenSSH, and Qt 6's `rcc` resource compiler.
4. Connect the rM2 over USB and verify SSH:

   ```sh
   ssh root@10.11.99.1 true
   ```

### Install

```sh
git clone https://github.com/kenunii/duchinese-remarkable.git
cd duchinese-remarkable
scripts/install-appload-rm2.sh
```

If the tablet uses an SSH alias or a Wi-Fi address, pass it explicitly:

```sh
scripts/install-appload-rm2.sh remarkable
```

If `rcc` is installed outside `PATH`, point the build at it:

```sh
RCC_BIN=/path/to/qt6/rcc scripts/install-appload-rm2.sh
```

The installer builds the resource bundle, copies it to
`/home/root/xovi/exthome/appload/duchinese`, and restarts `xochitl`. Unlock the
tablet, open AppLoad from the main UI, and tap **DuChinese**. Tap a Chinese word
to show its pinyin and synthetic English meaning. Use AppLoad's top-edge gesture
or the button at the bottom to close it.

Running the same installer again updates the existing installation.

### Troubleshooting

- No DuChinese entry: confirm that Xovi, `qt-resource-rebuilder`, and AppLoad
  load successfully, then restart `xochitl`.
- SSH fails: enable USB web interface/developer access on the tablet and verify
  that `10.11.99.1` is reachable.
- Build cannot find `rcc`: install Qt 6 development tools or set `RCC_BIN`.
- To inspect AppLoad startup errors:

  ```sh
  ssh root@10.11.99.1 journalctl -u xochitl -n 100 --no-pager
  ```

## Architecture

The working integration lives in `packaging/appload-native`. It is a native
AppLoad frontend rendered inside `xochitl`, so it does not compete with the
reMarkable UI for the physical E Ink framebuffer.

Build only the AppLoad package with:

```sh
scripts/build-appload-native.sh
```

The generated `manifest.json` and `resources.rcc` are written to
`build/appload-native`.
