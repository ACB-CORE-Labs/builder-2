from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TESTS = ROOT / "tests"

for path in (ROOT, TESTS):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)
