from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for candidate in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    path_str = str(candidate)
    if candidate.is_dir() and path_str not in sys.path:
        sys.path.insert(0, path_str)
