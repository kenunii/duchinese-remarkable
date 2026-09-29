#!/usr/bin/env python3
"""Find on-device PDF document IDs by matching the source PDF SHA-256."""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess

DOCUMENTS = '/home/root/.local/share/remarkable/xochitl'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', type=Path)
    parser.add_argument('--device', default='rm2')
    args = parser.parse_args()
    if not args.pdf.is_file():
        parser.error(f'Missing PDF: {args.pdf}')
    digest = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    size = args.pdf.stat().st_size
    output = subprocess.check_output([
        'ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=7', args.device,
        f'find {DOCUMENTS} -maxdepth 1 -type f -name "*.pdf" -size {size}c -exec sha256sum {{}} +',
    ], text=True)
    matches = []
    for line in output.splitlines():
        found_digest, _, path = line.partition('  ')
        match = re.fullmatch(rf'{re.escape(DOCUMENTS)}/([0-9a-f-]{{36}})\.pdf', path)
        if found_digest == digest and match:
            matches.append(match.group(1))
    if not matches:
        raise SystemExit('No on-device PDF matches this file hash')
    print('\n'.join(matches))


if __name__ == '__main__':
    main()
