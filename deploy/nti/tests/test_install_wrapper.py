"""The shell entry point delegates once to the seven-stage installer."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

WRAPPER = Path(__file__).resolve().parents[3] / 'install.sh'


class InstallWrapperTests(unittest.TestCase):
    def run_wrapper(self, *args):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shim = root / 'python3'
            shim.write_text('#!/bin/bash\nprintf "%s\\n" "$@" > "$WRAPPER_LOG"\n')
            shim.chmod(0o700)
            log = root / 'calls'
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'],
                       WRAPPER_LOG=str(log))
            result = subprocess.run(['bash', str(WRAPPER), *args], env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return log.read_text().splitlines()

    def test_no_arguments_opens_main_menu(self):
        calls = self.run_wrapper()
        self.assertTrue(calls[0].endswith('/pcirn.py'))
        self.assertEqual(len(calls), 1)

    def test_arguments_open_wizard_and_preserve_automation_options(self):
        options = ['--config', 'private.json', '--manifest', 'release.json',
                   '--data-package', 'package', '--authorize-migrations']
        calls = self.run_wrapper(*options)
        self.assertTrue(calls[0].endswith('/pcirn.py'))
        self.assertEqual(calls[1:], ['install', '--wizard', *options])
