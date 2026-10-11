"""Exercise the real installer against a fake SSH device, without touching a tablet."""
import os
import fcntl
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'deploy-appload.sh'

SSH = r'''#!/usr/bin/env python3
import os, pathlib, subprocess, sys
root = os.environ['FAKE_DEVICE']
def translate(s):
    return s.replace('/home/root', root + '/home/root').replace('/proc/', root + '/proc/')
args = sys.argv[2:]
if args[:2] == ['sh', '-s']:
    script = translate(sys.stdin.read())
    result = subprocess.run(['sh', '-s'] + [translate(a) for a in args[2:]], input=script, text=True)
    sys.exit(result.returncode)
command = translate(args[0])
if 'mktemp -d' in command:
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    sys.stdout.write(result.stdout.replace(root + '/home/root', '/home/root'))
    sys.stderr.write(result.stderr)
else:
    result = subprocess.run(command, shell=True)
    if result.returncode == 0 and os.environ.get('CORRUPT_UPLOAD') and 'tar -xf' in command:
        for path in pathlib.Path(root + '/home/root/.cache/duchinese-deploy').glob('*/resources.rcc'):
            path.write_text('corrupted transfer')
sys.exit(result.returncode)
'''
SYSTEMCTL = '''#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_DEVICE/service-calls"
if test "$*" = 'show xochitl -p MainPID --value'; then echo 123; else exit 99; fi
'''
MV = '''#!/bin/sh
if test -n "${FAIL_PROMOTION:-}" && test "$2" = "$FAKE_DEVICE/home/root/xovi/exthome/appload/duchinese"; then
    case "$1" in *.previous) ;; *) exit 1 ;; esac
fi
exec /usr/bin/mv "$@"
'''

class DeploymentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.device = self.root / 'device'
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        for name, contents in [('ssh', SSH), ('systemctl', SYSTEMCTL), ('mv', MV)]:
            path = self.bin / name
            path.write_text(contents)
            path.chmod(0o755)
        self.build = self.root / 'build'
        (self.build / 'backend').mkdir(parents=True)
        for name in ['manifest.json', 'icon.png', 'resources.rcc', 'backend/entry']:
            (self.build / name).write_text('new ' + name)
        self.target = self.device / 'home/root/xovi/exthome/appload/duchinese'
        self.target.mkdir(parents=True)
        (self.target / 'old-package').write_text('preserve me')
        (self.device / 'proc/sys/kernel/random').mkdir(parents=True)
        (self.device / 'proc/sys/kernel/random/boot_id').write_text('same-boot')
        self.env = dict(os.environ, FAKE_DEVICE=str(self.device), PATH=str(self.bin) + ':' + os.environ['PATH'])

    def run_install(self, **extra):
        result = subprocess.run(['bash', str(SCRIPT), str(self.build), 'fake', 'duchinese'],
                                env=dict(self.env, **extra), capture_output=True, text=True)
        calls = self.device / 'service-calls'
        if calls.exists():
            self.assertTrue(all(x == 'show xochitl -p MainPID --value' for x in calls.read_text().splitlines()))
        return result

    def test_inactive_install_keeps_backup_without_restart(self):
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.target / 'resources.rcc').read_text(), 'new resources.rcc')
        backups = list((self.device / 'home/root/.cache/duchinese-deploy').glob('*.previous/old-package'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), 'preserve me')
        self.assertIn('Runtime activation is pending', result.stdout)
        self.assertFalse((self.target / '.activated').exists())

    def test_resident_resource_stages_without_replacing(self):
        proc = self.device / 'proc/123'; proc.mkdir()
        (proc / 'maps').write_text('mapped /home/root/xovi/exthome/appload/duchinese/resources.rcc\n')
        result = self.run_install()
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertTrue((self.target / 'old-package').exists())
        self.assertIn('UI may already be closed', result.stderr)

    def test_lingering_backend_is_not_killed(self):
        proc = self.device / 'proc/456'; proc.mkdir()
        (proc / 'exe').symlink_to(self.target / 'backend/entry')
        result = self.run_install()
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertTrue((self.target / 'old-package').exists())

    def test_identical_package_does_not_claim_activation(self):
        self.assertEqual(self.run_install().returncode, 0)
        result = self.run_install()
        self.assertEqual(result.returncode, 0)
        self.assertIn('Runtime activation has not been checked', result.stdout)

    def test_corrupt_transfer_leaves_previous_package(self):
        result = self.run_install(CORRUPT_UPLOAD='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.target / 'old-package').read_text(), 'preserve me')

    def test_failed_promotion_restores_previous_without_restart(self):
        result = self.run_install(FAIL_PROMOTION='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.target / 'old-package').read_text(), 'preserve me')

    def test_concurrent_install_keeps_package_untouched(self):
        cache = self.device / 'home/root/.cache/duchinese-deploy'
        cache.mkdir(parents=True)
        with (cache / 'install.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_install()
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertTrue((self.target / 'old-package').exists())

    def test_capable_backend_is_asked_to_exit_before_install(self):
        proc = self.device / 'proc/456'; proc.mkdir()
        (proc / 'exe').symlink_to(self.target / 'backend/entry')
        (proc / 'maps').write_text('mapped /duchinese/resources.rcc\n')
        (self.build / 'backend/control-protocol').write_text('appload-exit-v1\n')
        (self.build / 'backend/entry').write_text('''#!/bin/sh
test "$1" = --request-exit && test "$2" = 456 || exit 1
printf 'requested\\n' > "$FAKE_DEVICE/exit-request"
unlink "$FAKE_DEVICE/proc/456/exe"
: > "$FAKE_DEVICE/proc/456/maps"
''')
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.device / 'exit-request').read_text(), 'requested\n')
        self.assertTrue((self.target / '.installed').exists())

if __name__ == '__main__':
    unittest.main()
