#!/usr/bin/env python3
"""Add optional AnyConnect VPN login to a private processor credential file."""
import argparse
import getpass
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('credentials', type=Path)
parser.add_argument('--server', required=True)
parser.add_argument('--username', required=True)
parser.add_argument('--authgroup', default='')
args = parser.parse_args()
server = urlsplit(args.server)
if server.scheme != 'https' or not server.hostname or server.username or server.password:
    parser.error('--server must be an HTTPS URL without embedded credentials')
if not sys.stdin.isatty():
    parser.error('run in an interactive terminal for hidden password input')
path = args.credentials.expanduser().resolve()
if path.stat().st_mode & 0o077:
    parser.error('credential file must have mode 0600')
config = json.loads(path.read_text())
password = getpass.getpass('VPN password (hidden): ')
if not password or '\n' in password or '\r' in password:
    parser.error('empty or multiline password')
config['vpn'] = {'server': args.server, 'username': args.username,
                 'password': password, 'authgroup': args.authgroup}
fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.vpn-config-')
try:
    with os.fdopen(fd, 'w') as output:
        json.dump(config, output)
        output.write('\n')
    os.replace(temporary, path)
finally:
    if os.path.exists(temporary): os.unlink(temporary)
print('VPN configuration saved privately. Install with scripts/install-pdf-processor.sh.')
