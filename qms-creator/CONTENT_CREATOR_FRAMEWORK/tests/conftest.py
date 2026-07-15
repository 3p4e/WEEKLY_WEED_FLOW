"""Shared config for the Letta integration test suite.

These tests exercise a live Letta server. When the letta_client SDK is
missing or no server is reachable (e.g. in CI), the suite is not
collected instead of erroring.
"""

import importlib.util
import os
import sys
from pathlib import Path
from urllib.request import urlopen

# Tests import via the CONTENT_CREATOR_FRAMEWORK package, so the repo
# root must be importable regardless of where pytest is invoked from.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

LETTA_BASE_URL = os.getenv("LETTA_BASE_URL", "http://localhost:8283")


def _letta_available() -> bool:
    if importlib.util.find_spec("letta_client") is None:
        return False
    try:
        urlopen(f"{LETTA_BASE_URL}/v1/health/", timeout=3)
        return True
    except Exception:
        return False


collect_ignore_glob = [] if _letta_available() else ["test_letta_*.py"]
