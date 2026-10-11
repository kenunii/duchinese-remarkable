#!/usr/bin/env bash
# Install an inactive AppLoad package; runtime activation belongs to AppLoad.
set -euo pipefail
build_dir=$(realpath "${1:?Usage: deploy-appload.sh BUILD_DIR DEVICE APP_DIRECTORY}")
device=${2:?Missing device}
app_dir=${3:?Missing app directory}
[[ "$app_dir" =~ ^[a-z0-9-]+$ ]] || exit 2
remote_cache=/home/root/.cache/duchinese-deploy
files=(manifest.json icon.png resources.rcc)
if [[ -f "$build_dir/backend/entry" ]]; then files+=(backend/entry); fi
if [[ -f "$build_dir/backend/control-protocol" ]]; then files+=(backend/control-protocol); fi
for file in "${files[@]}"; do test -f "$build_dir/$file"; done
(cd "$build_dir"; sha256sum "${files[@]}") > "$build_dir/SHA256SUMS"
package_id=$(sha256sum "$build_dir/SHA256SUMS" | cut -c1-16)
# Each transfer has its own directory, including concurrent identical builds.
remote_stage=$(ssh "$device" "mkdir -p '$remote_cache' && mktemp -d '$remote_cache/$app_dir-$package_id.XXXXXX'")
[[ "$remote_stage" =~ ^/home/root/\.cache/duchinese-deploy/[a-zA-Z0-9.-]+$ ]] || exit 2
tar -C "$build_dir" -cf - "${files[@]}" SHA256SUMS | ssh "$device" "tar -xf - -C '$remote_stage'"
ssh "$device" sh -s -- "$app_dir" "$package_id" "$remote_stage" <<'REMOTE'
set -eu
app=$1
version=$2
stage=$3
base=/home/root/xovi/exthome/appload
target=$base/$app
# Shared across app directories: all packages use the same xochitl process.
exec 9>/home/root/.cache/duchinese-deploy/install.lock
if ! flock -n 9; then
    echo "Another package install is in progress. Uploaded staging will remain at $stage." >&2
    exit 3
fi
cd "$stage"
sha256sum -c SHA256SUMS
if test -d "$target" && (cd "$target" && sha256sum -c "$stage/SHA256SUMS" >/dev/null 2>&1); then
    echo "Package $version already matches disk. Runtime activation has not been checked."
    echo "Use Reload in AppLoad with apps closed, then open $app."
    exit 0
fi
pid=$(systemctl show xochitl -p MainPID --value)
boot=$(cat /proc/sys/kernel/random/boot_id)
# A resident backend does not prove that the UI is open. Never signal it here.
# Builds with exit control ask the app to terminate through AppLoad itself.
if test "$app" = duchinese && test -f backend/control-protocol &&
   test "$(cat backend/control-protocol)" = appload-exit-v1; then
    chmod 755 backend/entry
    for executable in /proc/[0-9]*/exe; do
        running=$(readlink "$executable" 2>/dev/null || true)
        case "$running" in
            */"$app"/backend/entry|*/"$app"/backend/entry\ *)
                backend_pid=${executable#/proc/}
                backend_pid=${backend_pid%/exe}
                ./backend/entry --request-exit "$backend_pid" || true
                for attempt in 1 2 3 4 5; do
                    if ! test -e "$executable"; then break; fi
                    sleep 1
                done
                ;;
        esac
    done
fi
# Mapped RCCs also cover apps without backends and closed-but-cached resources.
resident=false
for executable in /proc/[0-9]*/exe; do
    running=$(readlink "$executable" 2>/dev/null || true)
    case "$running" in
        */"$app"/backend/entry|*/"$app"/backend/entry\ *) resident=true ;;
    esac
done
for maps in /proc/[0-9]*/maps; do
    if grep -Fq "/$app/resources.rcc" "$maps" 2>/dev/null; then resident=true; break; fi
done
if $resident; then
    echo "Package $version staged at $stage; the installed package is still resident." >&2
    echo "Its UI may already be closed. Fully quit it through AppLoad, then rerun this installer." >&2
    echo "No process signals or service restarts were used; installed files were unchanged." >&2
    exit 3
fi
if test "$(cat /proc/sys/kernel/random/boot_id)" != "$boot" ||
   test "$(systemctl show xochitl -p MainPID --value)" != "$pid"; then
    echo "xochitl changed during preflight; package remains staged at $stage." >&2
    exit 3
fi
if test -f backend/entry; then chmod 755 backend/entry; fi
mkdir -p "$base"
backup=$stage.previous
# Renames preserve the exact previous package. Recovery never restarts services.
restore_if_missing() {
    if ! test -e "$target" && test -d "$backup"; then mv "$backup" "$target"; fi
}
trap restore_if_missing HUP INT TERM EXIT
if test -d "$target"; then mv "$target" "$backup"; fi
if ! mv "$stage" "$target"; then exit 1; fi
cd "$target"
if ! sha256sum -c SHA256SUMS; then
    mv "$target" "$stage.failed"
    restore_if_missing
    echo "Verification failed; previous files restored. No service restart was attempted." >&2
    exit 1
fi
printf '%s\n' "$version" > .installed
trap - HUP INT TERM EXIT
echo "Installed package $version on disk. Previous package: $backup"
echo "xochitl was not restarted. With apps closed, tap Reload in AppLoad, then open $app."
echo "Runtime activation is pending verification after launch."
REMOTE
