#!/usr/bin/env bash
# Run on the build Mac after syncing mobile/, including its private content bundle.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${IOS_TEAM_ID:?Set IOS_TEAM_ID to your Apple Developer team}"
: "${IOS_PROFILE_NAME:?Set IOS_PROFILE_NAME to the App Store distribution profile name}"
version=${IOS_VERSION_NAME:-0.1}
build=${IOS_BUILD_NUMBER:-1}
[[ "$version" =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ && "$build" =~ ^[1-9][0-9]*$ ]] || { echo 'Invalid version or build number' >&2; exit 2; }
test -f composeApp/src/commonMain/composeResources/files/textbook/book.json || { echo 'Prepare the private textbook bundle first' >&2; exit 1; }
export JAVA_HOME=$(/usr/libexec/java_home -v 17)
export PATH="$JAVA_HOME/bin:$PATH"
out="build/ios-release/$version-$build"
mkdir -p "$out"
# The signing keychain must already be unlocked by the host deployment setup.
xcodebuild -project iosApp/iosApp.xcodeproj -scheme iosApp -configuration Release \
  -destination 'generic/platform=iOS' -archivePath "$out/ChineseReader.xcarchive" \
  -derivedDataPath build/ios-release/DerivedData \
  DEVELOPMENT_TEAM="$IOS_TEAM_ID" CODE_SIGN_STYLE=Manual \
  CODE_SIGN_IDENTITY="${IOS_SIGNING_IDENTITY:-Apple Distribution}" PROVISIONING_PROFILE_SPECIFIER="$IOS_PROFILE_NAME" \
  MARKETING_VERSION="$version" CURRENT_PROJECT_VERSION="$build" \
  DEBUG_INFORMATION_FORMAT=dwarf-with-dsym archive
export IOS_EXPORT_OPTIONS="$out/ExportOptions.plist"
python3 - <<'PY'
import os, plistlib
with open(os.environ['IOS_EXPORT_OPTIONS'], 'wb') as f:
    plistlib.dump({'method':'app-store-connect', 'teamID':os.environ['IOS_TEAM_ID'],
                  'signingStyle':'manual', 'signingCertificate':os.environ.get('IOS_SIGNING_IDENTITY','Apple Distribution'),
                  'provisioningProfiles':{'org.duchinese.reader':os.environ['IOS_PROFILE_NAME']},
                  'uploadSymbols':True, 'stripSwiftSymbols':True,
                  'manageAppVersionAndBuildNumber':False}, f)
PY
xcodebuild -exportArchive -archivePath "$out/ChineseReader.xcarchive" \
  -exportPath "$out/export" -exportOptionsPlist "$IOS_EXPORT_OPTIONS"
ipa="$out/export/ChineseReader.ipa"
test -f "$ipa"
shasum -a 256 "$ipa"
if [[ "${IOS_UPLOAD:-0}" == 1 ]]; then
  scripts/upload-ios.sh "$ipa"
fi
