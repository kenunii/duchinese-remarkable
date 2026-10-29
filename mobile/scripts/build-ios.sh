#!/usr/bin/env bash
# Build an unsigned simulator app using an SSH-accessible macOS/Xcode host.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
host=${1:?Usage: build-ios.sh SSH_HOST}
port=${MAC_SSH_PORT:-22}
work=${MAC_WORKDIR:-chinese-reader-mobile}
[[ "$port" =~ ^[0-9]+$ && "$work" =~ ^[a-zA-Z0-9/_-]+$ ]] || exit 2
rsync -a -e "ssh -p $port" --exclude=build --exclude=.gradle --exclude=.kotlin --exclude=local.properties --exclude=.git "$root/" "$host:$work/"
ssh -p "$port" "$host" bash -s -- "$work" <<'REMOTE'
set -euo pipefail
cd "$1"
export JAVA_HOME=$(/usr/libexec/java_home -v 17)
export PATH="$JAVA_HOME/bin:$PATH"
./gradlew --no-daemon :composeApp:compileKotlinIosX64 :composeApp:iosX64Test
xcodebuild -project iosApp/iosApp.xcodeproj -scheme iosApp -configuration Debug \
  -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath build/ios CODE_SIGNING_ALLOWED=NO build
COPYFILE_DISABLE=1 tar -C build/ios/Build/Products/Debug-iphonesimulator -czf build/ChineseReader-simulator.tar.gz ChineseReader.app
REMOTE
mkdir -p "$root/build/releases"
scp -P "$port" "$host:$work/build/ChineseReader-simulator.tar.gz" "$root/build/releases/"
