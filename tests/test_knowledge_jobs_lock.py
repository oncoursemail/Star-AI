"""Collect knowledge lock tests with the desktop's intentionally small dependencies.

Only import-time declarations of the search module need numpy in these tests; all
embedding and lookup work is replaced with fakes, and numerical search is not run.
The server's independent test suite can use real numpy as usual.
"""
from pathlib import Path
import sys
from types import ModuleType

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server" / "knowledge" / "tests"))

try:
    import numpy  # noqa: F401
except ModuleNotFoundError as exc:
    if exc.name != "numpy":
        raise
    sys.modules["numpy"] = ModuleType("numpy")
    try:
        from test_jobs_lock import *  # noqa: E402,F401,F403
    finally:
        del sys.modules["numpy"]
else:
    from test_jobs_lock import *  # noqa: E402,F401,F403
