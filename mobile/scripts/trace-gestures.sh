#!/usr/bin/env bash
# Only reader gesture diagnostics; no textbook text or other app logs.
set -euo pipefail
if [[ $# -gt 0 ]]; then export ANDROID_SERIAL=$1; fi
adb logcat -v threadtime -s System.out:I | grep --line-buffered 'ReaderGesture '
