"""Check wrapper ordering with a fake Python executable, without host probes."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

WRAPPER = Path(__file__).resolve().parents[3] / 'install.sh'


class InstallWrapperTests(unittest.TestCase):
    def run_wrapper(self, fail):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shim = root / 'python3'
            shim.write_text('#!/bin/bash\nprintf "%s\\n" "$1" >> "$WRAPPER_LOG"\n'
                            'if [[ "$1" == *preflight.py && "$PREFLIGHT_FAIL" == 1 ]]; then exit 7; fi\n')
            shim.chmod(0o700)
            log = root / 'calls'
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'],
                       WRAPPER_LOG=str(log), PREFLIGHT_FAIL=str(fail))
            process = subprocess.run(['bash', str(WRAPPER), '--manifest', 'fictional.json'], env=env,
                                     capture_output=True, text=True)
            return process.returncode, log.read_text().splitlines()

    def test_preflight_failure_prevents_install(self):
        code, calls = self.run_wrapper(1)
        self.assertEqual(code, 7)
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0].endswith('/preflight.py'))

    def test_preflight_runs_before_install(self):
        code, calls = self.run_wrapper(0)
        self.assertEqual(code, 0)
        self.assertTrue(calls[0].endswith('/preflight.py'))
        self.assertTrue(calls[1].endswith('/pcirn.py'))


if __name__ == '__main__': unittest.main()
