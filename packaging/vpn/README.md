# VPN only while fetching cloud results

Optional AnyConnect VPN support for the native PDF processor. OpenConnect and
ocproxy run on the tablet in userspace: no TUN device, kernel module, system DNS,
or routing changes are needed. Only the worker's HTTP client uses the local SOCKS
proxy (`127.0.0.1:1087`). DNS for cloud hosts is resolved through that proxy.

The VPN starts immediately before the first uncached cloud request. One connection
is shared by up to 10 concurrent page requests and reused for the rest of the
document job, then stopped on success, cancellation, or error.
Opening a cached page, checking progress, restarting the worker, or starting a
fully cached job does not connect. A failed login is not retried automatically.
After a stopped or interrupted job the user explicitly resumes from the PDF menu. The
systemd worker owns the child processes and stops them when the worker is stopped.

## Repeatable setup

Requirements on the build computer: Linux, Go (version in `processor/go.mod`),
Python 3.12+, GNU `ar`, SSH, and an internet connection. No cross compiler, Docker,
or changes to the computer's VPN are required to reproduce the locked runtime.

1. Keep the existing Google/DeepSeek credential JSON outside the repository,
   with mode 0600. Add VPN credentials with a hidden terminal prompt:

   ```sh
   python3 scripts/configure-pdf-vpn.py ~/.config/duchinese/pdf-processor-credentials.json \
       --server https://vpn.example.edu --username YOUR_LOGIN
   ```

   For Stuttgart, use the university's documented gateway, e.g.
   `https://vpn2.tik.uni-stuttgart.de`. Supply `--authgroup` only if required by
   the gateway. Username, password and server selection remain in this private
   file; the project contains no personal login data. The current implementation
   supports username/password authentication, not an interactive SSO/MFA flow.

2. Install the worker and its optional VPN runtime:

   ```sh
   scripts/install-pdf-processor.sh rm2 ~/.config/duchinese/pdf-processor-credentials.json
   ```

   The installer detects the private `vpn` object and runs `build-pdf-vpn.py`.
   It verifies every Debian ARM package against `packages.lock.json`, extracts
   into an isolated directory, and installs the private runtime at
   `/home/root/.local/lib/duchinese-vpn`. The matching loader and libraries are
   bundled; tablet system libraries are not replaced. The installer restarts
   only `duchinese-pdf-processing.service`, never xochitl or Xovi. A running
   processing job is interrupted and can be resumed from the menu.

3. Tap **Process Chinese document** in the PDF's native three-dot menu. Existing
   cache entries continue to work without the VPN. Remove the `vpn` object and
   reinstall the credentials to return to direct cloud access.

The native menu/overlay is installed separately as described in `processor/README.md`.
Updating only VPN/worker code does not require reloading Xovi.

## Runtime versions and maintenance

`packages.lock.json` records exact filenames, source URLs, SHA-256 checksums and
snapshot content hashes for Debian 12 ARM packages, including OpenConnect 9.01-3
and ocproxy 1.60-1+b2. Downloads fall back to Debian's snapshot archive if a package
has left the regular mirror. The snapshot hash is only an address; SHA-256 is
always verified. Debian package copyright documentation stays with the runtime.
The lock is deliberate: updating dependencies requires refreshing it and testing
the new runtime; a rebuild does not silently change versions.

The initial lock was resolved using Debian APT with signed repository metadata:

```sh
# In a disposable Debian bookworm container:
dpkg --add-architecture armhf
apt-get update
apt-get --print-uris --yes --no-install-recommends install openconnect:armhf ocproxy:armhf
apt-get --download-only --yes --no-install-recommends install openconnect:armhf ocproxy:armhf
```

Only the downloaded ARM packages are included. To update, resolve against a
maintained Debian release, record the new URLs and hashes, and run the ARM smoke
check plus a real VPN request. Do not merely change the version strings.

Tests: `cd processor && go test -race ./...` exercises lazy startup, connection
reuse, shutdown, failed authentication, timeout, cache-only jobs and cleanup after
cloud errors using a synthetic child process. The opt-in live cloud test can also
be cross-compiled and run on the tablet with private credentials (see
`processor/live_test.go`). It incurs normal provider usage and closes its VPN when
finished. Never enable OpenConnect HTTP dumps or put a password on a command line.

References: [OpenConnect script-tun](https://www.infradead.org/openconnect/manual.html),
[ocproxy](https://github.com/cernekee/ocproxy),
[Stuttgart VPN](https://www.tik.uni-stuttgart.de/support/anleitungen/vpn/).
