#!/usr/bin/env bash
# Deploy a complete package, verify it, and invalidate xochitl's QML cache.
set -euo pipefail
build_dir=$(realpath "${1:?Usage: deploy-appload.sh BUILD_DIR DEVICE APP_DIRECTORY}")
device=${2:?Missing device}
app_dir=${3:?Missing app directory}
[[ "$app_dir" =~ ^[a-z0-9-]+$ ]] || exit 2
remote_base=/home/root/xovi/exthome/appload
remote_stage=/home/root/.cache/duchinese-deploy
files=(manifest.json icon.png resources.rcc)
if [[ -f "$build_dir/backend/entry" ]]; then files+=(backend/entry); fi
for file in "${files[@]}"; do test -f "$build_dir/$file"; done
(cd "$build_dir"; sha256sum "${files[@]}") > "$build_dir/SHA256SUMS"
package_id=$(sha256sum "$build_dir/SHA256SUMS" | cut -c1-16)
ssh "$device" "mkdir -p '$remote_stage/$app_dir-$package_id'"
tar -C "$build_dir" -cf - "${files[@]}" SHA256SUMS | ssh "$device" "tar -xf - -C '$remote_stage/$app_dir-$package_id'"
ssh "$device" sh -s -- "$app_dir" "$package_id" <<'REMOTE'
set -eu
app=$1
version=$2
base=/home/root/xovi/exthome/appload
target=$base/$app
stage=/home/root/.cache/duchinese-deploy/$app-$version
backup=/home/root/.cache/duchinese-deploy/$app-previous
cd "$stage"
sha256sum -c SHA256SUMS
pid=$(systemctl show xochitl -p MainPID --value)
# A disk match alone is insufficient: a previous installer may have left old QML live.
if test -f "$target/.activated" && test "$(cat "$target/.activated")" = "$version $pid" &&
   (cd "$target" && sha256sum -c "$stage/SHA256SUMS" >/dev/null 2>&1); then
    echo "Package $version already activated in xochitl PID $pid; no restart needed."
    rm -rf "$stage"
    exit 0
fi
if test -f backend/entry; then chmod 755 backend/entry; fi
had_previous=false
if test -d "$target"; then had_previous=true; fi
# Keep the backup outside AppLoad's scan directory.
rm -rf "$backup"
if $had_previous; then cp -a "$target" "$backup"; fi
rollback() {
    echo 'Activation failed; restoring previous package.' >&2
    rm -rf "$target"
    if $had_previous; then cp -a "$backup" "$target"; fi
    systemctl restart xochitl || true
}
trap rollback HUP INT TERM
# Replacing the directory leaves any already-mapped old bundle intact until restart.
if test -d "$target"; then mv "$target" "$stage.replaced"; fi
if ! mv "$stage" "$target"; then
    if test -d "$stage.replaced"; then mv "$stage.replaced" "$target"; fi
    exit 1
fi
cd "$target"
if ! systemctl restart xochitl; then rollback; exit 1; fi
sleep 2
new_pid=$(systemctl show xochitl -p MainPID --value)
if ! systemctl is-active --quiet xochitl || test "$new_pid" = 0 || test "$new_pid" = "$pid"; then
    rollback
    exit 1
fi
printf '%s %s\n' "$version" "$new_pid" > .activated
rm -rf "$stage.replaced"
trap - HUP INT TERM
echo "Activated package $version; xochitl PID $pid -> $new_pid. Open the app in AppLoad."
REMOTE
