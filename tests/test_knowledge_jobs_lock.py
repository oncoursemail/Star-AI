"""Collect server-side knowledge lock regressions in the root offline test suite.

The default pytest configuration searches only tests/, not server/knowledge/tests/.
Keep the detailed fixtures and tests with the service; this module exposes them to CI.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server" / "knowledge" / "tests"))

from test_jobs_lock import *  # noqa: E402,F401,F403
