# Chinese PDF Reader — Android and iOS

An offline Kotlin Multiplatform / Compose reader dedicated to the existing
Contemporary Chinese 4 collection (currently PDF pages 1–50). Shared Kotlin code
handles page rendering, gestures, contextual lookup, sentence translation and
reading position. Platform entry points only host that shared UI.

- Swipe left/right at page-fit size to turn pages.
- Pinch to zoom (up to 6×); drag to pan while zoomed.
- Pinch inward to return to page-fit size. Double-tapping does not change zoom.
- Pages follow your finger while dragging, then snap using the built-in horizontal pager.
  Short slow drags snap back; flicks advance one page. A bottom page indicator briefly appears.
- Tap a Chinese word for pinyin and contextual meaning in a nearby popup.
  Tap anywhere on the popup to dismiss it.
- Toggle the top translation bar to show its sentence translation.
- The last page persists locally, keyed by the original PDF hash.

The original 240-DPI page rasters and existing word/sentence annotations are
bundled locally. This is a viewer for that prepared PDF collection, not a generic
PDF importer. The exporter reuses the reMarkable display-crop algorithm and
original image coordinates. It does not run OCR or call an LLM. The pager prepares adjacent page bitmaps for live dragging; page data is loaded once.

## Prepare private content

From the repository root, using the existing validated dataset:

```sh
python3 scripts/prepare-mobile-textbook.py build/textbook-first50
```

Generated `composeResources/files/textbook/` is ignored by Git. A fresh source
clone needs this export or a private copy of an existing bundle before building.
No credentials, network access, or server are needed by the installed app.

## Android

Use JDK 17 or newer and Android SDK 36. Set `sdk.dir` in ignored
`mobile/local.properties`, or set `ANDROID_HOME`.

```sh
cd mobile
./gradlew :composeApp:assembleDebug :composeApp:testDebugUnitTest
./gradlew :composeApp:connectedDebugAndroidTest  # emulator/device required
./gradlew :composeApp:installDebug
```

APK: `composeApp/build/outputs/apk/debug/composeApp-debug.apk`.
Application ID: `org.duchinese.reader`; it is separate from the reference app.

## iOS

On macOS with Xcode and JDK 17, open `iosApp/iosApp.xcodeproj`, choose `iosApp`,
and run on a simulator. The Xcode build phase builds and embeds the shared Kotlin
framework and bundled Compose resources. No signing identity is stored here.
A physical iPhone build requires selecting your development team in Xcode.

From a Linux host with SSH access to the build Mac:

```sh
MAC_SSH_PORT=22 scripts/build-ios.sh user@build-mac
```

The helper syncs this mobile subproject to `chinese-reader-mobile` in the remote
home directory, runs the shared tests on the Intel simulator target, and builds
an unsigned simulator app. `MAC_WORKDIR` and `MAC_SSH_PORT` override its destination.
It returns `build/releases/ChineseReader-simulator.tar.gz`. Store publication and
TestFlight signing are intentionally separate from this local test build.

## Why shared code

The existing deployment reference uses Kotlin Multiplatform and Compose, so this
subproject follows its toolchain while keeping its own application identity and
build directories. UI, hit testing and gestures live in `commonMain`; shared tests
exercise cropped/zoomed coordinates, pan limits and swipe boundaries.
Android instrumentation additionally drives real taps, swipes and pinch gestures,
checks movement before finger release, and verifies that short drags snap back
without changing the saved page.
An Android pass is useful evidence, but iOS compilation and runtime checks are
still needed for packaging, platform fonts and touch behavior.

Resource packaging follows the [Compose Multiplatform resource documentation](https://kotlinlang.org/docs/multiplatform/compose-multiplatform-resources-usage.html).

### App Store / TestFlight packaging

`iosApp` has a shared archive scheme, an opaque 1024px app icon, and a privacy
manifest. The app saves reading position in its own UserDefaults domain, collects
no data, and declares the file metadata and timing APIs used by Compose. See the
[Kotlin privacy manifest guidance](https://kotlinlang.org/docs/multiplatform/multiplatform-privacy-manifest.html).

On the build Mac, install an App Store distribution profile for
`org.duchinese.reader` and make its matching Apple Distribution private key
available in an unlocked signing keychain. Sync `mobile/` including its ignored
textbook bundle, then run:

```sh
IOS_TEAM_ID=YOUR_TEAM_ID \
IOS_PROFILE_NAME='YOUR_APP_STORE_PROFILE' \
IOS_VERSION_NAME=0.1 IOS_BUILD_NUMBER=1 \
  scripts/archive-ios.sh
```

The signed IPA is written to
`build/ios-release/0.1-1/export/ChineseReader.ipa`. The script prints its SHA-256.
Version and build number are explicit; increase the build number for each upload.
The script uses manual distribution signing and does not modify keychain settings.
Set `IOS_SIGNING_IDENTITY` to a certificate SHA-1 fingerprint when the host has
multiple distribution identities. Unlock its keychain in the same SSH session
as the archive command.

Once the App Store Connect app record exists, set `IOS_UPLOAD=1`,
`APPSTORE_API_KEY_ID` and `APPSTORE_ISSUER_ID` to validate and upload after export.
The API private key belongs in the build user's
`~/.appstoreconnect/private_keys/AuthKey_<key-id>.p8`, never in this repository.
Upload success must be followed by checking TestFlight processing and assigning
an internal testing group in App Store Connect.

## Source layout and diagnostics

`ReaderApp.kt` owns loading, paging, translation and saved reading position.
`ReaderPage.kt` owns page rendering, touch handling and the contextual popup.
`Book.kt` contains the data contract and coordinate calculations.

Gesture traces are enabled only in Android debug builds. Shared code defaults to
logging disabled, including the iOS host. Traces contain page/gesture state, not
word text or translations. Capture them outside Git with:

```sh
scripts/trace-gestures.sh DEVICE_SERIAL > build/gesture-trace.log
```

Build outputs, Gradle caches, private textbook resources and signing material are
ignored. Build directories should be ordinary local directories; no machine-specific
cache symlinks or credentials are required by the source tree.

To upload an existing IPA without rebuilding it, run on the Mac with the same
API environment variables set:

```sh
scripts/upload-ios.sh build/ios-release/0.1-1/export/ChineseReader.ipa
```

This checks the bundle identifier before sending the IPA to Apple.
