#!/usr/bin/env python3
"""Run the small maintenance gate; --full runs all installer checks sequentially."""
import argparse
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / 'deploy/nti/tests'
QUICK = (
    'test_repository_hygiene', 'test_install_wrapper', 'test_global_manager',
    'test_host_setup', 'test_releases', 'test_remote_data',
    'test_database_modes', 'test_automatic_wizard',
    'test_fresh_bootstrap_contract', 'test_docker_export',
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full', action='store_true')
    args = parser.parse_args()
    if not args.full:
        os.environ.pop('PCIRN_RUN_POSTGRES15', None)
    sys.path.insert(0, str(TESTS))
    loader = unittest.TestLoader()
    suite = (loader.discover(str(TESTS), pattern='test_*.py') if args.full
             else loader.loadTestsFromNames(QUICK))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
