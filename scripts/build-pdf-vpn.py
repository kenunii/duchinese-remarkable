#!/usr/bin/env python3
"""Package a pinned OpenConnect + ocproxy runtime without changing the host OS."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build/vpn-runtime'
PACKAGES = BUILD / 'packages'
OUTPUT = BUILD / 'runtime'

def main():
    lock = json.loads((ROOT / 'packaging/vpn/packages.lock.json').read_text())
    PACKAGES.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    (OUTPUT / 'root').mkdir(parents=True)
    for package in lock['packages']:
        path = PACKAGES / package['file']
        if not path.exists():
            urls = [package['url'], 'https://snapshot.debian.org/file/' + package['sha1']]
            for url in urls:
                try:
                    with urllib.request.urlopen(url, timeout=60) as response:
                        data = response.read()
                    if hashlib.sha256(data).hexdigest() != package['sha256']:
                        raise ValueError('Package checksum mismatch: ' + package['file'])
                    temporary = path.with_suffix('.pending')
                    temporary.write_bytes(data)
                    temporary.replace(path)
                    break
                except (OSError, ValueError):
                    if url == urls[-1]: raise
        if hashlib.sha256(path.read_bytes()).hexdigest() != package['sha256']:
            raise ValueError('Package checksum mismatch: ' + package['file'])
        members = subprocess.check_output(['ar', 't', str(path)], text=True).splitlines()
        member = next(name for name in members if name.startswith('data.tar.'))
        data = subprocess.check_output(['ar', 'p', str(path), member])
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            archive.extractall(OUTPUT / 'root', filter='data')
    for name in ['openconnect', 'ocproxy', 'proxy-script']:
        shutil.copyfile(ROOT / 'packaging/vpn' / name, OUTPUT / name)
        (OUTPUT / name).chmod(0o755)
    shutil.copyfile(ROOT / 'packaging/vpn/packages.lock.json', OUTPUT / 'packages.lock.json')
    # Keep package documentation/copyright files with the redistributed runtime.
    print('Built pinned ARM VPN runtime:', OUTPUT)

if __name__ == '__main__':
    main()
