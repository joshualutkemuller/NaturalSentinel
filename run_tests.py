#!/usr/bin/env python
"""
Run tests — tries pytest first, falls back to unittest discovery.

    python run_tests.py          # all tests
    python run_tests.py -v       # verbose
"""

import sys
import os

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

try:
    import pytest
    sys.exit(pytest.main(["-xvs", "tests"] + sys.argv[1:]))
except ImportError:
    print("pytest not available — using unittest\n")
    import unittest

    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2 if "-v" in sys.argv else 1)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
