#!/usr/bin/env bash
# Validate and upload an already exported IPA from the build Mac.
set -euo pipefail
ipa=${1:?Usage: upload-ios.sh PATH_TO_IPA}
: "${APPSTORE_API_KEY_ID:?Set APPSTORE_API_KEY_ID}"
: "${APPSTORE_ISSUER_ID:?Set APPSTORE_ISSUER_ID}"
test -f "$ipa" || { echo "IPA not found: $ipa" >&2; exit 1; }
# Avoid accidentally uploading another app from a shared deployment host.
python3 - "$ipa" <<'PY'
import plistlib, sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as archive:
    roots = [n for n in archive.namelist() if n.startswith('Payload/') and n.count('/') == 2 and n.endswith('.app/Info.plist')]
    if len(roots) != 1:
        raise SystemExit('Expected one top-level app in the IPA')
    info = plistlib.loads(archive.read(roots[0]))
    if info['CFBundleIdentifier'] != 'org.duchinese.reader':
        raise SystemExit('IPA bundle identifier is not org.duchinese.reader')
    print('Uploading Chinese PDF Reader', info['CFBundleShortVersionString'], 'build', info['CFBundleVersion'])
PY
# The matching AuthKey_*.p8 stays in ~/.appstoreconnect/private_keys/.
xcrun altool --validate-app "$ipa" --api-key "$APPSTORE_API_KEY_ID" --api-issuer "$APPSTORE_ISSUER_ID"
xcrun altool --upload-package "$ipa" --wait --api-key "$APPSTORE_API_KEY_ID" --api-issuer "$APPSTORE_ISSUER_ID"
